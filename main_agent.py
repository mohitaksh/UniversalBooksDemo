"""
main_agent.py — Single entrypoint for the UniversalBooks Voice AI agent.
═══════════════════════════════════════════════════════════════════════════

DISPATCH FLOW:
  1. server.py creates a room with metadata: {name, phone, call_type}
  2. LiveKit dispatches this agent to the room
  3. This entrypoint reads the metadata
  4. Picks the right call flow entry agent based on call_type
  5. Starts the AgentSession with Sarvam TTS/STT + Groq LLM

All call flows are in agents/{flow_name}/agent.py.

USAGE:
  python main_agent.py dev        # dev mode (auto-reload)
  python main_agent.py start      # production
"""

import json
import time
import asyncio
import logging
from datetime import datetime

from livekit.agents import (
    AgentSession,
    Agent,
    JobContext,
    WorkerOptions,
    cli,
    room_io,
)
from livekit.agents.voice import BackgroundAudioPlayer, AudioConfig
from livekit.plugins import silero, sarvam, groq
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Local imports
from config import GROQ_MODEL, SARVAM_API_KEY, GROQ_API_KEY
from models import (
    CallType,
    CallUserData,
    CostTracker,
    call_type_from_string,
    get_random_voice,
)

logger = logging.getLogger("main_agent")


# ═══════════════════════════════════════════════════════════════
# CALL TYPE → ENTRY AGENT MAPPING
# ═══════════════════════════════════════════════════════════════

def get_entry_agent(call_type: CallType):
    """
    Returns the entry agent class for the given call type.
    Each call flow has its own folder under agents/{flow_name}/.
    """
    if call_type in (CallType.NEW_TEACHER_COACHING, CallType.NEW_TEACHER_TUITION):
        from agents.new_teacher.agent import Step1_Greet
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
# BACKGROUND AUDIO
# ═══════════════════════════════════════════════════════════════

OFFICE_AMBIENCE = AudioConfig(
    file_path="sounds/office-ambience.mp3",
    gain=3.0,
    loop=True,
)

KEYBOARD_TYPING = AudioConfig(
    file_path="sounds/keyboard-typing.mp3",
    gain=0.5,
    loop=True,
)


# ═══════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═══════════════════════════════════════════════════════════════

async def entrypoint(ctx: JobContext):
    """Main entrypoint — dispatched by LiveKit when agent joins a room."""
    await ctx.connect()

    logger.info(f"Agent joined room: {ctx.room.name}")

    # ── Parse room metadata ──────────────────────────────────
    metadata = {}
    try:
        metadata = json.loads(ctx.room.metadata or "{}")
    except json.JSONDecodeError:
        logger.warning("Failed to parse room metadata")

    caller_name = metadata.get("name", "sir")
    phone_number = metadata.get("phone_number", "")
    call_type_str = metadata.get("call_type", "new_teacher_coaching")

    call_type = call_type_from_string(call_type_str)
    voice = get_random_voice()

    logger.info(
        f"CALL START | {caller_name} | {phone_number} | "
        f"type={call_type.value} | voice={voice.name}"
    )

    # ── Build shared call state ──────────────────────────────
    call_id = f"{phone_number}_{int(time.time())}"
    tracker = CostTracker(call_id=call_id)

    userdata = CallUserData(
        caller_name=caller_name,
        phone_number=phone_number,
        call_type=call_type,
        voice=voice,
        tracker=tracker,
        call_id=call_id,
    )

    # ── Pick the right entry agent ───────────────────────────
    EntryAgent = get_entry_agent(call_type)
    entry_agent = EntryAgent()

    # ── Configure TTS / STT / LLM ────────────────────────────
    tts_plugin = sarvam.TTS(
        api_key=SARVAM_API_KEY,
        model="bulbul:v3",
        speaker=voice.tts_speaker,
    )

    stt_plugin = sarvam.STT(
        api_key=SARVAM_API_KEY,
        model="saaras:v3",
        language="hi-IN",
    )

    llm_plugin = groq.LLM(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
    )

    # ── Configure session ────────────────────────────────────
    agent_session = AgentSession[CallUserData](
        userdata=userdata,
        stt=stt_plugin,
        llm=llm_plugin,
        tts=tts_plugin,
        vad=silero.VAD.load(),
        turn_handling={
            "turn_detection": MultilingualModel(),
        },
    )

    # ── Start the session ────────────────────────────────────
    await agent_session.start(
        room=ctx.room,
        agent=entry_agent,
    )

    # ── Background audio ─────────────────────────────────────
    bg = BackgroundAudioPlayer()
    try:
        bg.play(OFFICE_AMBIENCE)
        bg.play(KEYBOARD_TYPING)
    except Exception as e:
        logger.warning(f"Background audio failed: {e}")

    # ── Log on session close ─────────────────────────────────
    async def on_close():
        costs = tracker.calculate_costs()
        logger.info(
            f"CALL END | {caller_name} | {phone_number} | "
            f"type={call_type.value} | "
            f"duration={costs['duration_seconds']}s | "
            f"cost=₹{costs['total_cost_inr']} | "
            f"tag={userdata.lead_tag or 'none'}"
        )

    agent_session.on("close", on_close)


# ═══════════════════════════════════════════════════════════════
# CLI — run with: python main_agent.py dev
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
