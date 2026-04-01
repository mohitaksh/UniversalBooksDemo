"""
closer.py — Shared closing agent used by all call flows.
──────────
Says goodbye, tags the lead via N8N, ends the call.

EDIT YOUR SCRIPTS: Modify CLOSING_GOOD_WISHES below.
"""

import logging
import httpx
from livekit.agents import Agent, RunContext, function_tool
from livekit.agents.beta.tools.end_call import EndCallTool
from agents.base_agent import BaseUBAgent
from models import CallUserData
from config import N8N_TAG_LEAD_WEBHOOK_URL

logger = logging.getLogger("agents.closer")


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — Edit these
# ═══════════════════════════════════════════════════════════════

CLOSING_GOOD_WISHES = (
    "Thank you for your time sir, our content has empowered 1 Lakh+ institutes "
    "with better results and admissions and we are always here to keep working "
    "towards helping you teach better. Have a great day sir!"
)

# ═══════════════════════════════════════════════════════════════


class CloserAgent(BaseUBAgent):
    """
    Final agent — says goodbye, tags lead, and ends call.
    Used by ALL call flows as the terminal agent.

    Args:
        tag: Lead tag (Interested, Call Back, Not Interested, Wrong Contact)
        notes: Optional notes
    """

    def __init__(self, tag: str = "Not Interested", notes: str = "", **kwargs):
        self._tag = tag
        self._notes = notes
        super().__init__(
            instructions=(
                "The goodbye has been said. Call end_call to disconnect."
            ),
            tools=[EndCallTool()],
            **kwargs,
        )

    async def on_enter(self) -> None:
        # Say goodbye
        await self.say_script(CLOSING_GOOD_WISHES)

        # Tag the lead (best-effort webhook)
        ud = self.session.userdata
        ud.lead_tag = self._tag
        ud.lead_notes = self._notes

        if ud.tracker:
            ud.tracker.log_function("tag_lead", {"tag": self._tag, "notes": self._notes})

        logger.info(f"CLOSER | {ud.caller_name} | tag={self._tag}")

        if N8N_TAG_LEAD_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(N8N_TAG_LEAD_WEBHOOK_URL, json={
                        "phone": ud.phone_number,
                        "name": ud.caller_name,
                        "tag": self._tag,
                        "notes": self._notes,
                        "call_type": ud.call_type.value,
                        "call_id": ud.call_id,
                    })
            except Exception as e:
                logger.warning(f"N8N tag_lead webhook failed: {e}")
