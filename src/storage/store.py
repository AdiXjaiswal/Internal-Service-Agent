"""SQLite-backed persistence for tickets and audit events."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from .models import AuditEvent, Ticket

_TICKET_FIELDS = frozenset(
    {
        "ticket_id", "request_id", "employee", "email", "category", "summary",
        "priority_or_risk", "status", "recommended_action", "escalation_team",
        "source_ids", "created_at", "audit_id",
    }
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: str | None) -> list:
    if not value:
        return []
    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return list(data) if isinstance(data, list) else []


class Store:
    """SQLite-backed persistence for tickets and audit events.

    Parameters
    ----------
    db_path:
        Path to the SQLite database. Defaults to ``data/app.db``
        relative to the repository root.
    seed:
        When ``True``, populate the ticket table from ``data/tickets.json``
        if the database is empty.
    """

    def __init__(self, db_path: str | Path = "data/app.db", seed: bool = False) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._create_schema()
        if seed:
            self.seed_tickets()

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # schema
    # ------------------------------------------------------------------ #
    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id          TEXT PRIMARY KEY,
                request_id         TEXT,
                employee           TEXT NOT NULL,
                email              TEXT DEFAULT '',
                category           TEXT NOT NULL,
                summary            TEXT NOT NULL,
                priority_or_risk   TEXT DEFAULT 'medium',
                status             TEXT DEFAULT 'NEW',
                recommended_action TEXT DEFAULT '',
                escalation_team    TEXT,
                source_ids         TEXT DEFAULT '[]',
                created_at         TEXT NOT NULL,
                audit_id           TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                audit_id             TEXT PRIMARY KEY,
                timestamp            TEXT NOT NULL,
                request_id           TEXT,
                ticket_id            TEXT,
                user_input           TEXT DEFAULT '',
                retrieved_sources    TEXT DEFAULT '[]',
                action               TEXT NOT NULL,
                status               TEXT DEFAULT '',
                escalation_decision  TEXT,
                reason               TEXT DEFAULT '',
                evidence             TEXT,
                agent_tool_action    TEXT,
                destination          TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
            CREATE INDEX IF NOT EXISTS idx_tickets_employee ON tickets(employee);
            CREATE INDEX IF NOT EXISTS idx_audit_request_id ON audit_events(request_id);
            CREATE INDEX IF NOT EXISTS idx_audit_ticket_id ON audit_events(ticket_id);
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _next_ticket_id(self) -> str:
        row = self._conn.execute(
            "SELECT ticket_id FROM tickets "
            "WHERE ticket_id LIKE 'TK-%' "
            "ORDER BY CAST(SUBSTR(ticket_id, 4) AS INTEGER) DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return "TK-1000"
        try:
            n = int(row["ticket_id"][3:]) + 1
        except (ValueError, IndexError):
            n = 1000
        return f"TK-{n:04d}"

    def _next_audit_id(self) -> str:
        row = self._conn.execute(
            "SELECT audit_id FROM audit_events "
            "WHERE audit_id LIKE 'AUD-%' "
            "ORDER BY CAST(SUBSTR(audit_id, 5) AS INTEGER) DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return "AUD-0001"
        try:
            n = int(row["audit_id"][4:]) + 1
        except (ValueError, IndexError):
            n = 1
        return f"AUD-{n:04d}"

    # ------------------------------------------------------------------ #
    # tickets
    # ------------------------------------------------------------------ #
    def create_ticket(self, ticket: Ticket) -> Ticket:
        """Persist a ticket. If ``ticket_id`` is empty, generate one."""
        if not ticket.ticket_id:
            ticket = ticket.model_copy(update={"ticket_id": self._next_ticket_id()})
        created_at = ticket.created_at or _now_iso()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO tickets (
                    ticket_id, request_id, employee, email, category, summary,
                    priority_or_risk, status, recommended_action, escalation_team,
                    source_ids, created_at, audit_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket.ticket_id,
                    ticket.request_id,
                    ticket.employee,
                    ticket.email,
                    ticket.category,
                    ticket.summary,
                    ticket.priority_or_risk,
                    ticket.status,
                    ticket.recommended_action,
                    ticket.escalation_team,
                    _json_dumps(ticket.source_ids),
                    created_at,
                    ticket.audit_id,
                ),
            )
        return ticket.model_copy(update={"created_at": created_at})

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        row = self._conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        return self._row_to_ticket(row) if row else None

    def update_ticket(self, ticket_id: str, **updates: Any) -> Optional[Ticket]:
        """Patch a ticket with the supplied fields. Returns ``None`` if
        the ticket does not exist."""
        existing = self.get_ticket(ticket_id)
        if existing is None:
            return None
        fields = {k: v for k, v in updates.items() if k in _TICKET_FIELDS}
        if not fields:
            return existing
        if "source_ids" in fields and not isinstance(fields["source_ids"], str):
            fields["source_ids"] = _json_dumps(fields["source_ids"])
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [ticket_id]
        with self._conn:
            self._conn.execute(
                f"UPDATE tickets SET {set_clause} WHERE ticket_id = ?", values
            )
        return self.get_ticket(ticket_id)

    def list_tickets(
        self,
        status: Optional[str] = None,
        active_only: bool = False,
        employee: Optional[str] = None,
    ) -> list[Ticket]:
        """Return tickets, optionally filtered by status/employee and
        optionally restricted to active (non-historical) tickets."""
        query = "SELECT * FROM tickets WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if employee:
            query += " AND employee = ?"
            params.append(employee)
        query += " ORDER BY created_at DESC, ticket_id DESC"
        rows = self._conn.execute(query, params).fetchall()
        tickets = [self._row_to_ticket(r) for r in rows]
        if active_only:
            tickets = [t for t in tickets if t.is_active]
        return tickets

    def search_tickets(
        self, query: str, active_only: bool = False
    ) -> list[Ticket]:
        """Lightweight keyword search across ticket text fields."""
        q = f"%{query.strip()}%"
        rows = self._conn.execute(
            """
            SELECT * FROM tickets
            WHERE summary LIKE ? OR category LIKE ?
               OR employee LIKE ? OR recommended_action LIKE ?
               OR escalation_team LIKE ?
            ORDER BY created_at DESC, ticket_id DESC
            """,
            (q, q, q, q, q),
        ).fetchall()
        tickets = [self._row_to_ticket(r) for r in rows]
        if active_only:
            tickets = [t for t in tickets if t.is_active]
        return tickets

    # ------------------------------------------------------------------ #
    # audit events
    # ------------------------------------------------------------------ #
    def create_audit_event(self, event: AuditEvent) -> AuditEvent:
        """Persist an audit event. Generate ``audit_id`` if empty."""
        if not event.audit_id:
            event = event.model_copy(update={"audit_id": self._next_audit_id()})
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO audit_events (
                    audit_id, timestamp, request_id, ticket_id, user_input,
                    retrieved_sources, action, status, escalation_decision,
                    reason, evidence, agent_tool_action, destination
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.audit_id,
                    event.timestamp,
                    event.request_id,
                    event.ticket_id,
                    event.user_input,
                    _json_dumps(event.retrieved_sources),
                    event.action,
                    event.status,
                    event.escalation_decision,
                    event.reason,
                    event.evidence,
                    event.agent_tool_action,
                    event.destination,
                ),
            )
        return event

    # alias matching the action-layer tool name (docs/SYSTEM_DESIGN.md §2.6)
    append_audit_event = create_audit_event

    def get_audit_event(self, audit_id: str) -> Optional[AuditEvent]:
        """Fetch a single audit event by its identifier."""
        row = self._conn.execute(
            "SELECT * FROM audit_events WHERE audit_id = ?", (audit_id,)
        ).fetchone()
        return self._row_to_audit(row) if row else None

    def get_audit_events(
        self,
        request_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
    ) -> list[AuditEvent]:
        """Return audit events, newest first."""
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: list[Any] = []
        if request_id:
            query += " AND request_id = ?"
            params.append(request_id)
        if ticket_id:
            query += " AND ticket_id = ?"
            params.append(ticket_id)
        query += " ORDER BY timestamp ASC, audit_id ASC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_audit(r) for r in rows]

    # ------------------------------------------------------------------ #
    # seeding
    # ------------------------------------------------------------------ #
    def seed_tickets(self, data_path: str | Path = "data/tickets.json") -> int:
        """Populate the ticket table from the supplied historical ticket
        queue (data/tickets.json). Returns the number of inserted records."""
        path = Path(data_path)
        if not path.exists():
            return 0
        records = json.loads(path.read_text(encoding="utf-8"))
        inserted = 0
        for rec in records:
            tid = rec.get("ticket_id")
            if not tid or self.get_ticket(tid):
                continue
            ticket = Ticket(
                ticket_id=tid,
                employee=rec.get("employee", ""),
                email=rec.get("email", ""),
                category=rec.get("category", "Other/unclear"),
                summary=rec.get("issue_summary", ""),
                status=rec.get("status", "NEW"),
                source_ids=[tid],
                created_at=rec.get("date_opened", "") or rec.get("created_at", ""),
            )
            self.create_ticket(ticket)
            inserted += 1
        return inserted

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _row_to_ticket(self, row: sqlite3.Row) -> Ticket:
        return Ticket(
            ticket_id=row["ticket_id"],
            request_id=row["request_id"],
            employee=row["employee"],
            email=row["email"],
            category=row["category"],
            summary=row["summary"],
            priority_or_risk=row["priority_or_risk"],
            status=row["status"],
            recommended_action=row["recommended_action"],
            escalation_team=row["escalation_team"],
            source_ids=_json_loads(row["source_ids"]),
            created_at=row["created_at"],
            audit_id=row["audit_id"],
        )

    def _row_to_audit(self, row: sqlite3.Row) -> AuditEvent:
        return AuditEvent(
            audit_id=row["audit_id"],
            timestamp=row["timestamp"],
            request_id=row["request_id"],
            ticket_id=row["ticket_id"],
            user_input=row["user_input"],
            retrieved_sources=_json_loads(row["retrieved_sources"]),
            action=row["action"],
            status=row["status"],
            escalation_decision=row["escalation_decision"],
            reason=row["reason"],
            evidence=row["evidence"],
            agent_tool_action=row["agent_tool_action"],
            destination=row["destination"],
        )
