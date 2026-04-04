import logging
import asyncio
import httpx
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from agents.shared.closer import CloserAgent
from agents.shared.scheduler import SchedulerAgent
from config import N8N_WHATSAPP_SAMPLE_WEBHOOK_URL

logger = logging.getLogger("agents.digital_sample")

# ═══════════════════════════════════════════════════════════════
# SCRIPT STRINGS (DEVNAGARI HYBRID)
# ═══════════════════════════════════════════════════════════════

S1_GREETING = "Hello, क्या मेरी बात {caller_name} sir से हो रही है? Sir मेरा नाम {agent_name} है, Universal Books से। How are you sir?"

S2_RECALL = (
    "Sir हमने पिछली बार बात की थी, और मैंने आपको हमारे products का digital sample "
    "WhatsApp पर share किया था।"
)
S3_FOLLOW_UP = "Sir क्या आपने files देखीं? कैसा लगा आपको हमारा content?"

S4_NOT_SEEN = (
    "No issues sir, मै आपको files दोबारा resend कर रही हूँ। "
    "Please आप उसको check करें और हमें बताएं कैसा लगा।"
)

S4_SEEN_ASK = "Okay sir, आपका क्या feedback है? आपको content कैसा लगा?"
S4_SEEN_THANK = (
    "Thank you, आप जैसे teachers के feedback के basis पर ही हम अपना material "
    "design और improve करते हैं। मैंने अपनी senior team को भी यह feedback share कर दिया है।"
)

S5_POSITIVE = (
    "Sir हमारे products की और details के लिए मैंने अपने senior को inform कर दिया है। "
    "He will call you within the next 1 hour."
)
S5_HESITANT = (
    "No issues sir, आप एक बार content check करलें, अगर आपको और chapter भी चाहिए तोह आप मुझको बता सकते हैं। "
    "हमारी team आपको visit भी करलेगी। Furthermore sir, our minimum quantity is just 10 sets "
    "so you can even get single module to see if our branded material makes an impact."
)

S_NOT_INTERESTED = "No issues sir, I understand. Please let us know if and when you change your mind. Have a great day!"
S_BUSY = "कोई बात नहीं, हम आपको कब call कर सकते है? कोई टाइम बता दीजिए?"
S_NUMBER_SOURCE = "Sir आपका number हमारी team ने digital sources से लिया था, schools और institutes के database से।"
S_AI_RESPONSE = "जी मै Universal Books की AI assistant हूँ।"


# ═══════════════════════════════════════════════════════════════
# COMMON OBJECTION AGENT
# ═══════════════════════════════════════════════════════════════

class ObjectionAgent(BaseUBAgent):
    """Handles an objection, then tries to route back to the original step."""
    def __init__(self, return_agent: BaseUBAgent, **kwargs):
        self.return_agent = return_agent
        super().__init__(
            instructions=(
                "You just answered an objection (e.g. where did you get my number / are you AI). "
                "Now smoothly transition back by calling `continue_conversation`. "
                "Do NOT speak."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        pass

    @function_tool
    async def continue_conversation(self, context: RunCtx, thought: str = "returning") -> BaseUBAgent:
        return self.return_agent


# ═══════════════════════════════════════════════════════════════
# STEP 1: GREETING & CONFIRMATION
# ═══════════════════════════════════════════════════════════════

class Step1_Greet(BaseUBAgent):
    """Step 1a: Wait for the caller to pick up natively."""
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just said 'Hello?'. Listen carefully for the person to speak.\n"
                "When the person replies (hello, haan, ji, boliye, ha, etc.), "
                "call `caller_picked_up` IMMEDIATELY.\n"
                "Do NOT generate any additional speech. ONLY call the tool."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        logger.info("digital_sample | Step1_Greet | Saying hello...")
        await self.say_script("Hello?")

    @function_tool
    async def caller_picked_up(self, context: RunCtx, response: str = "hello") -> "Step1b_ConfirmIdentity":
        return Step1b_ConfirmIdentity()


class Step1b_ConfirmIdentity(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just greeted the caller. Listen for their response.\n"
                "- If they confirm they are the right person and say 'fine' etc., call identity_confirmed.\n"
                "- If wrong person, call wrong_person.\n"
                "- If they're busy (busy, baad me, class chal rahi), call person_busy.\n"
                "- If not interested, call not_interested.\n"
                "- If they ask 'where did you get my number' or 'are you AI', call handle_objection.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S1_GREETING)

    @function_tool
    async def identity_confirmed(self, context: RunCtx, response: str = "confirmed") -> "Step2_Recall":
        return Step2_Recall()

    @function_tool
    async def wrong_person(self, context: RunCtx, response: str = "wrong") -> BaseUBAgent:
        await self.say_script("Oh sorry, शायद wrong number लग गया। Have a great day!")
        return CloserAgent(tag="Wrong Contact")

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        await self.say_script(S_NOT_INTERESTED)
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        await self.say_script(S_BUSY)
        return SchedulerAgent()

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> BaseUBAgent:
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_Recall())


# ═══════════════════════════════════════════════════════════════
# STEP 2 & 3: RECALL PAST CHAT & ASK IF SEEN
# ═══════════════════════════════════════════════════════════════

class Step2_Recall(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked if they checked the whatsapp sample.\n"
                "ROUTING RULES:\n"
                "- If NOT SEEN (nahi dekha, time nahi mila), call files_not_seen.\n"
                "- If SEEN (haan dekhi, achi hai), call files_seen.\n"
                "- If busy, call person_busy.\n"
                "- If not interested, call not_interested.\n"
                "- If objection, call handle_objection.\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(f"{S2_RECALL} {S3_FOLLOW_UP}")

    @function_tool
    async def files_not_seen(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        """They haven't seen the files. Resend and close."""
        ud = context.userdata
        if N8N_WHATSAPP_SAMPLE_WEBHOOK_URL:
            asyncio.create_task(httpx.AsyncClient().post(N8N_WHATSAPP_SAMPLE_WEBHOOK_URL, json={
                "phone": ud.phone_number,
                "name": ud.caller_name,
                "call_type": ud.call_type.value,
                "call_id": ud.call_id,
            }))
        await self.say_script(S4_NOT_SEEN)
        return CloserAgent(tag="Sample Resent")

    @function_tool
    async def files_seen(self, context: RunCtx, response: str = "yes") -> "Step4_Feedback":
        """They saw the files. Ask for feedback."""
        # If they already gave their feedback eagerly, we skip step 4 and go to 5? 
        # But let's just transition to Step4 to formalize.
        return Step4_Feedback()

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        await self.say_script(S_NOT_INTERESTED)
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        await self.say_script(S_BUSY)
        return SchedulerAgent()

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> BaseUBAgent:
        await self.say_script(S_NUMBER_SOURCE if "number" in objection.lower() or "kahan" in objection.lower() else S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_ListenRecall())


class Step2_ListenRecall(BaseUBAgent):
    """Silent listener if an objection interrupts Step 2."""
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You are waiting for them to say if they checked the files.\n"
                "- If NOT SEEN, call files_not_seen.\n"
                "- If SEEN, call files_seen.\n"
                "- If busy, call person_busy.\n"
                "- If not interested, call not_interested.\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        pass

    @function_tool
    async def files_not_seen(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        ud = context.userdata
        if N8N_WHATSAPP_SAMPLE_WEBHOOK_URL:
            asyncio.create_task(httpx.AsyncClient().post(N8N_WHATSAPP_SAMPLE_WEBHOOK_URL, json={"phone": ud.phone_number, "call_type": ud.call_type.value}))
        await self.say_script(S4_NOT_SEEN)
        return CloserAgent(tag="Sample Resent")

    @function_tool
    async def files_seen(self, context: RunCtx, response: str = "yes") -> "Step4_Feedback":
        return Step4_Feedback()

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        await self.say_script(S_NOT_INTERESTED)
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        await self.say_script(S_BUSY)
        return SchedulerAgent()


# ═══════════════════════════════════════════════════════════════
# STEP 4: SEEN -> GET FEEDBACK
# ═══════════════════════════════════════════════════════════════

class Step4_Feedback(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked for their feedback. Listen closely.\n"
                "Based on their intent:\n"
                "- If POSITIVE (acha hai, price kya hai, book chaiye, send full sample), call details_positive.\n"
                "- If HESITANT (dekhte hai, abhi decide nahi kiya), call details_hesitant.\n"
                "- If NOT INTERESTED (bekar hai, nahi chahiye), call not_interested.\n"
                "- If busy, call person_busy.\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S4_SEEN_ASK)

    @function_tool
    async def details_positive(self, context: RunCtx, review: str = "good") -> BaseUBAgent:
        """They liked it and want next steps."""
        await self.say_script(f"{S4_SEEN_THANK} {S5_POSITIVE}")
        return SchedulerAgent()

    @function_tool
    async def details_hesitant(self, context: RunCtx, review: str = "unsure") -> BaseUBAgent:
        """They are hesitant."""
        await self.say_script(f"{S4_SEEN_THANK} {S5_HESITANT}")
        return CloserAgent(tag="Follow Up Later")

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        """They are explicitly not interested."""
        await self.say_script(S_NOT_INTERESTED)
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        await self.say_script(S_BUSY)
        return SchedulerAgent()
