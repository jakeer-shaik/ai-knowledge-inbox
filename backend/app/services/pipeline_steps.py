"""Step-by-step progress tracking for the ingestion pipeline.

Each step is persisted as it starts and finishes, so `GET /items` shows exactly
where an item is (and where it failed) while the worker is still running.
"""

import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog

from app.core.db import get_connection
from app.domain import PIPELINE_STEPS, PipelineStep, SourceType, StepName
from app.repositories import items_repo

log = structlog.get_logger("pipeline")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initial_steps(source_type: SourceType, received_detail: str) -> list[PipelineStep]:
    """All steps for this kind of item; 'received' is already done when the API accepts it."""
    now = _now()
    steps = [PipelineStep(name=name) for name in PIPELINE_STEPS[source_type]]
    steps[0] = PipelineStep(
        name="received", status="done", detail=received_detail, started_at=now, finished_at=now, duration_ms=0.0
    )
    return steps


class StepTracker:
    def __init__(self, item_id: str, steps: list[PipelineStep], describe_failure: Callable[[Exception], str]):
        self._item_id = item_id
        self._steps = {step.name: step for step in steps}
        self._ordered = steps
        self._describe_failure = describe_failure

    def restart(self) -> None:
        """Reset everything after 'received' (an item re-queued after a crash starts over)."""
        for step in self._ordered:
            if step.name != "received":
                step.status, step.detail, step.started_at, step.finished_at, step.duration_ms = "pending", None, None, None, None
        self._save()

    @asynccontextmanager
    async def step(self, name: StepName) -> AsyncIterator[PipelineStep]:
        """Mark `name` running, then done (or failed with a readable reason if the body raises)."""
        step = self._steps[name]
        step.status, step.started_at, step.detail = "running", _now(), None
        self._save()
        started = time.perf_counter()
        try:
            yield step
        except Exception as exc:
            step.status, step.detail = "failed", self._describe_failure(exc)
            self._finish(step, started)
            log.warning("step_failed", step=name, reason=step.detail, duration_ms=step.duration_ms)
            raise
        else:
            step.status = "done"
            self._finish(step, started)
            log.info("step_done", step=name, detail=step.detail, duration_ms=step.duration_ms)

    def _finish(self, step: PipelineStep, started: float) -> None:
        step.finished_at = _now()
        step.duration_ms = round((time.perf_counter() - started) * 1000, 1)
        self._save()

    def _save(self) -> None:
        with get_connection() as conn:
            items_repo.update_steps(conn, self._item_id, self._ordered)
