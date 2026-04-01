"""
scheduler.py
─────────────
SchedulerAgent — Asks for a callback time, calls N8N webhook,
then hands off to CloserAgent.

EDIT YOUR SCRIPTS: Modify the TIME_ASK and CONFIRM scripts below.
"""

from livekit.agents import RunContext, function_tool
from agents.base_agent import BaseUBAgent
from models import CallUserData
from tools.schedule_callback import schedule_callback_tool


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — Edit these
# ═══════════════════════════════════════════════════════════════

TIME_ASK = (
    "बहुत बढ़िया, आपको call करने का best time क्या रहेगा?"
)

CONFIRM_TEMPLATE = (
    "ठीक है जी, मैंने {callback_time} पर आपकी call book कर दी है। "
    "हमारी team आपसे बात करेगी।"
)

# ═══════════════════════════════════════════════════════════════


class SchedulerAgent(BaseUBAgent):
    """Collects callback time and schedules via N8N."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You need to collect a callback time from the person. "
                "Listen for when they say a time (e.g. 'kal subah', 'tomorrow 5 baje', 'Monday'). "
                "Once they say a time, call set_callback_time with the time string. "
                "Do NOT generate any speech yourself."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(TIME_ASK)

    @function_tool()
    async def set_callback_time(
        self,
        context: RunContext[CallUserData],
        callback_time: str,
    ):
        """Record the callback time the person provided (e.g. 'Tomorrow at 5pm', 'Monday morning')."""
        ud = context.userdata
        ud.callback_time = callback_time

        # Call the N8N webhook
        await schedule_callback_tool.aio_call(context, callback_time=callback_time)

        # Confirm the time
        confirm = CONFIRM_TEMPLATE.format(callback_time=callback_time)
        await self.say_script(confirm)

        from agents.closer import CloserAgent
        return CloserAgent(tag="Call Back", chat_ctx=self.chat_ctx), "Callback scheduled, closing"
