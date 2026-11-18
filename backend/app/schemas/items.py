"""Request/response models for ingestion and items."""

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.domain import Item, ItemStatus, PipelineStep, SourceType, StepName, StepStatus

MAX_NOTE_CHARS = 20_000
MAX_URL_CHARS = 2_048
MAX_TITLE_CHARS = 200
PREVIEW_CHARS = 400


class IngestRequest(BaseModel):
    """`{"type": "note", "content": "..."}` or `{"type": "url", "url": "https://..."}`."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {"type": "note", "content": "PgBouncer in transaction mode fixed our connection limits."},
                {"type": "url", "url": "https://fastapi.tiangolo.com/tutorial/background-tasks/"},
            ]
        },
    )

    type: SourceType
    content: str | None = Field(default=None, max_length=MAX_NOTE_CHARS, validate_default=True)
    url: str | None = Field(default=None, max_length=MAX_URL_CHARS, validate_default=True)
    title: str | None = Field(default=None, max_length=MAX_TITLE_CHARS)

    @field_validator("content")
    @classmethod
    def _content_matches_type(cls, value: str | None, info: ValidationInfo) -> str | None:
        kind = info.data.get("type")
        if kind == "note" and not value:
            raise ValueError("content is required when type is 'note'")
        if kind == "url" and value:
            raise ValueError("content is not accepted when type is 'url'; send the link in 'url'")
        return value

    @field_validator("url")
    @classmethod
    def _url_matches_type(cls, value: str | None, info: ValidationInfo) -> str | None:
        kind = info.data.get("type")
        if kind == "note":
            if value:
                raise ValueError("url is not accepted when type is 'note'; send the text in 'content'")
            return None
        if kind == "url":
            if not value:
                raise ValueError("url is required when type is 'url'")
            parsed = urlparse(value)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise ValueError("url must be an absolute http(s) link, like https://example.com/page")
        return value


class StepOut(BaseModel):
    """One stage of the ingestion pipeline (received -> [fetching] -> chunking -> embedding -> storing)."""

    name: StepName
    status: StepStatus
    detail: str | None = Field(description="What happened, or why the step failed")
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: float | None

    @classmethod
    def from_domain(cls, step: PipelineStep) -> "StepOut":
        return cls(
            name=step.name,
            status=step.status,
            detail=step.detail,
            started_at=step.started_at,
            finished_at=step.finished_at,
            duration_ms=step.duration_ms,
        )


class ItemOut(BaseModel):
    id: str
    source_type: SourceType
    title: str | None
    url: str | None
    status: ItemStatus
    error: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    content_preview: str | None = Field(description=f"First {PREVIEW_CHARS} characters of the stored text")
    steps: list[StepOut] = Field(description="Ingestion pipeline progress, in order")

    @classmethod
    def from_domain(cls, item: Item) -> "ItemOut":
        return cls(
            id=item.id,
            source_type=item.source_type,
            title=item.title,
            url=item.url,
            status=item.status,
            error=item.error,
            chunk_count=item.chunk_count,
            created_at=datetime.fromisoformat(item.created_at),
            updated_at=datetime.fromisoformat(item.updated_at),
            content_preview=item.raw_content[:PREVIEW_CHARS] if item.raw_content else None,
            steps=[StepOut.from_domain(step) for step in item.steps],
        )


class ItemResponse(BaseModel):
    item: ItemOut


class ItemListResponse(BaseModel):
    items: list[ItemOut]
