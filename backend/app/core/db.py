"""SQLite connection handling and schema.

A short-lived connection per unit of work keeps things simple and thread-safe.
WAL mode lets the background worker write while API requests read.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id           TEXT PRIMARY KEY,
    source_type  TEXT NOT NULL CHECK (source_type IN ('note', 'url')),
    title        TEXT,
    url          TEXT,
    raw_content  TEXT,
    status       TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
    error        TEXT,
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    steps        TEXT NOT NULL DEFAULT '[]',  -- JSON: ingestion pipeline progress
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_created_at ON items (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_status ON items (status);

CREATE TABLE IF NOT EXISTS chunks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          TEXT NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    chunk_index      INTEGER NOT NULL,
    text             TEXT NOT NULL,
    embedding        BLOB NOT NULL,     -- float32 vector
    embedding_model  TEXT NOT NULL,     -- vectors from different models are never compared
    UNIQUE (item_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_item_id ON chunks (item_id);
CREATE INDEX IF NOT EXISTS idx_chunks_model ON chunks (embedding_model);

CREATE TABLE IF NOT EXISTS conversations (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,     -- the first question
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL      -- last turn; history is ordered by this
);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations (updated_at DESC);

CREATE TABLE IF NOT EXISTS turns (
    id               TEXT PRIMARY KEY,
    conversation_id  TEXT NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    question         TEXT NOT NULL,
    search_query     TEXT NOT NULL,  -- standalone question actually searched (rewritten for follow-ups)
    kind             TEXT NOT NULL DEFAULT 'answer' CHECK (kind IN ('answer', 'not_found', 'small_talk')),
    answer           TEXT NOT NULL,
    sources          TEXT NOT NULL,  -- JSON snapshot, so history survives item deletion
    duration_ms      REAL,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_turns_conversation ON turns (conversation_id, created_at);
"""


def _database_path() -> Path:
    return Path(get_settings().database_path)


def init_db() -> None:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for databases created by earlier versions."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
    if "steps" not in columns:
        conn.execute("ALTER TABLE items ADD COLUMN steps TEXT NOT NULL DEFAULT '[]'")

    turn_columns = {row[1] for row in conn.execute("PRAGMA table_info(turns)")}
    if "kind" not in turn_columns:
        conn.execute("ALTER TABLE turns ADD COLUMN kind TEXT NOT NULL DEFAULT 'answer'")

    # v0.3 kept single questions in `queries`; each becomes a one-turn conversation.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'queries'").fetchone():
        conn.execute(
            """INSERT OR IGNORE INTO conversations (id, title, created_at, updated_at)
               SELECT id, substr(question, 1, 120), created_at, created_at FROM queries"""
        )
        conn.execute(
            """INSERT OR IGNORE INTO turns
                   (id, conversation_id, question, search_query, answer, sources, duration_ms, created_at)
               SELECT id, id, question, question, answer, sources, duration_ms, created_at FROM queries"""
        )
        conn.execute("DROP TABLE queries")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """One transaction: commits on success, rolls back on any exception."""
    conn = sqlite3.connect(_database_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
