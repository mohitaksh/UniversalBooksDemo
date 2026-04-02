"""
DIGITAL SAMPLE FOLLOW-UP — Teacher who received digital sample
═══════════════════════════════════════════════════════════════

6-step flow for following up after sharing digital sample.

Step 1: Greetings — Confirm name, share company name
Step 2: Recall — Reference past conversation & sample shared
Step 3: Follow up — Ask if they checked the files
Step 4: If NOT SEEN → Reshare / If SEEN → Take feedback
Step 5: Next steps (interested / hesitant / not interested)
Step 6: Good Wishes

EDIT YOUR SCRIPTS: Modify the constants below each ═══ header.
"""

import logging
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from models import CallUserData

logger = logging.getLogger("flow.digital_sample")


# ═══════════════════════════════════════════════════════════════
# STEP 1 — GREETING
# ═══════════════════════════════════════════════════════════════

S1_GREETING = (
    "Hello, kya meri baat {caller_name} se ho rahi hai? "
    "Mai {agent_name} bol {bol_raha} hूँ, Universal Books se। How are you sir?"
)

# ═══════════════════════════════════════════════════════════════
# STEP 2 — RECALL PAST CONVERSATION
# ═══════════════════════════════════════════════════════════════

S2_RECALL = (
    "Sir humne pichli baar baat ki thi aur maine aapko humare "
    "products ka digital sample share kiya tha WhatsApp par।"
)

# ═══════════════════════════════════════════════════════════════
# STEP 3 — FOLLOW UP
# ═══════════════════════════════════════════════════════════════

S3_FOLLOWUP = (
    "Sir, aapne files dekhi? Kaisa laga aapko humara content?"
)

# ═══════════════════════════════════════════════════════════════
# STEP 4 — BRANCHES
# ═══════════════════════════════════════════════════════════════

S4_NOT_SEEN = (
    "No issues sir, mai files dobara send kar {kar_deta} hूँ aapko। "
    "Please aap usko check kare aur humko bataiye kaisa laga।"
)

S4_FEEDBACK_ACK = (
    "Thank you sir, aap jaise teachers ke feedback ke basis par hi "
    "hum apna material design aur improve karte hai। "
    "Maine apni senior team ko bhi yeh feedback share kar diya hai।"
)

# ═══════════════════════════════════════════════════════════════
# STEP 5 — NEXT STEPS
# ═══════════════════════════════════════════════════════════════

S5_INTERESTED = (
    "Sir humare products ke aur details ke liye maine apne senior ko "
    "inform kar diya hai, he will call you within the next 1 hour।"
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
    """Step 1: Greeting — confirm identity."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You are following up with a teacher. You just greeted them. "
                "Listen for confirmation.\n"
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
        """Person confirmed identity."""
        return Step2_Recall(chat_ctx=self.chat_ctx), "Confirmed"

    @function_tool
    async def wrong_person(self, context: RunCtx, response: str = "ok"):
        """Wrong person."""
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Wrong Contact", chat_ctx=self.chat_ctx), "Wrong person"

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "ok"):
        """Person is busy."""
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Busy"


class Step2_Recall(BaseUBAgent):
    """Step 2: Recall past conversation + Step 3: Ask if checked."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You recalled the past conversation and asked if they checked the files. "
                "Listen for their response.\n"
                "- If they HAVE seen the files and share feedback, call sample_seen.\n"
                "- If they have NOT seen the files yet, call sample_not_seen.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_RECALL)
        await self.say_script(S3_FOLLOWUP)

    @function_tool
    async def sample_seen(self, context: RunCtx, response: str = "ok"):
        """Person has seen the digital sample and is sharing feedback."""
        await self.say_script(S4_FEEDBACK_ACK)
        return Step5_NextSteps(chat_ctx=self.chat_ctx), "Feedback received"

    @function_tool
    async def sample_not_seen(self, context: RunCtx, response: str = "ok"):
        """Person has NOT seen the files yet."""
        await self.say_script(S4_NOT_SEEN)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", notes="Reshared digital sample", chat_ctx=self.chat_ctx), "Reshared"


class Step5_NextSteps(BaseUBAgent):
    """Step 5: Next steps based on interest level."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "The teacher gave feedback. Listen for their next intent.\n"
                "- If they ask for more details, pricing, want a visit, or want to order — "
                "call interested.\n"
                "- If hesitant (dekhte hai, sochte hai, abhi nahi) — call hesitant.\n"
                "- If clearly not interested — call not_interested.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    @function_tool
    async def interested(self, context: RunCtx, response: str = "ok"):
        """Person wants more details, pricing, order, or visit."""
        await self.say_script(S5_INTERESTED)
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Interested"

    @function_tool
    async def hesitant(self, context: RunCtx, response: str = "ok"):
        """Person is hesitant."""
        await self.say_script(S5_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", chat_ctx=self.chat_ctx), "Hesitant"

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "ok"):
        """Person is not interested."""
        await self.say_script(S5_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested", chat_ctx=self.chat_ctx), "Not interested"
