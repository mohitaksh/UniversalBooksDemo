"""
scheduler.py — Shared scheduling agent used by all call flows.
──────────────
Creates a task for the senior team to call back.
Fires N8N webhook with the details.

EDIT YOUR SCRIPTS: Modify SETUP_CALL and CONFIRM below.

LEARNINGS APPLIED (see learnings.md):
  - @function_tool without parentheses
  - All tools have ≥1 parameter
  - Return Agent instance (not tuple)
"""

import logging
import httpx
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from models import CallUserData
from config import N8N_CALLBACK_WEBHOOK_URL

logger = logging.getLogger("agents.scheduler")


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — Edit these
# ═══════════════════════════════════════════════════════════════

SETUP_CALL = (
    "Sir, our senior will call you within the next 2~3 hours. "
    "Aapke paas koi specific time hai jo better ho?"
)

CONFIRM_SCHEDULED = (
    "Done sir, maine aapki call {callback_time} ke liye book kar di hai। "
    "Humari senior team aapse baat karegi।"
)

CONFIRM_DEFAULT = (
    "Done sir, our senior will call you within the next 1 hour."
)

# ═══════════════════════════════════════════════════════════════


class SchedulerAgent(BaseUBAgent):
    """
    Schedules a callback with the senior team.
    Fires an N8N webhook to create the task.
    """

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You need to schedule a call with the senior team. "
                "If the person gives a specific time, call set_callback_time with that time. "
                "If they say 'anytime' or 'within 1 hour is fine', call confirm_default_time. "
                "Do NOT generate any speech yourself."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(SETUP_CALL)

    @function_tool
    async def set_callback_time(
        self,
        context: RunCtx,
        callback_time: str,
    ) -> "BaseUBAgent":
        """Person gave a specific callback time (e.g. 'tomorrow 5pm', 'Monday morning')."""
        ud = context.userdata
        ud.callback_time = callback_time

        if ud.tracker:
            ud.tracker.log_function("schedule_callback", {"time": callback_time})

        logger.info(f"SCHEDULE | {ud.caller_name} | {callback_time}")

        # Fire N8N webhook
        await self._fire_webhook(ud, callback_time)

        await self.say_script(CONFIRM_SCHEDULED.format(callback_time=callback_time))

        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back")

    @function_tool
    async def confirm_default_time(self, context: RunCtx, response: str = "anytime") -> "BaseUBAgent":
        """Person is fine with default '1 hour' callback window."""
        ud = context.userdata
        ud.callback_time = "within 1 hour"

        if ud.tracker:
            ud.tracker.log_function("schedule_callback", {"time": "within 1 hour"})

        logger.info(f"SCHEDULE | {ud.caller_name} | default 1hr")

        await self._fire_webhook(ud, "within 1 hour")
        await self.say_script(CONFIRM_DEFAULT)

        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back")

    async def _fire_webhook(self, ud: CallUserData, callback_time: str):
        if N8N_CALLBACK_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(N8N_CALLBACK_WEBHOOK_URL, json={
                        "phone": ud.phone_number,
                        "name": ud.caller_name,
                        "callback_time": callback_time,
                        "call_type": ud.call_type.value,
                        "call_id": ud.call_id,
                        "exam_type": ud.exam_type or "",
                    })
            except Exception as e:
                logger.warning(f"N8N schedule webhook failed: {e}")
