"""Persistence for chunks and their embeddings (float32 vectors stored as BLOBs)."""

import sqlite3

import numpy as np

from app.domain import SearchableChunk


def replace_for_item(
    conn: sqlite3.Connection, item_id: str, texts: list[str], vectors: np.ndarray, embedding_model: str
) -> None:
    """Idempotent: re-indexing an item replaces its chunks instead of duplicating them."""
    conn.execute("DELETE FROM chunks WHERE item_id = ?", (item_id,))
    conn.executemany(
        """INSERT INTO chunks (item_id, chunk_index, text, embedding, embedding_model)
           VALUES (?, ?, ?, ?, ?)""",
        [
            (item_id, index, text, np.asarray(vector, dtype=np.float32).tobytes(), embedding_model)
            for index, (text, vector) in enumerate(zip(texts, vectors, strict=True))
        ],
    )


def load_searchable(conn: sqlite3.Connection, embedding_model: str) -> tuple[list[SearchableChunk], np.ndarray]:
    """All chunks of ready items embedded with `embedding_model`, plus their vectors as an (n, d) matrix."""
    rows = conn.execute(
        """SELECT c.item_id, c.chunk_index, c.text, c.embedding, i.title, i.url, i.source_type
           FROM chunks c JOIN items i ON i.id = c.item_id
           WHERE i.status = 'ready' AND c.embedding_model = ?""",
        (embedding_model,),
    ).fetchall()
    if not rows:
        return [], np.empty((0, 0), dtype=np.float32)

    chunks = [
        SearchableChunk(
            item_id=row["item_id"],
            chunk_index=row["chunk_index"],
            text=row["text"],
            title=row["title"],
            url=row["url"],
            source_type=row["source_type"],
        )
        for row in rows
    ]
    matrix = np.vstack([np.frombuffer(row["embedding"], dtype=np.float32) for row in rows])
    return chunks, matrix
