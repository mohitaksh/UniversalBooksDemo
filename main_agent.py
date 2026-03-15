"""
main_agent.py
─────────────
20-agent multi-agent architecture for Universal Books outbound sales calls.
Each agent has ONE focused job with handoffs via @function_tool.

Architecture:
  Layer 1 (Contact):    GreeterAgent → IdentityConfirmerAgent → GatekeeperAgent → HoldWaiterAgent
  Layer 2 (Pitch):      IntroAgent → NeedsAssessorAgent → ExamPitcherAgent → ClosingPitcherAgent
  Layer 3 (Objection):  OwnMaterialAgent, PriceHandlerAgent, NotInterestedAgent, ThinkAboutItAgent
  Layer 4 (Action):     MaterialSenderAgent, EmailCollectorAgent, BusySchedulerAgent, TeamConnectAgent
  Layer 5 (Closing):    GracefulCloserAgent, HostileExitAgent
  Layer 6 (Edge):       WrongNumberAgent, ReEngagerAgent
"""

import os
import json
import asyncio
import logging
import httpx
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    UserStateChangedEvent,
    cli,
    llm,
    Agent,
    function_tool,
    AgentSession,
)
from livekit.agents.voice import RunContext

from livekit.plugins import sarvam, anthropic
import livekit.plugins.groq as groq

from prompts import (
    IDENTITY_CONFIRMER_PROMPT, GATEKEEPER_PROMPT, HOLD_WAITER_PROMPT,
    INTRO_PROMPT, NEEDS_ASSESSOR_PROMPT, EXAM_PITCHER_PROMPT, CLOSING_PITCHER_PROMPT,
    OWN_MATERIAL_PROMPT, PRICE_HANDLER_PROMPT, NOT_INTERESTED_PROMPT, THINK_ABOUT_IT_PROMPT,
    MATERIAL_SENDER_PROMPT, EMAIL_COLLECTOR_PROMPT, BUSY_SCHEDULER_PROMPT, TEAM_CONNECT_PROMPT,
    GRACEFUL_CLOSER_PROMPT, HOSTILE_EXIT_PROMPT, WRONG_NUMBER_PROMPT, REENGAGER_PROMPT,
    KNOWLEDGE_BASE,
)
from logger import setup_loggers, write_cost_report
from models import CostTracker

load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)


# ═════════════════════════════════════════════════════════════════
# SHARED STATE
# ═════════════════════════════════════════════════════════════════

@dataclass
class CallUserData:
    """Shared state across all agents in a single call."""
    caller_name: str = "ji"
    call_type: str = "name"
    phone_number: str = ""
    tracker: CostTracker = None
    brief_log: logging.Logger = None
    personas: dict = field(default_factory=dict)
    prev_agent: Optional[Agent] = None
    ctx: Optional[JobContext] = None
    collected_email: str = ""
    exam_focus: str = ""
    material_sent_via: str = ""


RunCtx = RunContext[CallUserData]


# ═════════════════════════════════════════════════════════════════
# BASE AGENT — shared logic for all agents
# ═════════════════════════════════════════════════════════════════

class BaseAgent(Agent):
    """Base class with context preservation and handoff logic."""

    async def on_enter(self) -> None:
        agent_name = self.__class__.__name__
        userdata: CallUserData = self.session.userdata
        if userdata.brief_log:
            userdata.brief_log.info(f"AGENT_ENTER | {agent_name}")

        # Preserve context from previous agent
        chat_ctx = self.chat_ctx.copy()
        if userdata.prev_agent:
            items_copy = self._truncate_chat_ctx(
                userdata.prev_agent.chat_ctx.items, keep_function_call=True
            )
            existing_ids = {item.id for item in chat_ctx.items}
            items_copy = [item for item in items_copy if item.id not in existing_ids]
            chat_ctx.items.extend(items_copy)

        await self.update_chat_ctx(chat_ctx)
        self.session.generate_reply()

    def _truncate_chat_ctx(
        self, items: list, keep_last_n: int = 6,
        keep_system: bool = False, keep_function_call: bool = False,
    ) -> list:
        """Keep only the last N relevant messages for context efficiency."""
        def _valid(item) -> bool:
            if not keep_system and item.type == "message" and item.role == "system":
                return False
            if not keep_function_call and item.type in ["function_call", "function_call_output"]:
                return False
            return True

        result = []
        for item in reversed(items):
            if _valid(item):
                result.append(item)
            if len(result) >= keep_last_n:
                break
        result = result[::-1]

        # Don't start with function calls
        while result and result[0].type in ["function_call", "function_call_output"]:
            result.pop(0)
        return result

    async def _transfer_to(self, name: str, context: RunCtx) -> Agent:
        """Transfer to another agent with context preservation."""
        userdata = context.userdata
        userdata.prev_agent = context.session.current_agent
        return userdata.personas[name]


# ═════════════════════════════════════════════════════════════════
# LAYER 1: FIRST CONTACT
# ═════════════════════════════════════════════════════════════════

class GreeterAgent(BaseAgent):
    """Hardcoded opener — no LLM. Transfers immediately to IdentityConfirmer."""

    def __init__(self, caller_name: str = "ji", call_type: str = "name"):
        super().__init__(instructions="Wait for the caller to respond.")
        self.caller_name = caller_name
        self.call_type = call_type

    async def on_enter(self) -> None:
        userdata: CallUserData = self.session.userdata
        if userdata.brief_log:
            userdata.brief_log.info(
                f"AGENT_ENTER | GreeterAgent | {self.call_type}:{self.caller_name}"
            )

        await asyncio.sleep(5.0)  # SIP audio establishment delay

        if self.call_type == "institution":
            opener = f"Hello, क्या आप {self.caller_name} से बोल रहे हैं?"
        else:
            opener = f"Hello, क्या आप {self.caller_name} जी बोल रहे हैं जो tuition पढ़ाते हैं?"

        await self.session.say(opener)

        # Auto-transfer to identity confirmer
        self.session.update_agent(
            self.session.userdata.personas["identity_confirmer"]
        )

    @function_tool
    async def transfer_to_identity_confirmer(self, context: RunCtx) -> Agent:
        """Transfer to identity confirmation."""
        return await self._transfer_to("identity_confirmer", context)


class IdentityConfirmerAgent(BaseAgent):
    """Confirms caller identity and routes based on response."""

    def __init__(self, caller_name: str = "ji", call_type: str = "name"):
        super().__init__(
            instructions=IDENTITY_CONFIRMER_PROMPT.format(
                caller_name=caller_name, call_type=call_type
            )
        )

    @function_tool
    async def transfer_to_intro(self, context: RunCtx) -> Agent:
        """Transfer when identity is confirmed — move to introduction."""
        return await self._transfer_to("intro", context)

    @function_tool
    async def transfer_to_gatekeeper(self, context: RunCtx) -> Agent:
        """Transfer when speaking to wrong person — find the decision maker."""
        return await self._transfer_to("gatekeeper", context)

    @function_tool
    async def transfer_to_busy_scheduler(self, context: RunCtx) -> Agent:
        """Transfer when caller says they are busy."""
        return await self._transfer_to("busy_scheduler", context)

    @function_tool
    async def transfer_to_wrong_number(self, context: RunCtx) -> Agent:
        """Transfer when it's a wrong number."""
        return await self._transfer_to("wrong_number", context)

    @function_tool
    async def transfer_to_hostile_exit(self, context: RunCtx) -> Agent:
        """Transfer when caller is hostile or rude."""
        return await self._transfer_to("hostile_exit", context)

    # NOTE: silence/no-response is handled by system-level user_away_timeout,
    # not by the LLM. See user_state_changed handler in entrypoint().

    @function_tool
    async def tag_lead(self, context: RunCtx, tag: str, notes: str = "") -> str:
        """Tag the lead outcome."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("tag_lead", {"tag": tag, "notes": notes})
        if ud.brief_log:
            ud.brief_log.info(f"FUNCTION | tag_lead | tag='{tag}' | notes='{notes}'")
        return f"Lead tagged as {tag}."


class GatekeeperAgent(BaseAgent):
    """Speaks to receptionist/staff and asks for decision maker."""

    def __init__(self, caller_name: str = "ji"):
        super().__init__(
            instructions=GATEKEEPER_PROMPT.format(caller_name=caller_name)
        )

    @function_tool
    async def transfer_to_hold_waiter(self, context: RunCtx) -> Agent:
        """Transfer when being put on hold to reach decision maker."""
        return await self._transfer_to("hold_waiter", context)

    @function_tool
    async def transfer_to_busy_scheduler(self, context: RunCtx) -> Agent:
        """Transfer when DM is not available — schedule callback."""
        return await self._transfer_to("busy_scheduler", context)

    @function_tool
    async def transfer_to_graceful_closer(self, context: RunCtx) -> Agent:
        """Transfer to graceful close when they refuse."""
        return await self._transfer_to("graceful_closer", context)

    @function_tool
    async def transfer_to_hostile_exit(self, context: RunCtx) -> Agent:
        """Transfer when caller is hostile."""
        return await self._transfer_to("hostile_exit", context)

    @function_tool
    async def tag_lead(self, context: RunCtx, tag: str, notes: str = "") -> str:
        """Tag the lead outcome."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("tag_lead", {"tag": tag, "notes": notes})
        if ud.brief_log:
            ud.brief_log.info(f"FUNCTION | tag_lead | tag='{tag}' | notes='{notes}'")
        return f"Lead tagged as {tag}."


class HoldWaiterAgent(BaseAgent):
    """Waits on hold, re-verifies when someone new speaks."""

    def __init__(self):
        super().__init__(instructions=HOLD_WAITER_PROMPT)

    @function_tool
    async def transfer_to_intro(self, context: RunCtx) -> Agent:
        """Transfer to introduction when DM is confirmed."""
        return await self._transfer_to("intro", context)

    @function_tool
    async def transfer_to_graceful_closer(self, context: RunCtx) -> Agent:
        """Transfer if call seems dropped."""
        return await self._transfer_to("graceful_closer", context)

    @function_tool
    async def tag_lead(self, context: RunCtx, tag: str, notes: str = "") -> str:
        """Tag the lead outcome."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("tag_lead", {"tag": tag, "notes": notes})
        if ud.brief_log:
            ud.brief_log.info(f"FUNCTION | tag_lead | tag='{tag}' | notes='{notes}'")
        return f"Lead tagged as {tag}."


# ═════════════════════════════════════════════════════════════════
# LAYER 2: PITCH & DISCOVERY
# ═════════════════════════════════════════════════════════════════

class IntroAgent(BaseAgent):
    """Delivers the Universal Books introduction pitch."""

    def __init__(self):
        super().__init__(instructions=INTRO_PROMPT)

    @function_tool
    async def transfer_to_needs_assessor(self, context: RunCtx) -> Agent:
        """Transfer when caller is curious — assess their needs."""
        return await self._transfer_to("needs_assessor", context)

    @function_tool
    async def transfer_to_not_interested(self, context: RunCtx) -> Agent:
        """Transfer when caller says not interested."""
        return await self._transfer_to("not_interested", context)

    @function_tool
    async def transfer_to_price_handler(self, context: RunCtx) -> Agent:
        """Transfer when caller asks about price."""
        return await self._transfer_to("price_handler", context)

    @function_tool
    async def transfer_to_own_material(self, context: RunCtx) -> Agent:
        """Transfer when caller says they have their own material."""
        return await self._transfer_to("own_material", context)

    @function_tool
    async def transfer_to_busy_scheduler(self, context: RunCtx) -> Agent:
        """Transfer when caller wants to be called back later."""
        return await self._transfer_to("busy_scheduler", context)

    @function_tool
    async def transfer_to_material_sender(self, context: RunCtx) -> Agent:
        """Transfer when caller asks for material to be sent."""
        return await self._transfer_to("material_sender", context)

    @function_tool
    async def transfer_to_think_about_it(self, context: RunCtx) -> Agent:
        """Transfer when caller says they'll think about it."""
        return await self._transfer_to("think_about_it", context)


class NeedsAssessorAgent(BaseAgent):
    """Asks what exams the caller's students prepare for."""

    def __init__(self):
        super().__init__(instructions=NEEDS_ASSESSOR_PROMPT)

    @function_tool
    async def transfer_to_exam_pitcher(self, context: RunCtx) -> Agent:
        """Transfer to exam-specific pitch after understanding needs."""
        return await self._transfer_to("exam_pitcher", context)

    @function_tool
    async def transfer_to_not_interested(self, context: RunCtx) -> Agent:
        """Transfer when caller suddenly loses interest."""
        return await self._transfer_to("not_interested", context)


class ExamPitcherAgent(BaseAgent):
    """Uses get_knowledge to fetch exam-specific details and pitch."""

    def __init__(self):
        super().__init__(instructions=EXAM_PITCHER_PROMPT)

    @function_tool
    async def get_knowledge(self, context: RunCtx, topic: str) -> str:
        """Fetch product knowledge. Topics: product_neet_jee, product_cbse, product_foundation, value_propositions, objection_handling"""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("get_knowledge", {"topic": topic})
        if ud.brief_log:
            ud.brief_log.info(f"FUNCTION | get_knowledge | topic='{topic}'")
        content = KNOWLEDGE_BASE.get(topic)
        if content:
            return content
        return f"Topic '{topic}' not found. Available: {', '.join(KNOWLEDGE_BASE.keys())}"

    @function_tool
    async def transfer_to_closing_pitcher(self, context: RunCtx) -> Agent:
        """Transfer when caller is impressed — close the deal."""
        return await self._transfer_to("closing_pitcher", context)

    @function_tool
    async def transfer_to_not_interested(self, context: RunCtx) -> Agent:
        """Transfer when caller says not interested."""
        return await self._transfer_to("not_interested", context)

    @function_tool
    async def transfer_to_price_handler(self, context: RunCtx) -> Agent:
        """Transfer when caller asks about price."""
        return await self._transfer_to("price_handler", context)

    @function_tool
    async def transfer_to_material_sender(self, context: RunCtx) -> Agent:
        """Transfer when caller asks for material."""
        return await self._transfer_to("material_sender", context)


class ClosingPitcherAgent(BaseAgent):
    """Pushes gently for concrete action — sample, team callback, or material."""

    def __init__(self):
        super().__init__(instructions=CLOSING_PITCHER_PROMPT)

    @function_tool
    async def transfer_to_team_connect(self, context: RunCtx) -> Agent:
        """Transfer when caller wants to talk to the team."""
        return await self._transfer_to("team_connect", context)

    @function_tool
    async def transfer_to_material_sender(self, context: RunCtx) -> Agent:
        """Transfer when caller wants material sent."""
        return await self._transfer_to("material_sender", context)

    @function_tool
    async def transfer_to_busy_scheduler(self, context: RunCtx) -> Agent:
        """Transfer when caller wants callback."""
        return await self._transfer_to("busy_scheduler", context)

    @function_tool
    async def transfer_to_think_about_it(self, context: RunCtx) -> Agent:
        """Transfer when caller says they'll think about it."""
        return await self._transfer_to("think_about_it", context)


# ═════════════════════════════════════════════════════════════════
# LAYER 3: OBJECTION HANDLING
# ═════════════════════════════════════════════════════════════════

class OwnMaterialAgent(BaseAgent):
    """Handles 'we already have our own material' objection."""

    def __init__(self):
        super().__init__(instructions=OWN_MATERIAL_PROMPT)

    @function_tool
    async def transfer_to_material_sender(self, context: RunCtx) -> Agent:
        """Transfer to send sample."""
        return await self._transfer_to("material_sender", context)

    @function_tool
    async def transfer_to_team_connect(self, context: RunCtx) -> Agent:
        """Transfer when they want team."""
        return await self._transfer_to("team_connect", context)

    @function_tool
    async def transfer_to_graceful_closer(self, context: RunCtx) -> Agent:
        """Transfer to close gracefully."""
        return await self._transfer_to("graceful_closer", context)


class PriceHandlerAgent(BaseAgent):
    """Handles pricing questions without quoting numbers."""

    def __init__(self):
        super().__init__(instructions=PRICE_HANDLER_PROMPT)

    @function_tool
    async def transfer_to_material_sender(self, context: RunCtx) -> Agent:
        """Transfer to send sample."""
        return await self._transfer_to("material_sender", context)

    @function_tool
    async def transfer_to_team_connect(self, context: RunCtx) -> Agent:
        """Transfer when they want team for pricing."""
        return await self._transfer_to("team_connect", context)

    @function_tool
    async def transfer_to_graceful_closer(self, context: RunCtx) -> Agent:
        """Transfer to close gracefully."""
        return await self._transfer_to("graceful_closer", context)


class NotInterestedAgent(BaseAgent):
    """Handles firm 'not interested' with one soft clarifying question."""

    def __init__(self):
        super().__init__(instructions=NOT_INTERESTED_PROMPT)

    @function_tool
    async def transfer_to_material_sender(self, context: RunCtx) -> Agent:
        """Transfer if they soften and want material."""
        return await self._transfer_to("material_sender", context)

    @function_tool
    async def transfer_to_graceful_closer(self, context: RunCtx) -> Agent:
        """Transfer to close gracefully."""
        return await self._transfer_to("graceful_closer", context)


class ThinkAboutItAgent(BaseAgent):
    """Handles 'I'll think about it' — offers pamphlet, no pressure."""

    def __init__(self):
        super().__init__(instructions=THINK_ABOUT_IT_PROMPT)

    @function_tool
    async def transfer_to_material_sender(self, context: RunCtx) -> Agent:
        """Transfer to send pamphlet."""
        return await self._transfer_to("material_sender", context)

    @function_tool
    async def transfer_to_busy_scheduler(self, context: RunCtx) -> Agent:
        """Transfer to schedule callback."""
        return await self._transfer_to("busy_scheduler", context)

    @function_tool
    async def transfer_to_graceful_closer(self, context: RunCtx) -> Agent:
        """Transfer to close gracefully."""
        return await self._transfer_to("graceful_closer", context)


# ═════════════════════════════════════════════════════════════════
# LAYER 4: ACTION & FULFILLMENT
# ═════════════════════════════════════════════════════════════════

class MaterialSenderAgent(BaseAgent):
    """Sends pamphlet via WhatsApp or SMS."""

    def __init__(self):
        super().__init__(instructions=MATERIAL_SENDER_PROMPT)

    @function_tool
    async def send_demo_pdf_whatsapp(self, context: RunCtx) -> str:
        """Send pamphlet/catalogue over WhatsApp."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("send_demo_pdf_whatsapp", {})
        if ud.brief_log:
            ud.brief_log.info("FUNCTION | send_demo_pdf_whatsapp")

        webhook_url = os.getenv("N8N_WHATSAPP_WEBHOOK_URL", "")
        if not webhook_url:
            return "WhatsApp भेजने में problem हुई — webhook URL missing है।"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json={
                    "action": "send_pamphlet_whatsapp",
                    "phone": ud.phone_number,
                    "name": ud.caller_name,
                })
                if resp.status_code == 200:
                    ud.material_sent_via = "whatsapp"
                    return "WhatsApp pamphlet successfully भेज दिया गया।"
                return f"WhatsApp send failed — status {resp.status_code}"
        except Exception as e:
            if ud.brief_log:
                ud.brief_log.error(f"FUNCTION_ERROR | WhatsApp: {e}")
            return "WhatsApp भेजने में network error हुई।"

    @function_tool
    async def send_pamphlet_sms(self, context: RunCtx) -> str:
        """Send pamphlet link via SMS."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("send_pamphlet_sms", {})
        if ud.brief_log:
            ud.brief_log.info("FUNCTION | send_pamphlet_sms")

        webhook_url = os.getenv("N8N_SMS_WEBHOOK_URL", "")
        if not webhook_url:
            return "SMS भेजने में problem हुई — webhook URL missing है।"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json={
                    "action": "send_pamphlet_sms",
                    "phone": ud.phone_number,
                    "name": ud.caller_name,
                })
                if resp.status_code == 200:
                    ud.material_sent_via = "sms"
                    return "SMS link successfully भेज दिया गया।"
                return f"SMS send failed — status {resp.status_code}"
        except Exception as e:
            if ud.brief_log:
                ud.brief_log.error(f"FUNCTION_ERROR | SMS: {e}")
            return "SMS भेजने में network error हुई।"

    @function_tool
    async def transfer_to_email_collector(self, context: RunCtx) -> Agent:
        """Transfer when caller wants email instead."""
        return await self._transfer_to("email_collector", context)

    @function_tool
    async def transfer_to_graceful_closer(self, context: RunCtx) -> Agent:
        """Transfer to close after sending material."""
        return await self._transfer_to("graceful_closer", context)


class EmailCollectorAgent(BaseAgent):
    """Collects email address for sending material."""

    def __init__(self):
        super().__init__(instructions=EMAIL_COLLECTOR_PROMPT)

    @function_tool
    async def collect_email(self, context: RunCtx, email: str) -> str:
        """Send pamphlet to the collected email address."""
        ud = context.userdata
        ud.collected_email = email
        if ud.tracker:
            ud.tracker.log_function("collect_email", {"email": email})
        if ud.brief_log:
            ud.brief_log.info(f"FUNCTION | collect_email | email='{email}'")

        webhook_url = os.getenv("N8N_EMAIL_WEBHOOK_URL", "")
        if not webhook_url:
            return f"Email {email} noted — webhook URL missing, team will follow up."

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json={
                    "action": "send_pamphlet_email",
                    "email": email,
                    "phone": ud.phone_number,
                    "name": ud.caller_name,
                })
                if resp.status_code == 200:
                    ud.material_sent_via = "email"
                    return f"Email {email} पर pamphlet भेज दिया जाएगा।"
                return f"Email send failed — status {resp.status_code}"
        except Exception as e:
            if ud.brief_log:
                ud.brief_log.error(f"FUNCTION_ERROR | Email: {e}")
            return f"Email {email} note कर लिया — team follow up करेगी।"

    @function_tool
    async def transfer_to_material_sender(self, context: RunCtx) -> Agent:
        """Transfer back if they change to WhatsApp/SMS."""
        return await self._transfer_to("material_sender", context)

    @function_tool
    async def transfer_to_graceful_closer(self, context: RunCtx) -> Agent:
        """Transfer to close after collecting email."""
        return await self._transfer_to("graceful_closer", context)


class BusySchedulerAgent(BaseAgent):
    """Collects 2 preferred callback times."""

    def __init__(self):
        super().__init__(instructions=BUSY_SCHEDULER_PROMPT)

    @function_tool
    async def schedule_callback(self, context: RunCtx, time_1: str, time_2: str, notes: str = "") -> str:
        """Schedule manager/team callback with 2 preferred times."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("schedule_callback", {
                "time_1": time_1, "time_2": time_2, "notes": notes
            })
        if ud.brief_log:
            ud.brief_log.info(
                f"FUNCTION | schedule_callback | t1='{time_1}' | t2='{time_2}' | notes='{notes}'"
            )

        webhook_url = os.getenv("N8N_CALLBACK_WEBHOOK_URL", "")
        if not webhook_url:
            return "Callback note कर लिया — team follow up करेगी।"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json={
                    "action": "schedule_callback",
                    "phone": ud.phone_number,
                    "name": ud.caller_name,
                    "preferred_time_1": time_1,
                    "preferred_time_2": time_2,
                    "notes": notes,
                })
                if resp.status_code == 200:
                    return "Callback successfully schedule हो गया। Team preferred time पर call करेंगे।"
                return f"Callback noted but webhook returned {resp.status_code}"
        except Exception as e:
            if ud.brief_log:
                ud.brief_log.error(f"FUNCTION_ERROR | Callback: {e}")
            return "Callback note कर लिया — team follow up करेगी।"

    @function_tool
    async def transfer_to_graceful_closer(self, context: RunCtx) -> Agent:
        """Transfer to close after scheduling."""
        return await self._transfer_to("graceful_closer", context)


class TeamConnectAgent(BaseAgent):
    """Schedules team callback and optionally offers pamphlet."""

    def __init__(self):
        super().__init__(instructions=TEAM_CONNECT_PROMPT)

    @function_tool
    async def schedule_callback(self, context: RunCtx, time_1: str, time_2: str, notes: str = "") -> str:
        """Schedule team callback with 2 preferred times."""
        ud = context.userdata
        notes = f"Team callback requested. {notes}".strip()
        if ud.tracker:
            ud.tracker.log_function("schedule_callback", {
                "time_1": time_1, "time_2": time_2, "notes": notes
            })
        if ud.brief_log:
            ud.brief_log.info(
                f"FUNCTION | schedule_callback (manager) | t1='{time_1}' | t2='{time_2}'"
            )

        webhook_url = os.getenv("N8N_CALLBACK_WEBHOOK_URL", "")
        if not webhook_url:
            return "Manager callback note कर लिया — team follow up करेगी।"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json={
                    "action": "schedule_callback",
                    "phone": ud.phone_number,
                    "name": ud.caller_name,
                    "preferred_time_1": time_1,
                    "preferred_time_2": time_2,
                    "notes": notes,
                })
                if resp.status_code == 200:
                    return "Team callback schedule हो गया।"
                return f"Callback noted but webhook returned {resp.status_code}"
        except Exception as e:
            if ud.brief_log:
                ud.brief_log.error(f"FUNCTION_ERROR | Team callback: {e}")
            return "Team callback note कर लिया।"

    @function_tool
    async def transfer_to_material_sender(self, context: RunCtx) -> Agent:
        """Transfer to send pamphlet while they wait for team callback."""
        return await self._transfer_to("material_sender", context)

    @function_tool
    async def transfer_to_graceful_closer(self, context: RunCtx) -> Agent:
        """Transfer to close after scheduling team callback."""
        return await self._transfer_to("graceful_closer", context)


# ═════════════════════════════════════════════════════════════════
# LAYER 5: CLOSING
# ═════════════════════════════════════════════════════════════════

class GracefulCloserAgent(BaseAgent):
    """Warm goodbye and MUST tag the lead before ending."""

    def __init__(self):
        super().__init__(instructions=GRACEFUL_CLOSER_PROMPT)

    @function_tool
    async def tag_lead(self, context: RunCtx, tag: str, notes: str = "") -> str:
        """Tag the lead with final outcome. MUST be called before call ends."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("tag_lead", {"tag": tag, "notes": notes})
        if ud.brief_log:
            ud.brief_log.info(f"FUNCTION | tag_lead | tag='{tag}' | notes='{notes}'")
        return f"Lead successfully tagged as {tag}."


class HostileExitAgent(BaseAgent):
    """Calm professional exit when caller is rude/hostile."""

    def __init__(self):
        super().__init__(instructions=HOSTILE_EXIT_PROMPT)

    @function_tool
    async def tag_lead(self, context: RunCtx, tag: str, notes: str = "") -> str:
        """Tag lead as Not Interested with hostile notes."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("tag_lead", {"tag": tag, "notes": notes})
        if ud.brief_log:
            ud.brief_log.info(f"FUNCTION | tag_lead (hostile) | tag='{tag}' | notes='{notes}'")
        return f"Lead tagged as {tag}."


# ═════════════════════════════════════════════════════════════════
# LAYER 6: EDGE CASES
# ═════════════════════════════════════════════════════════════════

class WrongNumberAgent(BaseAgent):
    """Apologizes and ends call for wrong numbers."""

    def __init__(self):
        super().__init__(instructions=WRONG_NUMBER_PROMPT)

    @function_tool
    async def tag_lead(self, context: RunCtx, tag: str, notes: str = "") -> str:
        """Tag lead as Wrong Contact."""
        ud = context.userdata
        if ud.tracker:
            ud.tracker.log_function("tag_lead", {"tag": tag, "notes": notes})
        if ud.brief_log:
            ud.brief_log.info(f"FUNCTION | tag_lead (wrong#) | tag='{tag}' | notes='{notes}'")
        return f"Lead tagged as {tag}."


class ReEngagerAgent(BaseAgent):
    """Re-engages silent callers with 2 attempts."""

    def __init__(self):
        super().__init__(instructions=REENGAGER_PROMPT)

    @function_tool
    async def transfer_to_identity_confirmer(self, context: RunCtx) -> Agent:
        """Transfer back to identity check if caller responds."""
        return await self._transfer_to("identity_confirmer", context)

    @function_tool
    async def transfer_to_graceful_closer(self, context: RunCtx) -> Agent:
        """Transfer to close if still no response."""
        return await self._transfer_to("graceful_closer", context)


# ═════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═════════════════════════════════════════════════════════════════

async def entrypoint(ctx: JobContext):
    call_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    loggers = setup_loggers(call_id)
    full_log, brief_log, token_log, cost_log, llm_log, transcript_log = loggers

    # Read caller info from dispatch metadata
    caller_name = "ji"
    call_type = "name"
    phone_number = ""
    try:
        meta = json.loads(ctx.job.metadata or "{}")
        caller_name = meta.get("name", "ji") or "ji"
        call_type = meta.get("call_type", "name") or "name"
        phone_number = meta.get("phone", "") or ""
        full_log.info(f"Dispatch: name={caller_name}, type={call_type}, phone={phone_number}")
    except Exception:
        pass

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    full_log.info("=" * 60)
    full_log.info(f"📞 NEW CALL | ID: {call_id} | Room: {ctx.room.name}")
    full_log.info(f"📋 Type: {call_type} | Name: {caller_name} | Phone: {phone_number}")
    full_log.info("=" * 60)
    brief_log.info(f"CALL_START | {call_id} | type={call_type} | name={caller_name}")

    tracker = CostTracker(call_id=call_id)

    # ── Create shared state ─────────────────────────────────────
    userdata = CallUserData(
        caller_name=caller_name,
        call_type=call_type,
        phone_number=phone_number,
        tracker=tracker,
        brief_log=brief_log,
        ctx=ctx,
    )

    # ── Instantiate all 20 agents ────────────────────────────────
    agents = {
        "greeter": GreeterAgent(caller_name=caller_name, call_type=call_type),
        "identity_confirmer": IdentityConfirmerAgent(caller_name=caller_name, call_type=call_type),
        "gatekeeper": GatekeeperAgent(caller_name=caller_name),
        "hold_waiter": HoldWaiterAgent(),
        "intro": IntroAgent(),
        "needs_assessor": NeedsAssessorAgent(),
        "exam_pitcher": ExamPitcherAgent(),
        "closing_pitcher": ClosingPitcherAgent(),
        "own_material": OwnMaterialAgent(),
        "price_handler": PriceHandlerAgent(),
        "not_interested": NotInterestedAgent(),
        "think_about_it": ThinkAboutItAgent(),
        "material_sender": MaterialSenderAgent(),
        "email_collector": EmailCollectorAgent(),
        "busy_scheduler": BusySchedulerAgent(),
        "team_connect": TeamConnectAgent(),
        "graceful_closer": GracefulCloserAgent(),
        "hostile_exit": HostileExitAgent(),
        "wrong_number": WrongNumberAgent(),
        "reengager": ReEngagerAgent(),
    }
    userdata.personas = agents

    # ── Plugins ──────────────────────────────────────────────────
    llm_plugin = anthropic.LLM(
        model="claude-haiku-4-5-20251001",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
    )

    stt_plugin = sarvam.STT(
        language="en-IN",
        model="saaras:v3",
    )

    tts_plugin = sarvam.TTS(
        target_language_code="hi-IN",
        model="bulbul:v3",
        speaker="shubh",
    )

    # ── Session ──────────────────────────────────────────────────
    session = AgentSession[CallUserData](
        llm=llm_plugin,
        stt=stt_plugin,
        tts=tts_plugin,
        userdata=userdata,
        user_away_timeout=10,  # seconds of silence before triggering user_state_changed → away
    )

    # ── Metrics ──────────────────────────────────────────────────
    @session.on("metrics_collected")
    def on_metrics(event):
        try:
            m = event.metrics
            metric_type = getattr(m, "type", "")

            if metric_type in ("llm_metrics", "realtime_model_metrics"):
                input_t = getattr(m, "prompt_tokens", getattr(m, "input_tokens", 0)) or 0
                output_t = getattr(m, "completion_tokens", getattr(m, "output_tokens", 0)) or 0
                cancelled = getattr(m, "cancelled", False)
                if not cancelled and input_t > 0:
                    tracker.log_llm(input_t, output_t)
                    token_log.info(
                        f"LLM | in={input_t} out={output_t} | "
                        f"cum_in={tracker.llm_input_tokens_total} cum_out={tracker.llm_output_tokens_total}"
                    )
                    full_log.info(f"📊 LLM | in={input_t} out={output_t} tokens")
                    llm_log.info(f"=== LLM TURN: {input_t} IN | {output_t} OUT ===")
                    try:
                        for msg in session.chat_ctx.messages:
                            role = str(msg.role).upper().replace("ROLES.", "")
                            llm_log.info(f"[{role}]: {msg.content}")
                    except Exception as e:
                        llm_log.error(f"Chat context dump failed: {e}")
                    llm_log.info("=========================================\n")
                elif cancelled:
                    full_log.info("📊 LLM turn cancelled")

            elif metric_type == "tts_metrics":
                chars = getattr(m, "characters_count", 0) or 0
                audio_dur = getattr(m, "audio_duration", 0) or 0
                cancelled = getattr(m, "cancelled", False)
                if not cancelled and chars > 0:
                    tracker.tts_chars_total += chars
                    tracker.tts_active_seconds += audio_dur
                    token_log.info(f"TTS | chars={chars} audio={audio_dur:.2f}s")
                    full_log.info(f"🔊 TTS | {chars} chars → {audio_dur:.2f}s")

            elif metric_type == "stt_metrics":
                audio_dur = getattr(m, "audio_duration", 0) or 0
                if audio_dur > 0:
                    tracker.stt_active_seconds += audio_dur
                    token_log.info(f"STT | audio={audio_dur:.2f}s total={tracker.stt_active_seconds:.2f}s")
                    full_log.info(f"🎤 STT | {audio_dur:.2f}s")

        except Exception as e:
            full_log.error(f"Metrics hook error: {e}")

    @session.on("agent_speech_committed")
    def on_agent_speech(msg):
        if msg and msg.content:
            transcript_log.info(f"Agent: {msg.content}")

    @session.on("user_speech_committed")
    def on_user_speech(msg):
        if msg and msg.content:
            transcript_log.info(f"User: {msg.content}")

    # ── Silence detection ────────────────────────────────────────
    # If user doesn't speak for 10s, auto-transfer to ReEngagerAgent.
    # This is system-level code, NOT reliant on LLM detecting silence.
    inactivity_task: asyncio.Task | None = None

    @session.on("user_state_changed")
    def on_user_state_changed(ev: UserStateChangedEvent):
        nonlocal inactivity_task
        if ev.new_state == "away":
            brief_log.info("SILENCE | user_away detected — transferring to ReEngagerAgent")
            # Transfer to reengager without delay (user_away_timeout already waited)
            session.update_agent(agents["reengager"])
            return

        # User came back (speaking/listening) — cancel any pending inactivity task
        if inactivity_task is not None:
            inactivity_task.cancel()
            inactivity_task = None

    # ── Periodic cost log ────────────────────────────────────────
    async def periodic_cost_log():
        while True:
            await asyncio.sleep(5)
            c = tracker.calculate_costs()
            full_log.info(
                f"💰 COST | {c['duration_minutes']:.2f}min | "
                f"LLM in={c['llm_input_tokens']} out={c['llm_output_tokens']} | "
                f"₹{c['total_cost_inr']:.4f}"
            )

    full_log.info("Agent Session started — 20-agent multi-agent architecture.")
    cost_task = asyncio.create_task(periodic_cost_log())

    # ── Cleanup ──────────────────────────────────────────────────
    def shutdown_call(reason="room disconnected"):
        full_log.info(f"Closing Session | Reason: {reason}")
        cost_task.cancel()
        brief_log.info(f"CALL_END | {reason}")
        write_cost_report(tracker=tracker, full_log=full_log, cost_log=cost_log, brief_log=brief_log)
        full_log.info("Session closed.")

    @ctx.room.on("disconnected")
    def on_disconnected(*args):
        shutdown_call("room disconnected")

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        shutdown_call(f"participant {participant.identity} disconnected")

    # ── Start with GreeterAgent ──────────────────────────────────
    await session.start(room=ctx.room, agent=agents["greeter"])


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="UniversalBooksAgent",
        )
    )
