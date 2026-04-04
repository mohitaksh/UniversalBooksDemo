"""
main_agent.py — Single entrypoint for the UniversalBooks Voice AI agent.
═══════════════════════════════════════════════════════════════════════════

DISPATCH FLOW:
  1. server.py creates a room with metadata: {name, phone_number, call_type}
  2. LiveKit dispatches this agent to the room
  3. This entrypoint reads the metadata from ctx.job.metadata
  4. Picks the right call flow entry agent based on call_type
  5. Starts the AgentSession with Sarvam TTS/STT + Groq LLM

USAGE:
  python main_agent.py dev

LEARNINGS APPLIED (see learnings.md):
  - No VAD / silero (Sarvam has built-in)
  - No BackgroundAudioPlayer (not needed, was causing issues)
  - No speech_sample_rate (let Sarvam handle it)
  - ctx.job.metadata (NOT ctx.room.metadata)
  - user_away_timeout=10
  - load_dotenv at top
"""

import json
import time
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env.local")

from livekit.agents import (
    AutoSubscribe,
    AgentSession,
    Agent,
    JobContext,
    WorkerOptions,
    UserStateChangedEvent,
    ConversationItemAddedEvent,
    UserInputTranscribedEvent,
    BackgroundAudioPlayer,
    AudioConfig,
    BuiltinAudioClip,
    cli,
    room_io,
)
from livekit.plugins import sarvam, openai

# Local imports
from config import OPENAI_MODEL
from models import (
    CallType,
    CallUserData,
    CostTracker,
    call_type_from_string,
    get_random_voice,
)
from logger import setup_loggers, write_cost_report

logger = logging.getLogger("main_agent")


# ═══════════════════════════════════════════════════════════════
# CALL TYPE → ENTRY AGENT MAPPING
# ═══════════════════════════════════════════════════════════════

def get_entry_agent(call_type: CallType):
    """Returns the entry agent class for the given call type."""
    if call_type in (CallType.NEW_TEACHER_COACHING, CallType.NEW_TEACHER_TUITION):
        from agents.new_teacher.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.NEW_TEACHER_SCRIPT_1:
        from agents.new_teacher_script_1.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.NEW_TEACHER_SCRIPT_2:
        from agents.new_teacher_script_2.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.NEW_TEACHER_SCRIPT_3:
        from agents.new_teacher_script_3.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.NEW_TEACHER_SCRIPT_4:
        from agents.new_teacher_script_4.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.FOLLOWUP_DIGITAL_SAMPLE_1:
        from agents.digital_sample.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.FOLLOWUP_DIGITAL_SAMPLE_2:
        from agents.digital_sample_2.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.FOLLOWUP_PHYSICAL_SAMPLE_1:
        from agents.physical_sample.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.FOLLOWUP_PHYSICAL_SAMPLE_2:
        from agents.physical_sample_2.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.FOLLOWUP_VISIT:
        from agents.visit_followup.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.CONTACTED_PHYSICALLY:
        from agents.contacted_physically.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.CONTACTED_CALL:
        from agents.contacted_call.agent import Step1_Greet
        return Step1_Greet

    elif call_type == CallType.REFERRAL:
        from agents.referral.agent import Step1_Greet
        return Step1_Greet

    else:
        from agents.new_teacher.agent import Step1_Greet
        return Step1_Greet


# ═══════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═══════════════════════════════════════════════════════════════

async def entrypoint(ctx: JobContext):
    """Main entrypoint — dispatched by LiveKit when agent joins a room."""

    # ── Read metadata ────────────────────────────────────────
    # Server puts metadata on the ROOM (CreateRoomRequest.metadata),
    # so we read ctx.room.metadata.  ctx.job.metadata is only populated
    # when using explicit AgentDispatch — try it first as a fallback.
    caller_name = "Prakash"
    phone_number = ""
    call_type_str = "new_teacher_coaching"
    call_client_type = "teacher"

    # Connect first so ctx.room.metadata is available
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    try:
        # Try job metadata first (explicit dispatch)
        raw = ctx.job.metadata or ""
        meta = json.loads(raw) if raw.strip() else {}
        if not meta:
            # Fallback to room metadata (where server.py puts it)
            raw = ctx.room.metadata or ""
            meta = json.loads(raw) if raw.strip() else {}
        caller_name = meta.get("name", "sir") or "sir"
        call_type_str = meta.get("call_type", "new_teacher_coaching") or "new_teacher_coaching"
        phone_number = meta.get("phone_number", meta.get("phone", "")) or ""
        call_client_type = meta.get("call_client_type", "teacher") or "teacher"
    except Exception as e:
        logging.getLogger("entrypoint").warning(f"Metadata parse error: {e}")

    call_type = call_type_from_string(call_type_str)
    voice = get_random_voice()

    # ── Build shared call state ──────────────────────────────
    call_id = f"{phone_number}_{int(time.time())}"
    tracker = CostTracker(call_id=call_id)

    # ── Setup loggers (from working code) ────────────────────
    loggers = setup_loggers(call_id)
    full_log, brief_log, token_log, cost_log, llm_log, transcript_log = loggers

    full_log.info("=" * 60)
    full_log.info(f"📞 NEW CALL | ID: {call_id} | Room: {ctx.room.name}")
    full_log.info(f"📋 Type: {call_type_str} | Name: {caller_name} | Phone: {phone_number}")
    full_log.info("=" * 60)
    brief_log.info(f"CALL_START | {call_id} | type={call_type_str} | name={caller_name}")

    userdata = CallUserData(
        caller_name=caller_name,
        phone_number=phone_number,
        call_type=call_type,
        call_client_type=call_client_type,
        voice=voice,
        tracker=tracker,
        call_id=call_id,
        ctx=ctx,
    )

    # ── Pick the right entry agent ───────────────────────────
    EntryAgent = get_entry_agent(call_type)
    entry_agent = EntryAgent()

    # ── TTS / STT / LLM — matching working code exactly ─────
    tts_plugin = sarvam.TTS(
        target_language_code="hi-IN",
        model="bulbul:v3",
        speaker=voice.tts_speaker,
        pace=1.2,  # 1.0 = too slow for sales calls; 1.65 = natural fast
    )

    stt_plugin = sarvam.STT(
        language="hi-IN",
        model="saaras:v3",
        mode="codemix",
        # No VAD — Sarvam has built-in voice detection
    )

    llm_plugin = openai.LLM(
        model=OPENAI_MODEL,
    )

    # ── Session ────────────────────────────────────────────
    session = AgentSession[CallUserData](
        llm=llm_plugin,
        stt=stt_plugin,
        tts=tts_plugin,
        userdata=userdata,
        user_away_timeout=10,  # seconds of silence before triggering away
    )

    # ── Silence → re-engage ──────────────────────────────────
    @session.on("user_state_changed")
    def on_user_state_changed(ev: UserStateChangedEvent):
        if ev.new_state == "away":
            full_log.info("SILENCE | user_away — generating re-engagement")
            brief_log.info("SILENCE | user_away detected")
            session.generate_reply()

    # ── Metrics collection (from working code) ───────────────
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

    @session.on("user_input_transcribed")
    def on_user_transcribed(ev: UserInputTranscribedEvent):
        """Log interim/final STT results."""
        if ev.is_final:
            brief_log.info(f"STT_FINAL | {ev.transcript}")
        else:
            full_log.info(f"🎤 STT interim: {ev.transcript}")

    # ── Start session ────────────────────────────────────────
    full_log.info("Agent Session starting — multi-agent architecture.")
    await session.start(
        room=ctx.room,
        agent=entry_agent,
        room_options=room_io.RoomOptions(
            delete_room_on_close=True,  # Deletes room on shutdown → disconnects SIP call
        ),
    )

    # ── Background Audio (office ambience + keyboard typing) ──
    # Volume is a gain multiplier, NOT 0-1.  3.0 = amplify 3x.
    # Confirmed working at 3.0 in commit 746a063.
    background_audio = BackgroundAudioPlayer(
        ambient_sound=AudioConfig(BuiltinAudioClip.OFFICE_AMBIENCE, volume=3.0),
        thinking_sound=[
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.8),
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING2, volume=0.7),
        ],
    )
    userdata.background_audio = background_audio  # prevent GC
    await background_audio.start(room=ctx.room, agent_session=session)
    full_log.info("🔊 BackgroundAudioPlayer started (ambient=3.0, typing=0.8/0.7)")

    # ── Periodic cost log ────────────────────────────────────
    async def periodic_cost_log():
        while True:
            await asyncio.sleep(5)
            c = tracker.calculate_costs()
            full_log.info(
                f"💰 COST | {c['duration_minutes']:.2f}min | "
                f"LLM in={c['llm_input_tokens']} out={c['llm_output_tokens']} | "
                f"₹{c['total_cost_inr']:.4f}"
            )

    cost_task = asyncio.create_task(periodic_cost_log())

    # ── Cleanup ────────────────────────────────────────────────

    # Safety net: if the SIP participant hangs up, force-shutdown the session.
    # close_on_disconnect SHOULD do this automatically, but some SIP providers
    # don't send proper disconnect signals, leaving zombie sessions.
    @ctx.room.on("participant_disconnected")
    def on_participant_left(participant):
        full_log.info(f"Participant left: {participant.identity} — forcing session shutdown")
        session.shutdown()

    # Session 'close' event — fires on session.shutdown(), participant disconnect,
    # room delete, etc. This is where we write final reports.
    @session.on("close")
    def on_session_close():
        full_log.info("Session closing — writing final reports.")
        cost_task.cancel()

        # Gracefully shut down background audio to prevent WinError 10054 Proactor loop crash
        if hasattr(userdata, "background_audio") and userdata.background_audio:
            try:
                asyncio.get_event_loop().create_task(userdata.background_audio.aclose())
            except Exception:
                pass

        brief_log.info("CALL_END | session_closed")
        write_cost_report(tracker=tracker, full_log=full_log, cost_log=cost_log, brief_log=brief_log)
        full_log.info("Session closed.")


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
