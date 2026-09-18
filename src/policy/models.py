"""Data models for the deterministic policy engine.

Defines:
- :class:`PolicyRequest`  — normalised input fed to the engine
- :class:`PolicyVerdict`  — deterministic decision returned by the engine
- :class:`PolicyRule`     — internal rule descriptor (for documentation/introspection)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Decision(str, Enum):
    """Outcome produced by a policy rule evaluation."""

    RESOLVED = "RESOLVED"
    """Request can be handled directly — no additional approval needed."""

    ESCALATED = "ESCALATED"
    """Request must be routed to a human team for review/approval."""

    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    """More information is needed before a safe decision can be made."""

    PASS = "PASS"
    """Rule did not match — engine continues to the next rule."""


class EscalationTeam(str, Enum):
    """Canonical destination teams used throughout the agent."""

    SECURITY = "Security"
    FINANCE = "Finance"
    IT = "IT"
    IT_SECURITY = "IT Security"
    MANAGER = "Manager"
    HELPDESK = "Helpdesk"


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class PolicyRequest(BaseModel):
    """Normalised input to the policy engine.

    The agent (or test harness) populates this from the classified request
    context before calling :meth:`PolicyEngine.evaluate`.

    All boolean flags default to ``None`` (unknown) rather than ``False``
    so that rules can distinguish *explicitly false* from *not yet asked*.
    """

    # Core classification
    category: str = ""
    """KB/request category (e.g. 'VPN', 'Software Installation Requests')."""

    kb_ids: list[str] = Field(default_factory=list)
    """KB article IDs retrieved for this request (e.g. ['KB-02', 'KB-04'])."""

    raw_text: str = ""
    """Original free-text request from the employee."""

    # Employee context
    employee_type: Optional[str] = None
    """'employee' | 'contractor' | None (unknown)."""

    # Domain-specific flags — set by the LLM classifier or follow-up Q&A
    is_catalog_software: Optional[bool] = None
    """True if software is in the approved catalog; False if non-catalog; None if unknown."""

    laptop_age_years: Optional[float] = None
    """Reported age of the laptop in years; None if unknown."""

    hardware_failure_verified: Optional[bool] = None
    """True if a hardware failure has been confirmed; False explicitly denied; None unknown."""

    quota_gb_requested: Optional[float] = None
    """Mailbox quota in GB being requested (>25 triggers manager approval)."""

    is_guest_wifi: Optional[bool] = None
    """True when the request is specifically for guest Wi-Fi access."""

    expense_account_exists: Optional[bool] = None
    """True if the employee already has an expense account; False if brand new."""

    wfh_days_per_week: Optional[float] = None
    """How many days/week the employee works remotely (>3 -> eligible for equipment)."""

    extra: dict[str, Any] = Field(default_factory=dict)
    """Arbitrary additional context that specific rules may inspect."""


# ---------------------------------------------------------------------------
# Verdict model
# ---------------------------------------------------------------------------

class PolicyVerdict(BaseModel):
    """Deterministic outcome of a single policy evaluation."""

    decision: Decision
    """The resolved action to take."""

    rule_id: str = ""
    """Short identifier of the rule that fired (e.g. 'KB-09-phishing')."""

    source_kb_id: str = ""
    """Primary KB article that justifies the decision."""

    reason: str = ""
    """Human-readable explanation for audit/response (1-2 sentences)."""

    escalation_team: Optional[str] = None
    """Team to route to when ``decision == ESCALATED``."""

    follow_up_question: Optional[str] = None
    """Question to ask the employee when ``decision == FOLLOW_UP_REQUIRED``."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Extra data for downstream consumers (e.g. suggested self-service URL)."""

    @property
    def is_terminal(self) -> bool:
        """True when no further action is needed from the engine."""
        return self.decision in (Decision.RESOLVED, Decision.ESCALATED)

    @property
    def requires_human(self) -> bool:
        """True when a human team must be involved."""
        return self.decision == Decision.ESCALATED


# ---------------------------------------------------------------------------
# Rule descriptor (informational -- used for introspection / docs)
# ---------------------------------------------------------------------------

class PolicyRule(BaseModel):
    """Metadata descriptor for a registered policy rule.

    Not used at runtime beyond documentation and ``PolicyEngine.list_rules()``.
    """

    rule_id: str
    kb_id: str
    title: str
    description: str
    priority: int = 50
    """Lower value = evaluated first. Range 0-100."""
