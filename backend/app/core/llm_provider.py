"""
LLM Provider Abstraction for SmartSupply.
Provides a clean interface for LLM reasoning with production-safe REST integration for Gemini,
strict timeout enforcement, secret sanitization, and mock support for deterministic testing.
"""

import abc
import json
import logging
import re
from typing import Any, Dict, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Raised when an LLM provider fails, times out, or returns invalid content."""
    pass


class BaseLLMProvider(abc.ABC):
    """Abstract base interface for LLM reasoning providers."""

    @abc.abstractmethod
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: Optional[int] = None,
    ) -> str:
        """Generates a text completion given system and user prompts."""
        raise NotImplementedError


class GeminiRESTProvider(BaseLLMProvider):
    """
    Lightweight, production-safe Google Gemini REST provider using HTTPX.
    Does not require external heavy SDKs and isolates network calls.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", None)
        self.model_name = model_name or getattr(settings, "LLM_MODEL_NAME", "gemini-1.5-flash")
        self.timeout_seconds = timeout_seconds or getattr(settings, "LLM_TIMEOUT_SECONDS", 15)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: Optional[int] = None,
    ) -> str:
        if not self.is_configured():
            raise LLMProviderError("Gemini API key is not configured in environment or settings.")

        timeout_val = timeout or self.timeout_seconds
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        try:
            with httpx.Client(timeout=float(timeout_val)) as client:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    safe_msg = re.sub(r"key=[^\s&]+", "key=[REDACTED]", response.text[:200])
                    raise LLMProviderError(f"Gemini API returned HTTP {response.status_code}: {safe_msg}")

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise LLMProviderError("Gemini API returned no candidates.")

                content_parts = candidates[0].get("content", {}).get("parts", [])
                if not content_parts or "text" not in content_parts[0]:
                    raise LLMProviderError("Gemini API returned empty text part.")

                return content_parts[0]["text"].strip()

        except httpx.TimeoutException as exc:
            logger.warning("Gemini REST call timed out after %s seconds.", timeout_val)
            raise LLMProviderError(f"Gemini request timed out after {timeout_val}s") from exc
        except httpx.RequestError as exc:
            safe_err = re.sub(r"key=[^\s&]+", "key=[REDACTED]", str(exc))
            logger.warning("Gemini network request error: %s", safe_err)
            raise LLMProviderError(f"Network error contacting Gemini API: {safe_err}") from exc


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for unit tests and testing environments.
    """

    def __init__(
        self,
        default_response: Optional[str] = None,
        side_effect: Optional[Exception] = None,
    ):
        self.default_response = default_response or "{}"
        self.side_effect = side_effect
        self.call_history = []

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: Optional[int] = None,
    ) -> str:
        self.call_history.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "timeout": timeout,
        })
        if self.side_effect:
            raise self.side_effect
        return self.default_response


class GrokRESTProvider(BaseLLMProvider):
    """
    Lightweight, production-safe Grok (xAI) REST provider using HTTPX.
    Communicates with xAI's OpenAI-compatible /v1/chat/completions endpoint.
    Includes strict timeout enforcement and authorization sanitization in logs.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.api_key = api_key or getattr(settings, "GROK_API_KEY", None)
        self.model_name = model_name or getattr(settings, "GROK_MODEL", "grok-beta")
        self.base_url = (base_url or getattr(settings, "GROK_API_BASE_URL", "https://api.x.ai/v1")).rstrip("/")
        self.timeout_seconds = timeout_seconds or getattr(settings, "LLM_TIMEOUT_SECONDS", 15)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: Optional[int] = None,
    ) -> str:
        if not self.is_configured():
            raise LLMProviderError("Grok API key is not configured in environment or settings.")

        timeout_val = timeout or self.timeout_seconds
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        }

        try:
            with httpx.Client(timeout=float(timeout_val)) as client:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    safe_msg = re.sub(r"Bearer\s+[^\s]+", "Bearer [REDACTED]", response.text[:200])
                    raise LLMProviderError(f"Grok API returned HTTP {response.status_code}: {safe_msg}")

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise LLMProviderError("Grok API returned no choices.")

                message = choices[0].get("message", {})
                content = message.get("content", "")
                if not content:
                    raise LLMProviderError("Grok API returned empty message content.")

                return content.strip()

        except httpx.TimeoutException as exc:
            logger.warning("Grok REST call timed out after %s seconds.", timeout_val)
            raise LLMProviderError(f"Grok request timed out after {timeout_val}s") from exc
        except httpx.RequestError as exc:
            safe_err = re.sub(r"Bearer\s+[^\s]+", "Bearer [REDACTED]", str(exc))
            logger.warning("Grok network request error: %s", safe_err)
            raise LLMProviderError(f"Network error contacting Grok API: {safe_err}") from exc


# Global or default provider instance for Gemini (Member 3)
_active_provider: Optional[BaseLLMProvider] = None

# Global or default provider instance for Grok (Member 4)
_active_grok_provider: Optional[BaseLLMProvider] = None


def get_llm_provider() -> BaseLLMProvider:
    """Returns the currently active LLM provider (Gemini by default)."""
    global _active_provider
    if _active_provider is None:
        _active_provider = GeminiRESTProvider()
    return _active_provider


def set_llm_provider(provider: BaseLLMProvider) -> None:
    """Sets the active LLM provider (useful for testing and dependency injection)."""
    global _active_provider
    _active_provider = provider


def get_grok_provider() -> BaseLLMProvider:
    """Returns the currently active Grok LLM provider."""
    global _active_grok_provider
    if _active_grok_provider is None:
        _active_grok_provider = GrokRESTProvider()
    return _active_grok_provider


def set_grok_provider(provider: BaseLLMProvider) -> None:
    """Sets the active Grok LLM provider (useful for testing and dependency injection)."""
    global _active_grok_provider
    _active_grok_provider = provider

