"""Pydantic models for the storage layer.

These are the canonical in-memory representations of tickets and audit
events. They are used both by the Store (persistence) and by the rest of the
agent (orchestrator, tools, UI).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# Canonical ticket states (see docs/SYSTEM_DESIGN.md §3).
TICKET_STATES = {"NEW", "FOLLOW_UP_REQUIRED", "RESOLVED", "ESCALATED"}


class Ticket(BaseModel):
    """A structured IT-support ticket (FR-08)."""

    ticket_id: Optional[str] = None
    request_id: Optional[str] = None
    employee: str
    email: str = ""
    category: str
    summary: str
    priority_or_risk: str = "medium"
    status: str = "NEW"
    recommended_action: str = ""
    escalation_team: Optional[str] = None
    source_ids: list[str] = Field(default_factory=list)
    created_at: str = ""
    audit_id: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        # Historical seeded tickets carry free-text statuses such as
        # "Resolved (closed)" — only validate canonical agent-created states.
        if value in TICKET_STATES:
            return value
        if "(closed)" in value or value.startswith(("Resolved", "Rejected", "Approved", "Pending", "Escalated")):
            return value
        raise ValueError(f"status must be one of {TICKET_STATES} or a known historical status, got {value!r}")

    @property
    def is_closed(self) -> bool:
        """A ticket is closed (historical / not actionable) when it is either
        explicitly marked closed in the source data or has reached a terminal
        agent state (RESOLVED). ESCALATED tickets remain active — they are
        awaiting human/team handling."""
        if "(closed)" in self.status:
            return True
        return self.status == "RESOLVED"

    @property
    def is_active(self) -> bool:
        return not self.is_closed


class AuditEvent(BaseModel):
    """An auditable record of one agent decision/action (FR-10)."""

    audit_id: str
    timestamp: str = ""
    request_id: Optional[str] = None
    ticket_id: Optional[str] = None
    user_input: str = ""
    retrieved_sources: list[str] = Field(default_factory=list)
    action: str
    status: str = ""
    escalation_decision: Optional[str] = None
    reason: str = ""
    evidence: Optional[str] = None
    agent_tool_action: Optional[str] = None
    destination: Optional[str] = None

    def model_post_init(self, __context: object) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()