"""Direct FAISS vector store (with safe JSON metadata sidecar) over Catechism paragraphs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import faiss
import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class LocalDeterministicEmbeddings(Embeddings):
    """Lightweight, zero-download hashed n-gram embeddings for offline dev and tests."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        vec = np.zeros(self.dimension, dtype=np.float32)
        words = _TOKEN_RE.findall(text.lower())
        if not words:
            return vec.tolist()

        # Combine unigrams and bigrams so short thematic queries match accurately.
        features = list(words)
        features.extend(f"{words[i]}_{words[i + 1]}" for i in range(len(words) - 1))

        for feat in features:
            digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vec[idx] += sign

        norm = float(np.linalg.norm(vec))
        if norm > 0.0:
            vec /= norm
        return vec.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@dataclass(frozen=True)
class CatechismHit:
    """A retrieved Catechism entry with an explicit paragraph citation."""

    paragraph: int
    section: str
    text: str
    source_type: str = "seed_summary"

    @property
    def citation(self) -> str:
        return f"CCC §{self.paragraph}"

    def to_dict(self) -> dict[str, object]:
        return {
            "paragraph": self.paragraph,
            "section": self.section,
            "text": self.text,
            "source_type": self.source_type,
        }


def build_embeddings(
    provider: Literal["gemini", "local_hash"],
    *,
    gemini_api_key: str = "",
    gemini_embedding_model: str = "models/text-embedding-004",
) -> Embeddings:
    """Instantiate the configured LangChain Embeddings implementation."""
    if provider == "gemini":
        if not gemini_api_key.strip():
            raise ValueError("GEMINI_API_KEY is required when EMBEDDING_PROVIDER=gemini.")
        return GoogleGenerativeAIEmbeddings(
            google_api_key=gemini_api_key,
            model=gemini_embedding_model,
        )
    return LocalDeterministicEmbeddings()


def load_ccc_hits(source_path: Path) -> list[CatechismHit]:
    """Load CCC paragraphs from JSON into typed CatechismHit objects."""
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    hits: list[CatechismHit] = []
    for entry in raw:
        paragraph = int(entry["paragraph"])
        section = str(entry.get("section", "")).strip()
        text = str(entry["text"]).strip()
        source_type = str(entry.get("source_type", "official_text"))
        if not text:
            continue
        hits.append(
            CatechismHit(
                paragraph=paragraph,
                section=section,
                text=text,
                source_type=source_type,
            )
        )
    return hits


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return (matrix / norms).astype(np.float32)


def _extract_direct_paragraph_numbers(query: str) -> list[int]:
    """Detect explicit CCC paragraph numbers in a search query (e.g. '1374', 'CCC §2729')."""
    stripped = query.strip()
    if stripped.isdigit():
        num = int(stripped)
        return [num] if 1 <= num <= 2865 else []

    found: list[int] = []
    for match in re.finditer(r"(?:ccc\s*§?\s*|§\s*)(\d{1,4})\b", stripped, re.I):
        num = int(match.group(1))
        if 1 <= num <= 2865 and num not in found:
            found.append(num)
    return found


class CatechismIndex:
    """Direct FAISS IndexFlatIP store with safe JSON metadata sidecar (no pickle)."""

    def __init__(
        self,
        *,
        index: faiss.Index,
        hits: list[CatechismHit],
        embeddings: Embeddings,
    ) -> None:
        self.index = index
        self.hits = hits
        self.embeddings = embeddings
        self.paragraph_map: dict[int, CatechismHit] = {h.paragraph: h for h in hits}

    def get_by_paragraph(self, paragraph: int) -> CatechismHit | None:
        """O(1) exact lookup of a Catechism paragraph by number (1–2865)."""
        return self.paragraph_map.get(paragraph)

    @classmethod
    def build_from_json(cls, source_path: Path, embeddings: Embeddings) -> CatechismIndex:
        """Build a fresh cosine-similarity FAISS index from a CCC JSON file."""
        hits = load_ccc_hits(source_path)
        if not hits:
            raise ValueError(f"No CCC paragraphs found in {source_path}")

        texts = [
            f"CCC §{h.paragraph} — {h.section}\n{h.text}" if h.section else f"CCC §{h.paragraph}\n{h.text}"
            for h in hits
        ]
        vectors = np.asarray(embeddings.embed_documents(texts), dtype=np.float32)
        normalized = _l2_normalize(vectors)
        index = faiss.IndexFlatIP(normalized.shape[1])
        index.add(normalized)
        return cls(index=index, hits=hits, embeddings=embeddings)

    def save(self, index_dir: Path) -> None:
        """Persist FAISS index and safe JSON metadata sidecar to disk."""
        index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(index_dir / "index.faiss"))
        meta_payload = [h.to_dict() for h in self.hits]
        (index_dir / "metadata.json").write_text(
            json.dumps(meta_payload, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load_or_build(
        cls,
        *,
        index_dir: Path,
        source_path: Path,
        embeddings: Embeddings,
    ) -> CatechismIndex:
        """Load an existing FAISS + JSON sidecar index if present, otherwise build and save it."""
        faiss_file = index_dir / "index.faiss"
        meta_file = index_dir / "metadata.json"
        if faiss_file.exists() and meta_file.exists():
            index = faiss.read_index(str(faiss_file))
            raw_meta = json.loads(meta_file.read_text(encoding="utf-8"))
            hits = [
                CatechismHit(
                    paragraph=int(item["paragraph"]),
                    section=str(item.get("section", "")),
                    text=str(item["text"]),
                    source_type=str(item.get("source_type", "official_text")),
                )
                for item in raw_meta
            ]
            return cls(index=index, hits=hits, embeddings=embeddings)

        instance = cls.build_from_json(source_path, embeddings)
        instance.save(index_dir)
        return instance

    def search(self, query: str, k: int = 3) -> list[CatechismHit]:
        """Retrieve top-k CCC paragraphs using direct § lookup + hybrid FAISS/lexical fusion."""
        cleaned = query.strip()
        if not cleaned or not self.hits:
            return []

        results: list[CatechismHit] = []
        seen: set[int] = set()

        # 1. Exact paragraph number hits first (e.g., "1374", "CCC §2729")
        for num in _extract_direct_paragraph_numbers(cleaned):
            exact = self.get_by_paragraph(num)
            if exact is not None and exact.paragraph not in seen:
                results.append(exact)
                seen.add(exact.paragraph)
                if len(results) >= k:
                    return results

        # 2. Vector FAISS candidate pool + lexical overlap Reciprocal Rank Fusion (RRF)
        pool_size = min(max(k * 4, 12), len(self.hits))
        q_vec = np.asarray([self.embeddings.embed_query(cleaned)], dtype=np.float32)
        q_norm = _l2_normalize(q_vec)
        _, indices = self.index.search(q_norm, pool_size)

        query_tokens = {tok for tok in _TOKEN_RE.findall(cleaned.lower()) if len(tok) > 2}
        scored: list[tuple[float, CatechismHit]] = []
        for rank, idx in enumerate(indices[0], start=1):
            if idx < 0 or idx >= len(self.hits):
                continue
            hit = self.hits[idx]
            if hit.paragraph in seen:
                continue
            rrf_score = 1.0 / (20.0 + rank)
            if query_tokens:
                doc_tokens = set(_TOKEN_RE.findall(f"{hit.section} {hit.text}".lower()))
                overlap = len(query_tokens & doc_tokens) / len(query_tokens)
                rrf_score += 0.04 * overlap
            scored.append((rrf_score, hit))

        scored.sort(key=lambda item: item[0], reverse=True)
        for _, hit in scored:
            if hit.paragraph not in seen:
                results.append(hit)
                seen.add(hit.paragraph)
                if len(results) >= k:
                    break
        return results
