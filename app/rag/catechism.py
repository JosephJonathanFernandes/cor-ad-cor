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


class CatechismIndex:
    """Manages building, saving, loading, and querying the CCC FAISS index."""

    def __init__(self, vector_store: FAISS) -> None:
        self.vector_store = vector_store

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
        """Retrieve the top-k relevant CCC paragraphs for a query."""
        if not query.strip():
            return []
        docs = self.vector_store.similarity_search(query, k=k)
        hits: list[CatechismHit] = []
        for doc in docs:
            meta = doc.metadata
            hits.append(
                CatechismHit(
                    paragraph=int(meta["paragraph"]),
                    section=str(meta.get("section", "")),
                    text=str(meta.get("raw_text", doc.page_content)),
                    source_type=str(meta.get("source_type", "seed_summary")),
                )
            )
        return hits
