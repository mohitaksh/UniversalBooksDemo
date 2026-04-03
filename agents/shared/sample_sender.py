"""
sample_sender.py — Shared agent for sending WhatsApp samples via N8N.
─────────────────
Asks "WhatsApp par bhej du?" then fires N8N webhook on confirmation.
Used by new_teacher/Step6, digital_sample flows, etc.

LEARNINGS APPLIED (see learnings.md):
  - @function_tool without parentheses
  - All tools have ≥1 parameter (for Groq schema compat)
  - Return Agent instance (not tuple)
"""

import logging
import httpx
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from config import N8N_WHATSAPP_SAMPLE_WEBHOOK_URL

logger = logging.getLogger("agents.sample_sender")


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — Edit these
# ═══════════════════════════════════════════════════════════════

S_ASK_WHATSAPP = (
    "Sir, kya mai aapko humare content ka ek digital sample WhatsApp par bhej du? "
    "Aap dekh sakte hai aur fir decide kar sakte hai."
)

S_SAMPLE_SENT = (
    "Done sir, maine aapko WhatsApp par sample share kar diya hai। "
    "Please aap usko check kare, aur agar aapko aur details chaiye "
    "toh humari team aapko help karegi."
)

S_NO_SAMPLE = (
    "No issues sir, agar future mein aapko dekhna ho toh humko bata dijiye."
)


# ═══════════════════════════════════════════════════════════════


class SampleSenderAgent(BaseUBAgent):
    """
    Asks the teacher if they want a WhatsApp sample,
    then fires N8N webhook on confirmation.
    """

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked if they want a WhatsApp sample. Listen.\n"
                "- If YES (haan, bhej do, ok, send), call send_sample.\n"
                "- If NO (nahi, abhi nahi, baad mein), call no_sample.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S_ASK_WHATSAPP)

    @function_tool
    async def send_sample(self, context: RunCtx, response: str = "yes") -> "BaseUBAgent":
        """Person wants the WhatsApp sample. Send it via N8N."""
        ud = context.userdata
        logger.info(f"SAMPLE SEND | {ud.caller_name} | {ud.phone_number}")

        if ud.tracker:
            ud.tracker.log_function("send_whatsapp_sample", {
                "phone": ud.phone_number,
                "exam_type": ud.exam_type or "general",
            })

        # Fire N8N webhook
        if N8N_WHATSAPP_SAMPLE_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(N8N_WHATSAPP_SAMPLE_WEBHOOK_URL, json={
                        "phone": ud.phone_number,
                        "name": ud.caller_name,
                        "call_type": ud.call_type.value,
                        "exam_type": ud.exam_type or "general",
                        "call_id": ud.call_id,
                    })
            except Exception as e:
                logger.warning(f"N8N WhatsApp sample webhook failed: {e}")

        await self.say_script(S_SAMPLE_SENT)

        # After sending sample, schedule a senior callback
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent()

    @function_tool
    async def no_sample(self, context: RunCtx, response: str = "no") -> "BaseUBAgent":
        """Person doesn't want the sample right now."""
        await self.say_script(S_NO_SAMPLE)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back", notes="Declined WhatsApp sample")
