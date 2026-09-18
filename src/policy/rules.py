"""Deterministic policy rule implementations for the Internal Service Agent.

Each rule is a plain function:

    def rule_<name>(req: PolicyRequest) -> PolicyVerdict:
        ...

Rules return ``Decision.PASS`` when they don't apply, allowing the engine to
fall through to the next rule.  They return a terminal verdict (RESOLVED,
ESCALATED, or FOLLOW_UP_REQUIRED) when the rule fires.

Rules are ordered by priority (lower number = evaluated first) inside the
engine.  Security rules have the lowest priority numbers so they can never be
bypassed by a more permissive rule that appears earlier in the list.

Covered policies
----------------
KB-01  Password reset / account lockout
KB-02  VPN access (employee vs contractor)
KB-03  Laptop replacement (age + hardware failure)
KB-04  Software installation (catalog vs non-catalog)
KB-05  Printer troubleshooting
KB-06  Email mailbox quota (<=25 GB vs >25 GB)
KB-07  Guest Wi-Fi (no ticket required)
KB-08  Expense software access (Finance owns provisioning)
KB-09  Security incident / phishing (must escalate — highest priority)
KB-10  Work-from-home equipment (manager + Finance approval required)
Asset  Asset Management Policy (4-year hardware refresh cycle)
"""

from __future__ import annotations

import re
from typing import Optional

from .models import Decision, EscalationTeam, PolicyRequest, PolicyRule, PolicyVerdict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_kb(req: PolicyRequest, *kb_ids: str) -> bool:
    """Return True if any of the given KB IDs are in the request context."""
    req_ids = {k.upper() for k in req.kb_ids}
    return any(k.upper() in req_ids for k in kb_ids)


def _text_matches(req: PolicyRequest, *patterns: str) -> bool:
    """Case-insensitive substring check against raw_text + category."""
    haystack = (req.raw_text + " " + req.category).lower()
    return any(p.lower() in haystack for p in patterns)


def _pass() -> PolicyVerdict:
    return PolicyVerdict(decision=Decision.PASS)


# ---------------------------------------------------------------------------
# KB-09 — Security Incident / Phishing  (priority 5 — evaluated FIRST)
# ---------------------------------------------------------------------------

def rule_kb09_security_incident(req: PolicyRequest) -> PolicyVerdict:
    """Any suspected phishing, malware, or unauthorized access must be
    escalated to Security immediately — never auto-resolved.

    This rule matches on KB-09 retrieval OR strong keyword signals in the
    raw text to ensure it cannot be bypassed even without retrieval context.
    """
    security_keywords = [
        "phishing", "phish", "malware", "virus", "unauthorized access",
        "suspicious email", "suspicious link", "security incident",
        "data breach", "breach", "ransomware", "credential theft",
    ]
    triggered = _has_kb(req, "KB-09") or _text_matches(req, *security_keywords)
    if not triggered:
        return _pass()

    return PolicyVerdict(
        decision=Decision.ESCALATED,
        rule_id="KB-09-security-incident",
        source_kb_id="KB-09",
        escalation_team=EscalationTeam.SECURITY,
        reason=(
            "Per KB-09, any suspected phishing, malware, or unauthorized access "
            "must be reported to security@veridian-corp.example immediately and "
            "must not be forwarded to other employees. This request has been "
            "escalated to the Security team."
        ),
        metadata={"contact": "security@veridian-corp.example"},
    )


# ---------------------------------------------------------------------------
# KB-01 — Password Reset / Account Lockout  (priority 10)
# ---------------------------------------------------------------------------

def rule_kb01_password_reset(req: PolicyRequest) -> PolicyVerdict:
    """Employees can self-service reset passwords via the portal.
    If locked out after 5+ failed attempts, IT must manually unlock —
    still no approval required.
    """
    if not (_has_kb(req, "KB-01") or _text_matches(
        req, "password", "locked out", "lockout", "account locked",
        "failed attempts", "unlock", "login portal",
    )):
        return _pass()

    return PolicyVerdict(
        decision=Decision.RESOLVED,
        rule_id="KB-01-password-reset",
        source_kb_id="KB-01",
        reason=(
            "Per KB-01, employees can reset passwords via the self-service portal "
            "at any time. If the account is locked after 5 failed attempts, IT will "
            "manually unlock it — no manager approval is required."
        ),
        metadata={"self_service": True, "requires_it_manual": True},
    )


# ---------------------------------------------------------------------------
# KB-02 — VPN Access  (priority 15)
# ---------------------------------------------------------------------------

def rule_kb02_vpn_access(req: PolicyRequest) -> PolicyVerdict:
    """VPN is automatic for full-time employees; contractors need manager approval."""
    if not (_has_kb(req, "KB-02") or _text_matches(
        req, "vpn", "virtual private network", "remote access", "vpn credentials",
    )):
        return _pass()

    # If employee type is unknown, ask first
    if req.employee_type is None:
        return PolicyVerdict(
            decision=Decision.FOLLOW_UP_REQUIRED,
            rule_id="KB-02-vpn-employee-type-unknown",
            source_kb_id="KB-02",
            reason=(
                "Per KB-02, VPN access rules differ for employees vs contractors. "
                "Employee type must be confirmed before a decision can be made."
            ),
            follow_up_question=(
                "Are you a full-time employee or a contractor? "
                "(VPN access for contractors requires manager approval via the "
                "access request form.)"
            ),
        )

    if req.employee_type.lower() == "contractor":
        return PolicyVerdict(
            decision=Decision.ESCALATED,
            rule_id="KB-02-vpn-contractor",
            source_kb_id="KB-02",
            escalation_team=EscalationTeam.MANAGER,
            reason=(
                "Per KB-02, contractors require manager approval submitted via the "
                "access request form before VPN access can be granted."
            ),
        )

    # Full-time employee — self-service renewal
    return PolicyVerdict(
        decision=Decision.RESOLVED,
        rule_id="KB-02-vpn-employee",
        source_kb_id="KB-02",
        reason=(
            "Per KB-02, VPN access is granted automatically to all full-time "
            "employees. Credentials expire every 90 days and must be renewed by "
            "the employee. No approval is required."
        ),
        metadata={"self_service": True, "renewal_days": 90},
    )


# ---------------------------------------------------------------------------
# KB-03 + Asset Policy — Laptop / Hardware Replacement  (priority 20)
# ---------------------------------------------------------------------------

_LAPTOP_AGE_THRESHOLD_YEARS = 3.0   # KB-03 policy threshold
_ASSET_CYCLE_YEARS = 4.0            # Asset Management Policy cycle

def rule_kb03_laptop_replacement(req: PolicyRequest) -> PolicyVerdict:
    """Laptops are eligible for replacement after 3 years OR verified hardware failure.
    Early replacement (within the 4-year asset cycle) requires Finance sign-off.
    """
    if not (_has_kb(req, "KB-03", "Asset Management Policy") or _text_matches(
        req, "laptop", "hardware replacement", "device replacement",
        "broken laptop", "dead laptop", "hardware failure", "refresh",
    )):
        return _pass()

    age = req.laptop_age_years

    # Age unknown — ask
    if age is None:
        return PolicyVerdict(
            decision=Decision.FOLLOW_UP_REQUIRED,
            rule_id="KB-03-laptop-age-unknown",
            source_kb_id="KB-03",
            reason=(
                "Per KB-03 and the Asset Management Policy, replacement eligibility "
                "depends on the laptop's age. The age has not been provided."
            ),
            follow_up_question=(
                "How old is your current laptop (in years)? "
                "Also, has IT verified a hardware failure on this device?"
            ),
        )

    eligible_by_age = age >= _LAPTOP_AGE_THRESHOLD_YEARS

    # Eligible by age (>=3 years) — IT can process directly
    if eligible_by_age:
        return PolicyVerdict(
            decision=Decision.RESOLVED,
            rule_id="KB-03-laptop-eligible",
            source_kb_id="KB-03",
            reason=(
                f"The laptop is {age:.1f} years old and meets the "
                f"{_LAPTOP_AGE_THRESHOLD_YEARS}-year replacement eligibility threshold "
                "per KB-03. Requests should be raised at least 2 weeks in advance. "
                "IT will process the replacement."
            ),
            metadata={"advance_notice_weeks": 2},
        )

    # Below age threshold — hardware failure must be confirmed for early replacement
    if req.hardware_failure_verified is None:
        return PolicyVerdict(
            decision=Decision.FOLLOW_UP_REQUIRED,
            rule_id="KB-03-laptop-failure-unconfirmed",
            source_kb_id="KB-03",
            reason=(
                f"The laptop is reported as {age:.1f} years old, which is below the "
                f"standard {_LAPTOP_AGE_THRESHOLD_YEARS}-year replacement threshold. "
                "Eligibility for early replacement requires a verified hardware failure."
            ),
            follow_up_question=(
                "Has IT confirmed a hardware failure on your device? "
                "If so, please provide the fault report or ticket reference."
            ),
        )

    # Verified hardware failure — can proceed as early replacement via IT/Finance
    if req.hardware_failure_verified:
        return PolicyVerdict(
            decision=Decision.RESOLVED,
            rule_id="KB-03-laptop-early-verified-failure",
            source_kb_id="KB-03",
            reason=(
                f"The laptop is {age:.1f} years old but has a verified hardware failure. "
                "Per KB-03, early replacement is permitted in case of verified hardware "
                "failure. IT will process the replacement request."
            ),
            metadata={"advance_notice_weeks": 2},
        )

    # Explicitly no hardware failure AND below asset cycle — Finance sign-off required
    return PolicyVerdict(
        decision=Decision.ESCALATED,
        rule_id="KB-03-laptop-early-no-failure",
        source_kb_id="KB-03",
        escalation_team=EscalationTeam.FINANCE,
        reason=(
            f"The laptop is {age:.1f} years old. Per the Asset Management Policy, "
            f"early replacement before the {_ASSET_CYCLE_YEARS}-year cycle without "
            "a verified hardware failure requires Finance sign-off in addition to "
            "IT approval."
        ),
    )


# ---------------------------------------------------------------------------
# KB-04 — Software Installation  (priority 25)
# ---------------------------------------------------------------------------

def rule_kb04_software_installation(req: PolicyRequest) -> PolicyVerdict:
    """Catalog software can be self-installed; non-catalog needs Security review."""
    if not (_has_kb(req, "KB-04") or _text_matches(
        req, "software", "install", "application", "app install",
        "non-catalog", "not in catalog", "tool install",
    )):
        return _pass()

    # Catalog status unknown — ask
    if req.is_catalog_software is None:
        return PolicyVerdict(
            decision=Decision.FOLLOW_UP_REQUIRED,
            rule_id="KB-04-catalog-unknown",
            source_kb_id="KB-04",
            reason=(
                "Per KB-04, installation rights depend on whether the software is "
                "in the approved catalog. Catalog status has not been confirmed."
            ),
            follow_up_question=(
                "Is this software listed in the company's approved software catalog? "
                "If you're not sure, you can check the IT portal or provide the "
                "software name so we can verify."
            ),
        )

    if req.is_catalog_software:
        return PolicyVerdict(
            decision=Decision.RESOLVED,
            rule_id="KB-04-catalog-software",
            source_kb_id="KB-04",
            reason=(
                "Per KB-04, software listed in the approved catalog can be "
                "self-installed by employees directly without an IT ticket."
            ),
            metadata={"self_service": True},
        )

    # Non-catalog — Security review required
    return PolicyVerdict(
        decision=Decision.ESCALATED,
        rule_id="KB-04-non-catalog-software",
        source_kb_id="KB-04",
        escalation_team=EscalationTeam.IT_SECURITY,
        reason=(
            "Per KB-04, non-catalog software requires an IT Security review, "
            "which typically takes 3–5 business days. The request has been "
            "escalated to IT Security."
        ),
        metadata={"review_days_min": 3, "review_days_max": 5},
    )


# ---------------------------------------------------------------------------
# KB-05 — Printer Troubleshooting  (priority 30)
# ---------------------------------------------------------------------------

def rule_kb05_printer(req: PolicyRequest) -> PolicyVerdict:
    """Printer issues: self-service first (queue + spooler), then IT ticket."""
    if not (_has_kb(req, "KB-05") or _text_matches(
        req, "printer", "print", "printing", "spooler", "paper jam", "print queue",
    )):
        return _pass()

    return PolicyVerdict(
        decision=Decision.RESOLVED,
        rule_id="KB-05-printer",
        source_kb_id="KB-05",
        reason=(
            "Per KB-05, for printer problems: first check the printer queue and "
            "restart the print spooler. If the issue persists, log an IT ticket "
            "with the printer's asset tag number."
        ),
        metadata={"self_service": True, "requires_asset_tag_if_persists": True},
    )


# ---------------------------------------------------------------------------
# KB-06 — Email Mailbox Quota  (priority 35)
# ---------------------------------------------------------------------------

_DEFAULT_QUOTA_GB = 25.0
_MAX_QUOTA_GB = 50.0

def rule_kb06_mailbox_quota(req: PolicyRequest) -> PolicyVerdict:
    """Mailbox quota: archive first, >25 GB requires manager approval, max 50 GB."""
    if not (_has_kb(req, "KB-06") or _text_matches(
        req, "mailbox", "email quota", "inbox full", "quota", "storage full",
        "email storage", "archive",
    )):
        return _pass()

    requested = req.quota_gb_requested

    # If a specific quota above the default is requested
    if requested is not None and requested > _DEFAULT_QUOTA_GB:
        if requested > _MAX_QUOTA_GB:
            return PolicyVerdict(
                decision=Decision.ESCALATED,
                rule_id="KB-06-quota-exceeds-max",
                source_kb_id="KB-06",
                escalation_team=EscalationTeam.MANAGER,
                reason=(
                    f"Per KB-06, mailbox quota increases are capped at {_MAX_QUOTA_GB} GB. "
                    f"The requested {requested:.0f} GB exceeds the maximum allowed. "
                    "Please discuss with your manager and IT."
                ),
            )
        return PolicyVerdict(
            decision=Decision.ESCALATED,
            rule_id="KB-06-quota-increase",
            source_kb_id="KB-06",
            escalation_team=EscalationTeam.MANAGER,
            reason=(
                f"Per KB-06, quota increases beyond {_DEFAULT_QUOTA_GB} GB require "
                f"manager approval and are capped at {_MAX_QUOTA_GB} GB. "
                "The request has been escalated to the employee's manager."
            ),
        )

    # General mailbox issue / nearing quota — self-service guidance
    return PolicyVerdict(
        decision=Decision.RESOLVED,
        rule_id="KB-06-mailbox-self-service",
        source_kb_id="KB-06",
        reason=(
            f"Per KB-06, the default mailbox quota is {_DEFAULT_QUOTA_GB} GB. "
            "Employees nearing their quota should archive old email. "
            "No IT ticket is required for archiving."
        ),
        metadata={"self_service": True, "default_quota_gb": _DEFAULT_QUOTA_GB},
    )


# ---------------------------------------------------------------------------
# KB-07 — Guest Wi-Fi  (priority 40)
# ---------------------------------------------------------------------------

def rule_kb07_guest_wifi(req: PolicyRequest) -> PolicyVerdict:
    """Guest Wi-Fi codes can be self-generated — no IT ticket required."""
    if not (_has_kb(req, "KB-07") or _text_matches(
        req, "guest wifi", "guest wi-fi", "visitor wifi", "guest network",
        "wi-fi for guest", "wifi for visitor", "wifi access",
    )):
        return _pass()

    return PolicyVerdict(
        decision=Decision.RESOLVED,
        rule_id="KB-07-guest-wifi",
        source_kb_id="KB-07",
        reason=(
            "Per KB-07, guest Wi-Fi codes are valid for 24 hours and can be "
            "generated by any employee at the front-desk kiosk. "
            "No IT ticket is required."
        ),
        metadata={"self_service": True, "code_validity_hours": 24, "location": "front-desk kiosk"},
    )


# ---------------------------------------------------------------------------
# KB-08 — Expense Software Access  (priority 45)
# ---------------------------------------------------------------------------

def rule_kb08_expense_software(req: PolicyRequest) -> PolicyVerdict:
    """Expense tool provisioning is owned by Finance; IT handles login issues only."""
    if not (_has_kb(req, "KB-08") or _text_matches(
        req, "expense", "expense tool", "expense software", "expense account",
        "reimbursement tool", "finance tool",
    )):
        return _pass()

    # New account request — Finance must provision it
    if req.expense_account_exists is False:
        return PolicyVerdict(
            decision=Decision.ESCALATED,
            rule_id="KB-08-expense-new-account",
            source_kb_id="KB-08",
            escalation_team=EscalationTeam.FINANCE,
            reason=(
                "Per KB-08, access to the expense management tool is granted by "
                "Finance, not IT. Since no existing account was found, this request "
                "has been escalated to the Finance team."
            ),
        )

    # Account status unknown — ask
    if req.expense_account_exists is None:
        return PolicyVerdict(
            decision=Decision.FOLLOW_UP_REQUIRED,
            rule_id="KB-08-expense-account-unknown",
            source_kb_id="KB-08",
            reason=(
                "Per KB-08, IT can only assist with login or technical issues for "
                "existing expense accounts. Finance handles new account provisioning."
            ),
            follow_up_question=(
                "Do you already have an expense management account, or are you "
                "requesting a brand new account? "
                "(New accounts must be provisioned by Finance.)"
            ),
        )

    # Existing account — IT can assist with technical/login issues
    return PolicyVerdict(
        decision=Decision.RESOLVED,
        rule_id="KB-08-expense-login-issue",
        source_kb_id="KB-08",
        reason=(
            "Per KB-08, IT can assist with login and technical issues for employees "
            "who already have an expense management account. IT will investigate the "
            "technical issue."
        ),
    )


# ---------------------------------------------------------------------------
# KB-10 — Work-From-Home Equipment  (priority 50)
# ---------------------------------------------------------------------------

_WFH_DAYS_THRESHOLD = 3.0

def rule_kb10_wfh_equipment(req: PolicyRequest) -> PolicyVerdict:
    """WFH equipment (chair/monitor) requires manager + Finance approval; IT ships."""
    if not (_has_kb(req, "KB-10") or _text_matches(
        req, "work from home", "wfh", "home office", "remote equipment",
        "home monitor", "home chair", "equipment allowance",
    )):
        return _pass()

    days = req.wfh_days_per_week

    # WFH days unknown — ask
    if days is None:
        return PolicyVerdict(
            decision=Decision.FOLLOW_UP_REQUIRED,
            rule_id="KB-10-wfh-days-unknown",
            source_kb_id="KB-10",
            reason=(
                "Per KB-10, home-office equipment eligibility requires working "
                "remotely more than 3 days per week. The number of remote days "
                "has not been confirmed."
            ),
            follow_up_question=(
                "How many days per week do you currently work from home? "
                "(Employees working more than 3 days/week remotely are eligible "
                "for a one-time home office equipment allowance.)"
            ),
        )

    if days <= _WFH_DAYS_THRESHOLD:
        return PolicyVerdict(
            decision=Decision.RESOLVED,
            rule_id="KB-10-wfh-not-eligible",
            source_kb_id="KB-10",
            reason=(
                f"Per KB-10, the home-office equipment allowance requires working "
                f"remotely more than {_WFH_DAYS_THRESHOLD:.0f} days/week. "
                f"You work {days:.0f} days/week remotely, so you are not currently eligible."
            ),
        )

    # Eligible — needs manager + Finance before IT can ship
    return PolicyVerdict(
        decision=Decision.ESCALATED,
        rule_id="KB-10-wfh-approval-required",
        source_kb_id="KB-10",
        escalation_team=EscalationTeam.MANAGER,
        reason=(
            f"Per KB-10, employees working more than {_WFH_DAYS_THRESHOLD:.0f} days/week "
            "remotely are eligible for a one-time home-office equipment allowance "
            "(chair, monitor). This requires manager sign-off and Finance processing. "
            "IT will handle the shipping request once both approvals are obtained."
        ),
        metadata={"also_requires": "Finance"},
    )


# ---------------------------------------------------------------------------
# Registry — all rules in priority order
# ---------------------------------------------------------------------------

# Each entry: (rule_function, PolicyRule descriptor)
RULE_REGISTRY: list[tuple] = [
    (
        rule_kb09_security_incident,
        PolicyRule(
            rule_id="KB-09-security-incident",
            kb_id="KB-09",
            title="Security Incident / Phishing",
            description="Escalate all suspected phishing, malware, or unauthorized access to Security.",
            priority=5,
        ),
    ),
    (
        rule_kb01_password_reset,
        PolicyRule(
            rule_id="KB-01-password-reset",
            kb_id="KB-01",
            title="Password Reset & Account Lockout",
            description="Self-service portal for resets; IT manually unlocks after 5 failed attempts.",
            priority=10,
        ),
    ),
    (
        rule_kb02_vpn_access,
        PolicyRule(
            rule_id="KB-02-vpn-access",
            kb_id="KB-02",
            title="VPN Access",
            description="Auto-granted to employees; contractors need manager approval.",
            priority=15,
        ),
    ),
    (
        rule_kb03_laptop_replacement,
        PolicyRule(
            rule_id="KB-03-laptop-replacement",
            kb_id="KB-03",
            title="Laptop / Hardware Replacement",
            description="Eligible after 3 years or verified hardware failure; early replacement needs Finance.",
            priority=20,
        ),
    ),
    (
        rule_kb04_software_installation,
        PolicyRule(
            rule_id="KB-04-software-installation",
            kb_id="KB-04",
            title="Software Installation",
            description="Catalog software: self-install. Non-catalog: IT Security review (3-5 days).",
            priority=25,
        ),
    ),
    (
        rule_kb05_printer,
        PolicyRule(
            rule_id="KB-05-printer",
            kb_id="KB-05",
            title="Printer Troubleshooting",
            description="Self-service (queue + spooler restart); IT ticket if issue persists.",
            priority=30,
        ),
    ),
    (
        rule_kb06_mailbox_quota,
        PolicyRule(
            rule_id="KB-06-mailbox-quota",
            kb_id="KB-06",
            title="Email Mailbox Quota",
            description="25 GB default; >25 GB requires manager approval; max 50 GB.",
            priority=35,
        ),
    ),
    (
        rule_kb07_guest_wifi,
        PolicyRule(
            rule_id="KB-07-guest-wifi",
            kb_id="KB-07",
            title="Guest Wi-Fi Access",
            description="Self-service at front-desk kiosk; 24-hour codes; no IT ticket.",
            priority=40,
        ),
    ),
    (
        rule_kb08_expense_software,
        PolicyRule(
            rule_id="KB-08-expense-software",
            kb_id="KB-08",
            title="Expense Software Access",
            description="Finance provisions accounts; IT handles login issues for existing accounts.",
            priority=45,
        ),
    ),
    (
        rule_kb10_wfh_equipment,
        PolicyRule(
            rule_id="KB-10-wfh-equipment",
            kb_id="KB-10",
            title="Work-From-Home Equipment",
            description="Eligible if >3 days/week remote; needs manager + Finance approval before IT ships.",
            priority=50,
        ),
    ),
]
