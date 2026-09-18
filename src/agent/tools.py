"""Tool implementations for the agent orchestration layer (SYSTEM_DESIGN.md §2.6).

Exposes:
- `search_knowledge_base(query)`
- `search_tickets(query)`
- `check_policy(category, details)`
- `create_ticket(ticket_data)`
- `update_ticket(ticket_id, data)`
- `create_audit_event(event)`
"""

from __future__ import annotations

from typing import Any, Optional

from ..policy.engine import PolicyEngine
from ..policy.models import PolicyRequest, PolicyVerdict
from ..retrieval.models import RetrievalResult
from ..retrieval.service import UnifiedRetriever
from ..storage.models import AuditEvent, Ticket
from ..storage.store import Store


class AgentTools:
    """Tool provider wrapping retrieval, deterministic policy engine, and SQLite storage."""

    def __init__(
        self,
        retriever: Optional[UnifiedRetriever] = None,
        policy_engine: Optional[PolicyEngine] = None,
        store: Optional[Store] = None,
    ) -> None:
        self.retriever = retriever or UnifiedRetriever()
        self.policy_engine = policy_engine or PolicyEngine()
        self.store = store or Store()

    def search_knowledge_base(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        """Search company knowledge base policies and documentation."""
        return self.retriever.kb.search(query=query, top_k=top_k)

    def search_tickets(
        self, query: str, top_k: int = 2, active_only: bool = False
    ) -> list[RetrievalResult]:
        """Search ticket queue for previous resolutions or active cases."""
        return self.retriever.tickets.search(
            query=query, top_k=top_k, active_only=active_only
        )

    def check_policy(self, request: PolicyRequest) -> PolicyVerdict:
        """Run deterministic policy engine against the normalized request context."""
        return self.policy_engine.evaluate(request)

    def create_ticket(self, ticket: Ticket) -> Ticket:
        """Persist a new IT-support ticket."""
        return self.store.create_ticket(ticket)

    def update_ticket(self, ticket_id: str, **updates: Any) -> Optional[Ticket]:
        """Update an existing IT-support ticket with new fields."""
        return self.store.update_ticket(ticket_id, **updates)

    def create_audit_event(self, event: AuditEvent) -> AuditEvent:
        """Persist an audit trail entry for tracking and compliance."""
        return self.store.create_audit_event(event)
