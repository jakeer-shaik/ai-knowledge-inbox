"""Application factory and lifecycle."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, ingest, items, query
from app.core.config import get_settings
from app.core.db import init_db
from app.core.errors import register_exception_handlers
from app.core.logging_setup import configure_logging
from app.core.middleware import register_request_middleware
from app.providers import get_providers
from app.services.ingestion import IngestionPipeline, unfinished_item_ids
from app.workers.ingest_worker import IngestWorker

log = structlog.get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    init_db()
    providers = get_providers()

    pipeline = IngestionPipeline(settings, providers.embedder)
    worker = IngestWorker(pipeline.process, concurrency=settings.ingest_worker_concurrency)
    app.state.worker = worker
    await worker.start()

    requeued = unfinished_item_ids()
    for item_id in requeued:
        worker.enqueue(item_id)

    log.info(
        "startup",
        env=settings.app_env,
        embedding_model=providers.embedder.model_id,
        chat_model=settings.gemini_chat_model,
        db=settings.database_path,
        requeued_items=len(requeued),
    )
    yield
    await worker.stop()
    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.app_env == "prod")

    app = FastAPI(
        title="AI Knowledge Inbox",
        version="0.1.0",
        description="Save notes and URLs, then ask questions answered from them with cited sources.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Location"],
    )
    register_request_middleware(app)
    register_exception_handlers(app)

    for module in (health, ingest, items, query):
        app.include_router(module.router)
    return app


app = create_app()
