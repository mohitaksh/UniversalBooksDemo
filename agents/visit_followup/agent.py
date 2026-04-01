"""
VISIT FOLLOW-UP — Teacher who was visited in person
════════════════════════════════════════════════════

Step 1: Greetings
Step 2: Recall — Reference the visit + person who visited
Step 3: Take feedback on content & paper quality
Step 4: Share relevant USP (AI-generated from KB)
Step 5: Next steps

EDIT YOUR SCRIPTS below.
"""

import logging
from livekit.agents import RunContext, function_tool
from agents.base_agent import BaseUBAgent
from models import CallUserData
from knowledgebase import kb_to_prompt

logger = logging.getLogger("flow.visit_followup")


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — EDIT THESE
# ═══════════════════════════════════════════════════════════════

S1_GREETING = (
    "Hello, kya meri baat {caller_name} se ho rahi hai? "
    "Mai {agent_name} bol {bol_raha} hूँ, Universal Books se। How are you sir?"
)

S2_RECALL = (
    "Sir, aapko recently humare team member ne visit kiya tha। "
    "Mai unki behalf par call kar {bol_raha} hूँ aapka feedback lene ke liye "
    "aur agar koi query hai toh solve karne ke liye।"
)

S3_ASK_FEEDBACK = (
    "Sir aapko content aur paper quality kaisi lagi?"
)

S5_INTERESTED = (
    "Thank you for your feedback sir, humare products ke aur details ke liye "
    "maine apne senior ko inform kar diya hai, he will call you within the next 1 hour।"
)

S5_HESITANT = (
    "No issues sir, aap ek baar content check kar le, agar aapko "
    "aur chapters bhi chaiye toh aap mujko bata sakte hai। "
    "Humari team aapko visit bhi kar legi। "
    "Furthermore sir, our minimum quantity is just 10 sets so you can even "
    "get a single module to see if our branded material makes an impact।"
)

S5_NOT_INTERESTED = (
    "No issues sir, I understand। Please let us know if and when you change your mind।"
)


# ═══════════════════════════════════════════════════════════════


class Step1_Greet(BaseUBAgent):
    """Step 1: Greeting."""

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
    """Step 2: Recall visit + Step 3: Ask feedback."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You recalled the visit and asked for feedback. Listen.\n"
                "- If they share positive feedback or ask for more, call feedback_positive.\n"
                "- If hesitant, call hesitant.\n"
                "- If not interested, call not_interested.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_RECALL)
        await self.say_script(S3_ASK_FEEDBACK)

    @function_tool()
    async def feedback_positive(self, context: RunContext[CallUserData]):
        """Positive feedback or wants more product info."""
        # Use AI to share relevant USP based on what they teach
        return Step4_ShareUSP(chat_ctx=self.chat_ctx), "Positive feedback"

    @function_tool()
    async def hesitant(self, context: RunContext[CallUserData]):
        """Hesitant."""
        await self.say_script(S5_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", chat_ctx=self.chat_ctx), "Hesitant"

    @function_tool()
    async def not_interested(self, context: RunContext[CallUserData]):
        """Not interested."""
        await self.say_script(S5_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested", chat_ctx=self.chat_ctx), "Not interested"


class Step4_ShareUSP(BaseUBAgent):
    """Step 4: Share relevant USP (AI-generated from KB + company overview)."""

    def __init__(self, **kwargs):
        company_kb = kb_to_prompt("company_overview")
        super().__init__(
            instructions=(
                "Share 2-3 unique selling points of Universal Books naturally in Hinglish. "
                "Use the data below. After sharing, ask if they want a senior call.\n"
                "If YES call interested, if hesitant call hesitant, if no call not_interested.\n\n"
                f"COMPANY DATA:\n{company_kb}"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply()

    @function_tool()
    async def interested(self, context: RunContext[CallUserData]):
        """Wants senior call."""
        await self.say_script(S5_INTERESTED)
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Interested"

    @function_tool()
    async def hesitant(self, context: RunContext[CallUserData]):
        """Hesitant."""
        await self.say_script(S5_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", chat_ctx=self.chat_ctx), "Hesitant"

    @function_tool()
    async def not_interested(self, context: RunContext[CallUserData]):
        """Not interested."""
        await self.say_script(S5_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested", chat_ctx=self.chat_ctx), "Not interested"
