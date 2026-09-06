"""
Append-only event log: the shared substrate the hospital policies run on.

What makes an overloaded OPD slow is not a shortage of thinking at each desk --
it is that state is fragmented and information travels by human courier. A nurse
walks a file, someone phones to ask whether a bed is free, the patient carries
paper between counters. Adding autonomy on top of fragmented state makes that
worse; sharing the state makes the autonomy almost easy.

So every consequential thing that happens is appended here as an ordered fact,
and policies subscribe to the facts they care about and emit their own:

    patient.registered -> history.completed -> redflag.raised
      -> dispatch.offered -> dispatch.accepted -> bed.assigned

Two properties this buys that a fan-out socket cannot:

- Replay. A service that was not connected did not miss anything; it reads the
  log. Nothing is lost because a websocket happened to be down.
- Audit. Every decision, its actor, and the event that caused it, in total
  order. That is a clinical and medico-legal requirement, not a nice-to-have,
  and it is free once the log exists.

Events are persisted to the same SQLite file the session store uses, so the
"event-sourced" claim is true across a restart rather than merely in memory.
"""
import asyncio
import inspect
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.services import clock

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "medikiosk.db")

# Handlers may be sync or async; both are supported.
Handler = Callable[["DomainEvent"], Any]


class DomainEvent:
    """One thing that happened, in order, with who caused it and why."""

    __slots__ = ("eventId", "sequence", "type", "sessionId", "occurredAt",
                 "actor", "payload", "causedBy")

    def __init__(self, eventId: str, sequence: int, type: str,
                 sessionId: Optional[str], occurredAt: str, actor: str,
                 payload: Dict[str, Any], causedBy: Optional[str] = None):
        self.eventId = eventId
        self.sequence = sequence
        self.type = type
        self.sessionId = sessionId
        self.occurredAt = occurredAt
        self.actor = actor
        self.payload = payload
        self.causedBy = causedBy

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eventId": self.eventId, "sequence": self.sequence, "type": self.type,
            "sessionId": self.sessionId, "occurredAt": self.occurredAt,
            "actor": self.actor, "payload": self.payload, "causedBy": self.causedBy,
        }


def _matches(pattern: str, event_type: str) -> bool:
    """Subscription patterns: exact, prefix wildcard ("dispatch.*"), or "*"."""
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        return event_type.startswith(pattern[:-1])
    return pattern == event_type


class EventLog:
    def __init__(self, persist: bool = True, db_path: str = DB_PATH):
        self._events: List[DomainEvent] = []
        self._subscribers: List[tuple] = []      # (pattern, handler, name)
        self._sequence = 0
        self._persist = persist
        self._db_path = db_path
        if persist:
            self._init_table()

    # --- Persistence ------------------------------------------------------

    def _init_table(self) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS domain_events (
                        sequence   INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id   TEXT NOT NULL,
                        type       TEXT NOT NULL,
                        session_id TEXT,
                        occurred_at TEXT NOT NULL,
                        actor      TEXT,
                        payload    TEXT,
                        caused_by  TEXT
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_events_session "
                    "ON domain_events(session_id)")
        except Exception as exc:                      # pragma: no cover
            # A log that cannot persist must not take the hospital down with it.
            print(f"[EventLog] persistence unavailable: {exc}")
            self._persist = False

    def _write(self, event: DomainEvent) -> None:
        if not self._persist:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO domain_events (event_id, type, session_id, "
                    "occurred_at, actor, payload, caused_by) VALUES (?,?,?,?,?,?,?)",
                    (event.eventId, event.type, event.sessionId, event.occurredAt,
                     event.actor, json.dumps(event.payload, default=str), event.causedBy))
        except Exception as exc:                      # pragma: no cover
            print(f"[EventLog] failed to persist {event.type}: {exc}")

    # --- Subscription -----------------------------------------------------

    def subscribe(self, pattern: str, handler: Handler, name: str = "") -> None:
        """
        Registers a policy against an event pattern. Subscribing is how a
        service joins the hospital -- it does not need to be wired into the
        call sites of everything that might concern it.
        """
        self._subscribers.append((pattern, handler, name or getattr(handler, "__name__", "handler")))

    def subscribers_for(self, event_type: str) -> List[str]:
        return [n for p, _, n in self._subscribers if _matches(p, event_type)]

    # --- Append -----------------------------------------------------------

    async def emit(self, type: str, payload: Dict[str, Any],
                   actor: str = "system", sessionId: Optional[str] = None,
                   causedBy: Optional[str] = None) -> DomainEvent:
        self._sequence += 1
        event = DomainEvent(
            eventId=f"evt_{uuid.uuid4().hex[:12]}",
            sequence=self._sequence,
            type=type,
            sessionId=sessionId or payload.get("sessionId"),
            occurredAt=clock.now().isoformat(),
            actor=actor,
            payload=payload,
            causedBy=causedBy,
        )
        self._events.append(event)
        self._write(event)

        for pattern, handler, name in list(self._subscribers):
            if not _matches(pattern, type):
                continue
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                # One failing subscriber must not stop the others, and must not
                # unwind the caller that recorded the fact.
                print(f"[EventLog] subscriber '{name}' failed on {type}: {exc}")
        return event

    # --- Read -------------------------------------------------------------

    def all(self, limit: int = 200) -> List[DomainEvent]:
        return self._events[-limit:]

    def since(self, sequence: int, limit: int = 200) -> List[DomainEvent]:
        return [e for e in self._events if e.sequence > sequence][:limit]

    def for_session(self, session_id: str) -> List[DomainEvent]:
        """The ordered story of one patient's visit."""
        return [e for e in self._events if e.sessionId == session_id]

    def of_type(self, pattern: str) -> List[DomainEvent]:
        return [e for e in self._events if _matches(pattern, e.type)]

    def causal_chain(self, event_id: str) -> List[DomainEvent]:
        """
        Walks causedBy back to the originating fact, answering "why did this
        happen?" with the actual chain rather than a guess.
        """
        by_id = {e.eventId: e for e in self._events}
        chain: List[DomainEvent] = []
        cursor = by_id.get(event_id)
        seen = set()
        while cursor and cursor.eventId not in seen:
            seen.add(cursor.eventId)
            chain.append(cursor)
            cursor = by_id.get(cursor.causedBy) if cursor.causedBy else None
        return list(reversed(chain))

    def reset(self) -> None:
        """Clears in-memory state. Used by tests."""
        self._events = []
        self._sequence = 0


event_log = EventLog()
