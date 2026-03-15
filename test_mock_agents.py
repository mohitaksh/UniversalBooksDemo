"""
test_mock_agents.py
───────────────────
Lightweight mocks of all 20 agents for unit testing.
Mirrors real agents' tools without requiring a live AgentSession.
"""

import os
from livekit.agents import Agent
from prompts import KNOWLEDGE_BASE


class MockBaseAgent(Agent):
    """Mock base — tracks all tool calls."""

    def __init__(self, instructions="Mock"):
        super().__init__(instructions=instructions)
        self.tagged_leads = []
        self.whatsapp_calls = []
        self.sms_calls = []
        self.email_calls = []
        self.callback_calls = []
        self.knowledge_calls = []
        self.transfers = []

    async def _mock_transfer(self, target: str, context=None):
        self.transfers.append(target)
        return f"Transferred to {target}"

    async def tag_lead(self, context, tag: str, notes: str = "") -> str:
        allowed = ["Interested", "Send Sample", "Call Back", "Not Interested", "Wrong Contact"]
        if tag not in allowed:
            return f"Invalid tag '{tag}'. Must be one of: {allowed}"
        self.tagged_leads.append({"tag": tag, "notes": notes})
        return f"Lead tagged as {tag}."


# ── Layer 1 ─────────────────────────────────────────────────────

class MockGreeterAgent(MockBaseAgent):
    def __init__(self, caller_name="ji", call_type="name"):
        super().__init__("Greeter")
        self.caller_name = caller_name
        self.call_type = call_type


class MockIdentityConfirmerAgent(MockBaseAgent):
    def __init__(self, caller_name="ji", call_type="name"):
        super().__init__("IdentityConfirmer")
        self.caller_name = caller_name
        self.call_type = call_type

    async def transfer_to_intro(self, ctx): return await self._mock_transfer("intro", ctx)
    async def transfer_to_gatekeeper(self, ctx): return await self._mock_transfer("gatekeeper", ctx)
    async def transfer_to_busy_scheduler(self, ctx): return await self._mock_transfer("busy_scheduler", ctx)
    async def transfer_to_wrong_number(self, ctx): return await self._mock_transfer("wrong_number", ctx)
    async def transfer_to_hostile_exit(self, ctx): return await self._mock_transfer("hostile_exit", ctx)
    async def transfer_to_reengager(self, ctx): return await self._mock_transfer("reengager", ctx)


class MockGatekeeperAgent(MockBaseAgent):
    def __init__(self, caller_name="ji"):
        super().__init__("Gatekeeper")
        self.caller_name = caller_name

    async def transfer_to_hold_waiter(self, ctx): return await self._mock_transfer("hold_waiter", ctx)
    async def transfer_to_busy_scheduler(self, ctx): return await self._mock_transfer("busy_scheduler", ctx)
    async def transfer_to_graceful_closer(self, ctx): return await self._mock_transfer("graceful_closer", ctx)
    async def transfer_to_hostile_exit(self, ctx): return await self._mock_transfer("hostile_exit", ctx)


class MockHoldWaiterAgent(MockBaseAgent):
    async def transfer_to_intro(self, ctx): return await self._mock_transfer("intro", ctx)
    async def transfer_to_graceful_closer(self, ctx): return await self._mock_transfer("graceful_closer", ctx)


# ── Layer 2 ─────────────────────────────────────────────────────

class MockIntroAgent(MockBaseAgent):
    async def transfer_to_needs_assessor(self, ctx): return await self._mock_transfer("needs_assessor", ctx)
    async def transfer_to_not_interested(self, ctx): return await self._mock_transfer("not_interested", ctx)
    async def transfer_to_price_handler(self, ctx): return await self._mock_transfer("price_handler", ctx)
    async def transfer_to_own_material(self, ctx): return await self._mock_transfer("own_material", ctx)
    async def transfer_to_busy_scheduler(self, ctx): return await self._mock_transfer("busy_scheduler", ctx)
    async def transfer_to_material_sender(self, ctx): return await self._mock_transfer("material_sender", ctx)
    async def transfer_to_think_about_it(self, ctx): return await self._mock_transfer("think_about_it", ctx)


class MockNeedsAssessorAgent(MockBaseAgent):
    async def transfer_to_exam_pitcher(self, ctx): return await self._mock_transfer("exam_pitcher", ctx)
    async def transfer_to_not_interested(self, ctx): return await self._mock_transfer("not_interested", ctx)


class MockExamPitcherAgent(MockBaseAgent):
    async def get_knowledge(self, context, topic: str) -> str:
        self.knowledge_calls.append({"topic": topic})
        content = KNOWLEDGE_BASE.get(topic)
        if content:
            return content
        return f"Topic '{topic}' not found. Available: {', '.join(KNOWLEDGE_BASE.keys())}"

    async def transfer_to_closing_pitcher(self, ctx): return await self._mock_transfer("closing_pitcher", ctx)
    async def transfer_to_not_interested(self, ctx): return await self._mock_transfer("not_interested", ctx)
    async def transfer_to_price_handler(self, ctx): return await self._mock_transfer("price_handler", ctx)
    async def transfer_to_material_sender(self, ctx): return await self._mock_transfer("material_sender", ctx)


class MockClosingPitcherAgent(MockBaseAgent):
    async def transfer_to_team_connect(self, ctx): return await self._mock_transfer("team_connect", ctx)
    async def transfer_to_material_sender(self, ctx): return await self._mock_transfer("material_sender", ctx)
    async def transfer_to_busy_scheduler(self, ctx): return await self._mock_transfer("busy_scheduler", ctx)
    async def transfer_to_think_about_it(self, ctx): return await self._mock_transfer("think_about_it", ctx)


# ── Layer 3 ─────────────────────────────────────────────────────

class MockOwnMaterialAgent(MockBaseAgent):
    async def transfer_to_material_sender(self, ctx): return await self._mock_transfer("material_sender", ctx)
    async def transfer_to_team_connect(self, ctx): return await self._mock_transfer("team_connect", ctx)
    async def transfer_to_graceful_closer(self, ctx): return await self._mock_transfer("graceful_closer", ctx)


class MockPriceHandlerAgent(MockBaseAgent):
    async def transfer_to_material_sender(self, ctx): return await self._mock_transfer("material_sender", ctx)
    async def transfer_to_team_connect(self, ctx): return await self._mock_transfer("team_connect", ctx)
    async def transfer_to_graceful_closer(self, ctx): return await self._mock_transfer("graceful_closer", ctx)


class MockNotInterestedAgent(MockBaseAgent):
    async def transfer_to_material_sender(self, ctx): return await self._mock_transfer("material_sender", ctx)
    async def transfer_to_graceful_closer(self, ctx): return await self._mock_transfer("graceful_closer", ctx)


class MockThinkAboutItAgent(MockBaseAgent):
    async def transfer_to_material_sender(self, ctx): return await self._mock_transfer("material_sender", ctx)
    async def transfer_to_busy_scheduler(self, ctx): return await self._mock_transfer("busy_scheduler", ctx)
    async def transfer_to_graceful_closer(self, ctx): return await self._mock_transfer("graceful_closer", ctx)


# ── Layer 4 ─────────────────────────────────────────────────────

class MockMaterialSenderAgent(MockBaseAgent):
    async def send_demo_pdf_whatsapp(self, context) -> str:
        url = os.getenv("N8N_WHATSAPP_WEBHOOK_URL", "")
        if not url:
            return "WhatsApp भेजने में problem हुई — webhook URL missing है।"
        self.whatsapp_calls.append({"url": url})
        return "WhatsApp pamphlet successfully भेज दिया गया।"

    async def send_pamphlet_sms(self, context) -> str:
        url = os.getenv("N8N_SMS_WEBHOOK_URL", "")
        if not url:
            return "SMS भेजने में problem हुई — webhook URL missing है।"
        self.sms_calls.append({"url": url})
        return "SMS link successfully भेज दिया गया।"

    async def transfer_to_email_collector(self, ctx): return await self._mock_transfer("email_collector", ctx)
    async def transfer_to_graceful_closer(self, ctx): return await self._mock_transfer("graceful_closer", ctx)


class MockEmailCollectorAgent(MockBaseAgent):
    async def collect_email(self, context, email: str) -> str:
        self.email_calls.append({"email": email})
        return f"Email {email} पर pamphlet भेज दिया जाएगा।"

    async def transfer_to_material_sender(self, ctx): return await self._mock_transfer("material_sender", ctx)
    async def transfer_to_graceful_closer(self, ctx): return await self._mock_transfer("graceful_closer", ctx)


class MockBusySchedulerAgent(MockBaseAgent):
    async def schedule_callback(self, context, time_1: str, time_2: str, notes: str = "") -> str:
        self.callback_calls.append({"time_1": time_1, "time_2": time_2, "notes": notes})
        return "Callback successfully schedule हो गया।"

    async def transfer_to_graceful_closer(self, ctx): return await self._mock_transfer("graceful_closer", ctx)


class MockTeamConnectAgent(MockBaseAgent):
    async def schedule_callback(self, context, time_1: str, time_2: str, notes: str = "") -> str:
        self.callback_calls.append({"time_1": time_1, "time_2": time_2, "notes": f"Team callback. {notes}"})
        return "Team callback schedule हो गया।"

    async def transfer_to_material_sender(self, ctx): return await self._mock_transfer("material_sender", ctx)
    async def transfer_to_graceful_closer(self, ctx): return await self._mock_transfer("graceful_closer", ctx)


# ── Layer 5 ─────────────────────────────────────────────────────

class MockGracefulCloserAgent(MockBaseAgent):
    pass  # inherits tag_lead from MockBaseAgent


class MockHostileExitAgent(MockBaseAgent):
    pass  # inherits tag_lead from MockBaseAgent


# ── Layer 6 ─────────────────────────────────────────────────────

class MockWrongNumberAgent(MockBaseAgent):
    pass  # inherits tag_lead from MockBaseAgent


class MockReEngagerAgent(MockBaseAgent):
    async def transfer_to_identity_confirmer(self, ctx): return await self._mock_transfer("identity_confirmer", ctx)
    async def transfer_to_graceful_closer(self, ctx): return await self._mock_transfer("graceful_closer", ctx)
