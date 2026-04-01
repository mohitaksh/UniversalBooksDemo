import os
import requests
import logging
from livekit.agents import RunContext, function_tool, Agent, llm
try:
    from models import VoiceProfile, get_random_voice
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from models import VoiceProfile, get_random_voice

logger = logging.getLogger("agents.base")

class BaseSalesAgent(Agent):
    """
    Base Agent that provides universal tools:
    - schedule_callback (with N8N webhook trigger)
    - tag_lead
    """
    def __init__(self, instructions: str, chat_ctx: llm.ChatContext = None):
        super().__init__(
            instructions=instructions,
            chat_ctx=chat_ctx
        )

    @function_tool(description="Call this to schedule a callback with the team when they request it.")
    async def schedule_callback(self, context: RunContext, time_slot: str):
        """Use this to schedule a callback at a specific time provided by the user."""
        logger.info(f"Scheduling callback for: {time_slot}")
        
        # We can dynamically inject say() here to bypass LLM and immediately respond
        await self.session.say("ठीक है, मैंने आपकी call book कर दी है। हमारी team आपको दिए हुए time पर call करेगी। time देने के लिए बहुत बहुत शुक्रिया। आपका दिन अच्छा रहे, नमस्ते!", allow_interruptions=False)
        
        # Trigger N8N Webhook if configured
        webhook_url = os.getenv("N8N_RESCHEDULE_WEBHOOK")
        if webhook_url:
            try:
                # We can access metadata via context.userdata if we set it, or rely on caller_name/phone global state
                # For now, just send a basic payload 
                requests.post(webhook_url, json={"time_slot": time_slot}, timeout=5)
            except Exception as e:
                logger.error(f"Failed to trigger N8N webhook: {e}")
                
        # Signal to end call by dropping the session (or we use EndCallTool natively)
        # We can also manually trigger close here
        import asyncio
        asyncio.create_task(self._close_soon())
        return "Callback scheduled successfully. Ended call."

    @function_tool(description="Tags the lead. Categories: Interested, Call Back, Not Interested, Wrong Contact")
    async def tag_lead(self, context: RunContext, tag: str, notes: str = ""):
        """Call this to tag the lead at the end of the call."""
        logger.info(f"Lead Tagged: {tag} | Notes: {notes}")
        # Normally you would send this to DB or CRM
        
        # Wait a moment then close
        if "Interested" not in tag and "Call Back" not in tag:
            # Drop call if not interested and we haven't already said bye
            import asyncio
            asyncio.create_task(self._close_soon())
            
        return "Lead tagged."

    async def _close_soon(self):
        import asyncio
        await asyncio.sleep(2.0) # Wait for say() to finish streaming
        await self.session.aclose()
        if self.session.room:
            await self.session.room.disconnect()
