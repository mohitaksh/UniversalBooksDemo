"""
objection_handler.py
────────────────────
ObjectionHandlerAgent — Handles common objections with hardcoded scripts.
Returns to the previous agent after resolving.

EDIT YOUR SCRIPTS: Add/modify objection responses below.
"""

from livekit.agents import RunContext, function_tool
from agents.base_agent import BaseUBAgent
from models import CallUserData


# ═══════════════════════════════════════════════════════════════
# OBJECTION SCRIPTS — Edit these to change responses
# Each key is an objection type, value is the response script.
# ═══════════════════════════════════════════════════════════════

OBJECTION_SCRIPTS = {
    "price": (
        "जी, pricing subjects और quantity के हिसाब से customise होती है। "
        "हमारी team आपको detail में बता पाएगी — क्या मैं उनसे call arrange कर दूँ?"
    ),
    "own_material": (
        "जी समझ {samajh_gaya}। बहुत सारे institutes जो अब हमारे साथ हैं, "
        "उनका भी अपना material था। हमसे जुड़ने का Advantage ये है कि हमारा content "
        "हर साल latest exam pattern के हिसाब से update होता है — "
        "तो teachers का research time बचता है।"
    ),
    "think_about_it": (
        "बिल्कुल, कोई जल्दी की बात नहीं है। जब time मिले बताइएगा, "
        "हमें इसी number पर SMS या WhatsApp कर सकते हैं।"
    ),
    "who_gave_number": (
        "जी, आपकी details publicly available directories से मिली हैं। "
        "अगर आप नहीं चाहते कि हम आपको दोबारा कभी call करें तो हमें बताएं, "
        "हम note कर लेंगे।"
    ),
    "not_right_time": (
        "कोई बात नहीं जी। आपको कब time मिलेगा? मैं उस time call arrange करवा {kar_deta} हूँ।"
    ),
    "already_using": (
        "जी बहुत अच्छी बात है। हमारा material complement के तौर पर भी use हो सकता है। "
        "बहुत से institutes अपने material के साथ हमारा practice material भी रखते हैं।"
    ),
}

# Default fallback if objection type isn't recognized
DEFAULT_OBJECTION_RESPONSE = (
    "जी, मैं समझ {le_sakta} हूँ। क्या मैं आपके लिए कुछ और help कर {le_sakta} हूँ?"
)

# ═══════════════════════════════════════════════════════════════


class ObjectionHandlerAgent(BaseUBAgent):
    """
    Handles objections and routes back to the previous agent.

    Args:
        return_to: Which agent to return to after handling ("pitcher", "qualifier", "kb_presenter")
        return_kb: If returning to kb_presenter, which KB module to reload
    """

    def __init__(self, return_to: str = "pitcher", return_kb: str = "neet_jee", **kwargs):
        self._return_to = return_to
        self._return_kb = return_kb
        super().__init__(
            instructions=(
                "You are handling an objection from the caller. "
                "Listen to what they said and classify their objection. Then call the right handler: "
                "handle_price, handle_own_material, handle_think_about_it, "
                "handle_who_gave_number, handle_not_right_time, handle_already_using, "
                "or handle_generic for anything else. "
                "Do NOT generate any speech yourself."
            ),
            **kwargs,
        )

    def _get_return_agent(self):
        """Get the agent to return to after handling the objection."""
        if self._return_to == "qualifier":
            from agents.qualifier import QualifierAgent
            return QualifierAgent(chat_ctx=self.chat_ctx)
        elif self._return_to == "kb_presenter":
            from agents.kb_presenter import KBPresenterAgent
            return KBPresenterAgent(kb_module=self._return_kb, chat_ctx=self.chat_ctx)
        else:
            from agents.pitcher import PitcherAgent
            return PitcherAgent(chat_ctx=self.chat_ctx)

    async def _handle(self, key: str):
        script = OBJECTION_SCRIPTS.get(key, DEFAULT_OBJECTION_RESPONSE)
        await self.say_script(script)

    @function_tool()
    async def handle_price(self, context: RunContext[CallUserData]):
        """Person asked about pricing."""
        await self._handle("price")
        from agents.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Offering to schedule call for pricing"

    @function_tool()
    async def handle_own_material(self, context: RunContext[CallUserData]):
        """Person says they already have their own material."""
        await self._handle("own_material")
        return self._get_return_agent(), "Returning after answering"

    @function_tool()
    async def handle_think_about_it(self, context: RunContext[CallUserData]):
        """Person says they'll think about it."""
        await self._handle("think_about_it")
        from agents.closer import CloserAgent
        return CloserAgent(tag="Call Back", chat_ctx=self.chat_ctx), "Closing warmly"

    @function_tool()
    async def handle_who_gave_number(self, context: RunContext[CallUserData]):
        """Person asks who gave their number."""
        await self._handle("who_gave_number")
        return self._get_return_agent(), "Returning after answering"

    @function_tool()
    async def handle_not_right_time(self, context: RunContext[CallUserData]):
        """Person says it's not the right time."""
        await self._handle("not_right_time")
        from agents.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Scheduling callback"

    @function_tool()
    async def handle_already_using(self, context: RunContext[CallUserData]):
        """Person says they already use similar material."""
        await self._handle("already_using")
        return self._get_return_agent(), "Returning after answering"

    @function_tool()
    async def handle_generic(self, context: RunContext[CallUserData]):
        """Any other objection not covered above."""
        await self._handle("_generic_")
        return self._get_return_agent(), "Returning after answering"
