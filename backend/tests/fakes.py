"""Deterministic offline stand-ins for Gemini, so tests need no API key or network.

- KeywordEmbedder: hashed bag of words + bigrams (lexical overlap only).
- QuoteAnswerer: quotes the best-matching sentence of each passage with its [n] citation.
"""

import hashlib
import re

import numpy as np

from app.domain import AnswerDraft, Passage, PriorTurn

_WORD = re.compile(r"[a-z0-9]+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_SMALL_TALK = re.compile(r"^(hi|hello|hey|thanks|thank you|how are you)\b", re.IGNORECASE)
_STOPWORDS = frozenset("a an and are do does for how in is of on the to we what with".split())


def tokenize(text: str) -> list[str]:
    return [w.rstrip("s") if len(w) > 3 else w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


class KeywordEmbedder:
    model_id = "test:keyword-hash-256"
    default_min_similarity = 0.05

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._embed(t) for t in texts])

    async def embed_query(self, text: str) -> np.ndarray:
        return self._embed(text)

    @staticmethod
    def _embed(text: str, dimensions: int = 256) -> np.ndarray:
        tokens = tokenize(text)
        vector = np.zeros(dimensions, dtype=np.float32)
        for feature in tokens + [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]:
            digest = int.from_bytes(hashlib.blake2b(feature.encode(), digest_size=8).digest(), "little")
            vector[(digest >> 1) % dimensions] += 1.0 if digest & 1 else -1.0
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector


class QuoteAnswerer:
    def __init__(self):
        self.calls: list[dict] = []  # lets tests inspect what the generator was given

    async def rewrite_question(self, question: str, history: list[PriorTurn]) -> str:
        # Resolve the follow-up by prefixing the previous question (enough for keyword retrieval).
        return f"{history[-1].question} {question}"

    async def answer(self, question: str, passages: list[Passage], history: list[PriorTurn]) -> AnswerDraft:
        self.calls.append({"question": question, "history": history})
        if _SMALL_TALK.match(question.strip()):
            return AnswerDraft(kind="small_talk", text="Hi! Ask me anything about your saved notes and links.")
        terms = set(tokenize(question))
        # Like the real model: only "answer" when a passage actually talks about the question.
        if not any(terms.intersection(tokenize(p.text)) for p in passages):
            return AnswerDraft(kind="not_found", text="Your saved items don't cover that.")
        quotes = []
        for passage in passages:
            sentences = _SENTENCE.split(passage.text)
            best = max(sentences, key=lambda s: len(terms.intersection(tokenize(s))))
            quotes.append(f"{best} [{passage.number}]")
        return AnswerDraft(kind="answer", text=" ".join(quotes))
