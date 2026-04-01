"""
schedule_callback — schedules a callback via N8N webhook.
"""

import httpx
import logging
from livekit.agents import function_tool, RunContext
from models import CallUserData
from config import N8N_CALLBACK_WEBHOOK_URL

logger = logging.getLogger("tools.schedule_callback")


@function_tool()
async def schedule_callback_tool(
    context: RunContext[CallUserData],
    callback_time: str,
    notes: str = "",
):
    """Schedule a callback for the lead at a specific time.
    Call this when the person agrees to a follow-up and provides a time."""

    ud = context.userdata
    ud.callback_time = callback_time

    # Log to cost tracker
    if ud.tracker:
        ud.tracker.log_function("schedule_callback", {
            "time": callback_time,
            "notes": notes,
        })

    logger.info(f"SCHEDULE_CALLBACK | {ud.caller_name} | {callback_time}")

    # Fire N8N webhook (best-effort)
    if N8N_CALLBACK_WEBHOOK_URL:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(N8N_CALLBACK_WEBHOOK_URL, json={
                    "phone": ud.phone_number,
                    "name": ud.caller_name,
                    "callback_time": callback_time,
                    "notes": notes,
                    "call_type": ud.call_type.value,
                    "call_id": ud.call_id,
                })
        except Exception as e:
            logger.warning(f"N8N schedule_callback webhook failed: {e}")

    return f"Callback scheduled for: {callback_time}"
