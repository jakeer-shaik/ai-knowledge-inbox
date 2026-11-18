"""In-process background worker: an asyncio.Queue drained by N consumer tasks.

Trade-off: zero infrastructure, but jobs live in memory. Durability comes from the
database instead: item status is persisted, and unfinished items are re-queued on
startup. In production this becomes a real queue (Redis/RQ, Celery, SQS) with
separate worker processes.
"""

import asyncio
from collections.abc import Awaitable, Callable

import structlog

log = structlog.get_logger("worker")

Job = Callable[[str], Awaitable[None]]


class IngestWorker:
    def __init__(self, job: Job, concurrency: int = 2):
        self._job = job
        self._concurrency = concurrency
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    @property
    def running(self) -> bool:
        return any(not task.done() for task in self._tasks)

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    def enqueue(self, item_id: str) -> None:
        self._queue.put_nowait(item_id)
        log.debug("job_enqueued", item_id=item_id, queue_depth=self._queue.qsize())

    async def start(self) -> None:
        self._tasks = [asyncio.create_task(self._consume(n), name=f"ingest-worker-{n}") for n in range(self._concurrency)]
        log.info("worker_started", concurrency=self._concurrency)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        log.info("worker_stopped", unprocessed=self._queue.qsize())

    async def drain(self) -> None:
        """Wait until every queued job has finished (used by tests)."""
        await self._queue.join()

    async def _consume(self, worker_number: int) -> None:
        while True:
            item_id = await self._queue.get()
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(item_id=item_id, worker=worker_number)
            try:
                await self._job(item_id)
            except Exception:
                # The job handles its own expected failures; this keeps the consumer alive on bugs.
                log.exception("job_crashed")
            finally:
                self._queue.task_done()
