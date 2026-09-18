"""Unified retrieval service combining Knowledge Base policies and Ticket history."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..storage.store import Store

from .kb import KBRetriever
from .models import KBArticle, RetrievalResult
from .ticket import TicketRetriever


class UnifiedRetriever:
    """Unified retrieval interface serving policies and ticket context to the agent.

    Parameters
    ----------
    kb_retriever:
        Pre-configured :class:`KBRetriever`.
    ticket_retriever:
        Pre-configured :class:`TicketRetriever`.
    kb_path:
        Path to ``data/knowledge_base.json`` if ``kb_retriever`` is not provided.
    store:
        Optional :class:`Store` instance if ``ticket_retriever`` is not provided.
    db_path:
        Path to SQLite database if ``ticket_retriever`` and ``store`` are not provided.
    """

    def __init__(
        self,
        kb_retriever: Optional[KBRetriever] = None,
        ticket_retriever: Optional[TicketRetriever] = None,
        kb_path: str | Path = "data/knowledge_base.json",
        store: Optional[Store] = None,
        db_path: str | Path = "data/app.db",
    ) -> None:
        self.kb = kb_retriever or KBRetriever(data_path=kb_path)
        self.tickets = ticket_retriever or TicketRetriever(store=store, db_path=db_path)

    def close(self) -> None:
        self.tickets.close()

    def __enter__(self) -> "UnifiedRetriever":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def search(
        self,
        query: str,
        kb_k: int = 3,
        ticket_k: int = 2,
        active_only: bool = False,
    ) -> list[RetrievalResult]:
        """Query both Knowledge Base and Ticket queues, returning combined results."""
        kb_results = self.kb.search(query, top_k=kb_k)
        ticket_results = self.tickets.search(query, top_k=ticket_k, active_only=active_only)
        return kb_results + ticket_results

    def get_by_id(self, source_id: str) -> Optional[RetrievalResult]:
        """Look up a specific policy or ticket by ID."""
        cleaned = source_id.strip()
        if cleaned.upper().startswith("TK-"):
            return self.tickets.get(cleaned)

        kb_item = self.kb.get(cleaned)
        if kb_item:
            return RetrievalResult(
                source_id=kb_item.id,
                source_type="kb",
                title=kb_item.title,
                content=kb_item.content,
                score=1.0,
                citation=f"[{kb_item.id}]",
            )
        return None

    def format_context(self, results: list[RetrievalResult]) -> str:
        """Format retrieval results into structured context suitable for LLM prompts."""
        if not results:
            return "No relevant knowledge base policies or ticket history found."

        kb_items = [r for r in results if r.is_kb]
        ticket_items = [r for r in results if r.is_ticket]

        sections: list[str] = []

        if kb_items:
            sections.append("### Applicable Knowledge Base Policies & Guidelines:")
            for item in kb_items:
                sections.append(
                    f"- **{item.citation} {item.title}** (Relevance: {item.score:.2f})\n"
                    f"  {item.content.strip()}"
                )

        if ticket_items:
            sections.append("\n### Relevant Ticket History & Precedents:")
            for item in ticket_items:
                state_note = (
                    "HISTORICAL PRECEDENT (CLOSED - NOT ACTIONABLE)"
                    if item.is_closed
                    else f"ACTIVE TICKET ({item.metadata.get('status', 'ACTIVE')})"
                )
                sections.append(
                    f"- **{item.citation} {item.title}** [{state_note}]\n"
                    f"  {item.content.replace(chr(10), chr(10) + '  ')}"
                )

        return "\n".join(sections)
