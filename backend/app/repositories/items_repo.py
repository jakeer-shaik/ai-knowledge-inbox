"""Persistence for items. All item SQL lives here; callers pass an open connection (one transaction)."""

import sqlite3
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone

from app.domain import Item, ItemStatus, PipelineStep, SourceType, steps_to_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert(
    conn: sqlite3.Connection,
    *,
    source_type: SourceType,
    title: str | None,
    url: str | None,
    raw_content: str | None,
    steps: list[PipelineStep],
) -> Item:
    item_id = uuid.uuid4().hex
    now = _now()
    conn.execute(
        """INSERT INTO items (id, source_type, title, url, raw_content, status, steps, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
        (item_id, source_type, title, url, raw_content, steps_to_json(steps), now, now),
    )
    item = get(conn, item_id)
    assert item is not None
    return item


def get(conn: sqlite3.Connection, item_id: str) -> Item | None:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return Item.from_row(row) if row else None


def list_recent(conn: sqlite3.Connection, limit: int) -> list[Item]:
    rows = conn.execute("SELECT * FROM items ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [Item.from_row(row) for row in rows]


def list_ids_with_status(conn: sqlite3.Connection, statuses: Iterable[ItemStatus]) -> list[str]:
    statuses = list(statuses)
    placeholders = ",".join("?" * len(statuses))
    rows = conn.execute(
        f"SELECT id FROM items WHERE status IN ({placeholders}) ORDER BY created_at", statuses
    ).fetchall()
    return [row["id"] for row in rows]


def count_ready(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM items WHERE status = 'ready'").fetchone()[0]


def set_status(conn: sqlite3.Connection, item_id: str, status: ItemStatus, error: str | None = None) -> None:
    conn.execute(
        "UPDATE items SET status = ?, error = ?, updated_at = ? WHERE id = ?",
        (status, error, _now(), item_id),
    )


def update_steps(conn: sqlite3.Connection, item_id: str, steps: list[PipelineStep]) -> None:
    conn.execute(
        "UPDATE items SET steps = ?, updated_at = ? WHERE id = ?",
        (steps_to_json(steps), _now(), item_id),
    )


def mark_ready(
    conn: sqlite3.Connection, item_id: str, *, title: str | None, raw_content: str, chunk_count: int
) -> None:
    conn.execute(
        """UPDATE items SET status = 'ready', error = NULL, title = ?, raw_content = ?,
                  chunk_count = ?, updated_at = ?
           WHERE id = ?""",
        (title, raw_content, chunk_count, _now(), item_id),
    )


def delete(conn: sqlite3.Connection, item_id: str) -> bool:
    return conn.execute("DELETE FROM items WHERE id = ?", (item_id,)).rowcount > 0
