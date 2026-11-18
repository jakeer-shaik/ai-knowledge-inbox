"""Question answering.

    [follow-up]  rewrite into a standalone question using recent turns
    embed the (standalone) question -> retrieve top-k chunks -> generate a cited answer
    -> keep only the passages the answer actually cites
"""

import asyncio
import time
from dataclasses import dataclass

import structlog

from app.core.db import get_connection
from app.core.errors import AppError
from app.domain import AnswerKind, Passage, PriorTurn, RetrievedChunk
from app.providers.base import AnswerGenerator, EmbeddingProvider
from app.repositories import chunks_repo, items_repo
from app.services.citations import keep_cited
from app.services.retrieval import rank_by_cosine

log = structlog.get_logger("rag")

EMPTY_INBOX_ANSWER = "Your inbox has no indexed items yet. Save a note or a link first, then ask about it."
NO_MATCH_ANSWER = "I couldn't find anything about that in your saved items."


@dataclass(frozen=True)
class Answer:
    kind: AnswerKind  # answer | not_found | small_talk
    text: str
    sources: list[RetrievedChunk]
    search_query: str  # what was actually searched; differs from the question for follow-ups


class RagService:
    def __init__(self, embedder: EmbeddingProvider, answerer: AnswerGenerator, *, top_k: int, min_similarity: float | None):
        self._embedder = embedder
        self._answerer = answerer
        self._top_k = top_k
        self._min_similarity = min_similarity if min_similarity is not None else embedder.default_min_similarity

    async def answer(self, question: str, top_k: int | None = None, history: list[PriorTurn] | None = None) -> Answer:
        history = history or []
        started = time.perf_counter()

        # Nothing indexed: answer without spending AI calls (and without depending on Gemini being up).
        if await asyncio.to_thread(self._count_ready) == 0:
            log.info("query_empty_inbox")
            return Answer(kind="not_found", text=EMPTY_INBOX_ANSWER, sources=[], search_query=question)

        search_query = await self._standalone_question(question, history)

        # Even with no matching passages the model still replies: "how are you?" deserves a
        # friendly answer, and a real question gets a clear "not in your saved items".
        hits = await self.retrieve(search_query, top_k or self._top_k)
        passages = [
            Passage(number=n, title=hit.chunk.title or hit.chunk.url or "Untitled", text=hit.chunk.text)
            for n, hit in enumerate(hits, start=1)
        ]
        draft = await self._answerer.answer(question, passages, history)

        if draft.kind == "answer" and passages:
            text, cited = keep_cited(draft.text, len(passages))
            sources = [hits[n - 1] for n in cited]
        else:
            text, sources = draft.text, []  # small talk and "not found" never carry sources

        log.info(
            "query_answered",
            kind=draft.kind,
            follow_up=bool(history),
            retrieved=len(hits),
            cited=len(sources),
            top_score=round(hits[0].score, 3) if hits else None,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return Answer(kind=draft.kind, text=text or NO_MATCH_ANSWER, sources=sources, search_query=search_query)

    async def _standalone_question(self, question: str, history: list[PriorTurn]) -> str:
        """Rewrite a follow-up for search. Rewriting only improves recall, so if it fails
        (rate limit, outage) the original question is searched instead of failing the turn."""
        if not history:
            return question
        try:
            rewritten = await self._answerer.rewrite_question(question, history)
        except AppError as exc:
            log.warning("query_rewrite_skipped", reason=exc.code)
            return question
        if rewritten != question:
            log.info("query_rewritten", follow_up_chars=len(question), standalone_chars=len(rewritten))
        return rewritten

    async def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        query_vector = await self._embedder.embed_query(question)
        chunks, matrix = await asyncio.to_thread(self._load_index)
        ranked = rank_by_cosine(query_vector, matrix, top_k=top_k, min_score=self._min_similarity)
        return [RetrievedChunk(chunk=chunks[i], score=score) for i, score in ranked]

    def _load_index(self):
        with get_connection() as conn:
            return chunks_repo.load_searchable(conn, self._embedder.model_id)

    @staticmethod
    def _count_ready() -> int:
        with get_connection() as conn:
            return items_repo.count_ready(conn)
