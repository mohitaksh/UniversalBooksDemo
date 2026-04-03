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
                "You need to schedule a callback with the senior team. "
                "Listen carefully to what the person says.\n\n"
                "ROUTING RULES:\n"
                "1. If they give a specific time (e.g. 'kal 5 baje', 'Monday morning'), "
                "call set_callback_time.\n"
                "2. If they say 'anytime' or 'within 1 hour is fine' or 'koi bhi time', "
                "call confirm_default_time.\n"
                "3. If they CORRECT themselves or say they want to continue talking about "
                "products/classes (e.g. 'nahi maine kaha boards ki padhai hoti hai', "
                "'hum interested hain', 'meri baat suno', 'boards', 'NEET', mention "
                "any class/exam name), call misrouted_correction.\n"
                "4. If they say they are NOT interested (nahi chahiye, interest nahi, "
                "rakhiye, bye), call not_interested.\n\n"
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

    @function_tool
    async def misrouted_correction(self, context: RunCtx, what_they_said: str = "correction") -> "BaseUBAgent":
        """Person corrected themselves — they actually want to talk about classes/products, not schedule a callback."""
        logger.info(f"SCHEDULER | Misrouted correction: {what_they_said} — routing back to Step3")
        await self.say_script("जी बिल्कुल, कोई बात नहीं!")
        from agents.new_teacher.agent import Step3_AskClasses
        return Step3_AskClasses()

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "no") -> "BaseUBAgent":
        """Person is not interested at all."""
        logger.info(f"SCHEDULER | Not interested: {response}")
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested")

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
