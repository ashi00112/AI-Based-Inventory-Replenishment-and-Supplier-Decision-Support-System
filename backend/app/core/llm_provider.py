"""
LLM Provider Abstraction for SmartSupply.
Provides a clean interface for LLM reasoning with production-safe REST integration for Grok (xAI),
strict timeout enforcement, secret sanitization, and mock support for deterministic testing.
"""

import abc
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
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
        **kwargs: Any,
    ) -> str:
        """Generates a text completion given system and user prompts."""
        raise NotImplementedError


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
        self.call_history: List[Dict[str, Any]] = []

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        self.call_history.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "timeout": timeout,
            **kwargs,
        })
        if self.side_effect:
            raise self.side_effect
        return self.default_response


class GrokRESTProvider(BaseLLMProvider):
    """
    Lightweight, production-safe Grok (xAI) REST provider using HTTPX.
    Communicates with xAI's OpenAI-compatible /v1/chat/completions endpoint.
    Includes strict timeout enforcement, error handling, and authorization sanitization in logs.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = (
                getattr(settings, "GROK_API_KEY", None)
                or getattr(settings, "GROQ_API_KEY", None)
                or os.environ.get("GROK_API_KEY")
                or os.environ.get("GROQ_API_KEY")
            )

        # Detect whether we are using Groq Cloud (gsk_ key) or xAI Grok
        if self.api_key and self.api_key.startswith("gsk_"):
            is_groq_cloud = True
        elif self.api_key and self.api_key.startswith("xai-"):
            is_groq_cloud = False
        else:
            is_groq_cloud = bool(
                getattr(settings, "GROQ_API_KEY", None)
                and not getattr(settings, "GROK_API_KEY", None)
            )

        if model_name is not None:
            self.model_name = model_name
        elif is_groq_cloud:
            self.model_name = (
                getattr(settings, "GROQ_MODEL", None)
                or os.environ.get("GROQ_MODEL")
                or "openai/gpt-oss-120b"
            )
        else:
            self.model_name = (
                getattr(settings, "GROK_MODEL", None)
                or os.environ.get("GROK_MODEL")
                or "grok-beta"
            )

        if base_url is not None:
            self.base_url = base_url.rstrip("/")
        elif is_groq_cloud:
            self.base_url = (
                getattr(settings, "GROQ_API_BASE_URL", None)
                or os.environ.get("GROQ_API_BASE_URL")
                or "https://api.groq.com/openai/v1"
            ).rstrip("/")
        else:
            self.base_url = (
                getattr(settings, "GROK_API_BASE_URL", None)
                or os.environ.get("GROK_API_BASE_URL")
                or "https://api.x.ai/v1"
            ).rstrip("/")

        self.timeout_seconds = timeout_seconds or getattr(settings, "LLM_TIMEOUT_SECONDS", 15)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _sanitize_secrets(self, text: str) -> str:
        """Sanitizes API keys and tokens from log messages and exception strings."""
        if not text:
            return ""
        sanitized = str(text)
        if self.api_key and self.api_key.strip():
            sanitized = sanitized.replace(self.api_key.strip(), "[REDACTED]")
        sanitized = re.sub(r"Bearer\s+[^\s\"']+", "Bearer [REDACTED]", sanitized)
        sanitized = re.sub(r"xai-[a-zA-Z0-9_\-]+", "[REDACTED]", sanitized)
        sanitized = re.sub(r"gsk_[a-zA-Z0-9_\-]+", "[REDACTED]", sanitized)
        return sanitized

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: Optional[int] = None,
        **kwargs: Any,
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
                    safe_msg = self._sanitize_secrets(response.text[:300])
                    raise LLMProviderError(f"Grok API returned HTTP {response.status_code}: {safe_msg}")

                try:
                    data = response.json()
                except Exception as exc:
                    safe_err = self._sanitize_secrets(str(exc))
                    raise LLMProviderError(f"Grok API returned malformed non-JSON response: {safe_err}") from exc

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
            safe_err = self._sanitize_secrets(str(exc))
            logger.warning("Grok network request error: %s", safe_err)
            raise LLMProviderError(f"Network error contacting Grok API: {safe_err}") from exc


# Global or default provider instance for Grok (Standard Production LLM)
_active_provider: Optional[BaseLLMProvider] = None


def get_llm_provider() -> BaseLLMProvider:
    """Returns the currently active production LLM provider (GrokRESTProvider by default)."""
    global _active_provider
    if _active_provider is None:
        _active_provider = GrokRESTProvider()
    return _active_provider


def set_llm_provider(provider: Optional[BaseLLMProvider]) -> None:
    """Sets the active LLM provider (useful for testing and dependency injection)."""
    global _active_provider
    _active_provider = provider


def get_grok_provider() -> BaseLLMProvider:
    """Returns the currently active Grok LLM provider (alias for get_llm_provider)."""
    return get_llm_provider()


def set_grok_provider(provider: Optional[BaseLLMProvider]) -> None:
    """Sets the active Grok LLM provider (alias for set_llm_provider)."""
    set_llm_provider(provider)
