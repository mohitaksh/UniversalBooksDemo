"""
test_agent.py
─────────────
Unit tests for the 20-agent Universal Books multi-agent architecture.
Tests tools, handoffs, knowledge base, and agent identity.

Run:  pytest test_agent.py -v
"""

import pytest
from unittest.mock import MagicMock
from test_mock_agents import (
    MockGreeterAgent, MockIdentityConfirmerAgent, MockGatekeeperAgent,
    MockHoldWaiterAgent, MockIntroAgent, MockNeedsAssessorAgent,
    MockExamPitcherAgent, MockClosingPitcherAgent,
    MockOwnMaterialAgent, MockPriceHandlerAgent, MockNotInterestedAgent,
    MockThinkAboutItAgent,
    MockMaterialSenderAgent, MockEmailCollectorAgent,
    MockBusySchedulerAgent, MockTeamConnectAgent,
    MockGracefulCloserAgent, MockHostileExitAgent,
    MockWrongNumberAgent, MockReEngagerAgent,
)


@pytest.fixture
def ctx():
    return MagicMock()


# ═══════════════════════════════════════════════════════════════
# LAYER 1: FIRST CONTACT
# ═══════════════════════════════════════════════════════════════

class TestGreeterAgent:
    def test_name_call_type(self):
        a = MockGreeterAgent(caller_name="Santosh Kumar", call_type="name")
        assert a.caller_name == "Santosh Kumar"
        assert a.call_type == "name"

    def test_institution_call_type(self):
        a = MockGreeterAgent(caller_name="Tiwari Tutorials", call_type="institution")
        assert a.call_type == "institution"


class TestIdentityConfirmerAgent:
    @pytest.mark.asyncio
    async def test_transfers_to_intro(self, ctx):
        a = MockIdentityConfirmerAgent()
        result = await a.transfer_to_intro(ctx)
        assert "intro" in result
        assert a.transfers == ["intro"]

    @pytest.mark.asyncio
    async def test_transfers_to_gatekeeper(self, ctx):
        a = MockIdentityConfirmerAgent()
        await a.transfer_to_gatekeeper(ctx)
        assert a.transfers == ["gatekeeper"]

    @pytest.mark.asyncio
    async def test_transfers_to_busy(self, ctx):
        a = MockIdentityConfirmerAgent()
        await a.transfer_to_busy_scheduler(ctx)
        assert a.transfers == ["busy_scheduler"]

    @pytest.mark.asyncio
    async def test_transfers_to_wrong_number(self, ctx):
        a = MockIdentityConfirmerAgent()
        await a.transfer_to_wrong_number(ctx)
        assert a.transfers == ["wrong_number"]

    @pytest.mark.asyncio
    async def test_transfers_to_hostile(self, ctx):
        a = MockIdentityConfirmerAgent()
        await a.transfer_to_hostile_exit(ctx)
        assert a.transfers == ["hostile_exit"]

    @pytest.mark.asyncio
    async def test_transfers_to_reengager(self, ctx):
        a = MockIdentityConfirmerAgent()
        await a.transfer_to_reengager(ctx)
        assert a.transfers == ["reengager"]

    @pytest.mark.asyncio
    async def test_tag_lead(self, ctx):
        a = MockIdentityConfirmerAgent()
        result = await a.tag_lead(ctx, tag="Wrong Contact", notes="wrong person")
        assert "Wrong Contact" in result
        assert a.tagged_leads[0]["tag"] == "Wrong Contact"


class TestGatekeeperAgent:
    @pytest.mark.asyncio
    async def test_all_transfers(self, ctx):
        a = MockGatekeeperAgent()
        await a.transfer_to_hold_waiter(ctx)
        await a.transfer_to_busy_scheduler(ctx)
        await a.transfer_to_graceful_closer(ctx)
        await a.transfer_to_hostile_exit(ctx)
        assert a.transfers == ["hold_waiter", "busy_scheduler", "graceful_closer", "hostile_exit"]


# ═══════════════════════════════════════════════════════════════
# LAYER 2: PITCH & DISCOVERY
# ═══════════════════════════════════════════════════════════════

class TestIntroAgent:
    @pytest.mark.asyncio
    async def test_all_7_transfers(self, ctx):
        a = MockIntroAgent()
        await a.transfer_to_needs_assessor(ctx)
        await a.transfer_to_not_interested(ctx)
        await a.transfer_to_price_handler(ctx)
        await a.transfer_to_own_material(ctx)
        await a.transfer_to_busy_scheduler(ctx)
        await a.transfer_to_material_sender(ctx)
        await a.transfer_to_think_about_it(ctx)
        assert len(a.transfers) == 7


class TestExamPitcherAgent:
    @pytest.mark.asyncio
    async def test_knowledge_neet_jee(self, ctx):
        a = MockExamPitcherAgent()
        result = await a.get_knowledge(ctx, topic="product_neet_jee")
        assert "NEET" in result
        assert "JEE" in result

    @pytest.mark.asyncio
    async def test_knowledge_cbse(self, ctx):
        a = MockExamPitcherAgent()
        result = await a.get_knowledge(ctx, topic="product_cbse")
        assert "CBSE" in result

    @pytest.mark.asyncio
    async def test_knowledge_foundation(self, ctx):
        a = MockExamPitcherAgent()
        result = await a.get_knowledge(ctx, topic="product_foundation")
        assert "Foundation" in result

    @pytest.mark.asyncio
    async def test_knowledge_all_topics(self, ctx):
        a = MockExamPitcherAgent()
        for topic in ["product_neet_jee", "product_cbse", "product_foundation", "objection_handling", "value_propositions"]:
            result = await a.get_knowledge(ctx, topic=topic)
            assert "not found" not in result.lower()
        assert len(a.knowledge_calls) == 5

    @pytest.mark.asyncio
    async def test_knowledge_invalid_topic(self, ctx):
        a = MockExamPitcherAgent()
        result = await a.get_knowledge(ctx, topic="nonexistent")
        assert "not found" in result.lower()
        assert "product_neet_jee" in result


# ═══════════════════════════════════════════════════════════════
# LAYER 3: OBJECTION HANDLING
# ═══════════════════════════════════════════════════════════════

class TestOwnMaterialAgent:
    @pytest.mark.asyncio
    async def test_transfers(self, ctx):
        a = MockOwnMaterialAgent()
        await a.transfer_to_material_sender(ctx)
        await a.transfer_to_manager_connect(ctx)
        await a.transfer_to_graceful_closer(ctx)
        assert a.transfers == ["material_sender", "manager_connect", "graceful_closer"]


class TestNotInterestedAgent:
    @pytest.mark.asyncio
    async def test_transfers(self, ctx):
        a = MockNotInterestedAgent()
        await a.transfer_to_material_sender(ctx)
        await a.transfer_to_graceful_closer(ctx)
        assert a.transfers == ["material_sender", "graceful_closer"]


class TestThinkAboutItAgent:
    @pytest.mark.asyncio
    async def test_transfers(self, ctx):
        a = MockThinkAboutItAgent()
        await a.transfer_to_material_sender(ctx)
        await a.transfer_to_busy_scheduler(ctx)
        await a.transfer_to_graceful_closer(ctx)
        assert a.transfers == ["material_sender", "busy_scheduler", "graceful_closer"]


# ═══════════════════════════════════════════════════════════════
# LAYER 4: ACTION & FULFILLMENT
# ═══════════════════════════════════════════════════════════════

class TestMaterialSenderAgent:
    @pytest.mark.asyncio
    async def test_whatsapp_succeeds(self, ctx, monkeypatch):
        monkeypatch.setenv("N8N_WHATSAPP_WEBHOOK_URL", "https://example.com/wa")
        a = MockMaterialSenderAgent()
        result = await a.send_demo_pdf_whatsapp(ctx)
        assert "successfully" in result
        assert len(a.whatsapp_calls) == 1

    @pytest.mark.asyncio
    async def test_whatsapp_fails_no_url(self, ctx, monkeypatch):
        monkeypatch.setenv("N8N_WHATSAPP_WEBHOOK_URL", "")
        a = MockMaterialSenderAgent()
        result = await a.send_demo_pdf_whatsapp(ctx)
        assert "missing" in result

    @pytest.mark.asyncio
    async def test_sms_succeeds(self, ctx, monkeypatch):
        monkeypatch.setenv("N8N_SMS_WEBHOOK_URL", "https://example.com/sms")
        a = MockMaterialSenderAgent()
        result = await a.send_pamphlet_sms(ctx)
        assert "successfully" in result
        assert len(a.sms_calls) == 1

    @pytest.mark.asyncio
    async def test_sms_fails_no_url(self, ctx, monkeypatch):
        monkeypatch.setenv("N8N_SMS_WEBHOOK_URL", "")
        a = MockMaterialSenderAgent()
        result = await a.send_pamphlet_sms(ctx)
        assert "missing" in result


class TestEmailCollectorAgent:
    @pytest.mark.asyncio
    async def test_collect_email(self, ctx):
        a = MockEmailCollectorAgent()
        result = await a.collect_email(ctx, email="teacher@school.com")
        assert "teacher@school.com" in result
        assert a.email_calls[0]["email"] == "teacher@school.com"


class TestBusySchedulerAgent:
    @pytest.mark.asyncio
    async def test_schedule_callback(self, ctx):
        a = MockBusySchedulerAgent()
        result = await a.schedule_callback(ctx, time_1="कल दोपहर 2 बजे", time_2="कल शाम 6 बजे")
        assert "schedule" in result
        assert a.callback_calls[0]["time_1"] == "कल दोपहर 2 बजे"
        assert a.callback_calls[0]["time_2"] == "कल शाम 6 बजे"


class TestTeamConnectAgent:
    @pytest.mark.asyncio
    async def test_schedule_team_callback(self, ctx):
        a = MockTeamConnectAgent()
        result = await a.schedule_callback(ctx, time_1="Tomorrow 10 AM", time_2="Tomorrow 6 PM", notes="NEET discussion")
        assert "Team" in result
        assert "Team callback" in a.callback_calls[0]["notes"]


# ═══════════════════════════════════════════════════════════════
# LAYER 5: CLOSING
# ═══════════════════════════════════════════════════════════════

class TestGracefulCloserAgent:
    @pytest.mark.asyncio
    async def test_tag_lead_all_valid(self, ctx):
        a = MockGracefulCloserAgent()
        for tag in ["Interested", "Send Sample", "Call Back", "Not Interested", "Wrong Contact"]:
            result = await a.tag_lead(ctx, tag=tag)
            assert tag in result
        assert len(a.tagged_leads) == 5

    @pytest.mark.asyncio
    async def test_tag_lead_invalid(self, ctx):
        a = MockGracefulCloserAgent()
        result = await a.tag_lead(ctx, tag="Random")
        assert "Invalid" in result

    @pytest.mark.asyncio
    async def test_tag_lead_with_notes(self, ctx):
        a = MockGracefulCloserAgent()
        await a.tag_lead(ctx, tag="Interested", notes="Wants NEET modules")
        assert a.tagged_leads[0]["notes"] == "Wants NEET modules"


class TestHostileExitAgent:
    @pytest.mark.asyncio
    async def test_tag_lead(self, ctx):
        a = MockHostileExitAgent()
        result = await a.tag_lead(ctx, tag="Not Interested", notes="caller was rude")
        assert "Not Interested" in result


# ═══════════════════════════════════════════════════════════════
# LAYER 6: EDGE CASES
# ═══════════════════════════════════════════════════════════════

class TestWrongNumberAgent:
    @pytest.mark.asyncio
    async def test_tag_lead(self, ctx):
        a = MockWrongNumberAgent()
        result = await a.tag_lead(ctx, tag="Wrong Contact", notes="wrong number")
        assert "Wrong Contact" in result


class TestReEngagerAgent:
    @pytest.mark.asyncio
    async def test_transfers(self, ctx):
        a = MockReEngagerAgent()
        await a.transfer_to_identity_confirmer(ctx)
        await a.transfer_to_graceful_closer(ctx)
        assert a.transfers == ["identity_confirmer", "graceful_closer"]


# ═══════════════════════════════════════════════════════════════
# AGENT COUNT
# ═══════════════════════════════════════════════════════════════

def test_total_agent_count():
    """Sanity check: we have 20 mock agent classes."""
    from test_mock_agents import (
        MockGreeterAgent, MockIdentityConfirmerAgent, MockGatekeeperAgent,
        MockHoldWaiterAgent, MockIntroAgent, MockNeedsAssessorAgent,
        MockExamPitcherAgent, MockClosingPitcherAgent,
        MockOwnMaterialAgent, MockPriceHandlerAgent, MockNotInterestedAgent,
        MockThinkAboutItAgent,
        MockMaterialSenderAgent, MockEmailCollectorAgent,
        MockBusySchedulerAgent, MockTeamConnectAgent,
        MockGracefulCloserAgent, MockHostileExitAgent,
        MockWrongNumberAgent, MockReEngagerAgent,
    )
    agents = [
        MockGreeterAgent, MockIdentityConfirmerAgent, MockGatekeeperAgent,
        MockHoldWaiterAgent, MockIntroAgent, MockNeedsAssessorAgent,
        MockExamPitcherAgent, MockClosingPitcherAgent,
        MockOwnMaterialAgent, MockPriceHandlerAgent, MockNotInterestedAgent,
        MockThinkAboutItAgent,
        MockMaterialSenderAgent, MockEmailCollectorAgent,
        MockBusySchedulerAgent, MockTeamConnectAgent,
        MockGracefulCloserAgent, MockHostileExitAgent,
        MockWrongNumberAgent, MockReEngagerAgent,
    ]
    assert len(agents) == 20
