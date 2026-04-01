"""
tag_lead — tags the lead in the CRM via N8N webhook.
"""

import httpx
import logging
from livekit.agents import function_tool, RunContext
from models import CallUserData
from config import N8N_TAG_LEAD_WEBHOOK_URL

logger = logging.getLogger("tools.tag_lead")


@function_tool()
async def tag_lead_tool(
    context: RunContext[CallUserData],
    tag: str,
    notes: str = "",
):
    """Tag the lead with a status. Tags: Interested, Call Back, Not Interested, Wrong Contact.
    Always call this before ending a call."""

    ud = context.userdata
    ud.lead_tag = tag
    ud.lead_notes = notes

    # Log to cost tracker
    if ud.tracker:
        ud.tracker.log_function("tag_lead", {"tag": tag, "notes": notes})

    logger.info(f"TAG_LEAD | {ud.caller_name} | {tag} | {notes}")

    # Fire N8N webhook (best-effort)
    if N8N_TAG_LEAD_WEBHOOK_URL:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(N8N_TAG_LEAD_WEBHOOK_URL, json={
                    "phone": ud.phone_number,
                    "name": ud.caller_name,
                    "tag": tag,
                    "notes": notes,
                    "call_type": ud.call_type.value,
                    "call_id": ud.call_id,
                })
        except Exception as e:
            logger.warning(f"N8N tag_lead webhook failed: {e}")

    return f"Lead tagged as: {tag}"
