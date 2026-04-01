from livekit.agents import llm
from agents.base_agent import BaseSalesAgent
import json
import logging

logger = logging.getLogger("agents.new_teacher")

PROMPT = """
LANGUAGE RULES:
- Respond ONLY in Devanagari Hinglish.
- Always use "आप" (respectful).
- MAXIMUM 2 sentences per response. ONE question at a time.
- You are {agent_name} from Universal Books — a friendly sales caller.

# Caller
Name: {caller_name}
Call type: NEW TEACHER

# YOUR GOAL
You are speaking to a teacher or coaching institute for the first time.
1. Greet them: "जी, {mera} नाम {agent_name} है, मैं Universal Books से बोल {bol_raha} हूँ। हम teachers और coaching centers के लिए exam preparation books बनाते हैं। क्या आपसे बस एक minute ले {le_sakta} हूँ?"
2. If they say YES, present the quick pitch: "जी हम Nineteen Sixties से NEET, J double E, और Boards का material बना रहे हैं, जिसपे आपके institute की branding लग जाती है बिना किसी extra charge के। क्या आप इस बारे में जानना चाहेंगे?"
3. If they are interested, ask: "आप कौन से classes या exams की तैयारी करवाते हैं?"
4. Once they tell you their class/exam, YOU MUST USE THE TRANSFER TOOLS to hand off the call to a specialist! Do not try to answer questions about the books yourself.
"""

class NewTeacherAgent(BaseSalesAgent):
    def __init__(self, caller_name: str, voice_profile, chat_ctx: llm.ChatContext = None):
        formatted_prompt = PROMPT.format(
            agent_name=voice_profile.name,
            mera=voice_profile.mera,
            bol_raha=voice_profile.bol_raha,
            le_sakta=voice_profile.le_sakta,
            caller_name=caller_name
        )
        super().__init__(instructions=formatted_prompt, chat_ctx=chat_ctx)

    @llm.function_tool(description="Use this when the teacher mentions they teach Class 11/12 NEET or JEE.")
    async def transfer_to_neet_jee(self, context: llm.RunContext):
        """Transfers the call to the NEET/JEE specialist who handles class 11 and 12 modules."""
        logger.info("Transferring to NEET/JEE Specialist...")
        await self.session.say("जी, NEET और J double E का हमारा material बहुत बढ़िया है। मैं आपको इसकी detail बताती हूँ।")
        
        # Lazy import to avoid circular dependencies
        from agents.specialists.neet_jee import NeetJeeSpecialist
        # Hand off and optionally pass context summary if needed
        return llm.handoff(
            agent=NeetJeeSpecialist(chat_ctx=self.chat_ctx.copy(exclude_instructions=True)),
            returns="Transferring to NEET JEE Specialist"
        )
        
    @llm.function_tool(description="Use this when the teacher mentions they teach Class 11/12 CBSE Boards.")
    async def transfer_to_cbse_boards(self, context: llm.RunContext):
        """Transfers the call to the CBSE Boards specialist for class 11 and 12."""
        logger.info("Transferring to CBSE Boards Specialist...")
        await self.session.say("जी, CBSE boards के latest pattern का material हमारे पास है। मैं detail बताती हूँ।")
        from agents.specialists.cbse_boards import CbseBoardsSpecialist
        return llm.handoff(agent=CbseBoardsSpecialist(chat_ctx=self.chat_ctx.copy(exclude_instructions=True)))

    @llm.function_tool(description="Use this when the teacher mentions they teach Foundation Class 9 or 10, or Lower Classes 6, 7, 8.")
    async def transfer_to_foundation(self, context: llm.RunContext):
        """Transfers the call to the Foundation specialist for class 6 to 10."""
        logger.info("Transferring to Foundation Specialist...")
        await self.session.say("जी, 9th और 10th foundation का material हमारे पास ready है। मैं detail शेयर करती हूँ।")
        from agents.specialists.foundation import FoundationSpecialist
        return llm.handoff(agent=FoundationSpecialist(chat_ctx=self.chat_ctx.copy(exclude_instructions=True)))
