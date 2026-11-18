"""Small talk and off-topic questions get the right kind of reply, never fake sources."""

import pytest

from app.providers.gemini_provider import parse_answer
from tests.conftest import wait_for_status

NOTE = "PgBouncer in transaction pooling mode fixes too many Postgres connections."


@pytest.fixture
def chat(client):
    item = client.post("/ingest", json={"type": "note", "content": NOTE}).json()["item"]
    wait_for_status(client, item["id"])
    return client


def ask(client, question):
    response = client.post("/query", json={"question": question})
    assert response.status_code == 200, response.text
    return response.json()


def test_library_question_is_an_answer_with_sources(chat):
    turn = ask(chat, "How do we fix Postgres connections?")
    assert turn["kind"] == "answer"
    assert turn["sources"]


def test_small_talk_gets_a_friendly_reply_without_sources(chat):
    turn = ask(chat, "Hey, how are you?")
    assert turn["kind"] == "small_talk"
    assert turn["sources"] == []
    assert "saved notes" in turn["answer"]


def test_off_topic_question_is_not_found_without_sources(chat):
    turn = ask(chat, "zebra giraffe safari?")
    assert turn["kind"] == "not_found"
    assert turn["sources"] == []


def test_kind_is_kept_in_history(chat):
    turn = ask(chat, "thanks!")
    reopened = chat.get(f"/conversations/{turn['conversation_id']}").json()
    assert reopened["turns"][0]["kind"] == "small_talk"


@pytest.mark.parametrize(
    ("raw", "kind", "text"),
    [
        ('{"kind": "small_talk", "text": "Hi there!"}', "small_talk", "Hi there!"),
        ('{"kind": "answer", "text": "Use PgBouncer [1]."}', "answer", "Use PgBouncer [1]."),
        ('{"kind": "weird", "text": "x"}', "answer", "x"),  # unknown kind falls back to answer
        ("Plain text, not JSON [1].", "answer", "Plain text, not JSON [1]."),  # format ignored
    ],
)
def test_parse_answer_is_forgiving(raw, kind, text):
    draft = parse_answer(raw)
    assert (draft.kind, draft.text) == (kind, text)
