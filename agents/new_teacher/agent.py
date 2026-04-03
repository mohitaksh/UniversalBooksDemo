"""
NEW TEACHER — Cold Call Flow (Coaching / Tuition)
═════════════════════════════════════════════════

Flow:
  Step 1: Greetings — Confirm identity (teacher vs institution greeting)
  Step 2: Intro — "Do you know Errorless books?" (authority check)
    → YES: Ask permission (S2_ASK_PERMISSION)
    → NO:  Build authority + ask permission (S2_INTRO_MORE_THEN_ASK_PERMISSION)
  Step 2b: Permission — Wait for "haan boliye" / "no"
  Step 3: Ask Classes — What classes/exams they teach
  Step 4: Share Product — AI-generated from KB data (with language rules)
  Step 6: Offer Sample — Digital + physical sample offer

  OBJECTION / BUSY / NOT INTERESTED can fire at ANY stage.

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
# LANGUAGE RULES — injected into ALL agents that generate free text
# ═══════════════════════════════════════════════════════════════

LANGUAGE_RULES = """
LANGUAGE RULES (follow strictly):
- Respond ONLY in Devanagari Hinglish — Hindi in Devanagari script mixed with English words kept in English.
- Example: "जी, मैं Universal Books की तरफ़ से बोल रही हूँ। हम 60 सालो से, मतलब की Nineteen Sixty के दशक से teachers और coaching centers के लिए up-to-date exam preparation ki books aur material बनाते हैं."
- Always use "आप" (respectful). NEVER "तू" or "तुम".
- Speak numbers in English: 1960 → Nineteen Sixty, 5000 → Five Thousand, 350 → Three Fifty, 60 → Sixty
- Maximum 2-3 SHORT sentences per response. This is a voice call — keep it brief and punchy.
- One question at a time. Never stack questions.
- Use natural filler: "जी", "हाँ", "देखिए", "actually"
- Mirror the caller's energy — brief when they're rushed, slightly elaborate when they're curious.
- Use "mai" instead of "main" to avoid confusions with english words like "main" for TTS.

SPEECH STYLE (sound like a real sales rep on a call, NOT a bot):
- Talk about specific features conversationally, like you're explaining to a colleague.
- Example good: "और 9 10th में इस बार हम लोगों ने specially कई चीजें और add कर दी हैं, जैसे 1 marks, 2 marks, 3 marks, 5 marks questions, NCERT के questions और CBSE PYQ Twenty Six तक के add हैं"
- Example good: "हर एक chapter के बाद एक chapter test डाल रहे हैं, जैसे board में exam में पूछा जाता है"
- Example good: "ताकि एक book अगर बच्चा खरीदे तो सर पूरा का पूरा cover हो जाए, अलग अलग books use ना करनी पड़ें"
- React naturally to "ठीक है" / "ओके" / "हाँ" with brief acknowledgment before continuing.
- When they say "ठीक है" you can say "जी बिल्कुल," or "हाँ सर," and then continue.
- DON'T sound like you're reading a list. Weave features into a natural flow.
"""

AGENT_PROFILE = """
YOUR IDENTITY:
- Your name is {agent_name}. You are a FEMALE sales representative calling from Universal Books.
- ALWAYS use FEMALE Hindi verb forms:
  बोल रही (NOT बोल रहा), ले सकती (NOT ले सकता), चाहती (NOT चाहता),
  समझ गयी (NOT समझ गया), कर देती (NOT कर देता)
- The script templates use {{bol_raha}}, {{le_sakta}}, {{chahta}} etc — those are already gender-correct. But when YOU generate text, always use the feminine forms listed above.
- Be professional but warm. You represent a 60-year-old publishing company.
"""


# ═══════════════════════════════════════════════════════════════
# STEP 1 — GREETING SCRIPTS
# ═══════════════════════════════════════════════════════════════

S1_GREETING_TEACHER = (
    "Hello, क्या मेरी बात {caller_name} जी से हो रही है जो coaching मे पढ़ाते हैं?"
)

S1_GREETING_INSTITUTION = (
    "Hello, क्या ये number {caller_name} का है ?"
)

S1_WRONG_PERSON = (
    "Sorry, wrong number लगा दिया, sorry।"
)

# ═══════════════════════════════════════════════════════════════
# STEP 2 — COMPANY INTRO SCRIPTS
# ═══════════════════════════════════════════════════════════════

S2_INTRO = (
    "जी {mera} naam {agent_name} है, मै  Universal Books से बोल {bol_raha} हूँ।"
    "हमारी .. Errorless के नाम se books आती हैं मार्केट मे, आपने शायद सुना होगा, जैसे जो नीट और जे-ई-ई exams के लिए बोहत famous हैं! .. जानते हैं आप?"
)

S2_ASK_PERMISSION = (
    "जी हा, हम उन्ही बुक्स के पब्लिशर हैं ... और अब हम class sixth se twelfth tak ke liye CBSE boards ki books और Neet, जे ई ई और बाकी medical और engineering exams के लिए, Exam Preparation material बनाते हैं ... जिसपे हम आपकी coaching कि खुद कि branding लगा के देते हैं, बिना किसी extra charges के। और best बात यह है कि हमारी books मार्केट मे मिलने वाली books से बोहत अलग हैं .. और .. इसी वजह से हम directly सीधे आप लोगों से ही बात करना चाहते हैं ... तो क्या आप हमसे बस दो मिनट बात कर सकते हैं?"
)

S2_INTRO_MORE_THEN_ASK_PERMISSION = (
    "आच्छा, आप नहीं जानते तोह मै बताना चाहूंगी कि मैं Universal Books की तरफ़ से बोल रही हूँ। हम 60 सालो से, मतलब की Nineteen Sixty के समय से exam preparation ki books aur material बनाते आ रहे हैं। और अब हम class sixth se twelfth tak ke liye CBSE boards ki books और Neet, जे ई ई और बाकी medical और engineering exams के लिए, Exam Preparation material बनाते हैं ... जिसपे हम आपकी coaching कि खुद कि branding लगा के देते हैं, बिना किसी extra charges के। और best बात यह है कि हमारी books मार्केट मे मिलने वाली books से बोहत अलग हैं, और इस वजह से भी हम आप लोगों से directly ही बात करते हैं ... तो क्या आप बस दो minute बात कर सकते हैं?"
)

# ═══════════════════════════════════════════════════════════════
# STEP 3 — ASK CLASSES SCRIPTS
# ═══════════════════════════════════════════════════════════════

S3_ASK_CLASSES = (
    "जी, पहले तो मै जानना {chahta} हूँ कि आपके यहा कौन सी classes और exams की पढ़ाई कराई जाती है? सिर्फ boards की .. या नीट और जे-ई-ई जैसे exams की भी?"
)

# ═══════════════════════════════════════════════════════════════
# STEP 4/5 — PRODUCT INFO (AI-GENERATED FROM KB)
# These are prompt instructions, not scripts.
# The AI will generate natural speech using KB data.
# ═══════════════════════════════════════════════════════════════

S45_AI_INSTRUCTION = (
    """Based on the product data below, share 2-3 key highlights NATURALLY 
    in Hinglish. Be specific — mention subject names, number of questions, 
    unique features. Use the provided scripts to answer.
    After sharing, call offer_sample.
    """
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
    """कोई issue कि बात नहीं है , हम आपको Samples WhatsApp par bhej देते हैं,आप आराम से content check kar lijiye,
    हम आपको physical book भी arrange कर देंगे। हमारी team आपको call कर के और भी details share कर देगी।
    और बाद मे अगर ऑर्डर भी करना हो तोह हमारी मिनमम क्वानटिटी सिर्फ दस sets हैं। तो आप सिर्फ एक module मंगा के भी देख सकते हैं कि content कितना अच्छा है।
    """
)

S_NOT_INTERESTED = (
    "जी कोई बात नहीं। अगर कभी आपको कुछ market से अलग चाहिए हो तो हमे एक message कर दीजिएगा"
)

S_BUSY = (
    "कोई बात नहीं, हम आपको कब call कर सकते है? कोई टाइम बता दीजिए?"
)


# ═══════════════════════════════════════════════════════════════
# EXAM → KB MODULE MAPPING
# Maps what the teacher says → which knowledgebase to load
# Add new mappings here as you add KB files.
# ═══════════════════════════════════════════════════════════════

EXAM_TO_KB = {
    "neet":         ["neet_pyq", "dpp_neet", "neet_jee"],
    "jee":          ["jee_pyq", "dpp_jee", "neet_jee"],
    "j double e":   ["jee_pyq", "dpp_jee", "neet_jee"],
    "medical":      ["neet_pyq", "neet_jee"],
    "engineering":  ["jee_pyq", "neet_jee"],
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
# STEP 1a: WAIT FOR CALLER PICKUP
# The agent sits silently until the person says "hello" / anything.
# This prevents wasted TTS/LLM on unanswered or ringing calls.
# ═══════════════════════════════════════════════════════════════

class Step1_Greet(BaseUBAgent):
    """Step 1a: Wait silently for the caller to pick up and speak first.
    
    When the phone rings, the SIP participant joins the room immediately
    but the human hasn't answered yet. We wait for ANY speech from the
    user before firing the greeting. This saves TTS/LLM costs on
    unanswered calls.
    """

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "The phone is ringing. You are WAITING for the person to pick up.\n"
                "Do NOT speak until the person says something.\n"
                "When the person says ANYTHING (hello, haan, ji, boliye, ha, "
                "kya hai, kaun, etc.), call `caller_picked_up` immediately.\n"
                "Do NOT generate any speech. ONLY call the tool."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        # Don't speak — just wait for user's first utterance
        logger.info("Step1_Greet | Waiting for caller to pick up...")

    @function_tool
    async def caller_picked_up(self, context: RunCtx, response: str = "hello") -> "Step1b_ConfirmIdentity":
        """The caller picked up and said something (hello, haan, etc.). Start greeting."""
        logger.info(f"Step1 → Caller picked up | heard: {response}")
        return Step1b_ConfirmIdentity()


# ═══════════════════════════════════════════════════════════════
# STEP 1b: GREET & CONFIRM IDENTITY
# Now that the caller answered, say the greeting and wait for
# identity confirmation.
# ═══════════════════════════════════════════════════════════════

class Step1b_ConfirmIdentity(BaseUBAgent):
    """Step 1b: Say greeting → confirm caller identity.
    
    Branches based on call_client_type:
      - teacher: "क्या मेरी बात {name} से हो रही है जो coaching मे पढ़ाते हैं?"
      - institution: "क्या ये number {name} का है?"
    """

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
        # Branch greeting based on call_client_type
        client_type = self.ud.call_client_type
        if client_type == "institution":
            await self.say_script(S1_GREETING_INSTITUTION)
        else:
            await self.say_script(S1_GREETING_TEACHER)

    @function_tool
    async def identity_confirmed(self, context: RunCtx, response: str = "confirmed") -> "Step2_Intro":
        """Person confirmed they are the right contact. response is what they said."""
        logger.info(f"Step1b → Step2 | {response}")
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
# STEP 2: COMPANY INTRO — "Do you know Errorless books?"
# ═══════════════════════════════════════════════════════════════

class Step2_Intro(BaseUBAgent):
    """Step 2: Company intro — ask 'do you know Errorless books?'
    
    This is an authority check:
    - If they know → S2_ASK_PERMISSION (short: "hum unhi ke publisher hain, 2 min?")
    - If they don't → S2_INTRO_MORE_THEN_ASK_PERMISSION (long authority build + ask permission)
    
    Both paths end with asking permission, then hand off to Step2b_Permission.
    """

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just introduced yourself and asked if they know about Errorless books. "
                "Listen for their response.\n"
                "- If they say YES, they know Errorless (haan, pata hai, suna hai, jaante hain, errorless jaante hain), "
                "call knows_errorless.\n"
                "- If they say NO, they don't know (nahi, nahi pata, kya hai ye, nahi suna), "
                "call doesnt_know_errorless.\n"
                "- If they say not interested or don't call (interest nahi, mat call karo, don't call), "
                "call not_interested.\n"
                "- If busy (busy, baad me, class chal rahi, abhi nahi), call person_busy.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(S2_INTRO)

    @function_tool
    async def knows_errorless(self, context: RunCtx, response: str = "yes") -> "Step2b_Permission":
        """They know about Errorless books. Ask for 2 minutes of their time."""
        logger.info(f"Step2 → knows Errorless | {response}")
        await self.say_script(S2_ASK_PERMISSION)
        return Step2b_Permission()

    @function_tool
    async def doesnt_know_errorless(self, context: RunCtx, response: str = "no") -> "Step2b_Permission":
        """They don't know Errorless. Build authority with full intro, then ask permission."""
        logger.info(f"Step2 → doesn't know Errorless, building authority | {response}")
        await self.say_script(S2_INTRO_MORE_THEN_ASK_PERMISSION)
        return Step2b_Permission()

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
        return ObjectionAgent(return_agent=Step2_Intro())


# ═══════════════════════════════════════════════════════════════
# STEP 2b: WAIT FOR PERMISSION
# ═══════════════════════════════════════════════════════════════

class Step2b_Permission(BaseUBAgent):
    """Step 2b: Permission gate — wait for 'yes continue' or 'no'.
    
    The previous agent (Step2_Intro) already said the permission-asking
    script. This agent just listens for the response.
    """

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just asked the person for 2 minutes of their time. "
                "Listen for their response.\n"
                "- If they give permission (haan, boliye, bataiye, ha bolo, theek hai, ok), "
                "call permission_granted.\n"
                "- If not interested (nahi, interest nahi, mat bolo, don't call), "
                "call not_interested.\n"
                "- If busy (busy, baad me, class chal rahi, abhi nahi), call person_busy.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n"
                "Do NOT speak — only call tools."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        # No speech — the previous agent already said the permission script
        pass

    @function_tool
    async def permission_granted(self, context: RunCtx, response: str = "yes") -> "Step3_AskClasses":
        """Person gave permission to continue talking."""
        logger.info(f"Step2b → Permission granted | {response}")
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
                "- If busy (busy, baad me, class chal rahi), call person_busy.\n"
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

        # ── STT Guard: filter false positives ──
        # Sarvam STT can misinterpret "ji" (जी = respectful yes) as "JEE"
        cleaned = classes_and_exams.strip().lower()
        false_positives = {"ji", "jee", "haan", "ha", "ok", "theek hai", "boliye"}
        if cleaned in false_positives or len(cleaned) <= 3:
            # This is likely an affirmative, not a class name — ask again
            logger.warning(f"STT guard: '{classes_and_exams}' looks like affirmative, re-asking")
            await self.say_script("जी सर, मतलब आपके यहाँ कौन सी classes चलती हैं? जैसे NEET, JEE, Boards, या Class 9 10?")
            return Step3_AskClasses()

        ud.exam_type = classes_and_exams

        if ud.tracker:
            ud.tracker.log_function("set_exam_type", {"exam": classes_and_exams})

        kb_modules = resolve_kb_modules(classes_and_exams)
        return Step4_ShareProduct(kb_modules=kb_modules)

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
# STEP 4 + 5: SHARE PRODUCT & USP (AI-GENERATED FROM KB)
# ═══════════════════════════════════════════════════════════════

class Step4_ShareProduct(BaseUBAgent):
    """Step 4-5: Share relevant product info using KB data (AI-generated).
    
    Language rules and speech style instructions are injected here
    so the LLM generates natural Hinglish like a real caller.
    """

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
                "Keep it conversational, 2-3 sentences max.\n\n"
                "If there are SAMPLE SCRIPTS in the product data, USE THEM"
                "for how to phrase things. You can adapt them but keep the natural tone.\n\n"
                "After the person responds positively (ठीक है, ओके, हाँ, अच्छा): "
                "if they want to see samples or know more, call offer_sample. "
                "Or if they raise concerns, call handle_hesitation. "
                "If not interested at all, call not_interested.\n"
                "- If busy (busy, baad me, class chal rahi), call person_busy.\n"
                "- If they ask 'where did you get my number' or 'are you AI', "
                "call handle_objection.\n\n"
                f"{LANGUAGE_RULES}\n\n"
                f"{AGENT_PROFILE}\n\n"
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
                "- If busy (busy, baad me, class chal rahi), call person_busy.\n"
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
    async def person_busy(self, context: RunCtx, response: str = "busy") -> "BaseUBAgent":
        """Person is busy right now."""
        await self.say_script(S_BUSY)
        from agents.shared.scheduler import SchedulerAgent
        return SchedulerAgent()

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
