import pytest

from tests.conftest import wait_for_status

POOLING_NOTE = (
    "We hit too many connections on Postgres during the load test. "
    "The fix is to put PgBouncer in front of the database in transaction pooling mode. "
    "Cap the app pool at 20 connections per instance."
)


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"]
    assert error["request_id"] == response.headers["X-Request-ID"]
    return error


# --- health / cross-cutting ---------------------------------------------------------------


def test_health_reports_worker(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["worker_running"] is True


def test_unknown_route_uses_error_shape(client):
    assert_error(client.get("/nope"), 404, "NOT_FOUND")


def test_wrong_method_is_405(client):
    assert_error(client.get("/query"), 405, "METHOD_NOT_ALLOWED")


def test_request_id_is_echoed(client):
    response = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert response.headers["X-Request-ID"] == "trace-123"


# --- POST /ingest ---------------------------------------------------------------------------


def test_ingest_note_is_accepted_then_indexed(client):
    response = client.post("/ingest", json={"type": "note", "content": POOLING_NOTE})

    assert response.status_code == 202
    item = response.json()["item"]
    assert item["status"] == "pending"
    assert item["source_type"] == "note"
    assert response.headers["Location"] == f"/items/{item['id']}"

    assert [s["name"] for s in item["steps"]] == ["received", "chunking", "embedding", "storing"]
    assert [s["status"] for s in item["steps"]] == ["done", "pending", "pending", "pending"]

    indexed = wait_for_status(client, item["id"])
    assert indexed["status"] == "ready"
    assert indexed["chunk_count"] >= 1
    assert indexed["title"].startswith("We hit too many connections")
    assert all(s["status"] == "done" for s in indexed["steps"])
    assert all(s["duration_ms"] is not None for s in indexed["steps"])
    assert "chunk" in indexed["steps"][1]["detail"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"type": "note"}, "content"),
        ({"type": "note", "content": "   "}, "content"),
        ({"type": "note", "content": "x" * 20_001}, "content"),
        ({"type": "url"}, "url"),
        ({"type": "url", "url": "ftp://example.com/file"}, "url"),
        ({"type": "url", "url": "not a link"}, "url"),
        ({"type": "url", "url": "https://example.com", "content": "hi"}, "content"),
        ({"type": "pdf", "content": "hi"}, "type"),
        ({"type": "note", "content": "hi", "unexpected": 1}, "unexpected"),
    ],
)
def test_ingest_rejects_invalid_bodies(client, body, field):
    error = assert_error(client.post("/ingest", json=body), 422, "VALIDATION_ERROR")
    assert field in [d["field"] for d in error["details"]]


def test_ingest_rejects_malformed_json(client):
    response = client.post("/ingest", content="{not json", headers={"Content-Type": "application/json"})
    assert_error(response, 422, "VALIDATION_ERROR")


def test_ingest_url_to_private_network_fails_with_reason(client):
    response = client.post("/ingest", json={"type": "url", "url": "http://127.0.0.1:9/secret"})
    assert response.status_code == 202
    steps = response.json()["item"]["steps"]
    assert [s["name"] for s in steps] == ["received", "fetching", "chunking", "embedding", "storing"]

    item = wait_for_status(client, response.json()["item"]["id"])
    assert item["status"] == "failed"
    assert "private or local" in item["error"]
    statuses = {s["name"]: s["status"] for s in item["steps"]}
    assert statuses == {"received": "done", "fetching": "failed", "chunking": "pending", "embedding": "pending", "storing": "pending"}
    assert "private or local" in item["steps"][1]["detail"]


# --- GET /items -----------------------------------------------------------------------------


def test_list_items_newest_first(client):
    first = client.post("/ingest", json={"type": "note", "content": "first note"}).json()["item"]
    second = client.post("/ingest", json={"type": "note", "content": "second note"}).json()["item"]

    items = client.get("/items").json()["items"]
    assert [i["id"] for i in items] == [second["id"], first["id"]]


def test_list_items_validates_limit(client):
    assert_error(client.get("/items?limit=0"), 422, "VALIDATION_ERROR")


def test_get_and_delete_missing_item_are_404(client):
    assert_error(client.get("/items/does-not-exist"), 404, "ITEM_NOT_FOUND")
    assert_error(client.delete("/items/does-not-exist"), 404, "ITEM_NOT_FOUND")


def test_delete_item(client):
    item = client.post("/ingest", json={"type": "note", "content": "temporary"}).json()["item"]
    wait_for_status(client, item["id"])

    assert client.delete(f"/items/{item['id']}").status_code == 204
    assert client.get(f"/items/{item['id']}").status_code == 404


# --- POST /query ----------------------------------------------------------------------------


def test_query_with_empty_inbox_explains_why(client):
    body = client.post("/query", json={"question": "What is PgBouncer?"}).json()
    assert body["sources"] == []
    assert "no indexed items" in body["answer"]


def test_query_answers_with_cited_sources(client):
    item = client.post("/ingest", json={"type": "note", "content": POOLING_NOTE}).json()["item"]
    client.post("/ingest", json={"type": "note", "content": "Sprint retro: move the release cut to Tuesday."})
    wait_for_status(client, item["id"])

    body = client.post("/query", json={"question": "How do we fix too many Postgres connections?"}).json()

    assert "[1]" in body["answer"]
    assert len(body["sources"]) == body["answer"].count("[")  # only cited passages are returned
    top = body["sources"][0]
    assert top["item_id"] == item["id"]
    assert "PgBouncer" in top["snippet"]
    assert 0 < top["score"] <= 1


@pytest.mark.parametrize(
    "body",
    [{}, {"question": ""}, {"question": "   "}, {"question": "x" * 501}, {"question": "ok?", "top_k": 0}, {"question": "ok?", "top_k": 21}],
)
def test_query_rejects_invalid_bodies(client, body):
    assert_error(client.post("/query", json=body), 422, "VALIDATION_ERROR")
