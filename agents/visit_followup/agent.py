"""
VISIT FOLLOW-UP — Teacher who was visited in person
════════════════════════════════════════════════════

Step 1: Greetings
Step 2: Recall — Reference the visit + person who visited
Step 3: Take feedback on content & paper quality
Step 4: Share relevant USP (AI-generated from KB)
Step 5: Next steps

EDIT YOUR SCRIPTS below.

LEARNINGS APPLIED (see learnings.md):
  - @function_tool without parentheses
  - All tools have ≥1 parameter (for Groq schema compat)
  - Return Agent instance (not tuple)
  - asyncio.sleep(5.0) in first agent for SIP audio delay
"""

import asyncio
import logging
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from agents.shared.objection_handler import ObjectionAgent, S_NUMBER_SOURCE, S_AI_RESPONSE
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
            instructions=(
                "You greeted the teacher. Listen for confirmation.\n"
                "- If confirmed, call identity_confirmed.\n"
                "- If wrong, call wrong_person.\n"
                "- If busy, call person_busy.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await asyncio.sleep(5.0)
        await self.say_script(S1_GREETING)

    @function_tool
    async def identity_confirmed(self, context: RunCtx, response: str = "ok") -> "Step2_Recall":
        """Confirmed."""
        return Step2_Recall()

    @function_tool
    async def wrong_person(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Wrong."""
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Wrong Contact")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Busy."""
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent()

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Objection raised."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_Recall())


class Step2_Recall(BaseUBAgent):
    """Step 2: Recall visit + Step 3: Ask feedback."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You recalled the visit and asked for feedback. Listen.\n"
                "- If they share positive feedback or ask for more, call feedback_positive.\n"
                "- If hesitant, call hesitant.\n"
                "- If not interested, call not_interested.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_RECALL)
        await self.say_script(S3_ASK_FEEDBACK)

    @function_tool
    async def feedback_positive(self, context: RunCtx, response: str = "ok") -> "Step4_ShareUSP":
        """Positive feedback or wants more product info."""
        return Step4_ShareUSP()

    @function_tool
    async def hesitant(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Hesitant."""
        await self.say_script(S5_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back")

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Not interested."""
        await self.say_script(S5_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Objection raised."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_Recall())


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
        self.session.generate_reply()

    @function_tool
    async def interested(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Wants senior call."""
        await self.say_script(S5_INTERESTED)
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent()

    @function_tool
    async def hesitant(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Hesitant."""
        await self.say_script(S5_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back")

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Not interested."""
        await self.say_script(S5_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Objection raised."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step4_ShareUSP())
