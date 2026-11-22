"""Phase 3 tests for Evening Ignatian Examen, Season-Aware SQLite Memory, and Confession Prep."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.router import GroqGeminiRouter
from app.main import create_app
from app.memory.journal import JournalStore, extract_themes
from app.rag.catechism import CatechismIndex, LocalDeterministicEmbeddings
from app.services.companion import CompanionService


def test_theme_extraction_and_journal_store(tmp_path: Path) -> None:
    themes = extract_themes("I feel burned out at work, impatient, and dry in prayer lately.")
    assert "work burnout & exhaustion" in themes
    assert "impatience, anger & resentment" in themes
    assert "prayer dryness & distraction" in themes

    store = JournalStore(tmp_path / "journal.db")
    e1 = store.add_entry(
        liturgical_date="2026-11-20",
        season="Ordinary Time",
        entry_type="checkin",
        user_note="Exhausted and burned out at work today.",
        ccc_citations=["CCC §2729"],
    )
    assert e1.id == 1

    e2 = store.add_entry(
        liturgical_date="2026-11-21",
        season="Ordinary Time",
        entry_type="examen",
        user_note="Grateful for quiet morning prayer",
        consolation="Peaceful walk after lunch",
        desolation="Snapped in anger and frustration during evening traffic",
        ccc_citations=["CCC §1431"],
    )
    assert e2.id == 2

    summary = store.season_summary(season="Ordinary Time")
    assert summary.total_entries == 2
    prompt_ctx = summary.prompt_context()
    assert "Saved entries in current memory" in prompt_ctx
    assert "work burnout & exhaustion" in prompt_ctx

    deleted = store.clear_all()
    assert deleted == 2
    assert store.season_summary().total_entries == 0


def test_phase3_examen_memory_and_confession_endpoints(tmp_path: Path) -> None:
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
    app = create_app(service_override=service)

    with TestClient(app) as client:
        # 1. Opt-in Check-In saved to memory
        checkin_res = client.post(
            "/api/v1/checkin",
            json={
                "message": "I feel burned out at work and dry in prayer.",
                "date": "2026-11-21",
                "offline": True,
                "demo": True,
                "remember": True,
            },
        )
        assert checkin_res.status_code == 200
        assert checkin_res.json()["saved_entry_id"] == 1

        # 2. Evening Ignatian Examen saved to memory
        examen_res = client.post(
            "/api/v1/examen",
            json={
                "gratitude": "A kind word from a friend this afternoon",
                "consolation": "Patience with my family at dinner",
                "desolation": "Feeling resentful and impatient with deadlines",
                "date": "2026-11-21",
                "offline": True,
                "demo": True,
                "remember": True,
            },
        )
        assert examen_res.status_code == 200
        examen_data = examen_res.json()
        assert examen_data["saved_entry_id"] == 2
        assert "Gathering the Day in Gratitude" in examen_data["reflection"]

        # 3. Inspect Season Memory Summary
        mem_res = client.get("/api/v1/memory")
        assert mem_res.status_code == 200
        mem_data = mem_res.json()
        assert mem_data["total_entries"] == 2
        theme_names = [t["theme"] for t in mem_data["top_themes"]]
        assert "work burnout & exhaustion" in theme_names

        # 4. Generate Confession Prep grounded in season memory + CCC
        conf_res = client.post(
            "/api/v1/confession-prep",
            json={
                "focus_area": "Help me distinguish work exhaustion from impatience before Confession.",
                "date": "2026-11-21",
                "offline": True,
                "demo": True,
            },
        )
        assert conf_res.status_code == 200
        conf_data = conf_res.json()
        assert "Approaching Mercy Without Fear" in conf_data["reflection"]
        assert "Act of Contrition" in conf_data["reflection"]

        # 5. Clean Slate wipe after Confession
        del_res = client.delete("/api/v1/memory")
        assert del_res.status_code == 200
        assert del_res.json()["deleted_entries"] == 2

        mem_after = client.get("/api/v1/memory")
        assert mem_after.json()["total_entries"] == 0
