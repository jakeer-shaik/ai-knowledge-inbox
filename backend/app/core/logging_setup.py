"""Structured logging via structlog.

dev  -> human-readable console output
prod -> one JSON object per line (ready for log aggregation)

Request-scoped fields (e.g. request_id) are attached through structlog.contextvars.
"""

import logging

import structlog


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    log_level = logging.getLevelName(level.upper())
    logging.basicConfig(format="%(message)s", level=log_level)
    # Our middleware already logs every request (with request_id and duration),
    # so uvicorn's own access line would only duplicate it.
    logging.getLogger("uvicorn.access").disabled = True

    renderer = structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
