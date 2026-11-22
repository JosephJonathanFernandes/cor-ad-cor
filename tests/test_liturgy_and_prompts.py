"""Unit tests for liturgical parsers, pastoral guardrails, and FastAPI endpoints."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.data_sources.liturgy import (
    get_liturgical_day,
    parse_calapi_payload,
    parse_usccb_html,
)
from app.llm.router import GroqGeminiRouter
from app.main import create_app
from app.prompts.companion import detect_distress_signal
from app.rag.catechism import CatechismIndex, LocalDeterministicEmbeddings
from app.services.companion import CompanionService


@dataclass
class FakeMsg:
    content: str


def test_parse_usccb_html_and_calapi_payload() -> None:
    sample_html = """
    <html><body>
      <h1 class="page-title">Memorial of Saint Agnes</h1>
      <div class="b-verse">
        <h3 class="name">Reading 1</h3>
        <div class="address"><a href="#">Hebrews 7:25-8:6</a></div>
        <div class="content-body"><p>Jesus is always able to save those who approach God through him.</p></div>
      </div>
      <div class="b-verse">
        <h3 class="name">Gospel</h3>
        <div class="address"><a href="#">Mark 3:7-12</a></div>
        <div class="content-body"><p>Jesus withdrew toward the sea with his disciples.</p></div>
      </div>
    </body></html>
    """
    title, readings = parse_usccb_html(sample_html)
    assert title == "Memorial of Saint Agnes"
    assert len(readings) == 2
    assert readings[0].label == "Reading 1"
    assert readings[0].citation == "Hebrews 7:25-8:6"
    assert readings[1].label == "Gospel"

    season, celebration, saint = parse_calapi_payload(
        {
            "season": "ordinary",
            "celebrations": [
                {"title": "St. Agnes, virgin and martyr", "rank": "memorial", "colour": "red"}
            ],
        }
    )
    assert season == "Ordinary"
    assert celebration == "St. Agnes, virgin and martyr"
    assert saint is not None and saint.colour == "red"


def test_distress_detection() -> None:
    assert detect_distress_signal("I feel like I want to end my life tonight") is True
    assert detect_distress_signal("I feel exhausted and distant from God at work") is False


def test_api_daily_and_checkin_and_crisis_guardrail(tmp_path: Path) -> None:
    seed_path = Path(__file__).resolve().parent.parent / "data" / "ccc" / "ccc_seed.json"
    settings = Settings(
        groq_api_key_1="fake-k1",
        gemini_api_key="fake-gem",
        ccc_seed_path=seed_path,
        ccc_index_dir=tmp_path / "idx",
        readings_cache_dir=tmp_path / "cache",
    )

    def groq_factory(api_key: str, model: str, temperature: float):
        class _Client:
            def invoke(self, messages):
                return FakeMsg(content="### 1. 5 Minutes Before Mass\nGrounded test reflection [Gospel] [CCC §2729].")

        return _Client()

    router = GroqGeminiRouter(groq_keys=["fake-k1"], groq_factory=groq_factory)
    ccc_index = CatechismIndex.load_or_build(
        index_dir=settings.ccc_index_dir,
        source_path=seed_path,
        embeddings=LocalDeterministicEmbeddings(),
    )
    service = CompanionService(settings=settings, router=router, ccc_index=ccc_index)
    app = create_app(service_override=service)

    with TestClient(app) as client:
        daily = client.get("/api/v1/daily", params={"offline": True, "date": "2026-11-21"})
        assert daily.status_code == 200
        data = daily.json()
        assert data["llm"]["provider"] == "groq"
        assert len(data["ccc_citations"]) >= 3
        assert any(c["paragraph"] == 2729 for c in data["ccc_citations"])
        assert data["citation_verification"]["all_valid"] is True
        assert "5 Minutes Before Mass" in data["reflection"]

        checkin = client.post(
            "/api/v1/checkin",
            json={"message": "I feel dry in prayer lately", "offline": True, "date": "2026-11-21"},
        )
        assert checkin.status_code == 200
        assert checkin.json()["crisis_escalated"] is False

        crisis = client.post(
            "/api/v1/checkin",
            json={"message": "I want to kill myself", "offline": True, "date": "2026-11-21"},
        )
        assert crisis.status_code == 200
        crisis_data = crisis.json()
        assert crisis_data["crisis_escalated"] is True
        assert crisis_data["llm"] is None
        assert "988" in crisis_data["reflection"]

        day = get_liturgical_day(dt.date(2026, 11, 21), cache_dir=settings.readings_cache_dir, offline=True)
        assert day.source == "offline_sample"
