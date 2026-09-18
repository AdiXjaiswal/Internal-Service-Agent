"""Convenience helpers for loading bundled source data into storage."""

from __future__ import annotations

from pathlib import Path

from .store import Store


def seed_tickets(store: Store, data_path: str | Path = "data/tickets.json") -> int:
    """Load the historical ticket queue from ``data/tickets.json``.

    The function is idempotent: already-present ticket IDs are skipped.
    """
    return store.seed_tickets(data_path)
