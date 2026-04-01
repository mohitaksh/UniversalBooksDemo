"""
greeter.py
──────────
GreeterAgent — First agent in the call. Verifies caller identity
and asks for permission to speak. Hands off based on response.

EDIT YOUR SCRIPTS: Modify the GREETING and INTRO strings below.
"""

from livekit.agents import Agent, RunContext, function_tool
from agents.base_agent import BaseUBAgent
from models import CallUserData


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — Edit these to change what the agent says
# ═══════════════════════════════════════════════════════════════

# This is said automatically when the agent enters (opening line)
GREETING = (
    "Hello, क्या मेरी बात {caller_name} से हो रही है?"
)

# Said after they confirm identity
INTRO = (
    "जी, {mera} नाम {agent_name} है, मैं Universal Books से बोल {bol_raha} हूँ। "
    "हम एक publishing company हैं, क्या आपसे बस एक minute ले {le_sakta} हूँ?"
)

# Said when wrong person
WRONG_PERSON = (
    "माफ़ी {chahta} हूँ, ग़लत number पर call हो गई। Sorry for the disturbance।"
)

# Said when hostile
HOSTILE = (
    "जी, disturb करने का इरादा नहीं था। आपके time के लिए शुक्रिया। नमस्ते।"
)

# Said when busy
BUSY = (
    "कोई बात नहीं जी, कब time होगा आपके पास?"
)

# ═══════════════════════════════════════════════════════════════


class GreeterAgent(BaseUBAgent):
    """Handles identity verification and permission to speak."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You are a caller verifying the identity of the person on the phone. "
                "Listen to their response. If they confirm their identity, call confirm_identity. "
                "If it's the wrong person, call wrong_person. "
                "If they say they're busy, call person_busy. "
                "If they're hostile or say don't call, call hostile_response. "
                "Do NOT generate any speech yourself — all speaking is done via tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        """Say the opening greeting."""
        await self.say_script(GREETING)

    @function_tool()
    async def confirm_identity(self, context: RunContext[CallUserData]):
        """The person confirmed they are the right contact. Introduce yourself."""
        await self.say_script(INTRO)
        # After intro, LLM listens for permission — next tool handles it

    @function_tool()
    async def permission_granted(self, context: RunContext[CallUserData]):
        """The person gave permission to talk (said haan, boliye, etc). Transfer to pitch."""
        from agents.pitcher import PitcherAgent
        return PitcherAgent(chat_ctx=self.chat_ctx), "Proceeding to pitch"

    @function_tool()
    async def wrong_person(self, context: RunContext[CallUserData]):
        """Wrong person on the line."""
        await self.say_script(WRONG_PERSON)
        from agents.closer import CloserAgent
        return CloserAgent(tag="Wrong Contact", chat_ctx=self.chat_ctx), "Wrong contact, closing"

    @function_tool()
    async def hostile_response(self, context: RunContext[CallUserData]):
        """Person is hostile or doesn't want to talk."""
        await self.say_script(HOSTILE)
        from agents.closer import CloserAgent
        return CloserAgent(tag="Not Interested", chat_ctx=self.chat_ctx), "Not interested, closing"

    @function_tool()
    async def person_busy(self, context: RunContext[CallUserData]):
        """Person says they're busy right now."""
        await self.say_script(BUSY)
        from agents.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Person busy, scheduling callback"
