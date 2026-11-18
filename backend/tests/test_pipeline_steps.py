"""Unit tests for step tracking (persisted to a real temporary SQLite database)."""

import pytest

from app.core.db import get_connection, init_db
from app.repositories import items_repo
from app.services.pipeline_steps import StepTracker, initial_steps


@pytest.fixture
def item_id(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "steps.db"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    init_db()
    with get_connection() as conn:
        item = items_repo.insert(
            conn, source_type="url", title=None, url="https://example.com", raw_content=None,
            steps=initial_steps("url", "Link received"),
        )
    yield item.id
    get_settings.cache_clear()


def stored_steps(item_id):
    with get_connection() as conn:
        return {s.name: s for s in items_repo.get(conn, item_id).steps}


def test_initial_steps_for_links_and_notes():
    assert [s.name for s in initial_steps("url", "x")] == ["received", "fetching", "chunking", "embedding", "storing"]
    note = initial_steps("note", "Note received")
    assert [s.name for s in note] == ["received", "chunking", "embedding", "storing"]
    assert note[0].status == "done" and note[0].detail == "Note received"
    assert all(s.status == "pending" for s in note[1:])


async def test_step_is_persisted_as_running_then_done(item_id):
    with get_connection() as conn:
        steps = items_repo.get(conn, item_id).steps
    tracker = StepTracker(item_id, steps, describe_failure=str)

    async with tracker.step("chunking") as step:
        assert stored_steps(item_id)["chunking"].status == "running"  # visible to GET /items mid-step
        step.detail = "3 chunks"

    saved = stored_steps(item_id)["chunking"]
    assert (saved.status, saved.detail) == ("done", "3 chunks")
    assert saved.duration_ms is not None and saved.finished_at is not None


async def test_failed_step_records_reason_and_reraises(item_id):
    with get_connection() as conn:
        steps = items_repo.get(conn, item_id).steps
    tracker = StepTracker(item_id, steps, describe_failure=lambda exc: f"reason: {exc}")

    with pytest.raises(RuntimeError):
        async with tracker.step("fetching"):
            raise RuntimeError("boom")

    saved = stored_steps(item_id)
    assert (saved["fetching"].status, saved["fetching"].detail) == ("failed", "reason: boom")
    assert saved["chunking"].status == "pending"


async def test_restart_resets_everything_after_received(item_id):
    with get_connection() as conn:
        steps = items_repo.get(conn, item_id).steps
    tracker = StepTracker(item_id, steps, describe_failure=str)
    async with tracker.step("fetching") as step:
        step.detail = "done once"

    tracker.restart()
    saved = stored_steps(item_id)
    assert saved["received"].status == "done"
    assert saved["fetching"].status == "pending" and saved["fetching"].detail is None
