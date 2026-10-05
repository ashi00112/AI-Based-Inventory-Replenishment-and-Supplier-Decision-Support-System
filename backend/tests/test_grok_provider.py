"""
Unit tests for Grok (xAI) LLM Provider.
Verifies configuration, error handling, secret sanitization, timeout resilience,
freeform chat completion, structured JSON validation, and MockLLMProvider integration.
"""

import json
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.core.config import settings
from app.core.llm_provider import (
    BaseLLMProvider,
    GrokRESTProvider,
    MockLLMProvider,
    LLMProviderError,
    get_llm_provider,
    set_llm_provider,
    get_grok_provider,
    set_grok_provider,
)


def test_1_grok_provider_configured_correctly_from_settings(monkeypatch):
    """1. Grok provider initialized with settings picks up config and is_configured is True."""
    monkeypatch.setattr(settings, "GROK_API_KEY", "xai-test-key-12345")
    monkeypatch.setattr(settings, "GROK_MODEL", "grok-beta")
    monkeypatch.setattr(settings, "GROK_API_BASE_URL", "https://api.x.ai/v1")
    monkeypatch.setattr(settings, "LLM_TIMEOUT_SECONDS", 10)

    provider = GrokRESTProvider()
    assert provider.is_configured() is True
    assert provider.api_key == "xai-test-key-12345"
    assert provider.model_name == "grok-beta"
    assert provider.base_url == "https://api.x.ai/v1"
    assert provider.timeout_seconds == 10


def test_2_missing_grok_key_unconfigured(monkeypatch):
    """2. Missing Grok key: is_configured() = False and raises LLMProviderError on generate."""
    monkeypatch.setattr(settings, "GROK_API_KEY", None)
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    provider = GrokRESTProvider(api_key=None)
    assert provider.is_configured() is False

    with pytest.raises(LLMProviderError) as exc_info:
        provider.generate_text("System", "User")
    assert "not configured" in str(exc_info.value)


def test_3_grok_success_response_parsed_correctly():
    """3. Grok success response (OpenAI format with choices[0].message.content) parsed correctly."""
    provider = GrokRESTProvider(api_key="xai-valid-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Grok synthesized response text.",
                },
                "finish_reason": "stop",
            }
        ],
    }

    with patch.object(httpx.Client, "post", return_value=mock_resp) as mock_post:
        result = provider.generate_text("System prompt", "User prompt")
        assert result == "Grok synthesized response text."

        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["model"] == "grok-beta"
        assert call_kwargs["headers"]["Authorization"] == "Bearer xai-valid-key"
        assert call_kwargs["json"]["messages"][0]["content"] == "System prompt"
        assert call_kwargs["json"]["messages"][1]["content"] == "User prompt"


def test_4_grok_http_error_raises_sanitized_llm_provider_error():
    """4. Grok HTTP error raises sanitized LLMProviderError without leaking keys."""
    provider = GrokRESTProvider(api_key="xai-secret-auth-key-999")

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"error": {"message": "Invalid API key provided: xai-secret-auth-key-999", "type": "auth_error"}}'

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_text("System", "User")

        err_msg = str(exc_info.value)
        assert "HTTP 401" in err_msg
        assert "xai-secret-auth-key-999" not in err_msg
        assert "[REDACTED]" in err_msg


def test_5_grok_timeout_safely_handled():
    """5. Grok timeout safely caught and raised as LLMProviderError."""
    provider = GrokRESTProvider(api_key="xai-test-key", timeout_seconds=5)

    with patch.object(httpx.Client, "post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_text("System", "User")

        assert "timed out after 5s" in str(exc_info.value)


def test_6_grok_malformed_response_handled():
    """6. Malformed JSON or missing choices handled safely without raw crash."""
    provider = GrokRESTProvider(api_key="xai-test-key")

    # Case 6a: invalid json
    mock_resp_invalid_json = MagicMock()
    mock_resp_invalid_json.status_code = 200
    mock_resp_invalid_json.json.side_effect = json.JSONDecodeError("Expecting value", "bad json", 0)

    with patch.object(httpx.Client, "post", return_value=mock_resp_invalid_json):
        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_text("System", "User")
        assert "malformed non-JSON response" in str(exc_info.value)

    # Case 6b: empty choices list
    mock_resp_empty_choices = MagicMock()
    mock_resp_empty_choices.status_code = 200
    mock_resp_empty_choices.json.return_value = {"choices": []}

    with patch.object(httpx.Client, "post", return_value=mock_resp_empty_choices):
        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_text("System", "User")
        assert "returned no choices" in str(exc_info.value)

    # Case 6c: empty message content
    mock_resp_empty_content = MagicMock()
    mock_resp_empty_content.status_code = 200
    mock_resp_empty_content.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": ""}}]
    }

    with patch.object(httpx.Client, "post", return_value=mock_resp_empty_content):
        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_text("System", "User")
        assert "empty message content" in str(exc_info.value)


def test_7_api_key_never_appears_in_error_strings():
    """7. API key never appears in error strings across network errors or HTTP error bodies."""
    secret_key = "xai-ultra-confidential-token-777888"
    provider = GrokRESTProvider(api_key=secret_key)

    # Network RequestError containing the secret
    request_err = httpx.RequestError(f"Failed to connect using Bearer {secret_key}")
    with patch.object(httpx.Client, "post", side_effect=request_err):
        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_text("System", "User")

        err_text = str(exc_info.value)
        assert secret_key not in err_text
        assert "[REDACTED]" in err_text


def test_8_chat_freeform_response_works():
    """8. Freeform markdown/plain-text response for chatbot flows cleanly."""
    provider = GrokRESTProvider(api_key="xai-test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "There are **24** Wireless Mice available in inventory."
                }
            }
        ]
    }

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        res = provider.generate_text(
            system_prompt="You are SmartSupply Assistant.",
            user_prompt="How many Wireless Mice are available?",
        )
        assert "24" in res
        assert "**" in res


def test_9_structured_supplier_signal_response_validates_correctly():
    """9. Structured supplier JSON response from Grok validates against expected schema."""
    from app.agents.supplier_procurement_agent import SupplierProcurementAgent

    agent = SupplierProcurementAgent()
    raw_json_text = json.dumps({
        "assessments": [
            {
                "supplier_id": 1,
                "advantages": ["Standard 5-day delivery", "ISO 9001 certified"],
                "risks": ["Strict 50-unit MOQ"],
                "cited_document_ids": [101],
            }
        ]
    })

    parsed = agent._extract_and_parse_json(raw_json_text)
    assert parsed is not None
    assert "assessments" in parsed
    assert len(parsed["assessments"]) == 1
    assert parsed["assessments"][0]["supplier_id"] == 1
    assert parsed["assessments"][0]["cited_document_ids"] == [101]


def test_10_mock_llm_provider_remains_functional():
    """10. MockLLMProvider records calls, returns defaults, raises side_effects, and supports provider swapping."""
    mock = MockLLMProvider(default_response="Mock answer")
    set_llm_provider(mock)

    try:
        active = get_llm_provider()
        assert active is mock
        assert get_grok_provider() is mock

        ans = active.generate_text("sys", "usr", timeout=5)
        assert ans == "Mock answer"
        assert len(mock.call_history) == 1
        assert mock.call_history[0]["system_prompt"] == "sys"
        assert mock.call_history[0]["user_prompt"] == "usr"

        # Test side_effect
        mock.side_effect = LLMProviderError("Mock error")
        with pytest.raises(LLMProviderError):
            active.generate_text("sys", "usr")
    finally:
        set_llm_provider(None)
        set_grok_provider(None)
