"""
DIGITAL SAMPLE FOLLOW-UP #2 — Second follow-up after digital sample
════════════════════════════════════════════════════════════════════

Step 1: Greetings — How are you sir?
Step 2: Recall — Reference the scheduled feedback time
Step 3: If NOT SEEN → Reshare + send free test papers incentive
Step 4: If SEEN → Take feedback, offer physical sample
Step 5: If YES → Collect address / If NO → Close
Step 6: Good Wishes

EDIT YOUR SCRIPTS below.
"""

import logging
from livekit.agents import RunContext, function_tool
from agents.base_agent import BaseUBAgent
from models import CallUserData

logger = logging.getLogger("flow.digital_sample_2")


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — EDIT THESE
# ═══════════════════════════════════════════════════════════════

S1_GREETING = (
    "Hello {caller_name} sir, how are you? "
    "Mai {agent_name}, Universal Books se bol {bol_raha} hूँ।"
)

S2_RECALL = (
    "Sir aapne aaj ka time diya tha feedback share karne ke liye। "
    "I hope aapne humara content check kiya। Kaisa laga aapko humara content?"
)

S3_NOT_SEEN = (
    "No issues sir, mai files dobara send kar {kar_deta} hूँ aapko। "
    "Please aap usko check kare aur humko bataiye kaisa laga।"
)

S3_INCENTIVE = (
    "Mai aapko free test papers bhi send kar {kar_deta} hूँ "
    "aapke classroom ke liye, aap download aur print kar sakte hai sir।"
)

S4_FEEDBACK_ACK = (
    "Thank you sir, aap jaise teachers ke feedback ke basis par hi "
    "hum apna material design aur improve karte hai। "
    "Maine apni senior team ko bhi yeh feedback share kar diya hai। "
    "Kya aap physical book sample bhi chahte hai?"
)

S5_COLLECT_ADDRESS = (
    "Sure sir, aap apna address ek baar dictate kar dijiye। "
    "Name, house number, floor, street, landmark, city, state aur pincode।"
)

S5_ADDRESS_CONFIRMED = (
    "Thank you sir, our senior will call you within the next 1 hour "
    "aur aapka address aur details confirm kar lega for the sample sir।"
)

S5_NO_PHYSICAL = (
    "No issues sir, I understand। Please let us know if and when you change your mind। "
    "Do check our free content and sample for future।"
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

    @function_tool()
    async def identity_confirmed(self, context: RunContext[CallUserData]):
        """Confirmed."""
        return Step2_Recall(chat_ctx=self.chat_ctx), "Confirmed"

    @function_tool()
    async def wrong_person(self, context: RunContext[CallUserData]):
        """Wrong person."""
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Wrong Contact", chat_ctx=self.chat_ctx), "Wrong"

    @function_tool()
    async def person_busy(self, context: RunContext[CallUserData]):
        """Busy."""
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent(chat_ctx=self.chat_ctx), "Busy"


class Step2_Recall(BaseUBAgent):
    """Step 2: Recall + ask if checked."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked if they checked the content. Listen.\n"
                "- If SEEN and sharing feedback, call sample_seen.\n"
                "- If NOT SEEN, call sample_not_seen.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_RECALL)

    @function_tool()
    async def sample_seen(self, context: RunContext[CallUserData]):
        """Has seen the sample."""
        await self.say_script(S4_FEEDBACK_ACK)
        return Step4_PhysicalOffer(chat_ctx=self.chat_ctx), "Feedback received"

    @function_tool()
    async def sample_not_seen(self, context: RunContext[CallUserData]):
        """Has NOT seen."""
        await self.say_script(S3_NOT_SEEN)
        await self.say_script(S3_INCENTIVE)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", notes="Reshared + sent free test papers", chat_ctx=self.chat_ctx), "Reshared"


class Step4_PhysicalOffer(BaseUBAgent):
    """Step 4: Offer physical sample book."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked if they want a physical sample book. Listen.\n"
                "- If YES, call collect_address.\n"
                "- If NO, call no_physical.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    @function_tool()
    async def collect_address(self, context: RunContext[CallUserData]):
        """Person wants physical sample. Collect address."""
        await self.say_script(S5_COLLECT_ADDRESS)
        return Step5_AddressCollection(chat_ctx=self.chat_ctx), "Collecting address"

    @function_tool()
    async def no_physical(self, context: RunContext[CallUserData]):
        """Person doesn't want physical sample."""
        await self.say_script(S5_NO_PHYSICAL)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", chat_ctx=self.chat_ctx), "No physical"


class Step5_AddressCollection(BaseUBAgent):
    """Step 5: Collect address for physical sample."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked for the teacher's address for physical sample delivery. "
                "Listen and capture the full address. Once they finish dictating, "
                "call address_received with the full address.\n"
                "Do NOT speak."
            ),
            **kwargs,
        )

    @function_tool()
    async def address_received(
        self,
        context: RunContext[CallUserData],
        full_address: str,
    ):
        """Captured the full address for physical sample delivery."""
        ud = context.userdata
        ud.lead_notes = f"Address: {full_address}"

        if ud.tracker:
            ud.tracker.log_function("collect_address", {"address": full_address})

        await self.say_script(S5_ADDRESS_CONFIRMED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Interested", notes=f"Physical sample → {full_address}", chat_ctx=self.chat_ctx), "Address collected"
