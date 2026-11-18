"""Google Gemini embeddings + answer generation (google-genai SDK).

Embeddings use retrieval task types: passages are embedded as RETRIEVAL_DOCUMENT and
questions as RETRIEVAL_QUERY, which Gemini optimises for asymmetric search.
Provider failures are mapped to clear API errors (bad key, quota, timeout, outage).
"""

import json

import httpx
import numpy as np
import structlog
from google import genai
from google.genai import errors, types

from app.core.config import Settings
from app.core.errors import AppError, ServiceUnavailableError, UpstreamError
from app.domain import AnswerDraft, Passage, PriorTurn
from app.services.prompt import REWRITE_SYSTEM_PROMPT, SYSTEM_PROMPT, build_rewrite_prompt, build_user_prompt

log = structlog.get_logger("gemini")

EMBEDDING_BATCH_SIZE = 100  # Gemini's per-request limit
MAX_REWRITE_CHARS = 500
ANSWER_KINDS = ("answer", "not_found", "small_talk")

# Structured output: the model labels its reply in the same call that writes it.
ANSWER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "kind": {"type": "STRING", "enum": list(ANSWER_KINDS)},
        "text": {"type": "STRING"},
    },
    "required": ["kind", "text"],
}


def parse_answer(raw: str) -> AnswerDraft:
    """Read the {kind, text} JSON reply; if the model ignored the format, keep its text as a plain answer."""
    try:
        data = json.loads(raw)
        kind = data.get("kind") if data.get("kind") in ANSWER_KINDS else "answer"
        return AnswerDraft(kind=kind, text=str(data.get("text", "")).strip())
    except (json.JSONDecodeError, AttributeError):
        return AnswerDraft(kind="answer", text=raw.strip())
RETRYABLE_STATUS_CODES = [429, 500, 502, 503, 504]


def build_gemini_client(settings: Settings) -> genai.Client:
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(
            timeout=int(settings.ai_timeout_seconds * 1000),  # milliseconds
            retry_options=types.HttpRetryOptions(attempts=3, initial_delay=1.0, http_status_codes=RETRYABLE_STATUS_CODES),
        ),
    )


def _translate(exc: Exception, operation: str, model: str = "") -> AppError:
    # Keep Google's own status and message in the server log; the client gets a clear, safe summary.
    log.warning(
        "gemini_error",
        operation=operation,
        model=model,
        status=getattr(exc, "code", None),
        error_type=type(exc).__name__,
        detail=str(exc)[:300],
    )
    if isinstance(exc, httpx.TimeoutException):
        return UpstreamError(f"Gemini timed out during {operation}.", code="LLM_TIMEOUT", status_code=504)
    if isinstance(exc, httpx.RequestError):
        return UpstreamError("Couldn't reach Gemini. Check the network connection.", code="LLM_UNREACHABLE")

    code = getattr(exc, "code", None)
    if code == 503:
        return ServiceUnavailableError("Gemini is overloaded right now. Try again in a moment.", code="LLM_OVERLOADED")
    if code is not None and code >= 500:
        return UpstreamError(f"Gemini had a server error during {operation}. Try again.", code="LLM_SERVER_ERROR")
    if code in (401, 403) or (code == 400 and "API key" in str(exc)):
        return ServiceUnavailableError("The Gemini API key was rejected. Check GEMINI_API_KEY.", code="LLM_AUTH_FAILED")
    if code == 429:
        return ServiceUnavailableError(
            "Gemini is rate limiting requests or the free quota is used up. Try again in a minute.",
            code="LLM_RATE_LIMITED",
        )
    if code == 404:
        return UpstreamError(
            f"Gemini model '{model}' isn't available to this API key ({operation}). Set a current model name.",
            code="LLM_MODEL_NOT_FOUND",
        )
    return UpstreamError(f"Gemini returned an error during {operation}.", code="LLM_ERROR")


_PROVIDER_ERRORS = (errors.APIError, httpx.HTTPError)


class GeminiEmbedder:
    # Cosine score below which a passage is treated as irrelevant; override with MIN_SIMILARITY.
    default_min_similarity = 0.3

    def __init__(self, client: genai.Client, model: str, dimensions: int):
        self._client = client
        self._model = model
        self._dimensions = dimensions
        self.model_id = f"gemini:{model}:{dimensions}"

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        return await self._embed(texts, "RETRIEVAL_DOCUMENT")

    async def embed_query(self, text: str) -> np.ndarray:
        return (await self._embed([text], "RETRIEVAL_QUERY"))[0]

    async def _embed(self, texts: list[str], task_type: str) -> np.ndarray:
        config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=self._dimensions)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[start : start + EMBEDDING_BATCH_SIZE]
            try:
                response = await self._client.aio.models.embed_content(model=self._model, contents=batch, config=config)
            except _PROVIDER_ERRORS as exc:
                raise _translate(exc, "embedding", self._model) from exc
            vectors.extend(embedding.values for embedding in response.embeddings or [])

        if len(vectors) != len(texts):
            raise UpstreamError("Gemini returned an unexpected number of embeddings.", code="LLM_ERROR")
        return np.asarray(vectors, dtype=np.float32)


class GeminiAnswerer:
    def __init__(self, client: genai.Client, model: str, thinking_level: str = ""):
        self._client = client
        self._model = model
        self._thinking_level = thinking_level

    async def answer(self, question: str, passages: list[Passage], history: list[PriorTurn]) -> AnswerDraft:
        raw = await self._generate(
            build_user_prompt(question, passages, history),
            SYSTEM_PROMPT,
            "answer generation",
            json_schema=ANSWER_SCHEMA,
        )
        draft = parse_answer(raw)
        if not draft.text:
            raise UpstreamError(
                "Gemini returned an empty answer (it may have been blocked by safety filters).",
                code="LLM_EMPTY_ANSWER",
            )
        return draft

    async def rewrite_question(self, question: str, history: list[PriorTurn]) -> str:
        rewritten = await self._generate(
            build_rewrite_prompt(question, history), REWRITE_SYSTEM_PROMPT, "follow-up rewriting", temperature=0.0
        )
        # A blank or rambling rewrite is worse than searching the raw follow-up.
        first_line = rewritten.splitlines()[0].strip().strip('"') if rewritten else ""
        return first_line if 0 < len(first_line) <= MAX_REWRITE_CHARS else question

    async def _generate(
        self, prompt: str, system: str, operation: str, temperature: float = 0.1, json_schema: dict | None = None
    ) -> str:
        config = types.GenerateContentConfig(system_instruction=system, temperature=temperature)
        if self._thinking_level:
            config.thinking_config = types.ThinkingConfig(thinking_level=self._thinking_level)
        if json_schema:
            config.response_mime_type = "application/json"
            config.response_schema = json_schema
        try:
            response = await self._client.aio.models.generate_content(model=self._model, contents=prompt, config=config)
        except _PROVIDER_ERRORS as exc:
            raise _translate(exc, operation, self._model) from exc
        return (response.text or "").strip()
