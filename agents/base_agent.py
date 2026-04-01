"""
base_agent.py
─────────────
Base class for all UniversalBooks agents.
Provides say_script() helper, voice template formatting,
and shared access to session userdata (CallUserData).
"""

import logging
from livekit.agents import Agent, RunContext
from models import CallUserData, VoiceProfile

logger = logging.getLogger("agents.base")


class BaseUBAgent(Agent):
    """
    Base agent — all UB agents inherit from this.

    Provides:
    - say_script(text): Calls session.say() with voice-formatted text
    - fmt(text): Formats a template string with voice variables
    - ud (property): Quick access to session.userdata (CallUserData)
    """

    def __init__(self, instructions: str = "", **kwargs):
        super().__init__(instructions=instructions, **kwargs)

    # ── Helpers ──────────────────────────────────────────────

    @property
    def ud(self) -> CallUserData:
        """Shortcut to session.userdata."""
        return self.session.userdata

    def fmt(self, text: str) -> str:
        """Format a script string with voice + caller template variables."""
        try:
            return text.format(**self.ud.voice_vars())
        except (KeyError, AttributeError):
            return text

    async def say_script(self, text: str):
        """Say a pre-written script line via TTS (no LLM involved)."""
        formatted = self.fmt(text)
        logger.debug(f"SAY | {self.__class__.__name__} | {formatted[:80]}...")
        await self.session.say(formatted)

    async def say_and_handoff(self, text: str, next_agent: "BaseUBAgent"):
        """Say a script line, then hand off to the next agent."""
        await self.say_script(text)
        return next_agent
