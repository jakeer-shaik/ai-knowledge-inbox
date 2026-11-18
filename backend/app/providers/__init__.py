"""AI provider wiring. The rest of the app depends only on the protocols in `base`."""

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings
from app.providers.base import AnswerGenerator, EmbeddingProvider
from app.providers.gemini_provider import GeminiAnswerer, GeminiEmbedder, build_gemini_client


@dataclass(frozen=True)
class AIProviders:
    embedder: EmbeddingProvider
    answerer: AnswerGenerator


@lru_cache
def get_providers() -> AIProviders:
    settings = get_settings()
    client = build_gemini_client(settings)
    return AIProviders(
        embedder=GeminiEmbedder(client, settings.gemini_embedding_model, settings.gemini_embedding_dimensions),
        answerer=GeminiAnswerer(client, settings.gemini_chat_model, thinking_level=settings.gemini_thinking_level),
    )
