import httpx
import pytest
from google.genai import errors
from pydantic import ValidationError

from app.core.config import Settings
from app.providers.gemini_provider import _translate


def test_api_key_is_required(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="GEMINI_API_KEY is not set"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("code", "expected_status", "expected_code"),
    [
        (400, 502, "LLM_ERROR"),
        (403, 503, "LLM_AUTH_FAILED"),
        (404, 502, "LLM_MODEL_NOT_FOUND"),
        (429, 503, "LLM_RATE_LIMITED"),
        (500, 502, "LLM_SERVER_ERROR"),
        (503, 503, "LLM_OVERLOADED"),
    ],
)
def test_gemini_errors_map_to_clear_api_errors(code, expected_status, expected_code):
    error = _translate(errors.APIError(code, {"error": {"message": "boom", "status": "X"}}), "embedding")
    assert (error.status_code, error.code) == (expected_status, expected_code)


def test_timeouts_map_to_504():
    error = _translate(httpx.ReadTimeout("slow"), "answer generation")
    assert (error.status_code, error.code) == (504, "LLM_TIMEOUT")
