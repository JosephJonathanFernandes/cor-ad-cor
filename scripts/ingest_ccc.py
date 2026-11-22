"""Build or rebuild the Catechism (CCC) FAISS vector index."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.rag.catechism import CatechismIndex, build_embeddings


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the CCC FAISS index.")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Optional path to a CCC JSON file (defaults to ccc_full.json if present, else ccc_seed.json).",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="dryness in prayer and mercy",
        help="Sanity-check query to run after indexing.",
    )
    args = parser.parse_args()

    settings = get_settings()
    source_path = args.source or (
        settings.ccc_full_path if settings.ccc_full_path.exists() else settings.ccc_seed_path
    )
    provider = settings.resolved_embedding_provider()
    embeddings = build_embeddings(
        provider,
        gemini_api_key=settings.gemini_api_key,
        gemini_embedding_model=settings.gemini_embedding_model,
    )

    print(f"Building FAISS index from: {source_path}")
    print(f"Embedding provider: {provider}")
    index = CatechismIndex.build_from_json(source_path, embeddings)
    index.save(settings.ccc_index_dir)
    print(f"Saved CCC FAISS index to: {settings.ccc_index_dir}")

    hits = index.search(args.query, k=3)
    print(f"\nSanity query: {args.query!r}")
    for hit in hits:
        print(f"- [{hit.citation}] {hit.section}: {hit.text[:100]}...")


if __name__ == "__main__":
    main()
