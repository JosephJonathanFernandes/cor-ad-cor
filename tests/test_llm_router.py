"""Unit tests for 4-key Groq rotation and Gemini fallback routing."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.llm.router import AllProvidersExhaustedError, GroqGeminiRouter


@dataclass
class FakeResponse:
    content: str


class FakeClock:
    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_rotates_through_four_groq_keys_on_rate_limit() -> None:
    calls: list[str] = []

    def groq_factory(api_key: str, model: str, temperature: float):
        class _Client:
            def invoke(self, messages):
                calls.append(api_key)
                if api_key in ("k1", "k2"):
                    raise RuntimeError("429 rate_limit_exceeded")
                return FakeResponse(content=f"ok from {api_key}")

        return _Client()

    clock = FakeClock()
    router = GroqGeminiRouter(
        groq_keys=["k1", "k2", "k3", "k4"],
        gemini_api_key="gem-key",
        cooldown_seconds=60,
        groq_factory=groq_factory,
        clock=clock,
    )

    res = router.generate("sys", "usr")
    assert res.provider == "groq"
    assert res.key_slot == "groq_key_3"
    assert res.content == "ok from k3"
    assert res.attempts == 3
    assert calls == ["k1", "k2", "k3"]

    # Next call should advance to k4 and skip cooled-down k1/k2
    res2 = router.generate("sys", "usr")
    assert res2.key_slot == "groq_key_4"
    assert res2.attempts == 1


def test_falls_back_to_gemini_when_all_groq_keys_fail() -> None:
    gemini_called = False

    def groq_factory(api_key: str, model: str, temperature: float):
        class _FailingClient:
            def invoke(self, messages):
                raise RuntimeError("429 quota exceeded")

        return _FailingClient()

    def gemini_factory(api_key: str, model: str, temperature: float):
        class _GeminiClient:
            def invoke(self, messages):
                nonlocal gemini_called
                gemini_called = True
                return FakeResponse(content="grounded gemini response")

        return _GeminiClient()

    router = GroqGeminiRouter(
        groq_keys=["k1", "k2", "k3", "k4"],
        gemini_api_key="gem-key",
        groq_factory=groq_factory,
        gemini_factory=gemini_factory,
    )

    res = router.generate("sys", "usr")
    assert gemini_called is True
    assert res.provider == "gemini"
    assert res.key_slot == "gemini_fallback"
    assert res.content == "grounded gemini response"
    assert res.attempts == 5


def test_raises_when_no_keys_or_all_fail() -> None:
    router = GroqGeminiRouter(groq_keys=[], gemini_api_key="")
    with pytest.raises(AllProvidersExhaustedError):
        router.generate("sys", "usr")
