import logging
import asyncio
import httpx
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from agents.shared.closer import CloserAgent
from agents.shared.scheduler import SchedulerAgent
from config import N8N_WHATSAPP_SAMPLE_WEBHOOK_URL

logger = logging.getLogger("agents.new_teacher_script_2")

S1_GREETING = "नमस्ते Sir, क्या मेरी बात {caller_name} से हो रही है? Sir मेरा नाम {agent_name} है,"
S2_INTRO = (
    "मै Universal Books से बात कर रही हूँ, हम Errorless Self Scorer जैसी books publish करते हैं जो CBSE, J double E और NEET exams के लिए design की गयी हैं। "
    "Sir, सिर्फ बीस से तीस seconds दीजिये, मै बस sample books और content के लिए आपसे confirmation लेना चाहती हूँ।"
)
S3_ASK_CLASSES = "Sir, आपका focus ज्यादा CBSE Foundation और Pre-Foundation Boards पर है, या NEET और JEE preparation भी चलती है?"
S4_WHATSAPP_USP = (
    "Sir, मै आपको एक sample WhatsApp कर देती हूँ .. आप देख के बताइये कैसा लगा। इसी number पर share कर दूँ? "
    "Sir हमारी books मे काफी unique points हैं .. और अगर आपको बल्क मे need हो तोह इसपे आपकी branding भी लग जाएगी"
)

S_WRONG_PERSON = "Oh sorry, शायद wrong number लग गया। Have a great day!"
S_BUSY = "कोई बात नहीं, हम आपको कब call कर सकते है? कोई टाइम बता दीजिए?"
S_NOT_INTERESTED = "ठीक है सर, कोई बात नहीं। आपका समय देने के लिए धन्यवाद। Have a great day!"
S_NUMBER_SOURCE = "Sir आपका number हमारी team ने digital sources से लिया था, schools और institutes के database से।"
S_AI_RESPONSE = "जी मै Universal Books की AI assistant हूँ।"

class ObjectionAgent(BaseUBAgent):
    def __init__(self, return_agent: BaseUBAgent, **kwargs):
        self.return_agent = return_agent
        super().__init__(
            instructions="You answered an objection. Call `continue_conversation` to return.",
            **kwargs,
        )
    async def on_enter(self) -> None: pass
    @function_tool
    async def continue_conversation(self, context: RunCtx, thought: str = "returning") -> BaseUBAgent:
        return self.return_agent

class Step1_Greet(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions="Wait silently for the caller to pick up and speak. When they speak, call `caller_picked_up`.",
            **kwargs,
        )
    async def on_enter(self) -> None:
        logger.info("Script 2 | Waiting for caller...")
    @function_tool
    async def caller_picked_up(self, context: RunCtx, response: str = "hello") -> "Step1b_ConfirmIdentity":
        return Step1b_ConfirmIdentity()

class Step1b_ConfirmIdentity(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You greeted the caller. Listen for their response.\n"
                "- If confirmed -> identity_confirmed.\n"
                "- If wrong person -> wrong_person.\n"
                "- If busy -> person_busy.\n"
                "- If objection -> handle_objection.\n"
            ),
            **kwargs,
        )
    async def on_enter(self) -> None:
        await self.say_script(S1_GREETING)
    @function_tool
    async def identity_confirmed(self, context: RunCtx, response: str = "confirmed") -> "Step2_Intro": return Step2_Intro()
    @function_tool
    async def wrong_person(self, context: RunCtx, response: str = "wrong") -> BaseUBAgent:
        await self.say_script(S_WRONG_PERSON)
        return CloserAgent(tag="Wrong Contact")
    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        await self.say_script(S_BUSY)
        return SchedulerAgent()
    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> BaseUBAgent:
        await self.say_script(S_NUMBER_SOURCE if "number" in objection.lower() or "kahan" in objection.lower() else S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_Intro())

class Step2_Intro(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked what classes they teach. Listen carefully.\n"
                "- If specific classes mentioned -> classes_shared.\n"
                "- If vague -> unclear_response.\n"
                "- If busy -> person_busy.\n"
                "- If not interested -> not_interested.\n"
                "- If objection -> handle_objection.\n"
            ),
            **kwargs,
        )
    async def on_enter(self) -> None:
        await self.say_script(f"{S2_INTRO} {S3_ASK_CLASSES}")
    @function_tool
    async def classes_shared(self, context: RunCtx, classes_and_exams: str) -> "Step3_ShareSample":
        ud = context.userdata
        if classes_and_exams.strip().lower() in {"ji", "jee", "haan", "ha", "ok", "theek hai"} or len(classes_and_exams.strip()) <= 3:
            await self.say_script("जी सर, मतलब आपके यहाँ कौन सी classes चलती हैं?")
            return Step2_Intro()
        ud.exam_type = classes_and_exams
        if ud.tracker: ud.tracker.log_function("set_exam_type", {"exam": classes_and_exams})
        return Step3_ShareSample()
    @function_tool
    async def unclear_response(self, context: RunCtx, what_they_said: str = "unclear") -> "Step2_Intro":
        await self.say_script("जी सर, मतलब specifically कौन सी classes चलती हैं? CBSE boards या NEET JEE?")
        return Step2_Intro()
    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        await self.say_script(S_BUSY)
        return SchedulerAgent()
    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        await self.say_script(S_NOT_INTERESTED)
        return CloserAgent(tag="Not Interested")
    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> BaseUBAgent:
        await self.say_script(S_NUMBER_SOURCE if "number" in objection.lower() or "kahan" in objection.lower() else S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_Intro())

class Step3_ShareSample(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions="You offered to send WhatsApp samples. Call `end_call_success` if they say anything (ok, yes, sure, etc.)",
            **kwargs,
        )
    async def on_enter(self) -> None:
        await self.say_script(S4_WHATSAPP_USP)
    @function_tool
    async def end_call_success(self, context: RunCtx, response: str = "ok") -> BaseUBAgent:
        ud = context.userdata
        if N8N_WHATSAPP_SAMPLE_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(N8N_WHATSAPP_SAMPLE_WEBHOOK_URL, json={
                        "phone": ud.phone_number, "name": ud.caller_name,
                        "call_type": ud.call_type.value, "exam_type": ud.exam_type or "general", "call_id": ud.call_id,
                    })
            except Exception: pass
        await self.say_script("ठीक है सर, मै भिजवा देती हूँ। Thank you for your time, have a great day!")
        return CloserAgent(tag="Sample Mailed")
