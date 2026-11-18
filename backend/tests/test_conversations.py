"""Conversations: follow-ups continue a thread, are read in context, and history can be reopened."""

import sqlite3

import pytest

from tests.conftest import wait_for_status
from tests.fakes import KeywordEmbedder, QuoteAnswerer

POOLING = "PgBouncer in transaction pooling mode fixes too many Postgres connections."
RETRO = "Releases slipped because staging was shared. The release cut moves to Tuesday."


@pytest.fixture
def answerer():
    return QuoteAnswerer()


@pytest.fixture
def chat(make_client, answerer):
    client = make_client(embedder=KeywordEmbedder(), answerer=answerer)
    for note in (POOLING, RETRO):
        item = client.post("/ingest", json={"type": "note", "content": note}).json()["item"]
        wait_for_status(client, item["id"])
    return client


def ask(client, question, conversation_id=None, expect=200):
    body = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    response = client.post("/query", json=body)
    assert response.status_code == expect, response.text
    return response.json()


def test_first_question_starts_a_conversation(chat):
    turn = ask(chat, "How do we fix Postgres connections?")
    assert turn["conversation_id"]
    assert turn["search_query"] == turn["question"]  # nothing to rewrite yet

    conversation = chat.get(f"/conversations/{turn['conversation_id']}").json()
    assert conversation["title"] == "How do we fix Postgres connections?"
    assert conversation["turn_count"] == 1
    assert conversation["turns"][0] == turn  # reopening returns exactly what was shown


def test_follow_up_continues_the_thread_and_is_read_in_context(chat, answerer):
    first = ask(chat, "How do we fix Postgres connections?")
    follow_up = ask(chat, "and what mode?", first["conversation_id"])

    assert follow_up["conversation_id"] == first["conversation_id"]
    assert follow_up["search_query"] == "How do we fix Postgres connections? and what mode?"  # rewritten
    assert follow_up["sources"][0]["snippet"] == POOLING  # found via the rewrite, not the bare follow-up
    assert answerer.calls[-1]["history"][0].question == "How do we fix Postgres connections?"

    conversation = chat.get(f"/conversations/{first['conversation_id']}").json()
    assert [t["question"] for t in conversation["turns"]] == ["How do we fix Postgres connections?", "and what mode?"]
    assert conversation["turn_count"] == 2


def test_follow_up_still_answers_when_rewriting_fails(make_client, answerer):
    from app.core.errors import ServiceUnavailableError

    async def rate_limited(question, history):
        raise ServiceUnavailableError("Gemini is rate limiting requests.", code="LLM_RATE_LIMITED")

    answerer.rewrite_question = rate_limited
    client = make_client(embedder=KeywordEmbedder(), answerer=answerer)
    item = client.post("/ingest", json={"type": "note", "content": POOLING}).json()["item"]
    wait_for_status(client, item["id"])

    first = ask(client, "How do we fix Postgres connections?")
    follow_up = ask(client, "what about Postgres pooling mode?", first["conversation_id"])  # 200, not 503
    assert follow_up["search_query"] == "what about Postgres pooling mode?"  # fell back to the raw question
    assert follow_up["kind"] == "answer"


def test_new_question_without_id_starts_a_separate_conversation(chat):
    a = ask(chat, "How do we fix Postgres connections?")
    b = ask(chat, "When is the release cut?")
    assert a["conversation_id"] != b["conversation_id"]


def test_history_is_ordered_by_latest_activity(chat):
    older = ask(chat, "How do we fix Postgres connections?")
    newer = ask(chat, "When is the release cut?")
    ask(chat, "anything else?", older["conversation_id"])  # bumps the older conversation

    listed = chat.get("/conversations").json()["conversations"]
    assert [c["id"] for c in listed] == [older["conversation_id"], newer["conversation_id"]]
    assert listed[0]["turn_count"] == 2


def test_unknown_conversation_is_404_and_nothing_is_saved(chat):
    error = ask(chat, "Hello?", conversation_id="does-not-exist", expect=404)["error"]
    assert error["code"] == "CONVERSATION_NOT_FOUND"
    assert chat.get("/conversations").json()["conversations"] == []


def test_conversation_id_is_validated(chat):
    ask(chat, "Hi?", conversation_id="x" * 65, expect=422)


def test_deleting_a_conversation_removes_its_turns(chat, tmp_path):
    turn = ask(chat, "How do we fix Postgres connections?")
    ask(chat, "and what mode?", turn["conversation_id"])

    assert chat.delete(f"/conversations/{turn['conversation_id']}").status_code == 204
    assert chat.get(f"/conversations/{turn['conversation_id']}").status_code == 404
    assert chat.delete(f"/conversations/{turn['conversation_id']}").status_code == 404
    with sqlite3.connect(tmp_path / "test.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0] == 0


def test_sources_survive_deleting_the_item(chat):
    turn = ask(chat, "How do we fix Postgres connections?")
    chat.delete(f"/items/{turn['sources'][0]['item_id']}")

    reopened = chat.get(f"/conversations/{turn['conversation_id']}").json()
    assert reopened["turns"][0]["sources"][0]["snippet"] == POOLING


def test_invalid_questions_are_not_saved(chat):
    ask(chat, "", expect=422)
    assert chat.get("/conversations").json()["conversations"] == []


def test_empty_inbox_answers_without_calling_ai(client):
    turn = client.post("/query", json={"question": "Anything?"}).json()
    assert turn["answer"].startswith("Your inbox has no indexed items")
    assert turn["sources"] == []


def test_questions_saved_by_the_previous_version_are_migrated(make_client, tmp_path):
    with sqlite3.connect(tmp_path / "test.db") as conn:
        conn.execute(
            """CREATE TABLE queries (id TEXT PRIMARY KEY, question TEXT NOT NULL, answer TEXT NOT NULL,
               sources TEXT NOT NULL, duration_ms REAL, created_at TEXT NOT NULL)"""
        )
        conn.execute(
            "INSERT INTO queries VALUES ('q1', 'Old question?', 'Old answer [1].', '[]', 12.0, '2026-11-18T10:00:00+00:00')"
        )

    client = make_client()
    listed = client.get("/conversations").json()["conversations"]
    assert [(c["id"], c["title"], c["turn_count"]) for c in listed] == [("q1", "Old question?", 1)]
    assert client.get("/conversations/q1").json()["turns"][0]["answer"] == "Old answer [1]."
