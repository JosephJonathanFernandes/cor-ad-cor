"""Tests for Lectio Divina, Universalis JSONP parser, PWA assets, Journal export, and rate limiting."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.data_sources.liturgy import parse_universalis_jsonp
from app.llm.router import GroqGeminiRouter
from app.main import create_app
from app.rag.catechism import CatechismIndex, LocalDeterministicEmbeddings
from app.services.companion import CompanionService


def test_parse_universalis_jsonp() -> None:
    sample = (
        'universalisCallback({"day":"<b>Christ the King</b>",'
        '"Mass_R1":{"source":"Ezekiel 34:11-12","text":"<p>Thus says the Lord GOD.</p>"},'
        '"Mass_Ps":{"source":"Psalm 23","text":"<p>The Lord is my shepherd.</p>"},'
        '"Mass_G":{"source":"Matthew 25:31-46","text":"<p>When the Son of Man comes in his glory.</p>"}});'
    )
    title, readings = parse_universalis_jsonp(sample)
    assert title == "Christ the King"
    assert len(readings) == 3
    assert readings[0].label == "First Reading"
    assert readings[2].label == "Gospel"
    assert "Son of Man" in readings[2].text


def test_lectio_pwa_export_and_rate_limiting(tmp_path: Path) -> None:
    seed_path = Path(__file__).resolve().parent.parent / "data" / "ccc" / "ccc_seed.json"
    settings = Settings(
        ccc_seed_path=seed_path,
        ccc_index_dir=tmp_path / "idx",
        readings_cache_dir=tmp_path / "cache",
        journal_db_path=tmp_path / "journal" / "memory.db",
    )
    router = GroqGeminiRouter(groq_keys=[], gemini_api_key="")
    ccc_index = CatechismIndex.load_or_build(
        index_dir=settings.ccc_index_dir,
        source_path=seed_path,
        embeddings=LocalDeterministicEmbeddings(),
    )
    service = CompanionService(settings=settings, router=router, ccc_index=ccc_index)
    app = create_app(service_override=service, rate_limit_per_minute=2)

    with TestClient(app) as client:
        # 1. PWA static assets + security headers
        manifest = client.get("/static/manifest.json")
        sw = client.get("/static/sw.js")
        icon = client.get("/static/icon.svg")
        assert manifest.status_code == 200
        assert sw.status_code == 200
        assert icon.status_code == 200
        assert manifest.headers.get("x-content-type-options") == "nosniff"
        assert manifest.headers.get("x-frame-options") == "SAMEORIGIN"

        # 2. Lectio Divina endpoint (request #1 of 2 allowed per minute)
        lectio = client.post(
            "/api/v1/lectio",
            json={
                "selected_phrase": "Here are my mother and my brothers.",
                "date": "2026-11-21",
                "offline": True,
                "demo": True,
            },
        )
        assert lectio.status_code == 200
        lectio_data = lectio.json()
        assert "Lectio" in lectio_data["reflection"]
        assert "Contemplatio" in lectio_data["reflection"]
        assert any(c["paragraph"] == 2709 for c in lectio_data["ccc_citations"])

        # 3. Check-in (request #2 of 2 allowed per minute) + Journal export
        checkin = client.post(
            "/api/v1/checkin",
            json={
                "message": "Grateful for quiet prayer this morning",
                "date": "2026-11-21",
                "offline": True,
                "demo": True,
                "remember": True,
            },
        )
        assert checkin.status_code == 200

        export = client.get("/api/v1/memory/export")
        assert export.status_code == 200
        assert "attachment" in export.headers.get("content-disposition", "")
        assert export.json()["total_entries"] == 1

        # 4. Rate limit kicks in on request #3 within the same minute
        throttled = client.post(
            "/api/v1/lectio",
            json={"date": "2026-11-21", "offline": True, "demo": True},
        )
        assert throttled.status_code == 429
        assert throttled.headers.get("retry-after") == "60"
