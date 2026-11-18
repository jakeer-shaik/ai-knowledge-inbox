"""Provider interfaces. Swapping Gemini for another vendor or a local model means one new class."""

from typing import Protocol

import numpy as np

from app.domain import AnswerDraft, Passage, PriorTurn


class EmbeddingProvider(Protocol):
    # Stored next to every vector so vectors from different models are never compared.
    model_id: str
    # Cosine score below which a passage is treated as irrelevant (scales differ per model).
    default_min_similarity: float

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        """Embed passages for storage. Returns a (len(texts), dim) float32 matrix."""
        ...

    async def embed_query(self, text: str) -> np.ndarray:
        """Embed a search question. Returns a (dim,) float32 vector."""
        ...


class AnswerGenerator(Protocol):
    async def answer(self, question: str, passages: list[Passage], history: list[PriorTurn]) -> AnswerDraft:
        """Reply and label it: an answer citing passage n as [n], small talk, or not found.
        `passages` may be empty; `history` only clarifies intent."""
        ...

    async def rewrite_question(self, question: str, history: list[PriorTurn]) -> str:
        """Turn a follow-up ("what about the second one?") into a standalone search question."""
        ...
