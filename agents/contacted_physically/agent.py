"""
CONTACTED PHYSICALLY — Teacher previously contacted in person
═════════════════════════════════════════════════════════════

Follow-up call for a teacher who was previously met in person.

Step 1: Greetings — Confirm identity
Step 2: Recall — Reference in-person contact + ask interest
→ Interested → SchedulerAgent
→ Hesitant → CloserAgent(Call Back)
→ Not Interested → CloserAgent(Not Interested)

EDIT YOUR SCRIPTS below.

LEARNINGS APPLIED (see learnings.md):
  - @function_tool without parentheses
  - All tools have ≥1 parameter (for Groq schema compat)
  - Return Agent instance (not tuple)
  - asyncio.sleep(5.0) in first agent for SIP audio delay
"""

import asyncio
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from agents.shared.objection_handler import ObjectionAgent, S_NUMBER_SOURCE, S_AI_RESPONSE


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


# ═══════════════════════════════════════════════════════════════
# STEP 1: GREETINGS
# ═══════════════════════════════════════════════════════════════

class Step1_Greet(BaseUBAgent):
    """Step 1: Greeting — confirm identity."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You are following up with a teacher previously contacted in person. "
                "You just greeted them. Listen for confirmation.\n"
                "- If confirmed (haan, boliye, ji), call identity_confirmed.\n"
                "- If wrong person, call wrong_person.\n"
                "- If busy, call person_busy.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await asyncio.sleep(5.0)
        await self.say_script(S1_GREETING)

    @function_tool
    async def identity_confirmed(self, context: RunCtx, response: str = "confirmed") -> "Step2_Recall":
        """Person confirmed they are the right contact."""
        return Step2_Recall()

    @function_tool
    async def wrong_person(self, context: RunCtx, response: str = "wrong") -> "BaseUBAgent":
        """Wrong person on the line."""
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Wrong Contact")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> "BaseUBAgent":
        """Person is busy right now."""
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent()

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Person raised an objection (where got number, are you AI)."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_Recall())


# ═══════════════════════════════════════════════════════════════
# STEP 2: RECALL + ASK INTEREST
# ═══════════════════════════════════════════════════════════════

class Step2_Recall(BaseUBAgent):
    """Step 2: Recall personal contact and ask interest level."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You recalled the in-person contact and asked about interest. Listen.\n"
                "- If wants more details / interested, call interested.\n"
                "- If hesitant (dekhte hai, sochte hai), call hesitant.\n"
                "- If not interested, call not_interested.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_RECALL)
        await self.say_script(S3_ASK_INTEREST)

    @function_tool
    async def interested(self, context: RunCtx, response: str = "interested") -> "BaseUBAgent":
        """Interested in more details."""
        await self.say_script(S_INTERESTED)
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent()

    @function_tool
    async def hesitant(self, context: RunCtx, response: str = "hesitant") -> "BaseUBAgent":
        """Hesitant."""
        await self.say_script(S_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back")

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "not interested") -> "BaseUBAgent":
        """Not interested."""
        await self.say_script(S_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Person raised an objection."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_Recall())
