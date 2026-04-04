import logging
import asyncio
import httpx
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from agents.shared.closer import CloserAgent
from agents.shared.scheduler import SchedulerAgent
from config import N8N_WHATSAPP_SAMPLE_WEBHOOK_URL

logger = logging.getLogger("agents.physical_sample_2")

# ═══════════════════════════════════════════════════════════════
# SCRIPT STRINGS (DEVNAGARI HYBRID)
# ═══════════════════════════════════════════════════════════════

S1_GREETING = "Hello, क्या मेरी बात {caller_name} sir से हो रही है? Sir मेरा नाम {agent_name} है, Universal Books से। How are you sir?"

S2_RECALL = "Sir मै आपको call कर रही हूँ यह check करने के लिए की क्या आपको book parcel receive हुआ है?"

S3_NOT_RECEIVED = (
    "Okay sir, हमारी team के according parcel कुछ दिन पहले deliver हुआ है। Please check if someone "
    "from your office have received it. I'll inform my team and they will check आपको parcel क्यों नहीं मिला अभी तक। "
    "तब तक मैंने आपको digital samples की file WhatsApp पर share कर दी है। Please आप उसको check करें और हमें बताएं।"
)

S4_RECEIVED_ASK = "Great sir! आपको content और paper quality कैसी लगी?"

S5_POSITIVE = (
    "Thank you for your feedback sir, हमारे products की और details के लिए मैंने अपने senior को inform कर दिया है, "
    "he will call you within the next 1 hour."
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
    def __init__(self, return_agent: BaseUBAgent, **kwargs):
        self.return_agent = return_agent
        super().__init__(instructions="Wait silently for `continue_conversation`.", **kwargs)

    async def on_enter(self) -> None:
        pass

    @function_tool
    async def continue_conversation(self, context: RunCtx, thought: str = "returning") -> BaseUBAgent:
        return self.return_agent

# ═══════════════════════════════════════════════════════════════
# STEP 1: GREETING & CONFIRMATION
# ═══════════════════════════════════════════════════════════════

class Step1_Greet(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just said 'Hello?'. Listen carefully for the person to speak.\n"
                "When the person replies, call `caller_picked_up` IMMEDIATELY.\n"
                "Do NOT generate any additional speech."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        logger.info("physical_sample_2 | Step1_Greet | Saying hello...")
        await self.say_script("Hello?")

    @function_tool
    async def caller_picked_up(self, context: RunCtx, response: str = "hello") -> "Step1b_ConfirmIdentity":
        return Step1b_ConfirmIdentity()

class Step1b_ConfirmIdentity(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just greeted the caller. Listen for their response.\n"
                "- If they confirm they are the right person, call identity_confirmed.\n"
                "- If wrong person, call wrong_person.\n"
                "- If busy, call person_busy.\n"
                "- If not interested, call not_interested.\n"
                "- If objection regarding number or AI, call handle_objection.\n"
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
        await self.say_script(S_NUMBER_SOURCE if "number" in objection.lower() else S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_Recall())

# ═══════════════════════════════════════════════════════════════
# STEP 2 & 3: RECALL & CHECK IF RECEIVED
# ═══════════════════════════════════════════════════════════════

class Step2_Recall(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked if they received the physical sample box.\n"
                "- If NOT RECEIVED (nahi mila, parcel nahi aya), call parcel_not_received.\n"
                "- If RECEIVED (haan mila, office me hai), call parcel_received.\n"
                "- If busy, call person_busy.\n"
                "- If not interested, call not_interested.\n"
                "- If objection, call handle_objection.\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_RECALL)

    @function_tool
    async def parcel_not_received(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        """They haven't received the box yet. Insist tracking says delivered, send digital, and close."""
        ud = context.userdata
        if N8N_WHATSAPP_SAMPLE_WEBHOOK_URL:
            asyncio.create_task(httpx.AsyncClient().post(N8N_WHATSAPP_SAMPLE_WEBHOOK_URL, json={
                "phone": ud.phone_number,
                "name": ud.caller_name,
                "call_type": ud.call_type.value,
                "call_id": ud.call_id,
            }))
        await self.say_script(S3_NOT_RECEIVED)
        return CloserAgent(tag="Parcel Missing (Investigating)")

    @function_tool
    async def parcel_received(self, context: RunCtx, response: str = "yes") -> "Step4_Feedback":
        """They received it. Ask what they think of the paper quality."""
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
        await self.say_script(S_NUMBER_SOURCE if "number" in objection.lower() else S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_ListenRecall())

class Step2_ListenRecall(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(instructions="- If NOT RECEIVED, call parcel_not_received.\n- If RECEIVED, call parcel_received.\n", **kwargs)
    async def on_enter(self) -> None: pass
    
    @function_tool
    async def parcel_not_received(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        ud = context.userdata
        if N8N_WHATSAPP_SAMPLE_WEBHOOK_URL: asyncio.create_task(httpx.AsyncClient().post(N8N_WHATSAPP_SAMPLE_WEBHOOK_URL, json={"phone": ud.phone_number, "call_type": ud.call_type.value}))
        await self.say_script(S3_NOT_RECEIVED)
        return CloserAgent(tag="Parcel Missing")

    @function_tool
    async def parcel_received(self, context: RunCtx, response: str = "yes") -> "Step4_Feedback":
        return Step4_Feedback()

# ═══════════════════════════════════════════════════════════════
# STEP 4: FEEDBACK
# ═══════════════════════════════════════════════════════════════

class Step4_Feedback(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked for their feedback on paper quality and content. Listen carefully.\n"
                "- If POSITIVE (acha hai, price kya hai, book chaiye), call details_positive.\n"
                "- If HESITANT (dekhte hai, abhi decide nahi kiya), call details_hesitant.\n"
                "- If NOT INTERESTED (bekar hai, nahi chahiye), call not_interested.\n"
                "- If busy, call person_busy.\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S4_RECEIVED_ASK)

    @function_tool
    async def details_positive(self, context: RunCtx, review: str = "good") -> BaseUBAgent:
        await self.say_script(S5_POSITIVE)
        return SchedulerAgent()

    @function_tool
    async def details_hesitant(self, context: RunCtx, review: str = "unsure") -> BaseUBAgent:
        await self.say_script(S5_HESITANT)
        return CloserAgent(tag="Follow Up Later")

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        await self.say_script(S_NOT_INTERESTED)
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        await self.say_script(S_BUSY)
        return SchedulerAgent()
