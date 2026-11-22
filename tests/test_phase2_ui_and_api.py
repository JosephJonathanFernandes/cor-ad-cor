"""Phase 2 tests for the web UI static routes, non-LLM liturgy context endpoint, and demo preview mode."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.router import GroqGeminiRouter
from app.main import create_app
from app.rag.catechism import CatechismIndex, LocalDeterministicEmbeddings
from app.services.companion import CompanionService


def test_phase2_web_ui_and_endpoints(tmp_path: Path) -> None:
    seed_path = Path(__file__).resolve().parent.parent / "data" / "ccc" / "ccc_seed.json"
    settings = Settings(
        ccc_seed_path=seed_path,
        ccc_index_dir=tmp_path / "idx",
        readings_cache_dir=tmp_path / "cache",
    )
    # Router with no keys configured to verify liturgy context and demo preview mode work without keys
    router = GroqGeminiRouter(groq_keys=[], gemini_api_key="")
    ccc_index = CatechismIndex.load_or_build(
        index_dir=settings.ccc_index_dir,
        source_path=seed_path,
        embeddings=LocalDeterministicEmbeddings(),
    )
    service = CompanionService(settings=settings, router=router, ccc_index=ccc_index)
    app = create_app(service_override=service)

    with TestClient(app) as client:
        index_res = client.get("/")
        assert index_res.status_code == 200
        assert "Cor ad Cor" in index_res.text
        assert "Bring Your Day to Mass" in index_res.text

        css_res = client.get("/static/styles.css")
        js_res = client.get("/static/app.js")
        assert css_res.status_code == 200
        assert js_res.status_code == 200

        liturgy_res = client.get("/api/v1/liturgy", params={"offline": True, "date": "2026-11-21"})
        assert liturgy_res.status_code == 200
        liturgy_payload = liturgy_res.json()
        assert len(liturgy_payload["liturgy"]["readings"]) == 3
        assert len(liturgy_payload["ccc_citations"]) == 3

        daily_demo = client.get(
            "/api/v1/daily",
            params={"offline": True, "demo": True, "date": "2026-11-21"},
        )
        assert daily_demo.status_code == 200
        daily_data = daily_demo.json()
        assert daily_data["llm"]["provider"] == "preview"
        assert "5 Minutes Before Mass" in daily_data["reflection"]
        assert "[CCC §" in daily_data["reflection"]

        checkin_demo = client.post(
            "/api/v1/checkin",
            json={
                "message": "I feel burned out and distant in prayer today",
                "offline": True,
                "demo": True,
                "date": "2026-11-21",
            },
        )
        assert checkin_demo.status_code == 200
        checkin_data = checkin_demo.json()
        assert checkin_data["llm"]["provider"] == "preview"
        assert "[CCC §" in checkin_data["reflection"]
