"""
qualifier.py
─────────────
QualifierAgent — Asks what exams/classes the person teaches.
Maps their answer to the right knowledgebase file and hands off.

EDIT YOUR SCRIPTS: Modify QUALIFYING_QUESTION below.
"""

from livekit.agents import RunContext, function_tool
from agents.base_agent import BaseUBAgent
from models import CallUserData


# ═══════════════════════════════════════════════════════════════
# SCRIPTS — Edit these
# ═══════════════════════════════════════════════════════════════

QUALIFYING_QUESTION = (
    "आप कौन से exams की तैयारी करवाते हैं? "
    "Boards exam या J Double E और NEET वग़ैरा?"
)

# ═══════════════════════════════════════════════════════════════
# EXAM → KNOWLEDGEBASE MAPPING
# Add new mappings here as you add knowledgebase files.
# ═══════════════════════════════════════════════════════════════

EXAM_TO_KB = {
    "neet":         "neet_jee",
    "jee":          "neet_jee",
    "j double e":   "neet_jee",
    "medical":      "neet_jee",
    "engineering":  "neet_jee",
    "boards":       "cbse_boards",
    "cbse":         "cbse_boards",
    "board":        "cbse_boards",
    "12th":         "cbse_boards",
    "11th":         "cbse_boards",
    "foundation":   "foundation_9_10",
    "9th":          "foundation_9_10",
    "10th":         "foundation_9_10",
    "10":           "foundation_9_10",
    "9":            "foundation_9_10",
    "pre-foundation": "foundation_6_7_8",
    "6th":          "foundation_6_7_8",
    "7th":          "foundation_6_7_8",
    "8th":          "foundation_6_7_8",
    "6":            "foundation_6_7_8",
    "7":            "foundation_6_7_8",
    "8":            "foundation_6_7_8",
    "crash":        "crash_course",
    "test series":  "crash_course",
}


def resolve_kb(exam_type: str) -> str:
    """Resolve exam type string to knowledgebase module name."""
    exam_lower = exam_type.strip().lower()
    for key, kb in EXAM_TO_KB.items():
        if key in exam_lower:
            return kb
    # Default to neet_jee if no match
    return "neet_jee"


# ═══════════════════════════════════════════════════════════════


class QualifierAgent(BaseUBAgent):
    """Asks the qualifying question and routes to the right KB."""

    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You asked what exams the person teaches. Listen to their answer. "
                "When they tell you the exam type (JEE, NEET, Boards, Foundation, etc.), "
                "call set_exam_type with the exam name. "
                "If they ask a question or raise an objection, call objection_raised. "
                "Do NOT generate any speech yourself."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script(QUALIFYING_QUESTION)

    @function_tool()
    async def set_exam_type(
        self,
        context: RunContext[CallUserData],
        exam_type: str,
    ):
        """Record the exam type the person teaches (e.g. JEE, NEET, Boards, Foundation)."""
        ud = context.userdata
        ud.exam_type = exam_type

        kb_name = resolve_kb(exam_type)

        if ud.tracker:
            ud.tracker.log_function("set_exam_type", {"exam_type": exam_type, "kb": kb_name})

        from agents.kb_presenter import KBPresenterAgent
        return KBPresenterAgent(
            kb_module=kb_name,
            chat_ctx=self.chat_ctx,
        ), f"Presenting {kb_name} knowledgebase"

    @function_tool()
    async def objection_raised(self, context: RunContext[CallUserData]):
        """Person raised an objection instead of answering."""
        from agents.objection_handler import ObjectionHandlerAgent
        return ObjectionHandlerAgent(
            return_to="qualifier",
            chat_ctx=self.chat_ctx,
        ), "Handling objection"
