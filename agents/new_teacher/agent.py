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

logger = logging.getLogger("flow.new_teacher")


# ═══════════════════════════════════════════════════════════════
# STEP 1 — GREETING SCRIPTS
# ═══════════════════════════════════════════════════════════════

S1_GREETING = (
    "Hello, क्या मेरी बात {caller_name} से हो रही है?"
)

S1_WRONG_PERSON = (
    "Oh sorry sir, wrong number ho gaya. Aapko disturb karne ke liye maafi {chahta} hूँ।"
)

# ═══════════════════════════════════════════════════════════════
# STEP 2 — COMPANY INTRO SCRIPTS
# ═══════════════════════════════════════════════════════════════

S2_INTRO = (
    "Ji sir, {mera} naam {agent_name} hai, mai Universal Books se bol {bol_raha} hूँ। "
    "Humari Errorless book aati hai NEET aur J double E ke liye, "
    "aur ab hum customized study material bhi banate hai Class 6 se 12 tak। "
    "We publish books for CBSE, aur test prep material for NEET, J double E "
    "aur other Medical and Engineering exams ke liye। "
    "Kya mai aapka ek minute le {le_sakta} hूँ?"
)

# ═══════════════════════════════════════════════════════════════
# STEP 3 — ASK CLASSES SCRIPTS
# ═══════════════════════════════════════════════════════════════

S3_ASK_CLASSES = (
    "Sir, aapke yahan kis classes aur exams ki coaching hoti hai?"
)

# ═══════════════════════════════════════════════════════════════
# STEP 4/5 — PRODUCT INFO (AI-GENERATED FROM KB)
# These are prompt instructions, not scripts.
# The AI will generate natural speech using KB data.
# ═══════════════════════════════════════════════════════════════

S45_AI_INSTRUCTION = (
    "Based on the product data below, share 2-3 key highlights NATURALLY "
    "in Hinglish. Be specific — mention subject names, number of questions, "
    "unique features. Then mention that books pe unke institute ki branding "
    "lagti hai free of cost. After sharing, call offer_sample."
)

# ═══════════════════════════════════════════════════════════════
# STEP 6 — SAMPLE OFFER SCRIPTS
# ═══════════════════════════════════════════════════════════════

S6_OFFER_SAMPLE = (
    "Sir maine aapko humare content ka ek digital sample share kiya hai "
    "WhatsApp par, aap dekh sakte hai। Agar aapko physical book bhi "
    "dekhni hai toh bhi arrange ho jayega। "
    "Kya mai aapki call humare senior ke saath setup kar dूँ?"
)

# ═══════════════════════════════════════════════════════════════
# STEP — NOT INTERESTED / HESITANT SCRIPTS
# ═══════════════════════════════════════════════════════════════

S_HESITANT = (
    "No issues sir, aap ek baar content check kar le, agar aapko aur chapters bhi "
    "chaiye toh aap mujko bata sakte hai। Humari team aapko visit bhi kar legi। "
    "Furthermore sir, our minimum quantity is just 10 sets so you can even "
    "get a single module to see if our branded material makes an impact।"
)

S_NOT_INTERESTED = (
    "No issues sir, I understand। Please let us know if and when you change your mind।"
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
    "neet":         ["neet_jee"],
    "jee":          ["neet_jee"],
    "j double e":   ["neet_jee"],
    "medical":      ["neet_jee"],
    "engineering":  ["neet_jee"],
    "jee advanced": ["jee_advanced"],
    "boards":       ["class_11", "class_12"],
    "cbse":         ["class_11", "class_12"],
    "12":           ["class_12"],
    "11":           ["class_11"],
    "10":           ["class_10"],
    "9":            ["class_9"],
    "8":            ["class_8"],
    "7":            ["class_7"],
    "6":            ["class_6"],
    "kcet":         ["kcet"],
    "mhtcet":       ["mhtcet"],
    "eapcet":       ["eapcet"],
    "cuet":         ["cuet"],
    "foundation":   ["class_9", "class_10"],
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
                "Mention that books pe unke institute ki branding lagti hai free of cost. "
                "Keep it conversational, 3-4 sentences max.\n"
                "After the person responds, if they want to see samples or know more, "
                "call offer_sample. If they raise concerns, call handle_hesitation. "
                "If not interested at all, call not_interested.\n\n"
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


# ═══════════════════════════════════════════════════════════════
# STEP 6: OFFER SAMPLE
# ═══════════════════════════════════════════════════════════════

class Step6_OfferSample(BaseUBAgent):
    """Step 6: Offer digital sample + physical book, ask to setup call."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You offered sample material and asked if they want a senior call. "
                "Listen for their response.\n"
                "- If yes or interested, call setup_senior_call.\n"
                "- If hesitant, call handle_hesitation.\n"
                "- If not interested, call not_interested.\n"
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
