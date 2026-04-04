import logging
import asyncio
import httpx
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from agents.shared.closer import CloserAgent
from agents.shared.scheduler import SchedulerAgent
from config import N8N_WHATSAPP_SAMPLE_WEBHOOK_URL

logger = logging.getLogger("agents.digital_sample_2")

# ═══════════════════════════════════════════════════════════════
# SCRIPT STRINGS (DEVNAGARI HYBRID)
# ═══════════════════════════════════════════════════════════════

S1_GREETING = "Hello, क्या मेरी बात {caller_name} sir से हो रही है? How are you sir?"

S2_RECALL = (
    "Sir आपने आज का time दिया था, to share your feedback. I hope आपने हमारा content check किया। "
    "कैसा लगा आपको हमारा content?"
)

S3_NOT_SEEN = (
    "No issues sir I am resending the files to you. Please आप उसको check करें और हमें बताएं कैसा लगा। "
    "I am also sending free test papers to you for your classroom, that you can download and print."
)

S4_SEEN_FEEDBACK = (
    "Okay sir, आपका क्या feedback है? "
    "Thank you, आप जैसे teachers के feedback के basis पर ही हम अपना material design "
    "और improve करते हैं। मैंने अपनी senior team को भी यह feedback share कर दिया है। "
    "क्या आप physical book sample भी चाहते हैं?"
)

S5_YES_ADDRESS = (
    "Sure sir, आप अपना address एक बार dictate करदें मुझको। "
    "Name, house number, street or area, aur pin-code bata dijiye."
)
S5_ADDRESS_THANKS = "Thank you sir! Our senior will call you within the next 1 hour and confirm your address for the parcel."

S5_NO_ADDRESS = "No issues sir, I understand. Please let us know if and when you change your mind. Do check our free content for future. Have a great day!"

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
        logger.info("digital_sample_2 | Step1_Greet | Saying hello...")
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
                "- If they ask 'where did you get my number', call handle_objection.\n"
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
# STEP 2 & 3: RECALL & ASK IF SEEN
# ═══════════════════════════════════════════════════════════════

class Step2_Recall(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked if they checked the whatsapp sample.\n"
                "- If NOT SEEN, call files_not_seen.\n"
                "- If SEEN, call files_seen.\n"
                "- If busy, call person_busy.\n"
                "- If not interested, call not_interested.\n"
                "- If objection, call handle_objection.\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_RECALL)

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
        await self.say_script(S3_NOT_SEEN)
        return CloserAgent(tag="Sample Resent")

    @function_tool
    async def files_seen(self, context: RunCtx, response: str = "yes") -> "Step4_Feedback":
        """They saw the files. Ask if they want physical sample."""
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
        super().__init__(
            instructions=(
                "- If NOT SEEN, call files_not_seen.\n"
                "- If SEEN, call files_seen.\n"
            ),
            **kwargs,
        )
    async def on_enter(self) -> None: pass

    @function_tool
    async def files_not_seen(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        ud = context.userdata
        if N8N_WHATSAPP_SAMPLE_WEBHOOK_URL: asyncio.create_task(httpx.AsyncClient().post(N8N_WHATSAPP_SAMPLE_WEBHOOK_URL, json={"phone": ud.phone_number, "call_type": ud.call_type.value}))
        await self.say_script(S3_NOT_SEEN)
        return CloserAgent(tag="Sample Resent")

    @function_tool
    async def files_seen(self, context: RunCtx, response: str = "yes") -> "Step4_Feedback":
        return Step4_Feedback()

# ═══════════════════════════════════════════════════════════════
# STEP 4 & 5: SEEN -> GET ADDRESS OR DECLINE
# ═══════════════════════════════════════════════════════════════

class Step4_Feedback(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked if they want physical book samples.\n"
                "Listen closely.\n"
                "- If YES or POSITIVE, call wants_physical_sample.\n"
                "- If NO or NOT INTERESTED, call declines_physical_sample.\n"
                "- If busy, call person_busy.\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S4_SEEN_FEEDBACK)

    @function_tool
    async def wants_physical_sample(self, context: RunCtx, response: str = "yes") -> "Step5_CollectAddress":
        """They want the physical sample."""
        return Step5_CollectAddress()

    @function_tool
    async def declines_physical_sample(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        """They don't want physical book."""
        await self.say_script(S5_NO_ADDRESS)
        return CloserAgent(tag="No Physical Sample")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        await self.say_script(S_BUSY)
        return SchedulerAgent()

class Step5_CollectAddress(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked for their address so a senior can send a sample.\n"
                "Listen to the address dictation carefully.\n"
                "When they are done providing the address, call finish_address_dictation.\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S5_YES_ADDRESS)

    @function_tool
    async def finish_address_dictation(self, context: RunCtx, captured_address_string: str) -> BaseUBAgent:
        """The person gave their address. Save it to tracker and end."""
        ud = context.userdata
        if ud.tracker: ud.tracker.log_context("Address Dictated: " + captured_address_string)
        
        await self.say_script(S5_ADDRESS_THANKS)
        return SchedulerAgent()
