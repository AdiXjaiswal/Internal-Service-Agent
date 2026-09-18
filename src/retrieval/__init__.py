"""Retrieval layer for the Internal Service Agent (IT Support).

Provides:
- :class:`~src.retrieval.kb.KBRetriever` — Knowledge base / policy search
- :class:`~src.retrieval.ticket.TicketRetriever` — Ticket history and precedent search
- :class:`~src.retrieval.service.UnifiedRetriever` — Coordinated retrieval service
- :class:`~src.retrieval.models.KBArticle` — Knowledge base article data model
- :class:`~src.retrieval.models.RetrievalResult` — Normalized search result with citations
"""

from __future__ import annotations

from .kb import KBRetriever
from .models import KBArticle, RetrievalResult
from .service import UnifiedRetriever
from .ticket import TicketRetriever

__all__ = [
    "KBRetriever",
    "TicketRetriever",
    "UnifiedRetriever",
    "KBArticle",
    "RetrievalResult",
]
