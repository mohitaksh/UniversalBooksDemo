"""
closer.py
──────────
CloserAgent — Final agent. Says goodbye, tags the lead, ends the call.

EDIT YOUR SCRIPTS: Modify CLOSING below.
"""

import logging
from livekit.agents import RunContext, function_tool
from livekit.agents.beta import EndCallTool
from agents.base_agent import BaseUBAgent
from models import CallUserData
from tools.tag_lead import tag_lead_tool

logger = logging.getLogger("agents.closer")


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — Edit these
# ═══════════════════════════════════════════════════════════════

CLOSING = (
    "बहुत शुक्रिया आपका time देने के लिए। आपका दिन अच्छा रहे, नमस्ते!"
)

# ═══════════════════════════════════════════════════════════════


class CloserAgent(BaseUBAgent):
    """
    Final agent — says goodbye, tags lead, and ends call.

    Args:
        tag: Lead tag to apply (Interested, Call Back, Not Interested, Wrong Contact)
        notes: Optional notes for the tag
    """

    def __init__(self, tag: str = "Not Interested", notes: str = "", **kwargs):
        self._tag = tag
        self._notes = notes
        super().__init__(
            instructions=(
                "You are closing the call. The goodbye has been said. "
                "Now call end_call to disconnect."
            ),
            tools=[EndCallTool()],
            **kwargs,
        )

    async def on_enter(self) -> None:
        """Say goodbye, tag the lead, then the LLM calls end_call."""
        # Say the closing script
        await self.say_script(CLOSING)

        # Tag the lead via N8N
        # We call the tool function directly since we already know the tag
        ud = self.session.userdata
        ud.lead_tag = self._tag
        ud.lead_notes = self._notes

        if ud.tracker:
            ud.tracker.log_function("tag_lead", {"tag": self._tag, "notes": self._notes})

        logger.info(f"CLOSER | tag={self._tag} | notes={self._notes}")

        # Fire N8N webhook (best-effort, reusing the logic from the tool)
        import httpx
        from config import N8N_TAG_LEAD_WEBHOOK_URL
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
