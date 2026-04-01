"""
Knowledgebase package — structured product data for AI context.

HOW IT WORKS:
- Each file contains a DATA dict with product facts/features
- When the qualifier identifies which product the teacher needs,
  the relevant KB data gets injected into the LLM prompt
- The LLM then generates natural conversational responses using this data
- Critical lines (greeting, pitch, closing) are still hardcoded in agent scripts

HOW TO EDIT:
1. Open any file (e.g. class_6.py)
2. Edit the DATA dict with your product details
3. The AI will use this data to answer questions naturally

Template variables available: {agent_name}, {caller_name}, etc.
"""

import importlib
import logging
from typing import Optional

logger = logging.getLogger("knowledgebase")

# ═══════════════════════════════════════════════════════════════
# MASTER LIST — add new modules here after creating the file
# ═══════════════════════════════════════════════════════════════

KB_MODULES = [
    "class_6",
    "class_7",
    "class_8",
    "class_9",
    "class_10",
    "class_11",
    "class_12",
    "neet_jee",
    "worksheets",
    "cbse_12_pyq",
    "cbse_10_pyq",
    "neet_pyq",
    "jee_pyq",
    "dpp_neet",
    "dpp_jee",
    "crash_course",
    "formula_handbook",
    "kcet",
    "mhtcet",
    "eapcet",
    "cuet",
    "jee_advanced",
    "company_overview",
]


def load_kb(module_name: str) -> Optional[dict]:
    """Load a knowledgebase DATA dict by module name."""
    try:
        mod = importlib.import_module(f"knowledgebase.{module_name}")
        return mod.DATA
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to load KB: knowledgebase.{module_name}: {e}")
        return None


def kb_to_prompt(module_name: str) -> str:
    """
    Convert a KB DATA dict into a prompt-injectable string.
    This gets added to the LLM context so it can answer questions.
    """
    data = load_kb(module_name)
    if not data:
        return ""

    lines = [f"## Product: {data.get('title', module_name)}"]
    if data.get("subtitle"):
        lines.append(f"Subtitle: {data['subtitle']}")
    if data.get("target_classes"):
        lines.append(f"Target Classes: {data['target_classes']}")
    if data.get("subjects"):
        lines.append(f"Subjects: {', '.join(data['subjects'])}")

    if data.get("features"):
        lines.append("Key Features:")
        for feat in data["features"]:
            lines.append(f"  - {feat}")

    if data.get("usp"):
        lines.append(f"USP: {data['usp']}")

    if data.get("best_for"):
        lines.append(f"Best For: {data['best_for']}")

    if data.get("extra_notes"):
        lines.append(f"Notes: {data['extra_notes']}")

    return "\n".join(lines)
