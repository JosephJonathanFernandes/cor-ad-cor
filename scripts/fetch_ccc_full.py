"""Fetch, normalize, validate, and FAISS-index the full Catechism of the Catholic Church (CCC §1–2865)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.rag.catechism import CatechismIndex, build_embeddings
from app.rag.ccc_loader import normalize_ccc_payload, save_normalized_ccc

DEFAULT_DIRECT_URLS = [
    "https://github.com/aseemsavio/catholicism-in-json/releases/download/v2.0.0/catechism.json",
]

DEFAULT_GITHUB_REPOS = [
    "aseemsavio/catholicism-in-json",
    "nossbigg/catechism-ccc-json",
]


def _discover_github_json_urls(client: httpx.Client, repo: str) -> list[str]:
    """Query GitHub API for JSON files in repo root, data folders, or latest release assets."""
    discovered: list[str] = []
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "CorAdCorCompanion/0.4"}

    # 1. Check latest release assets (e.g., aseemsavio/catholicism-in-json)
    try:
        rel = client.get(f"https://api.github.com/repos/{repo}/releases/latest", headers=headers)
        if rel.status_code == 200:
            for asset in rel.json().get("assets", []):
                name = str(asset.get("name", "")).lower()
                url = str(asset.get("browser_download_url", ""))
                if name.endswith(".json") and ("ccc" in name or "catechism" in name) and url:
                    discovered.append(url)
    except Exception:  # noqa: BLE001
        pass

    # 2. Check repository tree for any ccc/catechism .json file
    try:
        meta = client.get(f"https://api.github.com/repos/{repo}", headers=headers)
        if meta.status_code == 200:
            branch = meta.json().get("default_branch", "main")
            tree = client.get(
                f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1",
                headers=headers,
            )
            if tree.status_code == 200:
                for item in tree.json().get("tree", []):
                    path = str(item.get("path", ""))
                    lower = path.lower()
                    if lower.endswith(".json") and ("ccc" in lower or "catechism" in lower):
                        discovered.append(
                            f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
                        )
    except Exception:  # noqa: BLE001
        pass

    return discovered


def fetch_raw_ccc_json(custom_url: str = "", timeout: float = 120.0) -> tuple[str, object]:
    """Discover and download a full public Catechism JSON corpus."""
    last_error: Exception | None = None
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        candidate_urls: list[str] = []
        if custom_url.strip():
            candidate_urls.append(custom_url.strip())
        else:
            candidate_urls.extend(DEFAULT_DIRECT_URLS)
            for repo in DEFAULT_GITHUB_REPOS:
                for url in _discover_github_json_urls(client, repo):
                    if url not in candidate_urls:
                        candidate_urls.append(url)

        for url in candidate_urls:
            try:
                resp = client.get(url)
                resp.raise_for_status()
                payload = resp.json()
                # Quick sanity check that it looks like a real multi-hundred paragraph CCC file
                records, _ = normalize_ccc_payload(payload)
                if len(records) >= 1000:
                    return url, payload
                print(f"Skipping {url} (only {len(records)} paragraphs)")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                print(f"Skipping {url} ({type(exc).__name__}: {exc})")

    raise RuntimeError(f"Unable to download full CCC JSON from any source: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download or convert a full Catechism JSON file into data/ccc/ccc_full.json and rebuild FAISS."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Optional local CCC JSON file to normalize instead of downloading.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="",
        help="Optional custom raw JSON URL to download.",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="Only write data/ccc/ccc_full.json without rebuilding the FAISS index.",
    )
    args = parser.parse_args()

    settings = get_settings()

    if args.input is not None:
        print(f"Reading local CCC JSON from: {args.input}")
        raw_payload = json.loads(args.input.read_text(encoding="utf-8"))
    else:
        source_url, raw_payload = fetch_raw_ccc_json(args.url)
        print(f"Downloaded full CCC JSON from: {source_url}")

    records, report = normalize_ccc_payload(raw_payload, source_type="official_text")
    save_normalized_ccc(records, settings.ccc_full_path)

    print(f"Saved normalized Catechism JSON to: {settings.ccc_full_path}")
    print(
        f"Coverage: {report.total_paragraphs} paragraphs "
        f"(CCC §{report.min_paragraph}–§{report.max_paragraph}, "
        f"missing: {len(report.missing_in_1_to_2865)}, duplicates merged: {report.duplicates_merged})"
    )

    if args.no_index:
        return

    provider = settings.resolved_embedding_provider()
    embeddings = build_embeddings(
        provider,
        gemini_api_key=settings.gemini_api_key,
        gemini_embedding_model=settings.gemini_embedding_model,
    )
    print(f"Rebuilding FAISS index ({provider} embeddings) over all {report.total_paragraphs} paragraphs...")
    index = CatechismIndex.build_from_json(settings.ccc_full_path, embeddings)
    index.save(settings.ccc_index_dir)
    print(f"Saved full CCC FAISS index to: {settings.ccc_index_dir}")

    for query in (
        "dryness and distraction in prayer",
        "real presence of Christ in the Eucharist",
        "interior repentance and confession of sins",
    ):
        hits = index.search(query, k=2)
        summary = ", ".join(f"[{h.citation}] {h.section}" for h in hits)
        print(f"  Query '{query}' -> {summary}")


if __name__ == "__main__":
    main()
