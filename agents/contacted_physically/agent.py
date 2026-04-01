"""
CONTACTED PHYSICALLY — Teacher previously contacted in person
═════════════════════════════════════════════════════════════

TEMPLATE — Fill in your scripts below.
Currently uses the same structure as visit_followup.

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
    "Mai {agent_name} bol {bol_raha} hूँ, Universal Books se। How are you sir?"
)

S2_RECALL = (
    "Sir, humare kisi team member ne aapse pehle contact kiya tha personally। "
    "Mai unke behalf par call kar {bol_raha} hूँ follow up ke liye।"
)

S3_ASK_INTEREST = (
    "Sir, kya aapne humara material check kiya? Kya aapko kuch aur details chaiye?"
)

S_INTERESTED = (
    "Sir, maine apne senior ko inform kar diya hai, he will call you within the next 1 hour।"
)

S_HESITANT = (
    "No issues sir, aap ek baar content check kar le। "
    "Humari team aapko visit bhi kar legi।"
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
        return Step2_Recall(chat_ctx=self.chat_ctx), "Confirmed"

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


class Step2_Recall(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions="Recalled contact and asked for interest. If wants more call interested, if hesitant call hesitant, if not interested call not_interested. Do NOT speak.",
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_RECALL)
        await self.say_script(S3_ASK_INTEREST)

    @function_tool()
    async def interested(self, context: RunContext[CallUserData]):
        """Interested."""
        await self.say_script(S_INTERESTED)
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Interested"

    @function_tool()
    async def hesitant(self, context: RunContext[CallUserData]):
        """Hesitant."""
        await self.say_script(S_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", chat_ctx=self.chat_ctx), "Hesitant"

    @function_tool()
    async def not_interested(self, context: RunContext[CallUserData]):
        """Not interested."""
        await self.say_script(S_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested", chat_ctx=self.chat_ctx), "Not interested"
