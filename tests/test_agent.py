"""Integration and unit tests for the agent orchestration layer (src/agent).

Tests the LangGraph workflow, deterministic policy enforcement, storage persistence,
and audit logging across all canonical examples from docs/SYSTEM_DESIGN.md.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from dotenv import load_dotenv

from src.agent import AgentOrchestrator, AgentRequest, AgentTools, get_llm
from src.agent.llm import extract_entities_with_fallback
from src.policy import PolicyEngine
from src.retrieval import UnifiedRetriever
from src.storage import Store

load_dotenv()


class TestAgentExtraction(unittest.TestCase):
    """Test heuristic & fallback entity extraction."""

    def test_phishing_extraction(self) -> None:
        text = "I received a suspicious phishing email asking for login credentials."
        entities = extract_entities_with_fallback(text, llm=None)
        self.assertEqual(entities["category"], "Security Incident")
        self.assertEqual(entities["priority_or_risk"], "critical")

    def test_guest_wifi_extraction(self) -> None:
        text = "Can I get Wi-Fi access for a guest visitor tomorrow?"
        entities = extract_entities_with_fallback(text, llm=None)
        self.assertEqual(entities["category"], "Guest Wi-Fi")
        self.assertTrue(entities["is_guest_wifi"])

    def test_contractor_vpn_extraction(self) -> None:
        text = "I am a contractor and I need VPN setup for my client work."
        entities = extract_entities_with_fallback(text, llm=None)
        self.assertEqual(entities["category"], "VPN")
        self.assertEqual(entities["employee_type"], "contractor")

    def test_non_catalog_software_extraction(self) -> None:
        text = "I want to install an unapproved tool that is not in the catalog."
        entities = extract_entities_with_fallback(text, llm=None)
        self.assertEqual(entities["category"], "Software Installation")
        self.assertFalse(entities["is_catalog_software"])

    def test_laptop_age_extraction(self) -> None:
        text = "My laptop is 4.5 years old and running slow."
        entities = extract_entities_with_fallback(text, llm=None)
        self.assertEqual(entities["category"], "Laptop/Hardware")
        self.assertEqual(entities["laptop_age_years"], 4.5)


class TestAgentTools(unittest.TestCase):
    """Test AgentTools wrapper functions."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.store = Store(db_path=self.tmp.name, seed=True)
        self.retriever = UnifiedRetriever(store=self.store, db_path=self.tmp.name)
        self.policy_engine = PolicyEngine()
        self.tools = AgentTools(
            retriever=self.retriever,
            policy_engine=self.policy_engine,
            store=self.store,
        )

    def tearDown(self) -> None:
        self.store.close()
        self.retriever.close()
        if os.path.exists(self.tmp.name):
            try:
                os.unlink(self.tmp.name)
            except OSError:
                pass

    def test_search_knowledge_base(self) -> None:
        results = self.tools.search_knowledge_base("password reset lockout")
        self.assertTrue(len(results) > 0)
        self.assertTrue(any(r.source_id == "KB-01" for r in results))

    def test_search_tickets(self) -> None:
        results = self.tools.search_tickets("VPN")
        self.assertTrue(isinstance(results, list))


class TestAgentOrchestratorScenarios(unittest.TestCase):
    """End-to-end scenario tests for the LangGraph AgentOrchestrator."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.store = Store(db_path=self.tmp.name, seed=True)
        self.retriever = UnifiedRetriever(store=self.store, db_path=self.tmp.name)
        self.policy_engine = PolicyEngine()
        # Initialize orchestrator with use_llm=False for instant, deterministic offline testing
        self.orchestrator = AgentOrchestrator(
            retriever=self.retriever,
            policy_engine=self.policy_engine,
            store=self.store,
            use_llm=False,
        )

    def tearDown(self) -> None:
        self.store.close()
        self.retriever.close()
        if os.path.exists(self.tmp.name):
            try:
                os.unlink(self.tmp.name)
            except OSError:
                pass

    def test_example_a_locked_account(self) -> None:
        """Example A: Password reset / locked account (>5 attempts)."""
        req = AgentRequest(
            employee="Alice Smith",
            email="alice@company.com",
            request="I am locked out of my account after 6 failed password attempts.",
            request_id="REQ-A01",
        )
        resp = self.orchestrator.run(req)

        self.assertEqual(resp.status, "resolved")
        self.assertEqual(resp.action, "resolve")
        self.assertIn("KB-01", resp.sources)
        self.assertIsNotNone(resp.ticket)
        self.assertEqual(resp.ticket["status"], "RESOLVED")
        self.assertIsNotNone(resp.audit_id)

        # Verify audit event in DB
        audit = self.store.get_audit_event(resp.audit_id)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, "resolve")
        self.assertEqual(audit.status, "resolved")

    def test_example_b_guest_wifi(self) -> None:
        """Example B: Guest Wi-Fi access (front-desk kiosk, 24h code)."""
        req = AgentRequest(
            employee="Bob Jones",
            email="bob@company.com",
            request="Can I get Wi-Fi access for a guest visitor tomorrow?",
            request_id="REQ-B01",
        )
        resp = self.orchestrator.run(req)

        self.assertEqual(resp.status, "resolved")
        self.assertEqual(resp.action, "resolve")
        self.assertIn("KB-07", resp.sources)
        self.assertEqual(resp.ticket["status"], "RESOLVED")
        self.assertIn("kiosk", resp.response.lower())

    def test_example_c_phishing_escalation(self) -> None:
        """Example C: Phishing security incident must escalate to Security."""
        req = AgentRequest(
            employee="Charlie Brown",
            email="charlie@company.com",
            request="I received a suspicious phishing email asking for my corporate credentials.",
            request_id="REQ-C01",
        )
        resp = self.orchestrator.run(req)

        self.assertEqual(resp.status, "escalated")
        self.assertEqual(resp.action, "escalate")
        self.assertEqual(resp.escalation_team, "Security")
        self.assertIn("KB-09", resp.sources)
        self.assertEqual(resp.ticket["status"], "ESCALATED")
        self.assertIn("Security", resp.ticket["escalation_team"])
        # Warning to not forward
        self.assertIn("forward", resp.response.lower())

        # Verify audit trail
        audit = self.store.get_audit_event(resp.audit_id)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.destination, "Security")

    def test_example_d_non_catalog_software(self) -> None:
        """Example D: Non-catalog software requires Security review (3-5 days)."""
        req = AgentRequest(
            employee="Diana Prince",
            email="diana@company.com",
            request="I need a data-analysis tool that is not in the catalog.",
            request_id="REQ-D01",
        )
        resp = self.orchestrator.run(req)

        self.assertEqual(resp.status, "escalated")
        self.assertEqual(resp.action, "escalate")
        self.assertEqual(resp.escalation_team, "IT Security")
        self.assertIn("KB-04", resp.sources)
        self.assertEqual(resp.ticket["status"], "ESCALATED")
        self.assertIn("3–5", resp.response)

    def test_example_e_contractor_vpn(self) -> None:
        """Example E: Contractor requesting VPN requires Manager approval."""
        req = AgentRequest(
            employee="Evan Wright",
            email="evan.c@company.com",
            request="I am a contractor and I need VPN access for my tasks.",
            request_id="REQ-E01",
        )
        resp = self.orchestrator.run(req)

        self.assertEqual(resp.status, "escalated")
        self.assertEqual(resp.action, "escalate")
        self.assertEqual(resp.escalation_team, "Manager")
        self.assertIn("KB-02", resp.sources)
        self.assertEqual(resp.ticket["status"], "ESCALATED")

    def test_follow_up_flow(self) -> None:
        """Test clarification flow when required information is missing."""
        req = AgentRequest(
            employee="Fiona Gallagher",
            email="fiona@company.com",
            request="I want a new replacement laptop please.",
            request_id="REQ-F01",
        )
        resp = self.orchestrator.run(req)

        self.assertEqual(resp.status, "follow_up_required")
        self.assertEqual(resp.action, "follow_up")
        self.assertEqual(resp.ticket["status"], "FOLLOW_UP_REQUIRED")
        self.assertIn("how old", resp.response.lower())

    def test_existing_ticket_update(self) -> None:
        """Test updating an existing ticket with a follow-up answer."""
        # 1. First request
        req1 = AgentRequest(
            employee="George Clark",
            email="george@company.com",
            request="I need a replacement laptop.",
        )
        resp1 = self.orchestrator.run(req1)
        self.assertEqual(resp1.status, "follow_up_required")
        ticket_id = resp1.ticket["ticket_id"]

        # 2. Follow-up response with laptop age 4.5 years
        req2 = AgentRequest(
            employee="George Clark",
            email="george@company.com",
            request="My laptop is 4.5 years old.",
            ticket_id=ticket_id,
        )
        resp2 = self.orchestrator.run(req2)
        self.assertEqual(resp2.status, "resolved")
        self.assertEqual(resp2.ticket["ticket_id"], ticket_id)
        self.assertEqual(resp2.ticket["status"], "RESOLVED")


class TestAgentLiveLLM(unittest.TestCase):
    """Live integration test against NVIDIA Nemotron endpoint."""

    @unittest.skipUnless(os.getenv("NVIDIA_API_KEY"), "NVIDIA_API_KEY not configured in environment")
    def test_live_nemotron_orchestrator(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        store = Store(db_path=tmp.name, seed=True)
        retriever = UnifiedRetriever(store=store, db_path=tmp.name)
        policy_engine = PolicyEngine()
        llm = get_llm()

        orchestrator = AgentOrchestrator(
            llm=llm,
            retriever=retriever,
            policy_engine=policy_engine,
            store=store,
        )

        req = AgentRequest(
            employee="Live Tester",
            email="livetester@company.com",
            request="I got a suspicious email asking me to click a link and give my login password.",
            request_id="REQ-LIVE-01",
        )
        resp = orchestrator.run(req)

        store.close()
        retriever.close()
        if os.path.exists(tmp.name):
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        self.assertEqual(resp.status, "escalated")
        self.assertEqual(resp.escalation_team, "Security")
        self.assertIn("KB-09", resp.sources)
        self.assertTrue(len(resp.response) > 20)
        self.assertIsNotNone(resp.ticket)
        self.assertIsNotNone(resp.audit_id)


if __name__ == "__main__":
    unittest.main()
