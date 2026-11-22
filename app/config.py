"""Application configuration loaded from environment variables and `.env`."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings for LLM routing, embeddings, and local data storage."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Up to 4 Groq keys (plus optional comma-separated GROQ_API_KEYS)
    groq_api_key_1: str = ""
    groq_api_key_2: str = ""
    groq_api_key_3: str = ""
    groq_api_key_4: str = ""
    groq_api_keys: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_cooldown_seconds: int = Field(default=60, ge=1)

    # Gemini fallback
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Embeddings
    embedding_provider: Literal["auto", "gemini", "local_hash"] = "auto"
    gemini_embedding_model: str = "models/text-embedding-004"

    # Storage paths
    data_dir: Path = BASE_DIR / "data"
    ccc_seed_path: Path = BASE_DIR / "data" / "ccc" / "ccc_seed.json"
    ccc_full_path: Path = BASE_DIR / "data" / "ccc" / "ccc_full.json"
    ccc_index_dir: Path = BASE_DIR / "data" / "index" / "ccc_faiss"
    readings_cache_dir: Path = BASE_DIR / "data" / "cache" / "readings"
    journal_db_path: Path = BASE_DIR / "data" / "journal" / "companion_memory.db"
    audio_cache_dir: Path = BASE_DIR / "data" / "cache" / "audio"

    # Phase 4: Voice-Note TTS & Telegram delivery
    tts_voice: str = "en-US-AndrewMultilingualNeural"
    tts_rate: str = "-6%"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_webhook_secret: str = ""

    def get_groq_keys(self) -> list[str]:
        """Return deduplicated, non-empty Groq API keys in priority order."""
        candidates = [
            self.groq_api_key_1,
            self.groq_api_key_2,
            self.groq_api_key_3,
            self.groq_api_key_4,
            *(k.strip() for k in self.groq_api_keys.split(",") if k.strip()),
        ]
        seen: set[str] = set()
        ordered: list[str] = []
        for key in candidates:
            cleaned = key.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                ordered.append(cleaned)
        return ordered

    def resolved_embedding_provider(self) -> Literal["gemini", "local_hash"]:
        """Resolve 'auto' embedding provider based on available API keys."""
        if self.embedding_provider == "auto":
            return "gemini" if self.gemini_api_key.strip() else "local_hash"
        return self.embedding_provider


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
