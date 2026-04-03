"""
PHYSICAL SAMPLE FOLLOW-UP #2 — Second follow-up for physical sample
════════════════════════════════════════════════════════════════════

Step 1: Greetings
Step 2: Check if parcel received
Step 3: IF NOT RECEIVED → Fire N8N delivery check + reshare digital
Step 5: IF RECEIVED → Ask feedback
Step 6: Next steps

EDIT YOUR SCRIPTS below.

LEARNINGS APPLIED (see learnings.md):
  - @function_tool without parentheses
  - All tools have ≥1 parameter (for Groq schema compat)
  - Return Agent instance (not tuple)
  - asyncio.sleep(5.0) in first agent for SIP audio delay
"""

import asyncio
import logging
import httpx
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from agents.shared.objection_handler import ObjectionAgent, S_NUMBER_SOURCE, S_AI_RESPONSE
from config import N8N_DELIVERY_CHECK_WEBHOOK_URL

logger = logging.getLogger("flow.physical_sample_2")


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — EDIT THESE
# ═══════════════════════════════════════════════════════════════

S1_GREETING = (
    "Hello {caller_name} sir, mai {agent_name} bol {bol_raha} hूँ, "
    "Universal Books se। How are you sir?"
)

S2_CHECK_PARCEL = (
    "Sir, calling to check if you have received the book parcel?"
)

S3_NOT_RECEIVED = (
    "Okay sir, humare team ke according parcel deliver hua hai। "
    "Please check if someone from your office have received it। "
    "Mai apni team ko inform kar {kar_deta} hूँ, "
    "woh check karenge aapko parcel kyu nahi mila abhi tak।"
)

S3_RESHARE_DIGITAL = (
    "Tab tak maine aapko digital samples ki file WhatsApp par share kar di hai। "
    "Please aap usko check kare aur humko bataiye kaisa laga।"
)

S5_ASK_FEEDBACK = (
    "Sir aapko content aur paper quality kaisi lagi?"
)

S6_INTERESTED = (
    "Thank you for your feedback sir, humare products ke aur details ke liye "
    "maine apne senior ko inform kar diya hai, he will call you within the next 1 hour।"
)

S6_HESITANT = (
    "No issues sir, aap ek baar content check kar le, agar aapko "
    "aur chapters bhi chaiye toh aap mujko bata sakte hai। "
    "Humari team aapko visit bhi kar legi। "
    "Furthermore sir, our minimum quantity is just 10 sets so you can even "
    "get a single module to see if our branded material makes an impact।"
)

S6_NOT_INTERESTED = (
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
    async def identity_confirmed(self, context: RunCtx, response: str = "ok") -> "Step2_CheckParcel":
        """Confirmed."""
        return Step2_CheckParcel()

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
        return ObjectionAgent(return_agent=Step2_CheckParcel())


class Step2_CheckParcel(BaseUBAgent):
    """Step 2: Check if parcel received."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked if parcel was received.\n"
                "- If YES, call parcel_received.\n"
                "- If NO, call parcel_not_received.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_CHECK_PARCEL)

    @function_tool
    async def parcel_received(self, context: RunCtx, response: str = "ok") -> "Step5_Feedback":
        """Received."""
        return Step5_Feedback()

    @function_tool
    async def parcel_not_received(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Not received. Fire delivery check webhook."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("create_task", {"task": "check_parcel_delivery_2"})

        # Fire N8N delivery check webhook
        if N8N_DELIVERY_CHECK_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(N8N_DELIVERY_CHECK_WEBHOOK_URL, json={
                        "phone": ud.phone_number,
                        "name": ud.caller_name,
                        "issue": "parcel_not_received_followup_2",
                        "call_type": ud.call_type.value,
                        "call_id": ud.call_id,
                    })
            except Exception as e:
                logger.warning(f"N8N delivery check webhook failed: {e}")

        await self.say_script(S3_NOT_RECEIVED)
        await self.say_script(S3_RESHARE_DIGITAL)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", notes="Parcel not received #2, reshared digital")

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Objection raised."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_CheckParcel())


class Step5_Feedback(BaseUBAgent):
    """Step 5: Feedback on content & paper quality."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked for feedback. Listen.\n"
                "- If wants more / interested, call interested.\n"
                "- If hesitant, call hesitant.\n"
                "- If not interested, call not_interested.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S5_ASK_FEEDBACK)

    @function_tool
    async def interested(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Interested."""
        await self.say_script(S6_INTERESTED)
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent()

    @function_tool
    async def hesitant(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Hesitant."""
        await self.say_script(S6_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back")

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "ok") -> "BaseUBAgent":
        """Not interested."""
        await self.say_script(S6_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Objection raised."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step5_Feedback())
