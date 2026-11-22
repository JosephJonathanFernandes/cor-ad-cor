"""Tests for Citation Verifier, exact CCC § lookup, Saint query cleaner, and SSE streaming."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.data_sources.liturgy import clean_saint_query, parse_vatican_news_html
from app.llm.router import GroqGeminiRouter
from app.main import create_app
from app.rag.catechism import CatechismIndex, LocalDeterministicEmbeddings
from app.rag.verifier import verify_and_hydrate_citations
from app.services.companion import CompanionService


def test_clean_saint_query() -> None:
    assert clean_saint_query("Memorial of St. Agnes, virgin and martyr") == "Saint Agnes"
    assert clean_saint_query("Optional Memorial of St. Thomas Aquinas, priest and doctor") == "Saint Thomas Aquinas"
    assert clean_saint_query("Feast of the Presentation of the Lord") == "the Presentation of the Lord"


def test_parse_vatican_news_html() -> None:
    html = """
    <html><body>
      <section class="section--evidence">
        <h2>Reading of the day</h2>
        <div class="section__content">
          <p>A reading from the Book of Ezekiel</p>
          <p>34:11-12, 15-17</p>
          <p>Thus says the Lord GOD: I myself will look after and tend my sheep.</p>
        </div>
      </section>
      <section class="section--evidence">
        <h2>Gospel of the day</h2>
        <div class="section__content">
          <p>From the Gospel according to Matthew</p>
          <p>25:31-46</p>
          <p>Jesus said to his disciples: When the Son of Man comes in his glory.</p>
        </div>
      </section>
      <section class="section--evidence">
        <h2>The words of the Popes</h2>
        <div class="section__content">
          <p>The criterion of judgment is concrete charity to our neighbour.</p>
        </div>
      </section>
    </body></html>
    """
    readings, papal = parse_vatican_news_html(html)
    assert len(readings) == 2
    assert readings[0].label == "First Reading"
    assert "34:11-12" in readings[0].citation
    assert readings[1].label == "Gospel"
    assert "Matthew" in readings[1].citation
    assert "concrete charity" in papal


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


def test_exact_ccc_endpoint_multiturn_checkin_and_rhythm_stats(tmp_path: Path) -> None:
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
        ok = client.get("/api/v1/ccc/2729")
        assert ok.status_code == 200
        assert ok.json()["paragraph"] == 2729

        missing = client.get("/api/v1/ccc/9999")
        assert missing.status_code == 404

        followup = client.post(
            "/api/v1/checkin",
            json={
                "message": "Honestly I think I am afraid of slowing down.",
                "date": "2026-11-22",
                "offline": True,
                "demo": True,
                "remember": True,
                "history": [
                    {"role": "user", "content": "I feel burned out at work."},
                    {"role": "assistant", "content": "What feels heaviest right now?"},
                ],
            },
        )
        assert followup.status_code == 200

        mem = client.get("/api/v1/memory")
        assert mem.status_code == 200
        assert mem.json()["distinct_days"] == 1
        assert mem.json()["last_entry_date"] == "2026-11-22"

        prayers = client.get("/api/v1/prayers", params={"moment": "trust"})
        assert prayers.status_code == 200
        titles = [p["title"] for p in prayers.json()["prayers"]]
        assert any("Suscipe" in t for t in titles)
