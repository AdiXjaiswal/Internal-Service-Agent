"""Data models for the retrieval layer."""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class KBArticle(BaseModel):
    """Structured representation of a Knowledge Base entry or policy."""

    id: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        return f"{self.id} - {self.title}: {self.content}"


class RetrievalResult(BaseModel):
    """Normalized search result returned by any retriever (KB or Ticket)."""

    source_id: str
    source_type: Literal["kb", "ticket"]
    title: str
    content: str
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    citation: str = ""

    def model_post_init(self, __context: object) -> None:
        if not self.citation:
            self.citation = f"[{self.source_id}]"

    @property
    def is_ticket(self) -> bool:
        return self.source_type == "ticket"

    @property
    def is_kb(self) -> bool:
        return self.source_type == "kb"

    @property
    def is_active(self) -> bool:
        """Returns True if this is an active ticket, or True for KB articles."""
        if self.source_type == "ticket":
            return bool(self.metadata.get("is_active", False))
        return True

    @property
    def is_closed(self) -> bool:
        """Returns True if this is a closed historical ticket."""
        if self.source_type == "ticket":
            return bool(self.metadata.get("is_closed", False))
        return False
