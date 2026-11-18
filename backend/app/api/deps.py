"""FastAPI dependencies. Routes receive collaborators here, which keeps them thin and testable."""

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.errors import ServiceUnavailableError
from app.providers import AIProviders, get_providers
from app.services.rag import RagService
from app.workers.ingest_worker import IngestWorker


def get_worker(request: Request) -> IngestWorker:
    worker: IngestWorker | None = getattr(request.app.state, "worker", None)
    if worker is None or not worker.running:
        raise ServiceUnavailableError(
            "The ingestion worker isn't running, so new items can't be indexed. Restart the server.",
            code="WORKER_UNAVAILABLE",
        )
    return worker


def get_rag_service(
    providers: AIProviders = Depends(get_providers), settings: Settings = Depends(get_settings)
) -> RagService:
    return RagService(
        providers.embedder,
        providers.answerer,
        top_k=settings.retrieval_top_k,
        min_similarity=settings.min_similarity,
    )
