"""Tests for Citation Verifier, exact CCC § lookup, Saint query cleaner, and SSE streaming."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.data_sources.liturgy import clean_saint_query
from app.llm.router import GroqGeminiRouter
from app.main import create_app
from app.rag.catechism import CatechismIndex, LocalDeterministicEmbeddings
from app.rag.verifier import verify_and_hydrate_citations
from app.services.companion import CompanionService


def test_clean_saint_query() -> None:
    assert clean_saint_query("Memorial of St. Agnes, virgin and martyr") == "Saint Agnes"
    assert clean_saint_query("Optional Memorial of St. Thomas Aquinas, priest and doctor") == "Saint Thomas Aquinas"
    assert clean_saint_query("Feast of the Presentation of the Lord") == "the Presentation of the Lord"


def test_exact_ccc_lookup_and_citation_verifier_hydration(tmp_path: Path) -> None:
    seed_path = Path(__file__).resolve().parent.parent / "data" / "ccc" / "ccc_seed.json"
    ccc_index = CatechismIndex.load_or_build(
        index_dir=tmp_path / "idx",
        source_path=seed_path,
        embeddings=LocalDeterministicEmbeddings(),
    )

    # Exact lookup by paragraph number
    direct = ccc_index.search("1374", k=2)
    assert direct[0].paragraph == 1374

    direct_prefixed = ccc_index.search("CCC §2729", k=2)
    assert direct_prefixed[0].paragraph == 2729

    # Citation verifier: 2729 is in retrieved_hits, 1374 should be auto-hydrated, 9999 flagged unverified
    initial_hits = [ccc_index.get_by_paragraph(2729)]
    reflection = "Sit quietly with [CCC §2729], receive [CCC §1374], and avoid [CCC §9999]."
    hydrated_hits, verification = verify_and_hydrate_citations(
        reflection,
        [h for h in initial_hits if h is not None],
        ccc_index,
    )

    assert verification.cited_paragraphs == [2729, 1374, 9999]
    assert verification.verified_paragraphs == [2729, 1374]
    assert verification.hydrated_paragraphs == [1374]
    assert verification.unverified_paragraphs == [9999]
    assert verification.all_valid is False
    assert any(h.paragraph == 1374 for h in hydrated_hits)


def test_sse_daily_stream_endpoint(tmp_path: Path) -> None:
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
        with client.stream(
            "GET",
            "/api/v1/daily/stream",
            params={"offline": True, "demo": True, "date": "2026-11-21"},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            body = "".join(resp.iter_text())

    assert "event: context" in body
    assert "event: chunk" in body
    assert "event: done" in body
    assert "citation_verification" in body
