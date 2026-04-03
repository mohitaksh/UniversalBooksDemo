"""
objection_handler.py — Shared objection handling agent.
────────────────────
Handles mid-conversation objections that can fire from ANY step:
  - "Where did you get my number?"
  - "Are you AI?" / "Yeh robot hai?"
  - "I'm busy / in class / outside"

After resolving, returns to the calling agent to continue naturally.

LEARNINGS APPLIED (see learnings.md):
  - @function_tool without parentheses
  - All tools have ≥1 parameter (for Groq schema compat)
  - Return Agent instance (not tuple)
"""

import logging
import httpx
from livekit.agents import function_tool, Agent
from agents.base_agent import BaseUBAgent, RunCtx
from config import N8N_DNC_WEBHOOK_URL

logger = logging.getLogger("agents.objection")


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — Edit these
# ═══════════════════════════════════════════════════════════════

S_NUMBER_SOURCE = (
    "Sir, hum Universal Books hai, India ke top educational publishers. "
    "Aapka number humari research team ne coaching directories se liya hai. "
    "Agar aap nahi chahte ki hum call karein, toh hum aapko list se remove kar denge. "
    "Lekin pehle mai aapko bata du ki hum kya offer karte hai, "
    "agar aapko interest nahi hai toh hum dobara call nahi karenge."
)

S_AI_RESPONSE = (
    "Ji sir, mai AI-assisted hun, lekin mai actually aapko help karne ke liye "
    "call kar {bol_raha} hun. Humari team ne mujhe aapke liye train kiya hai. "
    "Kya mai continue kar {le_sakta} hun?"
)

S_DNC_CONFIRMED = (
    "Sure sir, maine aapka number remove kar diya hai. "
    "Aapko aage se koi call nahi aayega. Sorry for the inconvenience."
)

S_CONTINUE = (
    "Thank you sir, toh mai continue karti hun."
)


# ═══════════════════════════════════════════════════════════════


class ObjectionAgent(BaseUBAgent):
    """
    Handles mid-call objections. After resolving, returns to the
    calling agent so the conversation continues naturally.

    Args:
        return_agent: The Agent instance to return to after resolving.
    """

    def __init__(self, return_agent: Agent = None, **kwargs):
        self._return_agent = return_agent
        super().__init__(
            instructions=(
                "The caller raised an objection during the call. "
                "You just addressed their concern. Listen for their response.\n"
                "- If they say OK, fine, continue, tell me — call resume_call.\n"
                "- If they insist on removal / do not call / angry — call remove_from_list.\n"
                "- If they say they're busy — call person_busy.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        # We don't auto-speak here — the calling agent already said
        # the objection script before transferring. The objection agent
        # picks up from the TTS that was played by the caller agent.
        pass

    @function_tool
    async def resume_call(self, context: RunCtx, response: str = "ok") -> "Agent":
        """Person is OK to continue. Resume the previous conversation."""
        logger.info(f"OBJECTION RESOLVED | Resuming call")
        if self._return_agent:
            return self._return_agent
        # Fallback: if no return agent, close gracefully
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back")

    @function_tool
    async def remove_from_list(self, context: RunCtx, response: str = "remove") -> "BaseUBAgent":
        """Person wants to be removed from call list (Do Not Call)."""
        ud = context.userdata
        logger.info(f"DNC REQUEST | {ud.caller_name} | {ud.phone_number}")

        # Fire N8N DNC webhook
        if N8N_DNC_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(N8N_DNC_WEBHOOK_URL, json={
                        "phone": ud.phone_number,
                        "name": ud.caller_name,
                        "action": "remove_from_list",
                        "call_id": ud.call_id,
                    })
            except Exception as e:
                logger.warning(f"N8N DNC webhook failed: {e}")

        await self.say_script(S_DNC_CONFIRMED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="DNC")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> "BaseUBAgent":
        """Person is busy right now."""
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent()
