"""
base_agent.py
─────────────
Base class for all UniversalBooks agents.
Provides say_script() helper, voice template formatting,
and shared access to session userdata (CallUserData).

LEARNINGS APPLIED (see learnings.md):
  - asyncio.sleep(5.0) for SIP audio establishment (NOT wait_for_participant)
  - Handoffs via returning Agent instance from @function_tool
  - session.update_agent() for programmatic (non-LLM) transfers
"""

import asyncio
import logging
from livekit.agents import Agent
from livekit.agents.voice import RunContext
from models import CallUserData, VoiceProfile

logger = logging.getLogger("agents.base")

# Type alias for convenience in all agent files
RunCtx = RunContext[CallUserData]


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
        except (KeyError, AttributeError) as e:
            logger.warning(f"FMT ERROR | {e} | text={text[:60]}")
            return text

    async def say_script(self, text: str):
        """Say a pre-written script line via TTS (no LLM involved)."""
        formatted = self.fmt(text)
        logger.info(f"SAY | {self.__class__.__name__} | {formatted[:100]}")
        await self.session.say(formatted)

    async def on_enter(self) -> None:
        """Override in subclasses. Base does nothing."""
        logger.info(f"ON_ENTER | {self.__class__.__name__} (base - no override)")

    async def _transfer_to(self, agent: "BaseUBAgent") -> Agent:
        """Transfer to another agent with context preservation."""
        userdata = self.session.userdata
        # Preserve context
        chat_ctx = agent.chat_ctx.copy()
        items_copy = self._truncate_chat_ctx(self.chat_ctx.items, keep_function_call=True)
        existing_ids = {item.id for item in chat_ctx.items}
        items_copy = [item for item in items_copy if item.id not in existing_ids]
        chat_ctx.items.extend(items_copy)
        await agent.update_chat_ctx(chat_ctx)
        return agent

    def _truncate_chat_ctx(
        self, items: list, keep_last_n: int = 6,
        keep_system: bool = False, keep_function_call: bool = False,
    ) -> list:
        """Keep only the last N relevant messages for context efficiency."""
        def _valid(item) -> bool:
            if not keep_system and item.type == "message" and item.role == "system":
                return False
            if not keep_function_call and item.type in ["function_call", "function_call_output"]:
                return False
            return True

        result = []
        for item in reversed(items):
            if _valid(item):
                result.append(item)
            if len(result) >= keep_last_n:
                break
        result = result[::-1]

        while result and result[0].type in ["function_call", "function_call_output"]:
            result.pop(0)
        return result
