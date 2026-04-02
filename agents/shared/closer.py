"""
closer.py — Shared closing agent used by all call flows.
──────────
Says goodbye, tags the lead via N8N, ends the call.

EDIT YOUR SCRIPTS: Modify CLOSING_GOOD_WISHES below.

LEARNINGS APPLIED (see learnings.md):
  - No EndCallTool (incompatible with Groq schema)
  - @function_tool without parentheses
  - All tools have ≥1 parameter
"""

import logging
import httpx
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
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
    Final agent — says goodbye, tags lead.
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
                "You just said goodbye to the caller. "
                "The call is ending. Do not say anything else."
            ),
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

        # Wait to let the goodbye TTS audio drain, then hang up
        import asyncio
        await asyncio.sleep(5.0)
        try:
            logger.info(f"DISCONNECTING SIP CALL | {ud.caller_name}")
            ud.ctx.room.disconnect()
        except Exception as e:
            logger.error(f"Failed to disconnect room: {e}")

    @function_tool
    async def tag_lead(self, context: RunCtx, tag: str, notes: str = "") -> str:
        """Tag the lead with final outcome. Tags: Interested, Call Back, Not Interested, Wrong Contact."""
        ud = context.userdata
        ud.lead_tag = tag
        ud.lead_notes = notes
        if ud.tracker:
            ud.tracker.log_function("tag_lead", {"tag": tag, "notes": notes})
        logger.info(f"TAG_LEAD | {tag} | {notes}")
        return f"Lead tagged as {tag}."
