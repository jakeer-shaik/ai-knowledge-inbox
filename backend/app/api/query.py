import time

import structlog
from fastapi import APIRouter, Depends, Query, Response, status
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_rag_service
from app.core.db import get_connection
from app.core.errors import NotFoundError
from app.domain import PriorTurn
from app.repositories import conversations_repo
from app.schemas.query import (
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    QueryRequest,
    Source,
    TurnOut,
)
from app.services.rag import RagService

router = APIRouter(tags=["query"])
log = structlog.get_logger("api.query")

# How many earlier turns a follow-up is read against.
HISTORY_TURNS = 4


def _conversation_not_found(conversation_id: str) -> NotFoundError:
    return NotFoundError(f"No conversation with id '{conversation_id}'.", code="CONVERSATION_NOT_FOUND")


@router.post(
    "/query",
    response_model=TurnOut,
    summary="Ask a question (or a follow-up) over saved items; returns a cited answer, saved to the conversation",
    responses={
        404: {"description": "conversation_id doesn't exist"},
        422: {"description": "Invalid body"},
        502: {"description": "AI provider error"},
        503: {"description": "AI provider unavailable (bad key, rate limit)"},
        504: {"description": "AI provider timed out"},
    },
)
async def query(body: QueryRequest, rag: RagService = Depends(get_rag_service)) -> TurnOut:
    log.info("query_received", question_chars=len(body.question), follow_up=body.conversation_id is not None)
    history = await run_in_threadpool(_load_history, body.conversation_id) if body.conversation_id else []

    started = time.perf_counter()
    answer = await rag.answer(body.question, body.top_k, history)
    sources = [
        Source(
            item_id=hit.chunk.item_id,
            chunk_index=hit.chunk.chunk_index,
            source_type=hit.chunk.source_type,
            title=hit.chunk.title,
            url=hit.chunk.url,
            snippet=hit.chunk.text,
            score=round(hit.score, 4),
        ).model_dump()
        for hit in answer.sources
    ]
    turn = await run_in_threadpool(
        _save_turn,
        body.conversation_id,
        question=body.question,
        search_query=answer.search_query,
        kind=answer.kind,
        answer=answer.text,
        sources=sources,
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    return TurnOut.from_domain(turn)


def _load_history(conversation_id: str) -> list[PriorTurn]:
    with get_connection() as conn:
        if conversations_repo.get(conn, conversation_id) is None:
            raise _conversation_not_found(conversation_id)
        turns = conversations_repo.recent_turns(conn, conversation_id, HISTORY_TURNS)
    return [PriorTurn(question=t.question, answer=t.answer) for t in turns]


def _save_turn(conversation_id: str | None, **fields) -> conversations_repo.Turn:
    """A conversation is only created once its first question has an answer."""
    with get_connection() as conn:
        if conversation_id is None or conversations_repo.get(conn, conversation_id) is None:
            conversation_id = conversations_repo.create(conn, fields["question"])
        return conversations_repo.add_turn(conn, conversation_id, **fields)


# --- conversation history --------------------------------------------------------------------


@router.get("/conversations", response_model=ConversationListResponse, summary="Conversations, most recent first")
def list_conversations(limit: int = Query(default=50, ge=1, le=200)) -> ConversationListResponse:
    with get_connection() as conn:
        conversations = conversations_repo.list_recent(conn, limit)
    return ConversationListResponse(conversations=[ConversationSummary.from_domain(c) for c in conversations])


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    summary="One conversation with every turn",
    responses={404: {"description": "Not found"}},
)
def get_conversation(conversation_id: str) -> ConversationDetail:
    with get_connection() as conn:
        conversation = conversations_repo.get(conn, conversation_id)
        if conversation is None:
            raise _conversation_not_found(conversation_id)
        turns = conversations_repo.turns(conn, conversation_id)
    summary = ConversationSummary.from_domain(conversation)
    return ConversationDetail(**summary.model_dump(), turns=[TurnOut.from_domain(t) for t in turns])


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation and all its turns",
    responses={404: {"description": "Not found"}},
)
def delete_conversation(conversation_id: str) -> Response:
    with get_connection() as conn:
        deleted = conversations_repo.delete(conn, conversation_id)
    if not deleted:
        raise _conversation_not_found(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
