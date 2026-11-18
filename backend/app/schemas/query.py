"""Request/response models for asking questions and conversation history."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain import AnswerKind, SourceType
from app.repositories.conversations_repo import Conversation, Turn

MAX_QUESTION_CHARS = 500


class QueryRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {"question": "How should we configure connection pooling?"},
                {"question": "What about the second option?", "conversation_id": "3f1c…"},
            ]
        },
    )

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    conversation_id: str | None = Field(
        default=None, min_length=1, max_length=64, description="Continue this conversation; omit to start a new one"
    )
    top_k: int | None = Field(default=None, ge=1, le=20, description="Passages to retrieve (defaults to server setting)")


class Source(BaseModel):
    """Source [n] in the answer is sources[n - 1]."""

    item_id: str
    chunk_index: int
    source_type: SourceType
    title: str | None
    url: str | None
    snippet: str
    score: float = Field(description="Cosine similarity between question and passage")


class TurnOut(BaseModel):
    """One question and its answer. `POST /query` returns the new turn."""

    id: str
    conversation_id: str
    question: str
    search_query: str = Field(description="What was searched: the question, or its standalone rewrite for follow-ups")
    kind: AnswerKind = Field(
        description="answer: cited from saved items; not_found: saved items don't cover it; small_talk: greeting/thanks"
    )
    answer: str
    sources: list[Source]
    created_at: datetime

    @classmethod
    def from_domain(cls, turn: Turn) -> "TurnOut":
        return cls(
            id=turn.id,
            conversation_id=turn.conversation_id,
            question=turn.question,
            search_query=turn.search_query,
            kind=turn.kind,
            answer=turn.answer,
            sources=[Source(**source) for source in turn.sources],
            created_at=datetime.fromisoformat(turn.created_at),
        )


class ConversationSummary(BaseModel):
    id: str
    title: str = Field(description="The first question")
    turn_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, conversation: Conversation) -> "ConversationSummary":
        return cls(
            id=conversation.id,
            title=conversation.title,
            turn_count=conversation.turn_count,
            created_at=datetime.fromisoformat(conversation.created_at),
            updated_at=datetime.fromisoformat(conversation.updated_at),
        )


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]


class ConversationDetail(ConversationSummary):
    turns: list[TurnOut]
