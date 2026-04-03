"""
NEW TEACHER — Cold Call Flow (Coaching / Tuition)
═════════════════════════════════════════════════

8-step flow for calling a new teacher who has never been contacted.

Step 1: Greetings — Get & Confirm Name
Step 2: Intro of Company — 10 second intro
Step 3: Ask for Classes — What classes/exams they teach
Step 4: Share Relevant Product — AI-generated from KB data
Step 5: Share Relevant USP — AI-generated from KB data
Step 6: Ask & Share Sample — Offer digital sample + physical book
Step 7: Set up call with Senior — Create task via N8N
Step 8: Good Wishes — Close

EDIT YOUR SCRIPTS: Modify the constants below each ═══ header.
Template variables: {agent_name}, {caller_name}, {bol_raha}, {le_sakta},
                    {chahta}, {samajh_gaya}, {kar_deta}, {mera}

LEARNINGS APPLIED (see learnings.md):
  - @function_tool without parentheses
  - All tools have ≥1 parameter (for Groq schema compat)
  - Return Agent instance (not tuple) from function_tool
  - asyncio.sleep(5.0) in first agent for SIP audio delay
"""

import asyncio
import logging
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from models import CallUserData
from knowledgebase import kb_to_prompt
from agents.shared.objection_handler import ObjectionAgent, S_NUMBER_SOURCE, S_AI_RESPONSE

logger = logging.getLogger("flow.new_teacher")


# ═══════════════════════════════════════════════════════════════
# STEP 1 — GREETING SCRIPTS
# ═══════════════════════════════════════════════════════════════

S1_GREETING = (
    "Hello, क्या मेरी बात {caller_name} से हो रही है जो tuition पढ़ाते हैं?"
)

S1_WRONG_PERSON = (
    "Sorry sir, Aapko disturb karne ke liye maafi {chahta} हूँ।"
)

# ═══════════════════════════════════════════════════════════════
# STEP 2 — COMPANY INTRO SCRIPTS
# ═══════════════════════════════════════════════════════════════

S2_INTRO = (
    "जी {mera} naam {agent_name} hai, mai Universal Books se bol {bol_raha} हूँ। हम एक साठ साल पुरानी publishing company हैं। "
    "हमारी  Errorless book आती है नीट और जे-ई-ई के लिए आपने सुना होगा, अब हम कोचिंगस के लिए study material भी बनाते है जिसपे आपकी खुद की branding लगती है और उस branding को लगाने का कोई एक्स्ट्रा चार्ज भी नहीं लगता। क्या मै आपका एक मिनट {le_sakta} हूँ?"
)

# ═══════════════════════════════════════════════════════════════
# STEP 3 — ASK CLASSES SCRIPTS
# ═══════════════════════════════════════════════════════════════

S3_ASK_CLASSES = (
    "जी, मै जानना {chahta} हूँ कि आपके यहा कौन सी classes और exams की पढ़ाई कराई जाती है?"
)

# ═══════════════════════════════════════════════════════════════
# STEP 4/5 — PRODUCT INFO (AI-GENERATED FROM KB)
# These are prompt instructions, not scripts.
# The AI will generate natural speech using KB data.
# ═══════════════════════════════════════════════════════════════

S45_AI_INSTRUCTION = (
    "Based on the product data below, share 2-3 key highlights NATURALLY "
    "in Hinglish. Be specific — mention subject names, number of questions, "
    "unique features. "
    "After sharing, call offer_sample."
)

# ═══════════════════════════════════════════════════════════════
# STEP 6 — SAMPLE OFFER SCRIPTS
# ═══════════════════════════════════════════════════════════════

S6_OFFER_SAMPLE = (
    "Okay तोह मैंने आपको WhatsApp पर sample share कर दिया है, और अगर आपको physical book भी देखनी है, तो वोह भी हम अरैन्ज कर देंगे।"
    "आप आराम से sample देख लीजिए, मुझे यकीन है आपको कुछ Market से अलग ही लगेगा। हम आपको बाद मे call कर के और भी details share कर देंगे"
)

# ═══════════════════════════════════════════════════════════════
# STEP — NOT INTERESTED / HESITANT SCRIPTS
# ═══════════════════════════════════════════════════════════════

S_HESITANT = (
    "कोई issue nahi sir, aap ek baar content check kar le, agar aapko aur chapters bhi "
    "chaiye toh aap mujko bata sakte hai। Humari team aapko visit bhi kar legi। "
    "Furthermore sir, our minimum quantity is just 10 sets so you can even "
    "get a single module to see if our branded material makes an impact।"
)

S_NOT_INTERESTED = (
    "No issues sir, I understand। Please let us know if and when you change your mind"
)

S_BUSY = (
    "Koi baat nahi sir, aapko kab time milega?"
)


# ═══════════════════════════════════════════════════════════════
# EXAM → KB MODULE MAPPING
# Maps what the teacher says → which knowledgebase to load
# Add new mappings here as you add KB files.
# ═══════════════════════════════════════════════════════════════

EXAM_TO_KB = {
    "neet":         ["neet_jee", "neet_pyq", "dpp_neet"],
    "jee":          ["neet_jee", "jee_pyq", "dpp_jee"],
    "j double e":   ["neet_jee", "jee_pyq", "dpp_jee"],
    "medical":      ["neet_jee", "neet_pyq"],
    "engineering":  ["neet_jee", "jee_pyq"],
    "jee advanced": ["jee_advanced", "jee_pyq"],
    "boards":       ["class_11", "class_12", "cbse_12_pyq", "worksheets"],
    "cbse":         ["class_11", "class_12", "cbse_12_pyq", "worksheets"],
    "12":           ["class_12", "cbse_12_pyq", "worksheets"],
    "11":           ["class_11", "worksheets"],
    "10":           ["class_10", "cbse_10_pyq", "worksheets"],
    "9":            ["class_9", "worksheets"],
    "8":            ["class_8", "worksheets"],
    "7":            ["class_7", "worksheets"],
    "6":            ["class_6", "worksheets"],
    "kcet":         ["kcet"],
    "mhtcet":       ["mhtcet"],
    "eapcet":       ["eapcet"],
    "cuet":         ["cuet"],
    "foundation":   ["class_9", "class_10", "worksheets", "cbse_10_pyq"],
}


def resolve_kb_modules(classes_text: str) -> list[str]:
    """Map teacher's answer to relevant KB module names."""
    text = classes_text.strip().lower()
    matched = set()
    for key, modules in EXAM_TO_KB.items():
        if key in text:
            matched.update(modules)
    if not matched:
        matched.add("neet_jee")  # default
    return list(matched)


# ═══════════════════════════════════════════════════════════════
# STEP 1: GREETINGS
# ═══════════════════════════════════════════════════════════════

class Step1_Greet(BaseUBAgent):
    """Step 1: Greeting — confirm caller identity."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You are calling a teacher. You just said a greeting. "
                "Listen for their response.\n"
                "- If they confirm they are the right person (haan, boliye, ji), "
                "call identity_confirmed.\n"
                "- If wrong person, call wrong_person.\n"
                "- If they're busy, call person_busy.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        # SIP audio establishment delay — 5 seconds (from working code)
        await asyncio.sleep(5.0)
        await self.say_script(S1_GREETING)

    @function_tool
    async def identity_confirmed(self, context: RunCtx, response: str = "confirmed") -> "Step2_Intro":
        """Person confirmed they are the right contact. response is what they said."""
        logger.info(f"Step1 → Step2 | {response}")
        return Step2_Intro()

    @function_tool
    async def wrong_person(self, context: RunCtx, response: str = "wrong") -> "BaseUBAgent":
        """Wrong person on the line."""
        await self.say_script(S1_WRONG_PERSON)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Wrong Contact")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> "BaseUBAgent":
        """Person is busy right now."""
        await self.say_script(S_BUSY)
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent()

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Person raised an objection (where got number, are you AI, busy/in class)."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_Intro())


# ═══════════════════════════════════════════════════════════════
# STEP 2: COMPANY INTRO
# ═══════════════════════════════════════════════════════════════

class Step2_Intro(BaseUBAgent):
    """Step 2: Company intro — 10 second pitch."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just introduced the company. Listen for the person's response.\n"
                "- If they give permission to continue (haan, boliye, bataiye), "
                "call permission_granted.\n"
                "- If they say not interested or don't call, call not_interested.\n"
                "- If busy, call person_busy.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_INTRO)

    @function_tool
    async def permission_granted(self, context: RunCtx, response: str = "yes") -> "Step3_AskClasses":
        """Person gave permission to continue."""
        return Step3_AskClasses()

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "no") -> "BaseUBAgent":
        """Person is not interested."""
        await self.say_script(S_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> "BaseUBAgent":
        """Person is busy right now."""
        await self.say_script(S_BUSY)
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent()

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Person raised an objection."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step3_AskClasses())


# ═══════════════════════════════════════════════════════════════
# STEP 3: ASK ABOUT CLASSES / EXAMS
# ═══════════════════════════════════════════════════════════════

class Step3_AskClasses(BaseUBAgent):
    """Step 3: Ask what classes/exams they teach."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked the teacher what classes and exams they teach. "
                "Listen for their answer. When they tell you "
                "(e.g. 'NEET', '9th to 12th', 'JEE and Boards'), "
                "call classes_shared with the info.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S3_ASK_CLASSES)

    @function_tool
    async def classes_shared(
        self,
        context: RunCtx,
        classes_and_exams: str,
    ) -> "Step4_ShareProduct":
        """Teacher shared their classes/exams (e.g. 'NEET and JEE', 'Class 9-12', 'Boards')."""
        ud = context.userdata
        ud.exam_type = classes_and_exams

        if ud.tracker:
            ud.tracker.log_function("set_exam_type", {"exam": classes_and_exams})

        kb_modules = resolve_kb_modules(classes_and_exams)
        return Step4_ShareProduct(kb_modules=kb_modules)

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Person raised an objection."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step3_AskClasses())


# ═══════════════════════════════════════════════════════════════
# STEP 4 + 5: SHARE PRODUCT & USP (AI-GENERATED FROM KB)
# ═══════════════════════════════════════════════════════════════

class Step4_ShareProduct(BaseUBAgent):
    """Step 4-5: Share relevant product info using KB data (AI-generated)."""

    def __init__(self, kb_modules: list[str] = None, **kwargs):
        self._kb_modules = kb_modules or ["neet_jee"]

        # Build KB context from all matched modules
        kb_context = "\n\n".join(
            kb_to_prompt(m) for m in self._kb_modules
            if kb_to_prompt(m)
        )

        super().__init__(
            instructions=(
                "You are sharing study material info with a teacher. "
                "Use the product details below to describe what Universal Books "
                "offers for their classes NATURALLY in Hinglish. "
                "Be specific — mention subject names, number of questions, unique features. "
                "IMPORTANT: If worksheet data is present, only mention worksheets for the "
                "classes the teacher actually teaches, NOT all available classes. "
                "Keep it conversational, 3-4 sentences max.\n"
                "After the person responds: if they want to see samples or know more, call offer_sample."
                "or if they raise concerns, call handle_hesitation. "
                "If not interested at all, call not_interested.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n\n"
                f"PRODUCT DATA:\n{kb_context}"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        # Let the AI generate a natural product summary from KB data
        self.session.generate_reply()

    @function_tool
    async def offer_sample(self, context: RunCtx, interest: str = "yes") -> "Step6_OfferSample":
        """Person wants to see samples or learn more. Offer sample link."""
        return Step6_OfferSample()

    @function_tool
    async def handle_hesitation(self, context: RunCtx, concern: str = "unsure") -> "BaseUBAgent":
        """Person is hesitant (dekhte hai, batata hu, abhi decide nahi kiya)."""
        await self.say_script(S_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back")

    @function_tool
    async def not_interested(self, context: RunCtx, reason: str = "not interested") -> "BaseUBAgent":
        """Person is not interested."""
        await self.say_script(S_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Person raised an objection."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step4_ShareProduct(kb_modules=self._kb_modules))


# ═══════════════════════════════════════════════════════════════
# STEP 6: OFFER SAMPLE
# ═══════════════════════════════════════════════════════════════

class Step6_OfferSample(BaseUBAgent):
    """Step 6: Offer digital sample + physical book, ask to setup call."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You offered sample material. Listen for their response.\n"
                "- If yes or interested in seeing samples, call send_whatsapp_sample.\n"
                "- If they want a senior call directly, call setup_senior_call.\n"
                "- If hesitant, call handle_hesitation.\n"
                "- If not interested, call not_interested.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S6_OFFER_SAMPLE)

    @function_tool
    async def setup_senior_call(self, context: RunCtx, response: str = "yes") -> "BaseUBAgent":
        """Person wants a senior call. Set it up."""
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent()

    @function_tool
    async def handle_hesitation(self, context: RunCtx, concern: str = "unsure") -> "BaseUBAgent":
        """Person is unsure."""
        await self.say_script(S_HESITANT)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Call Back")

    @function_tool
    async def not_interested(self, context: RunCtx, reason: str = "not interested") -> "BaseUBAgent":
        """Person is not interested."""
        await self.say_script(S_NOT_INTERESTED)
        from agents.shared.closer import CloserAgent
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def send_whatsapp_sample(self, context: RunCtx, response: str = "yes") -> "BaseUBAgent":
        """Person wants to see samples on WhatsApp."""
        from agents.shared.sample_sender import SampleSenderAgent
        return SampleSenderAgent()

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> "BaseUBAgent":
        """Person raised an objection."""
        if "number" in objection.lower() or "kahan" in objection.lower():
            await self.say_script(S_NUMBER_SOURCE)
        else:
            await self.say_script(S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step6_OfferSample())
