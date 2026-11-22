"""4-key Groq LLM router with automatic cooldown rotation and Gemini fallback."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)


class ChatModelLike(Protocol):
    """Minimal protocol satisfied by LangChain chat models and test doubles."""

    def invoke(self, messages: list[Any]) -> Any: ...


class AllProvidersExhaustedError(RuntimeError):
    """Raised when every configured Groq key and Gemini fallback fail."""


@dataclass(frozen=True)
class LLMResult:
    """Response payload paired with provider telemetry (never exposes secrets)."""

    content: str
    provider: str
    model: str
    key_slot: str | None = None
    attempts: int = 1


def _extract_text(response: Any) -> str:
    """Normalize LangChain AIMessage content (str or multipart list) into plain text."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        ]
        return "\n".join(p for p in parts if p).strip()
    return str(content).strip()


def _is_permanent_auth_error(exc: Exception) -> bool:
    """Detect invalid/revoked API key errors so the key is cooled down longer."""
    msg = str(exc).lower()
    return any(tok in msg for tok in ("401", "invalid_api_key", "invalid api key", "unauthorized"))


@dataclass
class GroqGeminiRouter:
    """Routes LLM calls across up to 4 Groq keys, falling back to Gemini."""

    groq_keys: list[str]
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    cooldown_seconds: int = 60
    groq_factory: Callable[[str, str, float], ChatModelLike] | None = None
    gemini_factory: Callable[[str, str, float], ChatModelLike] | None = None
    clock: Callable[[], float] = time.monotonic

    _next_index: int = field(default=0, init=False)
    _cooldown_until: dict[int, float] = field(default_factory=dict, init=False)

    def _build_groq_client(self, api_key: str, temperature: float) -> ChatModelLike:
        if self.groq_factory is not None:
            return self.groq_factory(api_key, self.groq_model, temperature)
        return ChatGroq(
            api_key=api_key,
            model=self.groq_model,
            temperature=temperature,
            max_retries=0,  # Router handles rotation directly instead of sleeping on one key.
        )

    def _build_gemini_client(self, temperature: float) -> ChatModelLike:
        if self.gemini_factory is not None:
            return self.gemini_factory(self.gemini_api_key, self.gemini_model, temperature)
        return ChatGoogleGenerativeAI(
            google_api_key=self.gemini_api_key,
            model=self.gemini_model,
            temperature=temperature,
        )

    def _active_groq_indices(self, now: float) -> list[int]:
        """Return Groq key indices in round-robin order, skipping cooled-down keys."""
        total = len(self.groq_keys)
        if total == 0:
            return []
        ordered = [(self._next_index + offset) % total for offset in range(total)]
        return [idx for idx in ordered if self._cooldown_until.get(idx, 0.0) <= now]

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.4,
    ) -> LLMResult:
        """Generate a completion using Groq keys first, then Gemini fallback."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        errors: list[str] = []
        attempts = 0
        now = self.clock()

        for idx in self._active_groq_indices(now):
            attempts += 1
            slot = f"groq_key_{idx + 1}"
            try:
                client = self._build_groq_client(self.groq_keys[idx], temperature)
                response = client.invoke(messages)
                text = _extract_text(response)
                if not text:
                    raise ValueError("Empty response from Groq")
                self._next_index = (idx + 1) % len(self.groq_keys)
                return LLMResult(
                    content=text,
                    provider="groq",
                    model=self.groq_model,
                    key_slot=slot,
                    attempts=attempts,
                )
            except Exception as exc:  # noqa: BLE001 — intentionally rotate on any provider failure
                cooldown = (
                    max(self.cooldown_seconds * 10, 600)
                    if _is_permanent_auth_error(exc)
                    else self.cooldown_seconds
                )
                self._cooldown_until[idx] = self.clock() + cooldown
                errors.append(f"{slot}: {type(exc).__name__}: {exc}")
                logger.warning("Groq %s failed (%s); rotating.", slot, type(exc).__name__)

        if self.gemini_api_key.strip():
            attempts += 1
            try:
                gemini_client = self._build_gemini_client(temperature)
                response = gemini_client.invoke(messages)
                text = _extract_text(response)
                if not text:
                    raise ValueError("Empty response from Gemini")
                return LLMResult(
                    content=text,
                    provider="gemini",
                    model=self.gemini_model,
                    key_slot="gemini_fallback",
                    attempts=attempts,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"gemini_fallback: {type(exc).__name__}: {exc}")
                logger.error("Gemini fallback failed: %s", exc)

        if not self.groq_keys and not self.gemini_api_key.strip():
            raise AllProvidersExhaustedError(
                "No LLM API keys configured. Set GROQ_API_KEY_1..4 or GEMINI_API_KEY in .env."
            )

        raise AllProvidersExhaustedError(
            "All configured LLM providers failed or are cooling down: " + " | ".join(errors)
        )
