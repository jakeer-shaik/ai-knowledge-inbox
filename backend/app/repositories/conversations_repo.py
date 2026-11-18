"""Persistence for conversations and their turns (one question + answer each).

Sources are stored as a JSON snapshot of what was cited, so an old answer still
shows its sources after the underlying item is deleted.
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

TITLE_CHARS = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    turn_count: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Turn:
    id: str
    conversation_id: str
    question: str
    search_query: str
    kind: str
    answer: str
    sources: list[dict[str, Any]]
    duration_ms: float | None
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Turn":
        values = {key: row[key] for key in row.keys()}
        values["sources"] = json.loads(values["sources"])
        return cls(**values)


_CONVERSATION_SELECT = """
    SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(t.id) AS turn_count
    FROM conversations c LEFT JOIN turns t ON t.conversation_id = c.id
"""


def _conversation(row: sqlite3.Row) -> Conversation:
    return Conversation(
        id=row["id"], title=row["title"], turn_count=row["turn_count"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def create(conn: sqlite3.Connection, first_question: str) -> str:
    conversation_id = uuid.uuid4().hex
    now = _now()
    conn.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (conversation_id, first_question[:TITLE_CHARS], now, now),
    )
    return conversation_id


def get(conn: sqlite3.Connection, conversation_id: str) -> Conversation | None:
    row = conn.execute(f"{_CONVERSATION_SELECT} WHERE c.id = ? GROUP BY c.id", (conversation_id,)).fetchone()
    return _conversation(row) if row else None


def list_recent(conn: sqlite3.Connection, limit: int) -> list[Conversation]:
    rows = conn.execute(f"{_CONVERSATION_SELECT} GROUP BY c.id ORDER BY c.updated_at DESC LIMIT ?", (limit,))
    return [_conversation(row) for row in rows]


def delete(conn: sqlite3.Connection, conversation_id: str) -> bool:
    return conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,)).rowcount > 0


def add_turn(
    conn: sqlite3.Connection,
    conversation_id: str,
    *,
    question: str,
    search_query: str,
    kind: str,
    answer: str,
    sources: list[dict[str, Any]],
    duration_ms: float,
) -> Turn:
    turn = Turn(
        id=uuid.uuid4().hex, conversation_id=conversation_id, question=question, search_query=search_query,
        kind=kind, answer=answer, sources=sources, duration_ms=duration_ms, created_at=_now(),
    )
    conn.execute(
        """INSERT INTO turns (id, conversation_id, question, search_query, kind, answer, sources, duration_ms, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (turn.id, conversation_id, question, search_query, kind, answer, json.dumps(sources), duration_ms, turn.created_at),
    )
    conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (turn.created_at, conversation_id))
    return turn


def turns(conn: sqlite3.Connection, conversation_id: str) -> list[Turn]:
    rows = conn.execute(
        "SELECT * FROM turns WHERE conversation_id = ? ORDER BY created_at", (conversation_id,)
    ).fetchall()
    return [Turn.from_row(row) for row in rows]


def recent_turns(conn: sqlite3.Connection, conversation_id: str, limit: int) -> list[Turn]:
    """The last `limit` turns, oldest first (the context a follow-up is read against)."""
    rows = conn.execute(
        "SELECT * FROM turns WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?", (conversation_id, limit)
    ).fetchall()
    return [Turn.from_row(row) for row in reversed(rows)]
