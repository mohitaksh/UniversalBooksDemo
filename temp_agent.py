"""
temp_agent.py — Minimal test agent matching the working pattern exactly.
"""

import json
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env.local")

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    Agent,
    AgentSession,
    function_tool,
    cli,
)
from livekit.agents.voice import RunContext

from livekit.plugins import sarvam, groq

logger = logging.getLogger("temp_agent")
logger.setLevel(logging.INFO)


@dataclass
class TempUserData:
    caller_name: str = "ji"
    ctx: Optional[JobContext] = None


RunCtx = RunContext[TempUserData]


class SimpleAgent(Agent):
    def __init__(self, caller_name: str = "ji"):
        super().__init__(
            instructions=(
                "You are a friendly Hindi receptionist named Shreya from Universal Books. "
                "Speak in Hinglish. Keep responses short (1-2 sentences). "
                "If they want to end the call, call tag_lead with appropriate tag and then say goodbye."
            ),
        )
        self.caller_name = caller_name

    async def on_enter(self) -> None:
        # SIP audio establishment delay — same as working code
        await asyncio.sleep(5.0)

        opener = f"Hello, kya meri baat {self.caller_name} se ho rahi hai?"
        await self.session.say(opener)

    @function_tool
    async def tag_lead(self, context: RunCtx, tag: str, notes: str = "") -> str:
        """Tag the lead outcome. Tags: Interested, Not Interested, Call Back, Wrong Contact."""
        logger.info(f"TAG_LEAD | tag={tag} notes={notes}")
        return f"Lead tagged as {tag}."

    @function_tool
    async def schedule_callback(self, context: RunCtx, time_1: str, time_2: str = "", notes: str = "") -> str:
        """Schedule a callback with preferred times."""
        logger.info(f"SCHEDULE | t1={time_1} t2={time_2}")
        return "Callback scheduled."


async def entrypoint(ctx: JobContext):
    caller_name = "ji"
    try:
        meta = json.loads(ctx.job.metadata or "{}")
        caller_name = meta.get("name", "ji") or "ji"
        logger.info(f"Meta: {meta}")
    except Exception:
        pass

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info(f"Connected: {ctx.room.name}")

    userdata = TempUserData(caller_name=caller_name, ctx=ctx)
    agent = SimpleAgent(caller_name=caller_name)

    # Exact same plugin config as working code (minus aws, using groq)
    session = AgentSession[TempUserData](
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        stt=sarvam.STT(language="hi-IN", model="saaras:v3", mode="codemix"),
        tts=sarvam.TTS(target_language_code="hi-IN", model="bulbul:v3", speaker="shubh"),
        userdata=userdata,
        user_away_timeout=10,
    )

    await session.start(room=ctx.room, agent=agent)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
