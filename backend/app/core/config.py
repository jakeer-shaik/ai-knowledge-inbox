"""Application settings, loaded from environment variables / .env and validated at startup."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["dev", "prod", "test"] = "dev"
    log_level: str = "INFO"
    database_path: str = "data/inbox.db"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Google Gemini (free key: https://aistudio.google.com/apikey)
    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dimensions: int = Field(default=768, ge=128, le=3072)
    # Flash-Lite: fastest in testing (~1.6 s) and its own free-tier quota
    # (gemini-3.8-flash allows only 20 requests/day on the free tier).
    gemini_chat_model: str = "gemini-3.5-flash-lite"
    # Gemini 3 models "think" before replying; the default level took 30 s+ for a cited summary,
    # "low" takes ~5 s with the same quality for this task. Empty = use the model's default.
    gemini_thinking_level: str = "low"
    ai_timeout_seconds: float = Field(default=30.0, gt=0)

    chunk_size: int = Field(default=800, ge=200, le=4000)
    chunk_overlap: int = Field(default=100, ge=0)
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    # None = use the active embedding provider's own sensible threshold.
    min_similarity: float | None = Field(default=None, ge=-1.0, le=1.0)

    fetch_timeout_seconds: float = Field(default=10.0, gt=0)
    fetch_max_bytes: int = Field(default=2_000_000, gt=0)
    # Off by default (SSRF protection). Tests turn it on to fetch pages from a local server.
    fetch_allow_private_hosts: bool = False
    ingest_worker_concurrency: int = Field(default=2, ge=1, le=16)

    @model_validator(mode="after")
    def _check_consistency(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if not self.gemini_api_key.strip():
            raise ValueError("GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
