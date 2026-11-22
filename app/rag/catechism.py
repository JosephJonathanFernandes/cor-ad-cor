"""FAISS vector store over Catechism of the Catholic Church paragraphs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
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


def load_ccc_documents(source_path: Path) -> list[Document]:
    """Load CCC paragraphs from JSON into LangChain Documents with paragraph metadata."""
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    docs: list[Document] = []
    for entry in raw:
        paragraph = int(entry["paragraph"])
        section = str(entry.get("section", "")).strip()
        text = str(entry["text"]).strip()
        source_type = str(entry.get("source_type", "official_text"))
        if not text:
            continue
        page_content = f"CCC §{paragraph} — {section}\n{text}" if section else f"CCC §{paragraph}\n{text}"
        docs.append(
            Document(
                page_content=page_content,
                metadata={
                    "paragraph": paragraph,
                    "section": section,
                    "raw_text": text,
                    "source_type": source_type,
                },
            )
        )
    return docs


_DIRECT_PARA_RE = re.compile(r"(?:ccc\s*§?\s*|§\s*|^)(\d{1,4})(?:\s*$|\b)", re.I)


def _doc_to_hit(doc: Document) -> CatechismHit:
    meta = doc.metadata
    return CatechismHit(
        paragraph=int(meta["paragraph"]),
        section=str(meta.get("section", "")),
        text=str(meta.get("raw_text", doc.page_content)),
        source_type=str(meta.get("source_type", "seed_summary")),
    )


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
    """Manages building, saving, loading, exact lookup, and hybrid search over the CCC FAISS index."""

    def __init__(self, vector_store: FAISS) -> None:
        self.vector_store = vector_store
        self.paragraph_map: dict[int, CatechismHit] = {}
        docstore_dict = getattr(vector_store.docstore, "_dict", None)
        if isinstance(docstore_dict, dict):
            for doc in docstore_dict.values():
                if isinstance(doc, Document) and "paragraph" in doc.metadata:
                    hit = _doc_to_hit(doc)
                    self.paragraph_map[hit.paragraph] = hit

    def get_by_paragraph(self, paragraph: int) -> CatechismHit | None:
        """O(1) exact lookup of a Catechism paragraph by number (1–2865)."""
        return self.paragraph_map.get(paragraph)

    @classmethod
    def build_from_json(cls, source_path: Path, embeddings: Embeddings) -> CatechismIndex:
        """Build a fresh FAISS index from a CCC JSON file."""
        docs = load_ccc_documents(source_path)
        if not docs:
            raise ValueError(f"No CCC paragraphs found in {source_path}")
        store = FAISS.from_documents(docs, embeddings)
        return cls(store)

    def save(self, index_dir: Path) -> None:
        """Persist FAISS index and metadata sidecar to disk."""
        index_dir.mkdir(parents=True, exist_ok=True)
        self.vector_store.save_local(str(index_dir))

    @classmethod
    def load_or_build(
        cls,
        *,
        index_dir: Path,
        source_path: Path,
        embeddings: Embeddings,
    ) -> CatechismIndex:
        """Load an existing FAISS index if present, otherwise build from JSON and save it."""
        faiss_file = index_dir / "index.faiss"
        pkl_file = index_dir / "index.pkl"
        if faiss_file.exists() and pkl_file.exists():
            store = FAISS.load_local(
                str(index_dir),
                embeddings,
                allow_dangerous_deserialization=True,
            )
            return cls(store)

        instance = cls.build_from_json(source_path, embeddings)
        instance.save(index_dir)
        return instance

    def search(self, query: str, k: int = 3) -> list[CatechismHit]:
        """Retrieve top-k CCC paragraphs using direct § lookup + hybrid FAISS/lexical fusion."""
        cleaned = query.strip()
        if not cleaned:
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
        pool_size = min(max(k * 4, 12), max(len(self.paragraph_map), k))
        vector_docs = self.vector_store.similarity_search(cleaned, k=pool_size)
        query_tokens = {tok for tok in _TOKEN_RE.findall(cleaned.lower()) if len(tok) > 2}

        scored: list[tuple[float, CatechismHit]] = []
        for rank, doc in enumerate(vector_docs, start=1):
            hit = _doc_to_hit(doc)
            if hit.paragraph in seen:
                continue
            # Reciprocal rank score from FAISS + normalized lexical overlap bonus
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
