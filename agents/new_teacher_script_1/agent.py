import logging
import asyncio
import httpx
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from agents.shared.closer import CloserAgent
from agents.shared.scheduler import SchedulerAgent
from config import N8N_WHATSAPP_SAMPLE_WEBHOOK_URL

logger = logging.getLogger("agents.new_teacher_script_1")

# ═══════════════════════════════════════════════════════════════
# SCRIPTS (SCRIPT 1)
# ═══════════════════════════════════════════════════════════════

S1_GREETING = "Hello, क्या मेरी बात {caller_name} sir से हो रही है? Sir मेरा नाम {agent_name} है,"

S2_INTRO = (
    "मै Universal Books से बोल रही हूँ। हम एक sixty year old brand हैं, जो CBSE, NEET और J double-E exams के लिए books publish और customize करते हैं। "
    "हमारी Errorless book series India की सबसे famous NEET और JEE books में से एक है।"
)

S3_ASK_CLASSES = "Sir, currently आप कौन सी classes या exams के लिए students को prepare कराते हैं?"

S4_WHATSAPP_USP = (
    "Sir, मै आपके साथ हमारी सारी digital sample files share कर रही हूँ। आप आराम से content और questions की quality review कर लीजिये। "
    "क्योंकि हमारी books बाकी publishers से काफी अलग हैं .. और अगर आपको बल्क मे need हो तोह इसपे आपकी branding भी लग जाएगी"
)

S_WRONG_PERSON = "Oh sorry, शायद wrong number लग गया। Have a great day!"
S_BUSY = "कोई बात नहीं, हम आपको कब call कर सकते है? कोई टाइम बता दीजिए?"
S_NOT_INTERESTED = "ठीक है सर, कोई बात नहीं। आपका समय देने के लिए धन्यवाद। Have a great day!"

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
        """Call this to continue the original script."""
        return self.return_agent


# ═══════════════════════════════════════════════════════════════
# STEP 1a: WAIT FOR CALLER PICKUP
# ═══════════════════════════════════════════════════════════════

class Step1_Greet(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just said 'Hello?'. Listen carefully for the person to speak."
                "When the person replies (hello, haan, ji, boliye, ha, etc.), "
                "call `caller_picked_up` IMMEDIATELY."
                "Do NOT generate any speech. ONLY call the tool."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script("Hello?")

    @function_tool
    async def caller_picked_up(self, context: RunCtx, response: str = "hello") -> "Step1b_ConfirmIdentity":
        return Step1b_ConfirmIdentity()


# ═══════════════════════════════════════════════════════════════
# STEP 1b: GREET & CONFIRM IDENTITY
# ═══════════════════════════════════════════════════════════════

class Step1b_ConfirmIdentity(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just greeted the caller. Listen for their response.\n"
                "- If they confirm they are the right person (haan, boliye, ji, ha), "
                "call identity_confirmed.\n"
                "- If wrong person (nahi, galat number, wrong number), call wrong_person.\n"
                "- If they're busy (busy, baad me, class chal rahi, abhi nahi), call person_busy.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S1_GREETING)

    @function_tool
    async def identity_confirmed(self, context: RunCtx, response: str = "confirmed") -> "Step2_Intro":
        """Person confirmed they are the right contact."""
        return Step2_ListenClasses()

    @function_tool
    async def wrong_person(self, context: RunCtx, response: str = "wrong") -> BaseUBAgent:
        """Wrong person on the line."""
        await self.say_script(S_WRONG_PERSON)
        return CloserAgent(tag="Wrong Contact")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        """Person is busy right now."""
        await self.say_script(S_BUSY)
        return SchedulerAgent()

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> BaseUBAgent:
        """Person raised an objection."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_ListenClasses())


# ═══════════════════════════════════════════════════════════════
# STEP 2: COMPANY INTRO + ASK CLASSES
# ═══════════════════════════════════════════════════════════════

class Step2_Intro(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just gave an intro and asked the teacher what classes and exams they teach. "
                "Listen carefully for their answer.\n\n"
                "ROUTING RULES (follow strictly):\n"
                "1. If they mention SPECIFIC classes/exams (e.g. 'NEET', '9th to 12th', "
                "'JEE and Boards', 'medical', 'engineering', '10th', 'boards', 'school'), "
                "call classes_shared with exactly what they said.\n"
                "2. If their answer is VAGUE or UNCLEAR (e.g. 'bahut padhai hoti hai', "
                "general statements without specific specifics), call unclear_response.\n"
                "3. If they say they are busy (busy, baad me, class chal rahi), call person_busy.\n"
                "4. If they say they are NOT interested (nahi chahiye, interest nahi), call not_interested.\n"
                "5. If they ask 'where did you get my number' or 'are you AI', call handle_objection.\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(f"{S2_INTRO} {S3_ASK_CLASSES}")

    @function_tool
    async def classes_shared(self, context: RunCtx, classes_and_exams: str) -> "Step3_ShareSample":
        """Teacher shared their classes/exams."""
        ud = context.userdata
        cleaned = classes_and_exams.strip().lower()
        false_positives = {"ji", "jee", "haan", "ha", "ok", "theek hai", "boliye"}
        if cleaned in false_positives or len(cleaned) <= 3:
            logger.warning("STT guard triggered")
            await self.say_script("जी सर, मतलब आपके यहाँ कौन सी classes चलती हैं? जैसे NEET, JEE, या Class 9 10?")
            return Step2_ListenClasses()

        ud.exam_type = classes_and_exams
        if ud.tracker: ud.tracker.log_function("set_exam_type", {"exam": classes_and_exams})
        return Step3_ShareSample()

    @function_tool
    async def unclear_response(self, context: RunCtx, what_they_said: str = "unclear") -> "Step2_Intro":
        """The teacher gave a vague/unclear answer."""
        await self.say_script(
            "जी सर, मतलब specifically कौन सी classes चलती हैं आपके यहाँ? "
            "जैसे Class 9, 10, 11, 12 .. या NEET, JEE जैसे exams?"
        )
        return Step2_ListenClasses()

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        """Person EXPLICITLY said they are busy right now."""
        await self.say_script(S_BUSY)
        return SchedulerAgent()

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        """Person is not interested."""
        await self.say_script(S_NOT_INTERESTED)
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> BaseUBAgent:
        """Person raised an objection."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_ListenClasses())


# ═══════════════════════════════════════════════════════════════
# STEP 3: SHARE SAMPLE & USP
# ═══════════════════════════════════════════════════════════════


class Step2_ListenClasses(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                 "You are waiting for the teacher to answer what classes they teach.\n"
                 "ROUTING RULES (follow strictly):\n"
                 "1. If they mention SPECIFIC classes/exams (e.g. 'NEET', '9th to 12th', 'JEE'), call classes_shared.\n"
                 "2. If their answer is VAGUE or UNCLEAR, call unclear_response.\n"
                 "3. If they say they are busy, call person_busy.\n"
                 "4. If they say they are NOT interested (nahi chahiye, interest nahi, no), call not_interested.\n"
                 "5. If they ask 'where did you get my number', call handle_objection.\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        pass  # NO SPEECH

    @function_tool
    async def classes_shared(self, context: RunCtx, classes_and_exams: str) -> "Step3_ShareSample":
        ud = context.userdata
        if classes_and_exams.strip().lower() in {"ji", "jee", "haan", "ha", "ok", "theek hai"} or len(classes_and_exams.strip()) <= 3:
            await self.say_script("जी सर, मतलब आपके यहाँ कौन सी classes चलती हैं?")
            return Step2_ListenClasses()
        ud.exam_type = classes_and_exams
        if ud.tracker: ud.tracker.log_function("set_exam_type", {"exam": classes_and_exams})
        return Step3_ShareSample()

    @function_tool
    async def unclear_response(self, context: RunCtx, what_they_said: str = "unclear") -> "Step2_ListenClasses":
        await self.say_script("जी सर, मतलब specifically कौन सी classes चलती हैं आपके यहाँ?")
        return Step2_ListenClasses()

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
        return ObjectionAgent(return_agent=Step2_ListenClasses())

class Step3_ShareSample(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just told them you are sending WhatsApp samples and gave the product USP. "
                "The conversation is now essentially over, as the goal was just to send the sample. "
                "If they say ok, haan bhej do, ok bye -> call end_call_success. "
                "If they ask questions -> since this is a simple script, call end_call_success anyway but politely close."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S4_WHATSAPP_USP)
        # Fire the webhook blindly as required by script
        # ud is inside Context, but we don't have access in on_enter without hack.
        # Wait, the best place to fire it is in the tool, or here.
        # It's better to fire it in a tool. Let's make an automated tool that the LLM hits?
        # No, let's just make the user say "Okay" and then we close.
        
    @function_tool
    async def end_call_success(self, context: RunCtx, response: str = "ok") -> BaseUBAgent:
        """Call this to end the conversation and send the sample."""
        ud = context.userdata
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

        await self.say_script("ठीक है सर, मै भिजवा देती हूँ। Thank you for your time, have a great day!")
        return CloserAgent(tag="Sample Mailed")
