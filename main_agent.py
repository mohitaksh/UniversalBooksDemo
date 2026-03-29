"""
main_agent.py
─────────────
Single-agent architecture for Universal Books outbound sales calls (Demo).
One SalesAgent with 2 tools: tag_lead + schedule_callback.
All logging, metrics, and cost tracking preserved.
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    UserStateChangedEvent,
    UserInputTranscribedEvent,
    ConversationItemAddedEvent,
    cli,
    llm,
    Agent,
    function_tool,
    AgentSession,
    BackgroundAudioPlayer,
    AudioConfig,
    BuiltinAudioClip,
)
from livekit.agents.voice import RunContext
from livekit.agents.beta import EndCallTool

from livekit.plugins import sarvam, groq

from prompts import AGENT_PROMPT
from logger import setup_loggers, write_cost_report
from models import CostTracker

load_dotenv(dotenv_path=".env.local")

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)


# ═════════════════════════════════════════════════════════════════
# SHARED STATE
# ═════════════════════════════════════════════════════════════════

@dataclass
class CallUserData:
    """Shared state for a single call."""
    caller_name: str = "ji"
    call_type: str = "name"
    phone_number: str = ""
    tracker: CostTracker = None
    brief_log: logging.Logger = None
    ctx: Optional[JobContext] = None


RunCtx = RunContext[CallUserData]


# ═════════════════════════════════════════════════════════════════
# SINGLE SALES AGENT
# ═════════════════════════════════════════════════════════════════

class SalesAgent(Agent):
    """Single agent that handles the entire outbound sales call."""

    def __init__(self, caller_name: str = "ji", call_type: str = "name"):
        super().__init__(
            instructions=AGENT_PROMPT.format(
                caller_name=caller_name,
                call_type=call_type,
            ),
            tools=[EndCallTool()],
        )
        self.caller_name = caller_name
        self.call_type = call_type

    async def on_enter(self) -> None:
        userdata: CallUserData = self.session.userdata
        if userdata.brief_log:
            userdata.brief_log.info(
                f"AGENT_ENTER | SalesAgent | {self.call_type}:{self.caller_name}"
            )

        # Wait for the SIP participant to be ready
        try:
            await self.session.userdata.ctx.wait_for_participant()
        except Exception:
            pass  # Fallback: participant might already be connected
        await asyncio.sleep(2.0)  # Short buffer for audio establishment

        # Hardcoded identity check opener
        if self.call_type == "institution":
            opener = f"Hello, क्या ये number {self.caller_name} का है?"
        else:
            opener = f"Hello, क्या मेरी बात {self.caller_name} से हो रही है जो tuition पढ़ाते हैं?"

        await self.session.say(opener)
        self.session.generate_reply()

    # ── Tools ────────────────────────────────────────────────────

    @function_tool
    async def tag_lead(self, context: RunCtx, tag: str, notes: str = "") -> str:
        """Tag the lead with final outcome. Tags: Interested, Call Back, Not Interested, Wrong Contact. MUST be called before call ends."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("tag_lead", {"tag": tag, "notes": notes})
        if ud.brief_log:
            ud.brief_log.info(f"FUNCTION | tag_lead | tag='{tag}' | notes='{notes}'")
        return f"Lead tagged as {tag}."

    @function_tool
    async def schedule_callback(self, context: RunCtx, time_1: str, time_2: str = "", notes: str = "") -> str:
        """Schedule a callback with 1-2 preferred times. Use when caller is interested but busy, or wants team to call back."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("schedule_callback", {
                "time_1": time_1, "time_2": time_2, "notes": notes
            })
        if ud.brief_log:
            ud.brief_log.info(
                f"FUNCTION | schedule_callback | t1='{time_1}' | t2='{time_2}' | notes='{notes}'"
            )
        return "Callback successfully schedule हो गया। Team preferred time पर call करेंगे।"


# ═════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═════════════════════════════════════════════════════════════════

async def entrypoint(ctx: JobContext):
    call_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    loggers = setup_loggers(call_id)
    full_log, brief_log, token_log, cost_log, llm_log, transcript_log = loggers

    # Read caller info from dispatch metadata
    caller_name = "ji"
    call_type = "name"
    phone_number = ""
    try:
        meta = json.loads(ctx.job.metadata or "{}")
        caller_name = meta.get("name", "ji") or "ji"
        call_type = meta.get("call_type", "name") or "name"
        phone_number = meta.get("phone", "") or ""
        full_log.info(f"Dispatch: name={caller_name}, type={call_type}, phone={phone_number}")
    except Exception:
        pass

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # ── Debug logger (writes everything to a log file) ───────────
    debug_log_path = os.path.join("logs", f"{call_id}_debug.log")
    console_log = logging.getLogger(f"debug.{call_id}")
    console_log.setLevel(logging.DEBUG)
    if not console_log.handlers:
        fh = logging.FileHandler(debug_log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [DEBUG] %(message)s", datefmt="%H:%M:%S"
        ))
        console_log.addHandler(fh)

    console_log.info("=" * 60)
    console_log.info(f"📞 NEW CALL | ID: {call_id} | Room: {ctx.room.name}")
    console_log.info(f"📋 Type: {call_type} | Name: {caller_name} | Phone: {phone_number}")
    console_log.info(f"🔗 Connected to room: {ctx.room.name} | SID: {ctx.room.sid}")
    console_log.info(f"👥 Participants already in room: {len(ctx.room.remote_participants)}")
    for pid, p in ctx.room.remote_participants.items():
        console_log.info(f"   ├─ {p.identity} (sid={p.sid})")
        for tid, pub in p.track_publications.items():
            console_log.info(f"   │  └─ track: {pub.source} kind={pub.kind} subscribed={pub.subscribed}")
    console_log.info("=" * 60)

    # ── Room event hooks (debug everything LiveKit sends) ────────
    @ctx.room.on("participant_connected")
    def _on_participant_connected(participant):
        console_log.info(f"🟢 PARTICIPANT_CONNECTED | {participant.identity} (sid={participant.sid})")

    @ctx.room.on("participant_disconnected")
    def _on_participant_disconnected(participant):
        console_log.info(f"🔴 PARTICIPANT_DISCONNECTED | {participant.identity}")

    @ctx.room.on("track_published")
    def _on_track_published(publication, participant):
        console_log.info(
            f"📡 TRACK_PUBLISHED | by={participant.identity} | "
            f"source={publication.source} kind={publication.kind} sid={publication.sid}"
        )

    @ctx.room.on("track_subscribed")
    def _on_track_subscribed(track, publication, participant):
        console_log.info(
            f"✅ TRACK_SUBSCRIBED | by={participant.identity} | "
            f"source={publication.source} kind={track.kind} sid={track.sid}"
        )

    @ctx.room.on("track_unsubscribed")
    def _on_track_unsubscribed(track, publication, participant):
        console_log.info(
            f"❌ TRACK_UNSUBSCRIBED | by={participant.identity} | "
            f"source={publication.source} kind={track.kind}"
        )

    @ctx.room.on("track_muted")
    def _on_track_muted(publication, participant):
        console_log.info(f"🔇 TRACK_MUTED | by={participant.identity} | source={publication.source}")

    @ctx.room.on("track_unmuted")
    def _on_track_unmuted(publication, participant):
        console_log.info(f"🔊 TRACK_UNMUTED | by={participant.identity} | source={publication.source}")

    @ctx.room.on("disconnected")
    def _on_room_disconnected(*args):
        console_log.info(f"⚡ ROOM_DISCONNECTED | args={args}")

    @ctx.room.on("reconnecting")
    def _on_reconnecting(*args):
        console_log.warning(f"🔄 ROOM_RECONNECTING")

    @ctx.room.on("reconnected")
    def _on_reconnected(*args):
        console_log.info(f"✅ ROOM_RECONNECTED")

    full_log.info("=" * 60)
    full_log.info(f"📞 NEW CALL | ID: {call_id} | Room: {ctx.room.name}")
    full_log.info(f"📋 Type: {call_type} | Name: {caller_name} | Phone: {phone_number}")
    full_log.info("=" * 60)
    brief_log.info(f"CALL_START | {call_id} | type={call_type} | name={caller_name}")

    tracker = CostTracker(call_id=call_id)

    # ── Create shared state ─────────────────────────────────────
    userdata = CallUserData(
        caller_name=caller_name,
        call_type=call_type,
        phone_number=phone_number,
        tracker=tracker,
        brief_log=brief_log,
        ctx=ctx,
    )

    # ── Single agent ────────────────────────────────────────────
    agent = SalesAgent(caller_name=caller_name, call_type=call_type)

    # ── Plugins ──────────────────────────────────────────────────
    llm_plugin = groq.LLM(
        model="llama-3.3-70b-versatile",
    )

    stt_plugin = sarvam.STT(
        language="hi-IN",
        model="saaras:v3",
        mode="codemix",
    )

    tts_plugin = sarvam.TTS(
        target_language_code="hi-IN",
        model="bulbul:v3",
        speaker="shubh",
        speech_sample_rate=8000,  # 8kHz WAV for SIP telephony compatibility
    )

    # ── Session ──────────────────────────────────────────────────
    session = AgentSession[CallUserData](
        llm=llm_plugin,
        stt=stt_plugin,
        tts=tts_plugin,
        userdata=userdata,
        user_away_timeout=10,
    )

    # ── Metrics ──────────────────────────────────────────────────
    @session.on("metrics_collected")
    def on_metrics(event):
        try:
            m = event.metrics
            metric_type = getattr(m, "type", "")

            if metric_type in ("llm_metrics", "realtime_model_metrics"):
                input_t = getattr(m, "prompt_tokens", getattr(m, "input_tokens", 0)) or 0
                output_t = getattr(m, "completion_tokens", getattr(m, "output_tokens", 0)) or 0
                cancelled = getattr(m, "cancelled", False)
                if not cancelled and input_t > 0:
                    tracker.log_llm(input_t, output_t)
                    token_log.info(
                        f"LLM | in={input_t} out={output_t} | "
                        f"cum_in={tracker.llm_input_tokens_total} cum_out={tracker.llm_output_tokens_total}"
                    )
                    full_log.info(f"📊 LLM | in={input_t} out={output_t} tokens")
                    llm_log.info(f"=== LLM TURN: {input_t} IN | {output_t} OUT ===")
                    try:
                        for msg in session.chat_ctx.messages:
                            role = str(msg.role).upper().replace("ROLES.", "")
                            llm_log.info(f"[{role}]: {msg.content}")
                    except Exception as e:
                        llm_log.error(f"Chat context dump failed: {e}")
                    llm_log.info("=========================================\n")
                elif cancelled:
                    full_log.info("📊 LLM turn cancelled")

            elif metric_type == "tts_metrics":
                chars = getattr(m, "characters_count", 0) or 0
                audio_dur = getattr(m, "audio_duration", 0) or 0
                cancelled = getattr(m, "cancelled", False)
                if not cancelled and chars > 0:
                    tracker.tts_chars_total += chars
                    tracker.tts_active_seconds += audio_dur
                    token_log.info(f"TTS | chars={chars} audio={audio_dur:.2f}s")
                    full_log.info(f"🔊 TTS | {chars} chars → {audio_dur:.2f}s")

            elif metric_type == "stt_metrics":
                audio_dur = getattr(m, "audio_duration", 0) or 0
                if audio_dur > 0:
                    tracker.stt_active_seconds += audio_dur
                    token_log.info(f"STT | audio={audio_dur:.2f}s total={tracker.stt_active_seconds:.2f}s")
                    full_log.info(f"🎤 STT | {audio_dur:.2f}s")

        except Exception as e:
            full_log.error(f"Metrics hook error: {e}")

    @session.on("conversation_item_added")
    def on_conversation_item(ev: ConversationItemAddedEvent):
        """Log every committed user/agent message to the transcript."""
        item = ev.item
        role = str(item.role).split(".")[-1].capitalize()
        text = item.text_content
        if text:
            label = "User" if "user" in role.lower() else "Agent"
            transcript_log.info(f"{label}: {text}")
            full_log.info(f"💬 [{label}] {text}")
            console_log.info(f"💬 [{label}] {text}")

    @session.on("user_input_transcribed")
    def on_user_transcribed(ev: UserInputTranscribedEvent):
        """Log interim/final STT results for debugging."""
        if ev.is_final:
            brief_log.info(f"STT_FINAL | {ev.transcript}")
            console_log.info(f"🎤 STT FINAL: {ev.transcript}")
        else:
            full_log.info(f"🎤 STT interim: {ev.transcript}")
            console_log.debug(f"🎤 STT interim: {ev.transcript}")

    # ── Silence re-engagement ────────────────────────────────────
    @session.on("user_state_changed")
    def on_user_state_changed(ev: UserStateChangedEvent):
        if ev.new_state == "away":
            brief_log.info("SILENCE | user_away detected — prompting re-engagement")
            console_log.info("⏳ SILENCE | user_away — re-engaging")
            session.generate_reply()

    # ── Periodic cost log ────────────────────────────────────────
    async def periodic_cost_log():
        while True:
            await asyncio.sleep(5)
            c = tracker.calculate_costs()
            full_log.info(
                f"💰 COST | {c['duration_minutes']:.2f}min | "
                f"LLM in={c['llm_input_tokens']} out={c['llm_output_tokens']} | "
                f"₹{c['total_cost_inr']:.4f}"
            )

    full_log.info("Agent Session started — Single agent architecture (Demo).")
    cost_task = asyncio.create_task(periodic_cost_log())

    # ── Cleanup ──────────────────────────────────────────────────
    shutdown_triggered = False

    async def shutdown_call(reason="room disconnected"):
        nonlocal shutdown_triggered
        if shutdown_triggered:
            return  # Prevent double-shutdown
        shutdown_triggered = True

        full_log.info(f"Closing Session | Reason: {reason}")
        console_log.info(f"🔴 SHUTDOWN | {reason}")
        cost_task.cancel()
        brief_log.info(f"CALL_END | {reason}")
        write_cost_report(tracker=tracker, full_log=full_log, cost_log=cost_log, brief_log=brief_log)

        # Actually close the session and disconnect
        try:
            await session.close()
        except Exception as e:
            full_log.error(f"Session close error: {e}")
        try:
            await ctx.room.disconnect()
        except Exception as e:
            full_log.error(f"Room disconnect error: {e}")

        full_log.info("Session closed.")

    @ctx.room.on("disconnected")
    def on_disconnected(*args):
        asyncio.create_task(shutdown_call("room disconnected"))

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        # Only shutdown if the SIP participant (caller) disconnected, not the agent
        if participant.identity.startswith("sip_"):
            asyncio.create_task(shutdown_call(f"caller {participant.identity} hung up"))

    # ── Start ────────────────────────────────────────────────────
    await session.start(room=ctx.room, agent=agent)

    # ── Background Audio (office ambience) ───────────────────────
    background_audio = BackgroundAudioPlayer(
        ambient_sound=AudioConfig(BuiltinAudioClip.OFFICE_AMBIENCE, volume=3.0),
        thinking_sound=[
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.8),
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING2, volume=0.7),
        ],
    )
    await background_audio.start(room=ctx.room, agent_session=session)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="UniversalBooksAgent",
        )
    )
