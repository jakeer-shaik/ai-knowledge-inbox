"""Request context middleware: request IDs, access logs, last-resort error handling."""

import time
import uuid

import structlog
from fastapi import FastAPI, Request

from app.core.errors import error_response

log = structlog.get_logger("http")


def register_request_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # Anything that escaped the domain handlers is a bug: log it fully,
            # but never leak internals to the client.
            log.exception("unhandled_error", method=request.method, path=request.url.path)
            response = error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")

        log.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        response.headers["X-Request-ID"] = request_id
        return response
