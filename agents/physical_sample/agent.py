"""
PHYSICAL SAMPLE FOLLOW-UP — Teacher who received physical sample
═════════════════════════════════════════════════════════════════

Step 1: Greetings — Confirm name
Step 2: Recall — Ask if received physical sample books
Step 3: IF NOT RECEIVED → Create task to check delivery, reshare digital
Step 5: IF RECEIVED → Ask feedback on content & paper quality
Step 6: Next steps (interested / hesitant / not interested)

EDIT YOUR SCRIPTS below.
"""

import logging
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from models import CallUserData

logger = logging.getLogger("flow.physical_sample")


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — EDIT THESE
# ═══════════════════════════════════════════════════════════════

S1_GREETING = (
    "Hello, kya meri baat {caller_name} se ho rahi hai? "
    "Mai {agent_name} bol {bol_raha} hूँ, Universal Books se। How are you sir?"
)

S2_RECALL = (
    "Sir, aapko recently humare physical sample books mile honge। "
    "Kya aapne unka content check kiya?"
)

S3_NOT_RECEIVED = (
    "Okay sir, mai apni team ko inform kar {kar_deta} hूँ, "
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
                "- If wrong person, call wrong_person.\n"
                "- If busy, call person_busy.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S1_GREETING)

    @function_tool
    async def identity_confirmed(self, context: RunCtx, response: str = "ok"):
        """Confirmed."""
        return Step2_Recall(chat_ctx=self.chat_ctx), "Confirmed"

    @function_tool
    async def wrong_person(self, context: RunCtx, response: str = "ok"):
        """Wrong person."""
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Wrong Contact", chat_ctx=self.chat_ctx), "Wrong"

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "ok"):
        """Busy."""
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Busy"


class Step2_Recall(BaseUBAgent):
    """Step 2: Ask if received physical sample."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked if they received the physical sample books.\n"
                "- If YES received, call sample_received.\n"
                "- If NOT received, call sample_not_received.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_RECALL)

    @function_tool
    async def sample_received(self, context: RunCtx, response: str = "ok"):
        """Person received the physical sample."""
        return Step5_Feedback(chat_ctx=self.chat_ctx), "Received"

    @function_tool
    async def sample_not_received(self, context: RunCtx, response: str = "ok"):
        """Person did NOT receive the sample. Create task + reshare digital."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("create_task", {"task": "check_parcel_delivery"})

        await self.say_script(S3_NOT_RECEIVED)
        await self.say_script(S3_RESHARE_DIGITAL)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", notes="Parcel not received, reshared digital", chat_ctx=self.chat_ctx), "Not received"


class Step5_Feedback(BaseUBAgent):
    """Step 5: Ask feedback on content & paper quality."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked about content and paper quality. Listen to their feedback.\n"
                "- If they ask for more (pricing, order, visit, more samples), call interested.\n"
                "- If hesitant (dekhte hai, sochte hai), call hesitant.\n"
                "- If not interested, call not_interested.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S5_ASK_FEEDBACK)

    @function_tool
    async def interested(self, context: RunCtx, response: str = "ok"):
        """Wants more details, pricing, visit, or order."""
        await self.say_script(S6_INTERESTED)
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Interested"

    @function_tool
    async def hesitant(self, context: RunCtx, response: str = "ok"):
        """Hesitant."""
        await self.say_script(S6_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", chat_ctx=self.chat_ctx), "Hesitant"

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "ok"):
        """Not interested."""
        await self.say_script(S6_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested", chat_ctx=self.chat_ctx), "Not interested"
