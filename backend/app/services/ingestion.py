"""Ingestion: create items synchronously, index them asynchronously.

    POST /ingest -> create_item()               step 1 received, status=pending, queued
    worker       -> IngestionPipeline.process()  status=processing
                      [links only] fetching   load the page and extract readable text
                      chunking                split text into overlapping chunks
                      embedding               one vector per chunk (Gemini)
                      storing                 chunks + vectors written to SQLite
                    -> status=ready | failed (the failed step carries the reason)
"""

import asyncio
from urllib.parse import urlparse

import numpy as np
import structlog

from app.core.config import Settings
from app.core.db import get_connection
from app.core.errors import AppError
from app.domain import IN_PROGRESS_STATUSES, Item
from app.providers.base import EmbeddingProvider
from app.repositories import chunks_repo, items_repo
from app.schemas.items import IngestRequest
from app.services.chunking import chunk_text
from app.services.fetcher import FetchError, fetch_page
from app.services.pipeline_steps import StepTracker, initial_steps

log = structlog.get_logger("ingestion")

NOTE_TITLE_CHARS = 80
UNEXPECTED_FAILURE = "Unexpected error while indexing. Check the server logs for details."


class IndexingError(Exception):
    """Expected failure while indexing; the message is stored on the item and shown to the user."""


def describe_failure(exc: Exception) -> str:
    if isinstance(exc, FetchError | IndexingError):
        return str(exc)
    if isinstance(exc, AppError):
        return exc.message
    return UNEXPECTED_FAILURE


def create_item(request: IngestRequest) -> Item:
    if request.type == "note":
        content = request.content or ""
        fields = {"title": request.title or _title_from_text(content), "url": None, "raw_content": content}
        received = f"Note received ({len(content):,} characters)"
    else:
        # Title and content are filled in by the worker once the page is loaded.
        fields = {"title": request.title, "url": request.url, "raw_content": None}
        received = f"Link received ({urlparse(request.url).hostname})"
    with get_connection() as conn:
        return items_repo.insert(
            conn, source_type=request.type, steps=initial_steps(request.type, received), **fields
        )


def unfinished_item_ids() -> list[str]:
    """Items left pending/processing by a previous run (crash or restart) are re-queued at startup."""
    with get_connection() as conn:
        ids = items_repo.list_ids_with_status(conn, IN_PROGRESS_STATUSES)
        for item_id in ids:
            items_repo.set_status(conn, item_id, "pending")
    return ids


class IngestionPipeline:
    def __init__(self, settings: Settings, embedder: EmbeddingProvider):
        self._settings = settings
        self._embedder = embedder

    async def process(self, item_id: str) -> None:
        with get_connection() as conn:
            item = items_repo.get(conn, item_id)
            if item is None or item.status not in IN_PROGRESS_STATUSES:
                log.info("ingest_skipped", reason="missing or already processed")
                return
            items_repo.set_status(conn, item_id, "processing")

        tracker = StepTracker(item_id, item.steps, describe_failure)
        tracker.restart()
        try:
            title, text = item.title, item.raw_content or ""
            if item.source_type == "url":
                async with tracker.step("fetching") as step:
                    title, text = await self._load_page(item)
                    step.detail = f"Loaded {len(text):,} characters from {urlparse(item.url).hostname}"

            async with tracker.step("chunking") as step:
                chunks = chunk_text(text, self._settings.chunk_size, self._settings.chunk_overlap)
                if not chunks:
                    raise IndexingError("There is no text to index.")
                step.detail = f"{_count(len(chunks), 'chunk')} of up to {self._settings.chunk_size} characters"

            async with tracker.step("embedding") as step:
                vectors = await self._embedder.embed_documents(chunks)
                step.detail = f"{_count(len(vectors), 'vector')} with {vectors.shape[1]} dimensions"

            async with tracker.step("storing") as step:
                await asyncio.to_thread(self._store, item_id, chunks, vectors)
                step.detail = f"Saved {_count(len(chunks), 'chunk')} with {'its vector' if len(chunks) == 1 else 'their vectors'}"

            with get_connection() as conn:
                items_repo.mark_ready(conn, item_id, title=title, raw_content=text, chunk_count=len(chunks))
            log.info("ingest_completed", source_type=item.source_type, chars=len(text), chunks=len(chunks))
        except Exception as exc:
            if describe_failure(exc) == UNEXPECTED_FAILURE:
                log.exception("ingest_crashed")
            self._fail(item_id, describe_failure(exc))

    async def _load_page(self, item: Item) -> tuple[str | None, str]:
        page = await fetch_page(
            item.url or "",
            timeout_seconds=self._settings.fetch_timeout_seconds,
            max_bytes=self._settings.fetch_max_bytes,
            allow_private_hosts=self._settings.fetch_allow_private_hosts,
        )
        return item.title or page.title or urlparse(page.url).hostname, page.text

    def _store(self, item_id: str, chunks: list[str], vectors: np.ndarray) -> None:
        with get_connection() as conn:
            chunks_repo.replace_for_item(conn, item_id, chunks, vectors, self._embedder.model_id)

    @staticmethod
    def _fail(item_id: str, reason: str) -> None:
        log.warning("ingest_failed", reason=reason)
        with get_connection() as conn:
            items_repo.set_status(conn, item_id, "failed", error=reason)


def _count(n: int, noun: str) -> str:
    return f"{n:,} {noun if n == 1 else noun + 's'}"


def _title_from_text(text: str) -> str:
    first_line = text.strip().split("\n", 1)[0]
    if len(first_line) <= NOTE_TITLE_CHARS:
        return first_line
    return first_line[:NOTE_TITLE_CHARS].rsplit(" ", 1)[0] + "…"
