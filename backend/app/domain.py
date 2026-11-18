"""Core domain types shared by repositories and services (no framework dependencies)."""

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Literal

SourceType = Literal["note", "url"]
ItemStatus = Literal["pending", "processing", "ready", "failed"]
IN_PROGRESS_STATUSES: tuple[ItemStatus, ...] = ("pending", "processing")

# The ingestion pipeline, in order. Links have one extra step: loading the page.
StepName = Literal["received", "fetching", "chunking", "embedding", "storing"]
StepStatus = Literal["pending", "running", "done", "failed"]
PIPELINE_STEPS: dict[SourceType, tuple[StepName, ...]] = {
    "note": ("received", "chunking", "embedding", "storing"),
    "url": ("received", "fetching", "chunking", "embedding", "storing"),
}


@dataclass
class PipelineStep:
    name: StepName
    status: StepStatus = "pending"
    detail: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: float | None = None


def steps_to_json(steps: list[PipelineStep]) -> str:
    return json.dumps([asdict(step) for step in steps])


def steps_from_json(raw: str | None) -> list[PipelineStep]:
    return [PipelineStep(**step) for step in json.loads(raw or "[]")]


@dataclass(frozen=True)
class Item:
    id: str
    source_type: SourceType
    title: str | None
    url: str | None
    raw_content: str | None
    status: ItemStatus
    error: str | None
    chunk_count: int
    created_at: str
    updated_at: str
    steps: list[PipelineStep] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Item":
        values = {key: row[key] for key in row.keys()}
        values["steps"] = steps_from_json(values.get("steps"))
        return cls(**values)


@dataclass(frozen=True)
class SearchableChunk:
    """A chunk joined with the item metadata needed to cite it."""

    item_id: str
    chunk_index: int
    text: str
    title: str | None
    url: str | None
    source_type: SourceType


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: SearchableChunk
    score: float


# What kind of reply the model gave (decided by the model in the same call that writes it).
AnswerKind = Literal["answer", "not_found", "small_talk"]


@dataclass(frozen=True)
class AnswerDraft:
    kind: AnswerKind
    text: str


@dataclass(frozen=True)
class PriorTurn:
    """An earlier question and answer in the same conversation, used to read follow-ups."""

    question: str
    answer: str


@dataclass(frozen=True)
class Passage:
    """A retrieved chunk as presented to the answer generator: number n is cited as [n]."""

    number: int
    title: str
    text: str
