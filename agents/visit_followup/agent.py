import logging
from livekit.agents import function_tool
from agents.base_agent import BaseUBAgent, RunCtx
from agents.shared.closer import CloserAgent
from agents.shared.scheduler import SchedulerAgent
from knowledgebase import kb_to_prompt
from agents.prompts import LANGUAGE_RULES, AGENT_PROFILE

logger = logging.getLogger("agents.visit_followup")

# ═══════════════════════════════════════════════════════════════
# SCRIPT STRINGS (DEVNAGARI HYBRID)
# ═══════════════════════════════════════════════════════════════

S1_GREETING = "Hello, क्या मेरी बात {caller_name} sir से हो रही है? Sir मेरा नाम {agent_name} है, Universal Books से। How are you sir?"

S2_RECALL = (
    "Sir, आपको recently हमारे team member ने visit किया था। "
    "मै उनके behalf पर call कर रही हूँ आपका feedback लेने के लिए, "
    "और अगर कोई query है तोह solve करने के लिए।"
)

S3_ASK_FEEDBACK = "Sir आपको content और paper quality कैसी लगी?"

S5_INTERESTED = (
    "Thank you for your feedback sir, हमारे products की और details के लिए "
    "मैंने अपने senior को inform कर दिया है, he will call you within the next 1 hour।"
)

S5_HESITANT = (
    "No issues sir, आप एक बार content check कर ले, अगर आपको "
    "और chapters भी चाहिए तोह आप मुझको बता सकते है। "
    "हमारी team आपको visit भी कर लेगी। "
    "Furthermore sir, our minimum quantity is just 10 sets so you can even "
    "get a single module to see if our branded material makes an impact।"
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
        logger.info("visit_followup | Step1_Greet | Saying hello...")
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
                "- If they ask 'where did you get my number' or 'are you AI', call handle_objection.\n"
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
# STEP 2 & 3: RECALL VISIT AND GET FEEDBACK
# ═══════════════════════════════════════════════════════════════

class Step2_Recall(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked for their feedback on paper quality and content after recalling a visit. Listen carefully.\n"
                "- If POSITIVE feedback or want more info, call feedback_positive.\n"
                "- If HESITANT (dekhte hai, abhi decide nahi kiya), call hesitant.\n"
                "- If NOT INTERESTED (bekar hai, nahi chahiye), call not_interested.\n"
                "- If busy, call person_busy.\n"
                "- If objection, call handle_objection.\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(f"{S2_RECALL} {S3_ASK_FEEDBACK}")

    @function_tool
    async def feedback_positive(self, context: RunCtx, review: str = "good") -> "Step4_ShareUSP":
        """Positive feedback or wants more product info."""
        return Step4_ShareUSP()

    @function_tool
    async def hesitant(self, context: RunCtx, review: str = "unsure") -> BaseUBAgent:
        await self.say_script(S5_HESITANT)
        return CloserAgent(tag="Call Back")

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
                "- If POSITIVE, call feedback_positive.\n"
                "- If HESITANT, call hesitant.\n"
                "- If NOT INTERESTED, call not_interested.\n"
            ),
            **kwargs,
        )
    async def on_enter(self) -> None: pass
    
    @function_tool
    async def feedback_positive(self, context: RunCtx, review: str = "good") -> "Step4_ShareUSP":
        return Step4_ShareUSP()

    @function_tool
    async def hesitant(self, context: RunCtx, review: str = "unsure") -> BaseUBAgent:
        await self.say_script(S5_HESITANT)
        return CloserAgent(tag="Call Back")

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        await self.say_script(S_NOT_INTERESTED)
        return CloserAgent(tag="Not Interested")

# ═══════════════════════════════════════════════════════════════
# STEP 4: SHARE USP (AI-GENERATED) & CLOSE
# ═══════════════════════════════════════════════════════════════

class Step4_ShareUSP(BaseUBAgent):
    def __init__(self, **kwargs):
        company_kb = kb_to_prompt("company_overview")
        super().__init__(
            instructions=(
                "Share 2-3 unique selling points of Universal Books naturally in Hinglish. "
                "Use the data below. After sharing, ask if they want a senior call.\n"
                "- If YES call interested.\n"
                "- If HESITANT call hesitant.\n"
                "- If NO call not_interested.\n"
                "- If busy call person_busy.\n\n"
                f"{LANGUAGE_RULES}\n\n"
                f"{AGENT_PROFILE}\n\n"
                f"COMPANY DATA:\n{company_kb}"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        self.session.generate_reply()

    @function_tool
    async def interested(self, context: RunCtx, response: str = "ok") -> BaseUBAgent:
        """They want a senior call."""
        await self.say_script(S5_INTERESTED)
        return SchedulerAgent()

    @function_tool
    async def hesitant(self, context: RunCtx, response: str = "ok") -> BaseUBAgent:
        """They are hesitant."""
        await self.say_script(S5_HESITANT)
        return CloserAgent(tag="Call Back")

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "ok") -> BaseUBAgent:
        """They are not interested."""
        await self.say_script(S_NOT_INTERESTED)
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        await self.say_script(S_BUSY)
        return SchedulerAgent()

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> BaseUBAgent:
        await self.say_script(S_NUMBER_SOURCE if "number" in objection.lower() else S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step4_ListenUSP())

class Step4_ListenUSP(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "- If YES, call interested.\n"
                "- If HESITANT, call hesitant.\n"
                "- If NO, call not_interested.\n"
            ),
            **kwargs,
        )
    async def on_enter(self) -> None: pass
    
    @function_tool
    async def interested(self, context: RunCtx, response: str = "ok") -> BaseUBAgent:
        await self.say_script(S5_INTERESTED)
        return SchedulerAgent()

    @function_tool
    async def hesitant(self, context: RunCtx, response: str = "ok") -> BaseUBAgent:
        await self.say_script(S5_HESITANT)
        return CloserAgent(tag="Call Back")

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "ok") -> BaseUBAgent:
        await self.say_script(S_NOT_INTERESTED)
        return CloserAgent(tag="Not Interested")
