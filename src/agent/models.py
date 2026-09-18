"""Data models for the agent orchestration layer.

Defines:
- :class:`AgentRequest`  — Incoming IT-support request from employee/UI
- :class:`AgentResponse` — Structured outcome returned to employee/UI
- :class:`AgentState`    — State schema passed through the LangGraph workflow
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from ..policy.models import PolicyVerdict
from ..retrieval.models import RetrievalResult
from ..storage.models import Ticket


class AgentRequest(BaseModel):
    """Input request from an employee or reviewer (FR-01)."""

    employee: str = Field(description="Name of the employee making the request")
    email: str = Field(default="", description="Email of the employee")
    request: str = Field(description="Free-text IT-support request")
    request_id: Optional[str] = Field(default=None, description="Optional external request identifier")
    ticket_id: Optional[str] = Field(default=None, description="Optional existing ticket ID if updating/continuing")


class AgentResponse(BaseModel):
    """Structured response returned by the orchestrator (FR-08, FR-09, FR-10)."""

    category: str = Field(description="Classified request category")
    status: str = Field(description="resolved | follow_up_required | escalated")
    response: str = Field(description="Customer-facing response or follow-up question")
    action: str = Field(description="Action taken (resolve, escalate, follow_up)")
    escalation_team: Optional[str] = Field(default=None, description="Team to which the request was routed, if escalated")
    sources: list[str] = Field(default_factory=list, description="IDs of knowledge base articles or tickets cited")
    ticket: Optional[dict[str, Any]] = Field(default=None, description="Full structured ticket representation")
    audit_id: Optional[str] = Field(default=None, description="Identifier of the recorded audit trail event")


class AgentState(BaseModel):
    """Execution state container flowing across LangGraph nodes."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    request: AgentRequest
    extracted_entities: dict[str, Any] = Field(default_factory=dict)
    retrieval_results: list[Any] = Field(default_factory=list)
    kb_ids: list[str] = Field(default_factory=list)
    ticket_ids: list[str] = Field(default_factory=list)
    policy_verdict: Optional[Any] = None
    generated_response: str = ""
    ticket: Optional[Any] = None
    audit_id: Optional[str] = None
    final_response: Optional[AgentResponse] = None
