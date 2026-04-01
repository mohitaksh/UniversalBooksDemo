"""
kb_presenter.py
───────────────
KBPresenterAgent — Reads from the matched knowledgebase script,
then asks if they want a detailed team call.

The knowledgebase files are in knowledgebase/*.py.
Each exports a SCRIPT string. This agent reads it via say_script().
"""

import importlib
import logging
from livekit.agents import RunContext, function_tool
from agents.base_agent import BaseUBAgent
from models import CallUserData

logger = logging.getLogger("agents.kb_presenter")


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — Edit these
# ═══════════════════════════════════════════════════════════════

INTEREST_QUESTION = (
    "क्या आप हमारी team से थोड़ा detail में जानने में interested हैं?"
)

# ═══════════════════════════════════════════════════════════════


class KBPresenterAgent(BaseUBAgent):
    """Reads the matched knowledgebase script, then asks for interest."""

    def __init__(self, kb_module: str = "neet_jee", **kwargs):
        self._kb_module = kb_module
        super().__init__(
            instructions=(
                "You just shared info about the study material. Listen to the person. "
                "If they want to learn more or connect with the team, call person_interested_detail. "
                "If they say no, call not_interested. "
                "If they raise an objection, call objection_raised. "
                "Do NOT generate any speech yourself."
            ),
            **kwargs,
        )

    def _load_kb_script(self) -> str:
        """Dynamically load the knowledgebase script."""
        try:
            mod = importlib.import_module(f"knowledgebase.{self._kb_module}")
            return mod.SCRIPT
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load KB module: knowledgebase.{self._kb_module}: {e}")
            # Fallback to company overview
            from knowledgebase.company_overview import SCRIPT
            return SCRIPT

    async def on_enter(self) -> None:
        """Read the KB script, then ask for interest."""
        script = self._load_kb_script()
        await self.say_script(script)
        await self.say_script(INTEREST_QUESTION)

    @function_tool()
    async def person_interested_detail(self, context: RunContext[CallUserData]):
        """Person wants to connect with the team for a detailed call."""
        from agents.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Moving to scheduling"

    @function_tool()
    async def not_interested(self, context: RunContext[CallUserData]):
        """Person is not interested in a detailed call."""
        from agents.closer import CloserAgent
        return CloserAgent(tag="Not Interested", chat_ctx=self.chat_ctx), "Not interested, closing"

    @function_tool()
    async def objection_raised(self, context: RunContext[CallUserData]):
        """Person raised an objection."""
        from agents.objection_handler import ObjectionHandlerAgent
        return ObjectionHandlerAgent(
            return_to="kb_presenter",
            return_kb=self._kb_module,
            chat_ctx=self.chat_ctx,
        ), "Handling objection"
