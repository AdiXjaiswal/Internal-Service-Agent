"""Storage layer for the Internal Service Agent (IT Support).

Provides:
- :class:`~storage.store.Store` — SQLite-backed persistence
- :class:`~storage.models.Ticket` — structured ticket model
- :class:`~storage.models.AuditEvent` — audit trail model
- :func:`~storage.seeding.seed_tickets` — seed historical tickets
"""

from __future__ import annotations

from .models import AuditEvent, Ticket
from .seeding import seed_tickets
from .store import Store

__all__ = ["Store", "Ticket", "AuditEvent", "seed_tickets"]
