"""
REFERRAL — Teacher referred by someone
═══════════════════════════════════════

TEMPLATE — Fill in your scripts below.

EDIT YOUR SCRIPTS below.
"""

from livekit.agents import RunContext, function_tool
from agents.base_agent import BaseUBAgent
from models import CallUserData


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — EDIT THESE WITH YOUR ACTUAL SCRIPTS
# ═══════════════════════════════════════════════════════════════

S1_GREETING = (
    "Hello, kya meri baat {caller_name} se ho rahi hai? "
    "Mai {agent_name} bol {bol_raha} hूँ, Universal Books se।"
)

S2_REFERRAL = (
    "Sir, aapke baare mein humko referral mila hai। "
    "Unhone bataya ki aap coaching classes lete hai। "
    "Hum customized study material banate hai teachers ke liye। "
    "Kya mai aapka ek minute le {le_sakta} hूँ?"
)

S_INTERESTED = (
    "Sir, maine apne senior ko inform kar diya hai, he will call you within the next 1 hour।"
)

S_NOT_INTERESTED = (
    "No issues sir, I understand। Please let us know if and when you change your mind।"
)


class Step1_Greet(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions="Greeting. If confirmed call identity_confirmed, if wrong call wrong_person, if busy call person_busy. Do NOT speak.",
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S1_GREETING)

    @function_tool()
    async def identity_confirmed(self, context: RunContext[CallUserData]):
        """Confirmed."""
        return Step2_Referral(chat_ctx=self.chat_ctx), "Confirmed"

    @function_tool()
    async def wrong_person(self, context: RunContext[CallUserData]):
        """Wrong."""
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Wrong Contact", chat_ctx=self.chat_ctx), "Wrong"

    @function_tool()
    async def person_busy(self, context: RunContext[CallUserData]):
        """Busy."""
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Busy"


class Step2_Referral(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You mentioned the referral and asked for a minute. "
                "If they agree, call permission_granted. "
                "If not interested, call not_interested. "
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_REFERRAL)

    @function_tool()
    async def permission_granted(self, context: RunContext[CallUserData]):
        """Permission to continue — hand off to new teacher flow for pitch."""
        from agents.new_teacher.agent import Step3_AskClasses
        return Step3_AskClasses(chat_ctx=self.chat_ctx), "Referral → pitch"

    @function_tool()
    async def not_interested(self, context: RunContext[CallUserData]):
        """Not interested."""
        await self.say_script(S_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested", chat_ctx=self.chat_ctx), "Not interested"
