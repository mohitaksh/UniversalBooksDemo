"""
main_agent.py — Single entrypoint for the UniversalBooks Voice AI agent.
═══════════════════════════════════════════════════════════════════════════

DISPATCH FLOW:
  1. server.py creates a room with metadata: {name, phone, call_type}
  2. LiveKit dispatches this agent to the room
  3. This entrypoint reads the metadata
  4. Picks the right call flow entry agent based on call_type
  5. Starts the AgentSession with that agent + Sarvam TTS/STT + Groq LLM

All call flows are in agents/{flow_name}/agent.py.
"""

import json
import time
import asyncio
import logging
from datetime import datetime

from livekit.agents import (
    AgentSession,
    Agent,
    RtcSession,
    rtc_session,
    room_io,
)
from livekit.agents.voice import BackgroundAudioPlayer, AudioConfig
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Local imports
from config import GROQ_MODEL
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
        # Default: new teacher coaching
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

@rtc_session()
async def entrypoint(session: RtcSession):
    """Main entrypoint — dispatched by LiveKit when agent joins a room."""
    logger.info(f"Agent joined room: {session.room.name}")

    # ── Parse room metadata ──────────────────────────────────
    metadata = {}
    try:
        metadata = json.loads(session.room.metadata or "{}")
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

    # ── Configure session ────────────────────────────────────
    agent_session = AgentSession[CallUserData](
        userdata=userdata,
        stt=f"sarvam/saaras:v3:hi-IN",
        llm=f"groq/{GROQ_MODEL}",
        tts=f"sarvam/bulbul:v3:{voice.tts_speaker}",
        vad=silero.VAD.load(),
        turn_handling={
            "turn_detection": MultilingualModel(),
        },
    )

    # ── Start the session ────────────────────────────────────
    await agent_session.start(
        room=session.room,
        agent=entry_agent,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )

    # ── Background audio ─────────────────────────────────────
    bg = BackgroundAudioPlayer()
    try:
        bg.play(OFFICE_AMBIENCE)
        bg.play(KEYBOARD_TYPING)
    except Exception as e:
        logger.warning(f"Background audio failed: {e}")

    # ── Wait for session to end ──────────────────────────────
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
