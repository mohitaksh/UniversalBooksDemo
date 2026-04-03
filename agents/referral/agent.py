"""
REFERRAL — Teacher referred by someone
═══════════════════════════════════════

Step 1: Greetings — Confirm identity
Step 2: Mention referral — Ask for a minute
→ Permission granted → Jump to new_teacher/Step3_AskClasses
→ Not interested → CloserAgent

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
    "Mai {agent_name} bol {bol_raha} hूँ, Universal Books se।"
)

S2_REFERRAL = (
    "Sir, aapke baare mein humko referral mila hai। "
    "Unhone bataya ki aap coaching classes lete hai। "
    "Hum customized study material banate hai teachers ke liye। "
    "Kya mai aapka ek minute le {le_sakta} hूँ?"
)

S_NOT_INTERESTED = (
    "No issues sir, I understand। Please let us know if and when you change your mind।"
)


class Step1_Greet(BaseUBAgent):
    """Step 1: Greeting — confirm identity."""

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
    async def identity_confirmed(self, context: RunCtx, response: str = "ok") -> "Step2_Referral":
        """Confirmed."""
        return Step2_Referral()

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
        return ObjectionAgent(return_agent=Step2_Referral())


class Step2_Referral(BaseUBAgent):
    """Step 2: Mention referral and ask for a minute."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You mentioned the referral and asked for a minute. Listen.\n"
                "- If they agree / say yes / boliye, call permission_granted.\n"
                "- If not interested, call not_interested.\n"
                "- If busy, call person_busy.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_REFERRAL)

    @function_tool
    async def permission_granted(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Permission to continue — hand off to new teacher flow for pitch."""
        from agents.new_teacher.agent import Step3_AskClasses
        return Step3_AskClasses()

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Not interested."""
        await self.say_script(S_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested")

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
        return ObjectionAgent(return_agent=Step2_Referral())
