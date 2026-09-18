"""Unit tests for the deterministic policy engine (src/policy)."""

from __future__ import annotations

import unittest

from src.policy import Decision, EscalationTeam, PolicyEngine, PolicyRequest


class TestPolicyEngineSetup(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.default()

    def test_rules_are_loaded(self) -> None:
        rules = self.engine.list_rules()
        self.assertGreater(len(rules), 0)

    def test_rules_sorted_by_priority(self) -> None:
        rules = self.engine.list_rules()
        priorities = [r.priority for r in rules]
        self.assertEqual(priorities, sorted(priorities))

    def test_security_rule_is_first(self) -> None:
        rules = self.engine.list_rules()
        self.assertEqual(rules[0].kb_id, "KB-09")

    def test_get_rule_by_id(self) -> None:
        rule = self.engine.get_rule("KB-01-password-reset")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.kb_id, "KB-01")

    def test_get_rule_missing(self) -> None:
        self.assertIsNone(self.engine.get_rule("nonexistent"))


# ---------------------------------------------------------------------------
# KB-09 — Security Incident (must always escalate)
# ---------------------------------------------------------------------------

class TestKB09SecurityIncident(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.default()

    def _req(self, **kw) -> PolicyRequest:
        return PolicyRequest(**kw)

    def test_phishing_via_kb_id(self) -> None:
        v = self.engine.evaluate(self._req(kb_ids=["KB-09"]))
        self.assertEqual(v.decision, Decision.ESCALATED)
        self.assertEqual(v.escalation_team, EscalationTeam.SECURITY)
        self.assertEqual(v.source_kb_id, "KB-09")

    def test_phishing_via_raw_text(self) -> None:
        v = self.engine.evaluate(self._req(
            raw_text="I received a suspicious phishing email asking for my credentials"
        ))
        self.assertEqual(v.decision, Decision.ESCALATED)
        self.assertEqual(v.escalation_team, EscalationTeam.SECURITY)

    def test_malware_keyword(self) -> None:
        v = self.engine.evaluate(self._req(raw_text="My laptop has malware on it"))
        self.assertEqual(v.decision, Decision.ESCALATED)

    def test_security_beats_other_rules(self) -> None:
        """Security escalation must win even when other KB IDs are present."""
        v = self.engine.evaluate(self._req(
            kb_ids=["KB-01", "KB-09"],
            raw_text="password reset and phishing attack",
        ))
        self.assertEqual(v.decision, Decision.ESCALATED)
        self.assertEqual(v.source_kb_id, "KB-09")

    def test_verdict_is_terminal(self) -> None:
        v = self.engine.evaluate(self._req(kb_ids=["KB-09"]))
        self.assertTrue(v.is_terminal)
        self.assertTrue(v.requires_human)


# ---------------------------------------------------------------------------
# KB-01 — Password Reset
# ---------------------------------------------------------------------------

class TestKB01PasswordReset(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.default()

    def test_password_reset_via_kb(self) -> None:
        v = self.engine.evaluate(PolicyRequest(kb_ids=["KB-01"]))
        self.assertEqual(v.decision, Decision.RESOLVED)
        self.assertEqual(v.source_kb_id, "KB-01")

    def test_locked_out_keyword(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            raw_text="I am locked out after too many failed attempts"
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)
        self.assertFalse(v.requires_human)

    def test_password_keyword(self) -> None:
        v = self.engine.evaluate(PolicyRequest(raw_text="forgot my password"))
        self.assertEqual(v.decision, Decision.RESOLVED)


# ---------------------------------------------------------------------------
# KB-02 — VPN Access
# ---------------------------------------------------------------------------

class TestKB02VPN(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.default()

    def test_vpn_employee_type_unknown(self) -> None:
        v = self.engine.evaluate(PolicyRequest(kb_ids=["KB-02"]))
        self.assertEqual(v.decision, Decision.FOLLOW_UP_REQUIRED)
        self.assertIsNotNone(v.follow_up_question)

    def test_vpn_full_time_employee(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-02"], employee_type="employee"
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)
        self.assertFalse(v.requires_human)

    def test_vpn_contractor(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-02"], employee_type="contractor"
        ))
        self.assertEqual(v.decision, Decision.ESCALATED)
        self.assertEqual(v.escalation_team, EscalationTeam.MANAGER)

    def test_vpn_keyword_unknown_type(self) -> None:
        v = self.engine.evaluate(PolicyRequest(raw_text="My VPN credentials expired"))
        self.assertEqual(v.decision, Decision.FOLLOW_UP_REQUIRED)


# ---------------------------------------------------------------------------
# KB-03 + Asset Policy — Laptop Replacement
# ---------------------------------------------------------------------------

class TestKB03LaptopReplacement(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.default()

    def test_age_unknown(self) -> None:
        v = self.engine.evaluate(PolicyRequest(kb_ids=["KB-03"]))
        self.assertEqual(v.decision, Decision.FOLLOW_UP_REQUIRED)

    def test_eligible_by_age(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-03"], laptop_age_years=3.5
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)
        self.assertEqual(v.source_kb_id, "KB-03")

    def test_young_laptop_no_failure_confirmed(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-03"], laptop_age_years=1.5,
            hardware_failure_verified=None,
        ))
        self.assertEqual(v.decision, Decision.FOLLOW_UP_REQUIRED)

    def test_young_laptop_no_failure(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-03"], laptop_age_years=1.5,
            hardware_failure_verified=False,
        ))
        self.assertEqual(v.decision, Decision.ESCALATED)
        self.assertEqual(v.escalation_team, EscalationTeam.FINANCE)

    def test_young_laptop_with_verified_failure(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-03"], laptop_age_years=2.0,
            hardware_failure_verified=True,
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)

    def test_exactly_3_years(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-03"], laptop_age_years=3.0
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)

    def test_asset_policy_keyword(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            raw_text="My laptop is completely dead", laptop_age_years=4.5
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)


# ---------------------------------------------------------------------------
# KB-04 — Software Installation
# ---------------------------------------------------------------------------

class TestKB04Software(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.default()

    def test_catalog_unknown(self) -> None:
        v = self.engine.evaluate(PolicyRequest(kb_ids=["KB-04"]))
        self.assertEqual(v.decision, Decision.FOLLOW_UP_REQUIRED)

    def test_catalog_software(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-04"], is_catalog_software=True
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)

    def test_non_catalog_software(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-04"], is_catalog_software=False
        ))
        self.assertEqual(v.decision, Decision.ESCALATED)
        self.assertEqual(v.escalation_team, EscalationTeam.IT_SECURITY)

    def test_non_catalog_keyword(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            raw_text="I need to install a non-catalog data analysis tool",
            is_catalog_software=False,
        ))
        self.assertEqual(v.decision, Decision.ESCALATED)


# ---------------------------------------------------------------------------
# KB-05 — Printer
# ---------------------------------------------------------------------------

class TestKB05Printer(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.default()

    def test_printer_via_kb(self) -> None:
        v = self.engine.evaluate(PolicyRequest(kb_ids=["KB-05"]))
        self.assertEqual(v.decision, Decision.RESOLVED)

    def test_printer_keyword(self) -> None:
        v = self.engine.evaluate(PolicyRequest(raw_text="Printer on floor 3 has a paper jam"))
        self.assertEqual(v.decision, Decision.RESOLVED)

    def test_printer_metadata(self) -> None:
        v = self.engine.evaluate(PolicyRequest(kb_ids=["KB-05"]))
        self.assertTrue(v.metadata.get("self_service"))
        self.assertTrue(v.metadata.get("requires_asset_tag_if_persists"))


# ---------------------------------------------------------------------------
# KB-06 — Mailbox Quota
# ---------------------------------------------------------------------------

class TestKB06MailboxQuota(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.default()

    def test_general_quota_issue(self) -> None:
        v = self.engine.evaluate(PolicyRequest(kb_ids=["KB-06"]))
        self.assertEqual(v.decision, Decision.RESOLVED)

    def test_quota_increase_within_cap(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-06"], quota_gb_requested=40.0
        ))
        self.assertEqual(v.decision, Decision.ESCALATED)
        self.assertEqual(v.escalation_team, EscalationTeam.MANAGER)

    def test_quota_exceeds_max(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-06"], quota_gb_requested=60.0
        ))
        self.assertEqual(v.decision, Decision.ESCALATED)
        self.assertIn("50", v.reason)

    def test_quota_at_default(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-06"], quota_gb_requested=25.0
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)


# ---------------------------------------------------------------------------
# KB-07 — Guest Wi-Fi
# ---------------------------------------------------------------------------

class TestKB07GuestWifi(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.default()

    def test_guest_wifi_via_kb(self) -> None:
        v = self.engine.evaluate(PolicyRequest(kb_ids=["KB-07"]))
        self.assertEqual(v.decision, Decision.RESOLVED)
        self.assertTrue(v.metadata.get("self_service"))
        self.assertEqual(v.metadata.get("code_validity_hours"), 24)

    def test_guest_wifi_keyword(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            raw_text="Can I get guest wifi access for a visitor tomorrow?"
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)


# ---------------------------------------------------------------------------
# KB-08 — Expense Software
# ---------------------------------------------------------------------------

class TestKB08ExpenseSoftware(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.default()

    def test_account_exists_unknown(self) -> None:
        v = self.engine.evaluate(PolicyRequest(kb_ids=["KB-08"]))
        self.assertEqual(v.decision, Decision.FOLLOW_UP_REQUIRED)

    def test_new_account_request(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-08"], expense_account_exists=False
        ))
        self.assertEqual(v.decision, Decision.ESCALATED)
        self.assertEqual(v.escalation_team, EscalationTeam.FINANCE)

    def test_existing_account_login_issue(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-08"], expense_account_exists=True
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)


# ---------------------------------------------------------------------------
# KB-10 — Work-From-Home Equipment
# ---------------------------------------------------------------------------

class TestKB10WFHEquipment(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine.default()

    def test_wfh_days_unknown(self) -> None:
        v = self.engine.evaluate(PolicyRequest(kb_ids=["KB-10"]))
        self.assertEqual(v.decision, Decision.FOLLOW_UP_REQUIRED)

    def test_not_enough_wfh_days(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-10"], wfh_days_per_week=2.0
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)
        self.assertIn("not currently eligible", v.reason)

    def test_exactly_threshold(self) -> None:
        """Exactly 3 days is NOT eligible (must be MORE than 3)."""
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-10"], wfh_days_per_week=3.0
        ))
        self.assertEqual(v.decision, Decision.RESOLVED)
        self.assertIn("not currently eligible", v.reason)

    def test_eligible_wfh(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            kb_ids=["KB-10"], wfh_days_per_week=4.0
        ))
        self.assertEqual(v.decision, Decision.ESCALATED)
        self.assertEqual(v.escalation_team, EscalationTeam.MANAGER)

    def test_wfh_keyword(self) -> None:
        v = self.engine.evaluate(PolicyRequest(
            raw_text="I work from home 4 days a week and need a monitor",
            wfh_days_per_week=4.0,
        ))
        self.assertEqual(v.decision, Decision.ESCALATED)


# ---------------------------------------------------------------------------
# Engine fallback — no rule matches
# ---------------------------------------------------------------------------

class TestEngineNoMatch(unittest.TestCase):
    def test_no_match_returns_follow_up(self) -> None:
        engine = PolicyEngine.default()
        v = engine.evaluate(PolicyRequest(
            category="completely unknown request",
            raw_text="I need something that doesn't match any policy",
        ))
        self.assertEqual(v.decision, Decision.FOLLOW_UP_REQUIRED)
        self.assertEqual(v.rule_id, "engine-no-match")

    def test_evaluate_all_returns_multiple(self) -> None:
        engine = PolicyEngine.default()
        # A request that could match both KB-01 (password) and KB-09 (security incident)
        results = engine.evaluate_all(PolicyRequest(
            kb_ids=["KB-01", "KB-09"],
            raw_text="password reset and phishing",
        ))
        rule_ids = [v.rule_id for v in results]
        self.assertIn("KB-09-security-incident", rule_ids)
        self.assertIn("KB-01-password-reset", rule_ids)


# ---------------------------------------------------------------------------
# PolicyVerdict properties
# ---------------------------------------------------------------------------

class TestPolicyVerdictProperties(unittest.TestCase):
    def test_is_terminal_resolved(self) -> None:
        from src.policy.models import Decision, PolicyVerdict
        v = PolicyVerdict(decision=Decision.RESOLVED, reason="ok")
        self.assertTrue(v.is_terminal)
        self.assertFalse(v.requires_human)

    def test_is_terminal_escalated(self) -> None:
        from src.policy.models import Decision, PolicyVerdict
        v = PolicyVerdict(decision=Decision.ESCALATED, reason="escalate")
        self.assertTrue(v.is_terminal)
        self.assertTrue(v.requires_human)

    def test_follow_up_not_terminal(self) -> None:
        from src.policy.models import Decision, PolicyVerdict
        v = PolicyVerdict(decision=Decision.FOLLOW_UP_REQUIRED, reason="need info")
        self.assertFalse(v.is_terminal)


if __name__ == "__main__":
    unittest.main()
