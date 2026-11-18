"""The ingestion pipeline end to end: API -> worker -> fetch -> chunk -> embed -> store -> query."""

import sqlite3

import numpy as np
import pytest

from app.core.errors import ServiceUnavailableError
from tests.conftest import step_statuses, wait_for_status
from tests.fakes import KeywordEmbedder

ALL_DONE = {"received": "done", "fetching": "done", "chunking": "done", "embedding": "done", "storing": "done"}


@pytest.fixture
def local_client(make_client):
    """Client allowed to fetch from the local page server."""
    return make_client(FETCH_ALLOW_PRIVATE_HOSTS="true")


def ingest_url(client, url: str) -> dict:
    response = client.post("/ingest", json={"type": "url", "url": url})
    assert response.status_code == 202, response.text
    return wait_for_status(client, response.json()["item"]["id"])


# --- links: every step, success and each failure point ------------------------------------


def test_link_runs_every_step_and_becomes_searchable(local_client, page_server):
    item = ingest_url(local_client, f"{page_server}/article")

    assert item["status"] == "ready"
    assert step_statuses(item) == ALL_DONE
    assert item["title"] == "Connection Pooling Guide"
    fetching = item["steps"][1]
    assert fetching["detail"].startswith("Loaded ") and "127.0.0.1" in fetching["detail"]
    assert "PgBouncer" in item["content_preview"]
    assert "Copyright Example Corp" not in (item["content_preview"] or "")  # boilerplate stripped

    answer = local_client.post("/query", json={"question": "What does PgBouncer transaction pooling do?"}).json()
    assert answer["sources"][0]["item_id"] == item["id"]
    assert answer["sources"][0]["url"] == f"{page_server}/article"
    assert "[1]" in answer["answer"]


def test_plain_text_link_is_supported(local_client, page_server):
    item = ingest_url(local_client, f"{page_server}/notes.txt")
    assert item["status"] == "ready"


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("/missing", "HTTP 404"),
        ("/data.json", "Unsupported content type 'application/json'"),
        ("/empty", "Couldn't find readable text"),
    ],
)
def test_link_failures_stop_at_loading_page(local_client, page_server, path, reason):
    item = ingest_url(local_client, f"{page_server}{path}")

    assert item["status"] == "failed"
    assert reason in item["error"]
    assert step_statuses(item) == {
        "received": "done",
        "fetching": "failed",
        "chunking": "pending",
        "embedding": "pending",
        "storing": "pending",
    }
    assert reason in item["steps"][1]["detail"]


def test_unreachable_host_fails_with_reason(local_client):
    item = ingest_url(local_client, "http://127.0.0.1:9/nothing-listens-here")
    assert item["status"] == "failed"
    assert "Couldn't connect" in item["error"]


def test_oversized_page_is_rejected(make_client, page_server):
    client = make_client(FETCH_ALLOW_PRIVATE_HOSTS="true", FETCH_MAX_BYTES="100")
    item = ingest_url(client, f"{page_server}/article")
    assert item["status"] == "failed"
    assert "larger than" in item["error"]


# --- AI provider failures surface on the right step ---------------------------------------


class FailingEmbedder(KeywordEmbedder):
    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        raise ServiceUnavailableError("Gemini is rate limiting requests.", code="LLM_RATE_LIMITED")


def test_embedding_failure_is_reported_on_embedding_step(make_client):
    client = make_client(embedder=FailingEmbedder())
    response = client.post("/ingest", json={"type": "note", "content": "Some note worth indexing."})
    item = wait_for_status(client, response.json()["item"]["id"])

    assert item["status"] == "failed"
    assert item["error"] == "Gemini is rate limiting requests."
    assert step_statuses(item) == {"received": "done", "chunking": "done", "embedding": "failed", "storing": "pending"}


# --- notes: chunk counts flow through every step ------------------------------------------


def test_long_note_is_split_into_multiple_chunks(client):
    paragraphs = [f"Paragraph {i} explains topic {i} in enough words to matter. " * 6 for i in range(8)]
    response = client.post("/ingest", json={"type": "note", "content": "\n\n".join(paragraphs)})
    item = wait_for_status(client, response.json()["item"]["id"])

    assert item["chunk_count"] > 1
    chunking, embedding, storing = item["steps"][1:]
    assert chunking["detail"].startswith(f"{item['chunk_count']} chunks")
    assert embedding["detail"].startswith(f"{item['chunk_count']} vectors")
    assert storing["detail"] == f"Saved {item['chunk_count']} chunks with their vectors"


def test_deleting_an_item_removes_it_from_search(client):
    response = client.post("/ingest", json={"type": "note", "content": "Kubernetes pods restart when probes fail."})
    item = wait_for_status(client, response.json()["item"]["id"])
    assert client.post("/query", json={"question": "Why do pods restart?"}).json()["sources"]

    client.delete(f"/items/{item['id']}")
    assert client.post("/query", json={"question": "Why do pods restart?"}).json()["sources"] == []


# --- durability: restart recovery and schema migration ------------------------------------


def test_unfinished_items_are_requeued_on_startup(make_client, tmp_path):
    first = make_client()
    item_id = first.post("/ingest", json={"type": "note", "content": "Survives a restart."}).json()["item"]["id"]
    wait_for_status(first, item_id)

    # Simulate a crash mid-pipeline: item stuck in "processing" with a half-finished step.
    with sqlite3.connect(tmp_path / "test.db") as conn:
        conn.execute("UPDATE items SET status = 'processing' WHERE id = ?", (item_id,))

    restarted = make_client()
    item = wait_for_status(restarted, item_id)
    assert item["status"] == "ready"
    assert all(step["status"] == "done" for step in item["steps"])


def test_old_database_without_steps_column_is_migrated(make_client, tmp_path):
    with sqlite3.connect(tmp_path / "test.db") as conn:
        conn.execute(
            """CREATE TABLE items (id TEXT PRIMARY KEY, source_type TEXT NOT NULL, title TEXT, url TEXT,
               raw_content TEXT, status TEXT NOT NULL, error TEXT, chunk_count INTEGER NOT NULL DEFAULT 0,
               created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
        )
        conn.execute(
            "INSERT INTO items VALUES ('old', 'note', 'Legacy', NULL, 'text', 'ready', NULL, 1, "
            "'2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
        )

    client = make_client()
    item = client.get("/items/old").json()["item"]
    assert item["title"] == "Legacy"
    assert item["steps"] == []
