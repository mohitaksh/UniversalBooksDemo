"""
pitcher.py
──────────
PitcherAgent — Delivers the main sales pitch for new teacher calls.
Hands off to QualifierAgent if interested, CloserAgent if not.

EDIT YOUR SCRIPTS: Modify the PITCH string below.
"""

from livekit.agents import RunContext, function_tool
from agents.base_agent import BaseUBAgent
from models import CallUserData


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — Edit these to change what the agent says
# ═══════════════════════════════════════════════════════════════

PITCH = (
    "जी जैसा कि मैंने बताया, मैं Universal Books से बोल {bol_raha} हूँ। "
    "हम साठ सालों से, यानि की Nineteen Sixties के समय से teachers और "
    "coaching centers के लिए exam preparation books और material बनाते आ रहे हैं, "
    "जिसमें NEET, J double E, CBSE और बाकी काई exams covered हैं। "
    "हमारे material पर आपके institute की branding लगती है, "
    "और इस branding को लगाने का कोई भी extra charge नहीं लगता, "
    "और best बात ये है की हम हर साल updated content देते हैं। "
    "क्या आप हमारे इन सब exam material के बारे में थोड़ा और जानना चाहेंगे?"
)

NOT_INTERESTED_CLOSE = (
    "ठीक है, कोई बात नहीं है। अगर आपको कभी need हो तो हमें इसी number पर "
    "SMS या WhatsApp कर सकते हैं। समय देने के लिये शुक्रिया।"
)

# ═══════════════════════════════════════════════════════════════


class PitcherAgent(BaseUBAgent):
    """Delivers the core pitch and detects interest."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just delivered the sales pitch. Listen to the person's response. "
                "If they want to know more or say yes, call person_interested. "
                "If they say no or not interested, call not_interested. "
                "If they raise an objection (price, already have material, etc.), call objection_raised. "
                "Do NOT generate any speech yourself — all speaking is done via tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        """Deliver the pitch."""
        await self.say_script(PITCH)

    @function_tool()
    async def person_interested(self, context: RunContext[CallUserData]):
        """Person wants to know more about the material."""
        from agents.qualifier import QualifierAgent
        return QualifierAgent(chat_ctx=self.chat_ctx), "Moving to qualification"

    @function_tool()
    async def not_interested(self, context: RunContext[CallUserData]):
        """Person is not interested."""
        await self.say_script(NOT_INTERESTED_CLOSE)
        from agents.closer import CloserAgent
        return CloserAgent(tag="Not Interested", chat_ctx=self.chat_ctx), "Not interested, closing"

    @function_tool()
    async def objection_raised(self, context: RunContext[CallUserData]):
        """Person raised an objection."""
        from agents.objection_handler import ObjectionHandlerAgent
        return ObjectionHandlerAgent(
            return_to="pitcher",
            chat_ctx=self.chat_ctx,
        ), "Handling objection"
