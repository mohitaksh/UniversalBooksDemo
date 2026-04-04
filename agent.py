"""
agent.py
─────────────
Unified Monolithic Agent File for UniversalBooks.
Contains BaseUBAgent, CloserAgent, and the MainTeacherAgent monolithic flow.
"""

import asyncio
import logging
import httpx
from typing import Optional
from livekit.agents import Agent, function_tool
from livekit.agents.voice import RunContext
from models import CallUserData, VoiceProfile
from knowledgebase import kb_to_prompt
from config import N8N_TAG_LEAD_WEBHOOK_URL, N8N_WHATSAPP_SAMPLE_WEBHOOK_URL

logger = logging.getLogger("flow.unified_agent")

RunCtx = RunContext[CallUserData]

# ═══════════════════════════════════════════════════════════════
# 1. BASE UB AGENT
# ═══════════════════════════════════════════════════════════════

class BaseUBAgent(Agent):
    """
    Base agent — all UB agents inherit from this.
    Provides session helper shortcuts and script formatting via voice variables.
    """

    def __init__(self, instructions: str = "", **kwargs):
        super().__init__(instructions=instructions, **kwargs)

    @property
    def ud(self) -> CallUserData:
        return self.session.userdata

    def fmt(self, text: str) -> str:
        try:
            return text.format(**self.ud.voice_vars())
        except (KeyError, AttributeError) as e:
            logger.warning(f"FMT ERROR | {e} | text={text[:60]}")
            return text

    async def say_script(self, text: str):
        formatted = self.fmt(text)
        logger.info(f"SAY | {self.__class__.__name__} | {formatted[:100]}")
        await self.session.say(formatted)

    async def on_enter(self) -> None:
        logger.info(f"ON_ENTER | {self.__class__.__name__}")


# ═══════════════════════════════════════════════════════════════
# 2. CLOSER AGENT
# ═══════════════════════════════════════════════════════════════

CLOSING_GOOD_WISHES = (
    "Thank you for your time. Have a great day sir!"
)

class CloserAgent(BaseUBAgent):
    """Final agent — says goodbye, tags lead in N8N, gracefully shutdowns."""

    def __init__(self, tag: str = "Not Interested", notes: str = "", **kwargs):
        self._tag = tag
        self._notes = notes
        super().__init__(
            instructions="You just said goodbye. The call is ending. Do not speak.",
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(CLOSING_GOOD_WISHES)
        ud = self.session.userdata
        ud.lead_tag = self._tag
        ud.lead_notes = self._notes

        if ud.tracker:
            ud.tracker.log_function("tag_lead", {"tag": self._tag, "notes": self._notes})

        logger.info(f"CLOSER | {ud.caller_name} | tag={self._tag}")

        if N8N_TAG_LEAD_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(N8N_TAG_LEAD_WEBHOOK_URL, json={
                        "phone": ud.phone_number,
                        "name": ud.caller_name,
                        "tag": self._tag,
                        "notes": self._notes,
                        "call_id": ud.call_id,
                    })
            except Exception as e:
                logger.warning(f"N8N tag_lead webhook failed: {e}")

        await asyncio.sleep(2.0)
        try:
            logger.info(f"SHUTTING DOWN SESSION | {ud.caller_name}")
            self.session.shutdown()
        except Exception as e:
            logger.error(f"Failed to shutdown session: {e}")


# ═══════════════════════════════════════════════════════════════
# 3. NEW TEACHER MONOLITH
# ═══════════════════════════════════════════════════════════════

LANGUAGE_RULES = """
LANGUAGE RULES (follow strictly):
- Respond ONLY in Devanagari Hinglish — Hindi in Devanagari script mixed with English words kept in English.
- Always use "आप" (respectful). NEVER "तू" या "तुम".
- Speak numbers in English: 1960 → Nineteen Sixty, 5000 → Five Thousand, 350 → Three Fifty, 60 → Sixty
- Maximum 2-3 SHORT sentences per response. This is a voice call — keep it brief and punchy.
- One question at a time. Never stack questions.
- Use natural filler: "जी", "हाँ", "देखिए", "actually"
- Use "mai" instead of "main" to avoid confusions.
"""

AGENT_PROFILE = """
YOUR IDENTITY:
- Your name is {agent_name} (from Universal Books).
- ALWAYS use FEMALE Hindi verb forms:
  बोल रही (NOT बोल रहा), ले सकती (NOT ले सकता), चाहती (NOT चाहता),
  समझ गयी (NOT समझ गया), कर देती (NOT कर देता)
- Be professional but warm. You represent a 60-year-old publishing company.
"""

SCRIPT_INSTRUCTIONS = """
YOU MUST FOLLOW THIS SCRIPT SEQUENCE STEP-BY-STEP. DO NOT SKIP STEPS.

### STEP 1: Confirm Identity
Say exactly: "Hello, क्या मेरी बात {caller_name} sir से हो रही है?"
Wait for them to confirm or deny.
- If wrong person, say "Sorry, wrong number लग गया।" and call `end_call("Wrong_Number")`.

### STEP 2: Intro & Authority Check
Once confirmed, say:
"जी मेरा नाम {agent_name} है, मै Universal Books से बोल रही हूँ। हमारी Errorless के नाम से books आती हैं Market मे, जो competitive exams के लिए बहुत famous हैं! जैसे Errorless Self Scorer वगेरा... क्या आपने सुना है?"
Wait for their response (Yes or No).

### STEP 3: Ask Permission
- IF THEY SAY YES: "जी हाँ, हम उन्ही books के पब्लिशर हैं... और अब हम CBSE, Neet और JEE के लिए Exam Preparation material बनाते हैं... content हर साल updated रहता है जिसपे हम आपकी coaching कि खुद कि branding लगा के देते हैं, बिना किसी extra charges के। हमारी books Market मे मिलने वाली books से बहुत अलग हैं और इसी वजह से हम directly आप लोगों से बात करना चाहते हैं... तो क्या आप हमसे बस दो मिनट बात कर सकते हैं?"
- IF THEY SAY NO: "अच्छा, आप नहीं जानते तोह मै बताना चाहूंगी कि हम 60 सालो से exam preparation ki books aur material बनाते आ रहे हैं। और अब हम class sixth से twelfth तक के लिए CBSE boards की books और Neet, JEE और बाकी exams के लिए preparation material बनाते हैं... जिसपे हम आपकी coaching कि खुद कि branding लगा के देते हैं, बिना किसी extra charges के। हमारी books Market की books से बहुत अलग हैं... तो क्या आप बात कर सकते हैं?"
Wait for permission (Haan boliye, okay etc).
- If they are busy/not interested, say "कोई बात नहीं I understand. Have a great day!" and call `end_call("Not_Interested")`.

### STEP 4: Ask Classes
Once permission granted, say:
"जी, पहले तो मै जानना चाहती हूँ कि आपके यहाँ कौन सी classes और exams की पढ़ाई कराई जाती है? सिर्फ boards की या नीट और JEE जैसे exams की भी?"
Listen to what they teach.

### STEP 5: Share Product USP
Use the Product Data provided below to share 1-2 specific highlighted features that match what they teach (e.g. if they teach boards, mention CBSE features. If NEET, mention NEET features).
Limit to two concise sentences in Hinglish. 
Finally ask: "क्या मैं आपको WhatsApp पर एक sample भेज सकती हूँ?"

### STEP 6: Send Sample & End
If they say yes to sample or "bhej do", say:
"Okay तोह मैंने आपको WhatsApp पर sample share कर दिया है, और अगर आपको physical book भी देखनी है, तो वोह भी हम arrange कर देंगे। आप आराम से sample देख लीजिए, हम आपको बाद मे call कर के और details share कर लेंगे। Have a great day!"
IMMEDIATELY call the `send_whatsapp_sample` tool after speaking this.
"""

class Step1_Greet(BaseUBAgent):
    """Step 1: Wait for SIP connection to fully open and the user to speak."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just said 'Hello?'. Listen carefully for the person to speak.\n"
                "When the person replies (hello, haan, ji, boliye, ha, etc.), "
                "call `caller_picked_up` IMMEDIATELY to start the conversation.\n"
                "Do NOT generate any additional speech. ONLY call the tool."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        logger.info("unified_agent | Step1_Greet | Saying hello...")
        await self.say_script("Hello?")

    @function_tool
    async def caller_picked_up(self, context: RunCtx, response: str = "hello") -> "MainTeacherAgent":
        """The person has picked up and spoken."""
        return MainTeacherAgent()


class MainTeacherAgent(BaseUBAgent):
    """Monolithic agent that runs the entire new_teacher script organically."""

    def __init__(self, **kwargs):
        product_data = kb_to_prompt("products")
        
        instructions = (
            f"{AGENT_PROFILE}\n\n"
            f"{LANGUAGE_RULES}\n\n"
            f"{SCRIPT_INSTRUCTIONS}\n\n"
            f"PRODUCT DATA (For Step 5):\n"
            f"{product_data}\n\n"
            f"GLOBAL OBJECTIONS:\n"
            f"- If they say 'Where did you get my number?': Say 'सर आपका number हमारी team ने digital sources से लिया था, schools और institutes के database से।'\n"
            f"- If they ask 'Are you AI/Bot?': Say 'जी मै Universal Books की AI assistant हूँ।'\n"
            f"Always return to the script step smoothly after answering."
        )
        super().__init__(instructions=instructions, **kwargs)

    async def on_enter(self) -> None:
        v_vars = self.session.userdata.voice_vars()
        self.session.instructions = self.session.instructions.replace(
            "{caller_name}", v_vars["caller_name"]
        ).replace(
            "{agent_name}", v_vars["agent_name"]
        )
        self.session.generate_reply()

    @function_tool
    async def end_call(self, context: RunCtx, reason: str) -> None:
        """Call this to end the conversation (e.g. wrong number, not interested). Do NOT call this if sending sample."""
        return CloserAgent(tag=reason)

    @function_tool
    async def send_whatsapp_sample(self, context: RunCtx, intent: str = "send") -> None:
        """Call this ONLY when the user agrees to receive the digital sample on whatsapp at the end (Step 6)."""
        ud = context.userdata
        if N8N_WHATSAPP_SAMPLE_WEBHOOK_URL:
            asyncio.create_task(httpx.AsyncClient().post(N8N_WHATSAPP_SAMPLE_WEBHOOK_URL, json={
                "phone": ud.phone_number,
                "name": ud.caller_name,
                "call_id": ud.call_id,
            }))
        return CloserAgent(tag="Sample Shared")
