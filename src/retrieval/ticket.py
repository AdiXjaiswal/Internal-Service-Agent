"""Ticket retrieval engine supporting active case lookup and historical precedent search."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..storage.models import Ticket
from ..storage.store import Store

from .kb import _tokenize
from .models import RetrievalResult


class TicketRetriever:
    """Searches active and historical IT tickets stored in SQLite.

    Parameters
    ----------
    store:
        Existing :class:`~src.storage.store.Store` instance. If None,
        creates one using ``db_path``.
    db_path:
        Path to SQLite database (default: ``data/app.db``).
    """

    def __init__(
        self,
        store: Optional[Store] = None,
        db_path: str | Path = "data/app.db",
    ) -> None:
        if store is not None:
            self.store = store
            self._owns_store = False
        else:
            self.store = Store(db_path=db_path, seed=True)
            self._owns_store = True

    def close(self) -> None:
        if self._owns_store:
            self.store.close()

    def get(self, ticket_id: str) -> Optional[RetrievalResult]:
        """Fetch a specific ticket by its ID and return as a RetrievalResult."""
        t = self.store.get_ticket(ticket_id)
        if not t:
            return None
        return self._to_retrieval_result(t, score=1.0)

    def search(
        self,
        query: str,
        top_k: int = 3,
        active_only: bool = False,
        threshold: float = 0.0,
    ) -> list[RetrievalResult]:
        """Search tickets using multi-field token matching and status weighting.

        Parameters
        ----------
        query:
            Free-text query or employee issue.
        top_k:
            Maximum results to return.
        active_only:
            If True, only return active tickets. If False, returns both active and closed.
        threshold:
            Minimum score threshold.
        """
        if not query.strip():
            return []

        # Retrieve candidate tickets from storage
        candidates = self.store.list_tickets(active_only=active_only)
        if not candidates:
            return []

        q_tokens = set(_tokenize(query))
        q_lower = query.lower()

        scored: list[tuple[float, Ticket]] = []

        for ticket in candidates:
            score = 0.0
            t_id = (ticket.ticket_id or "").lower()
            if t_id and t_id in q_lower:
                score += 20.0

            # Employee name match
            emp_tokens = set(_tokenize(ticket.employee))
            if emp_tokens.intersection(q_tokens):
                score += 5.0

            # Category match
            cat_tokens = set(_tokenize(ticket.category))
            score += len(cat_tokens.intersection(q_tokens)) * 3.0

            # Summary match
            sum_tokens = set(_tokenize(ticket.summary))
            score += len(sum_tokens.intersection(q_tokens)) * 2.5

            # Recommended action / resolution match
            act_tokens = set(_tokenize(ticket.recommended_action))
            score += len(act_tokens.intersection(q_tokens)) * 1.5

            if score > threshold:
                scored.append((score, ticket))

        scored.sort(key=lambda x: x[0], reverse=True)

        max_score = scored[0][0] if scored and scored[0][0] > 0 else 1.0
        results: list[RetrievalResult] = []

        for s, ticket in scored[:top_k]:
            normalized_score = min(1.0, round(s / max(max_score, 1.0), 3))
            results.append(self._to_retrieval_result(ticket, score=normalized_score))

        return results

    def list_precedents(
        self,
        query: Optional[str] = None,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Find closed historical tickets that can serve as precedents."""
        if query:
            all_results = self.search(query, top_k=top_k * 2, active_only=False)
            return [r for r in all_results if r.is_closed][:top_k]

        all_tickets = self.store.list_tickets(active_only=False)
        closed_tickets = [t for t in all_tickets if t.is_closed][:top_k]
        return [self._to_retrieval_result(t, score=0.5) for t in closed_tickets]

    def _to_retrieval_result(self, ticket: Ticket, score: float = 0.0) -> RetrievalResult:
        t_id = ticket.ticket_id or "TK-UNKNOWN"
        status_label = "Closed (Historical Precedent)" if ticket.is_closed else f"Active ({ticket.status})"
        content_lines = [
            f"Employee: {ticket.employee}",
            f"Category: {ticket.category}",
            f"Summary: {ticket.summary}",
            f"Status: {ticket.status} [{status_label}]",
        ]
        if ticket.recommended_action:
            content_lines.append(f"Recommended Action: {ticket.recommended_action}")
        if ticket.escalation_team:
            content_lines.append(f"Escalation Team: {ticket.escalation_team}")

        return RetrievalResult(
            source_id=t_id,
            source_type="ticket",
            title=f"{ticket.employee} - {ticket.summary}",
            content="\n".join(content_lines),
            score=score,
            metadata={
                "ticket_id": t_id,
                "status": ticket.status,
                "is_active": ticket.is_active,
                "is_closed": ticket.is_closed,
                "employee": ticket.employee,
                "category": ticket.category,
                "escalation_team": ticket.escalation_team,
            },
            citation=f"[{t_id}]",
        )
