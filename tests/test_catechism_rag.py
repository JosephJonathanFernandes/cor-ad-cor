"""Unit tests for Catechism FAISS indexing and citation retrieval."""

from __future__ import annotations

from pathlib import Path

from app.rag.catechism import CatechismIndex, LocalDeterministicEmbeddings


def test_build_save_reload_and_search_ccc_seed(tmp_path: Path) -> None:
    seed_path = Path(__file__).resolve().parent.parent / "data" / "ccc" / "ccc_seed.json"
    index_dir = tmp_path / "ccc_faiss"
    embeddings = LocalDeterministicEmbeddings()

    built = CatechismIndex.load_or_build(
        index_dir=index_dir,
        source_path=seed_path,
        embeddings=embeddings,
    )
    assert (index_dir / "index.faiss").exists()
    assert (index_dir / "metadata.json").exists()

    reloaded = CatechismIndex.load_or_build(
        index_dir=index_dir,
        source_path=seed_path,
        embeddings=embeddings,
    )
    hits = reloaded.search("dryness and distraction in prayer", k=3)
    assert len(hits) == 3
    assert any(hit.paragraph == 2729 for hit in hits)
    assert all(hit.citation.startswith("CCC §") for hit in hits)
