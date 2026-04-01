"""
PHYSICAL SAMPLE FOLLOW-UP #2 — Second follow-up for physical sample
════════════════════════════════════════════════════════════════════

Step 1: Greetings
Step 2: Check if parcel received
Step 3: IF NOT RECEIVED → Check delivery status + reshare digital
Step 5: IF RECEIVED → Ask feedback
Step 6: Next steps

EDIT YOUR SCRIPTS below.
"""

import logging
from livekit.agents import RunContext, function_tool
from agents.base_agent import BaseUBAgent
from models import CallUserData

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
            instructions="Greeting. If confirmed call identity_confirmed, if wrong call wrong_person, if busy call person_busy. Do NOT speak.",
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S1_GREETING)

    @function_tool()
    async def identity_confirmed(self, context: RunContext[CallUserData]):
        """Confirmed."""
        return Step2_CheckParcel(chat_ctx=self.chat_ctx), "Confirmed"

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


class Step2_CheckParcel(BaseUBAgent):
    """Step 2: Check if parcel received."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions="Asked if parcel received. If YES call parcel_received, if NO call parcel_not_received. Do NOT speak.",
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_CHECK_PARCEL)

    @function_tool()
    async def parcel_received(self, context: RunContext[CallUserData]):
        """Received."""
        return Step5_Feedback(chat_ctx=self.chat_ctx), "Received"

    @function_tool()
    async def parcel_not_received(self, context: RunContext[CallUserData]):
        """Not received."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("create_task", {"task": "check_parcel_delivery_2"})
        await self.say_script(S3_NOT_RECEIVED)
        await self.say_script(S3_RESHARE_DIGITAL)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", notes="Parcel not received #2, reshared digital", chat_ctx=self.chat_ctx), "Not received"


class Step5_Feedback(BaseUBAgent):
    """Step 5: Feedback on content & paper quality."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions="Asked for feedback. If wants more call interested, if hesitant call hesitant, if not interested call not_interested. Do NOT speak.",
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S5_ASK_FEEDBACK)

    @function_tool()
    async def interested(self, context: RunContext[CallUserData]):
        """Interested."""
        await self.say_script(S6_INTERESTED)
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Interested"

    @function_tool()
    async def hesitant(self, context: RunContext[CallUserData]):
        """Hesitant."""
        await self.say_script(S6_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", chat_ctx=self.chat_ctx), "Hesitant"

    @function_tool()
    async def not_interested(self, context: RunContext[CallUserData]):
        """Not interested."""
        await self.say_script(S6_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested", chat_ctx=self.chat_ctx), "Not interested"
