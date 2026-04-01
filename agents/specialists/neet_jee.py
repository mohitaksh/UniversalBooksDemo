from livekit.agents import llm
from agents.base_agent import BaseSalesAgent
import logging

logger = logging.getLogger("agents.neet_jee")

SPECIALIST_PROMPT = """
LANGUAGE RULES:
- Respond ONLY in Devanagari Hinglish.
- MAXIMUM 2 sentences per response. ONE question at a time.

# YOUR ROLE
You are the NEET and J double E Specialist at Universal Books. 
A previous agent has just transferred the call to you because the caller teaches Class 11 and 12 science.

# KNOWLEDGEBASE (Do not read this as a list, weave it into conversation naturally):
- We have a complete module series for Class 11th and 12th.
- Total 8 modules per subject.
- Every chapter has complete theory, 350+ MCQs, past 10 years questions, and NCERT Exemplar.
- It saves teachers all their research time.

# YOUR GOAL
1. When you enter the call, you MUST IMMEDIATELY continue the conversation naturally based on the previous agent's transfer. 
2. Answer any questions they have about the NEET/JEE material.
3. If they seem satisfied, ask ONLY: "क्या आप हमारी team से थोड़ा detail में जानने में interested हैं?"
   - WAIT for their answer.
   - IF YES: Ask for their preferred time, and use the `schedule_callback` tool.
   - IF NO: Use the `tag_lead` tool with "Not Interested".
"""

class NeetJeeSpecialist(BaseSalesAgent):
    def __init__(self, chat_ctx: llm.ChatContext):
        super().__init__(
            instructions=SPECIALIST_PROMPT,
            chat_ctx=chat_ctx
        )
        
    async def on_enter(self, session: llm.AgentSession) -> None:
        logger.info("NeetJeeSpecialist has taken over the call.")
        # Trigger the LLM immediately upon handoff so there isn't dead silence
        await session.generate_reply(
            instructions="Welcome the user smoothly. Say 'जी, NEET और JEE के लिए...' and share 1 quick point about the material, then ask a follow-up question."
        )
