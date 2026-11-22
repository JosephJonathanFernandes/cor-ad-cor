"""Phase 4 tests for spoken audio voice-notes and Telegram companion bot delivery."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.delivery.audio import (
    VoiceNoteSynthesizer,
    estimate_duration_seconds,
    prepare_spoken_script,
)
from app.delivery.telegram_bot import TelegramCompanionBot, split_telegram_text
from app.llm.router import GroqGeminiRouter
from app.main import create_app
from app.rag.catechism import CatechismIndex, LocalDeterministicEmbeddings
from app.services.companion import CompanionService


def test_spoken_script_cleaner_and_telegram_chunking() -> None:
    md = "### 1. 5 Minutes Before Mass\nIn **[Gospel]**, Christ draws near ([CCC §2729]).\n> Pray quietly."
    spoken = prepare_spoken_script(md)
    assert "###" not in spoken
    assert "**" not in spoken
    assert "the Gospel" in spoken
    assert "Catechism paragraph 2729" in spoken
    assert estimate_duration_seconds(spoken) >= 1

    long_text = ("Paragraph one. " * 200) + "\n\n" + ("Paragraph two. " * 200)
    chunks = split_telegram_text(long_text, max_len=1000)
    assert len(chunks) >= 2
    assert all(len(c) <= 1000 for c in chunks)


def test_phase4_audio_endpoints_and_telegram_bot(tmp_path: Path) -> None:
    seed_path = Path(__file__).resolve().parent.parent / "data" / "ccc" / "ccc_seed.json"
    settings = Settings(
        ccc_seed_path=seed_path,
        ccc_index_dir=tmp_path / "idx",
        readings_cache_dir=tmp_path / "cache",
        journal_db_path=tmp_path / "journal" / "memory.db",
        audio_cache_dir=tmp_path / "audio",
        telegram_webhook_secret="secret-123",
    )
    router = GroqGeminiRouter(groq_keys=[], gemini_api_key="")
    ccc_index = CatechismIndex.load_or_build(
        index_dir=settings.ccc_index_dir,
        source_path=seed_path,
        embeddings=LocalDeterministicEmbeddings(),
    )
    service = CompanionService(settings=settings, router=router, ccc_index=ccc_index)

    synth_calls = 0

    async def fake_synth(spoken: str, voice: str, rate: str, out_path: Path) -> Path:
        nonlocal synth_calls
        synth_calls += 1
        out_path.write_bytes(b"ID3FAKE_MP3_BYTES")
        return out_path

    synthesizer = VoiceNoteSynthesizer(
        cache_dir=settings.audio_cache_dir,
        synthesizer=fake_synth,
    )
    app = create_app(service_override=service, synthesizer_override=synthesizer)

    with TestClient(app) as client:
        # 1. Spoken script endpoint
        script_res = client.post(
            "/api/v1/audio/script",
            json={"text": "### Reflection\nSee [Gospel] and [CCC §2729]."},
        )
        assert script_res.status_code == 200
        assert "Catechism paragraph 2729" in script_res.json()["spoken_script"]

        # 2. MP3 synthesis & cache reuse
        mp3_res_1 = client.post(
            "/api/v1/audio/voice-note",
            json={"text": "### Reflection\nSee [Gospel] and [CCC §2729]."},
        )
        assert mp3_res_1.status_code == 200
        assert mp3_res_1.headers["content-type"].startswith("audio/mpeg")
        assert mp3_res_1.content == b"ID3FAKE_MP3_BYTES"
        assert synth_calls == 1

        mp3_res_2 = client.post(
            "/api/v1/audio/voice-note",
            json={"text": "### Reflection\nSee [Gospel] and [CCC §2729]."},
        )
        assert mp3_res_2.status_code == 200
        assert synth_calls == 1  # Served from cache

        # 3. Telegram webhook secret enforcement
        bad_secret = client.post(
            "/api/v1/telegram/webhook",
            params={"send": False},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            json={"message": {"chat": {"id": 42}, "text": "/start"}},
        )
        assert bad_secret.status_code == 403

        good_webhook = client.post(
            "/api/v1/telegram/webhook",
            params={"send": False},
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret-123"},
            json={"message": {"chat": {"id": 42}, "text": "/ccc dryness in prayer"}},
        )
        assert good_webhook.status_code == 200
        assert "CCC §2729" in good_webhook.json()["reply_preview"]

    # 4. Direct Telegram bot command routing (including /voice, /examen, /confession, /wipe, crisis)
    bot = TelegramCompanionBot(
        bot_token="",
        service=service,
        synthesizer=synthesizer,
        offline=True,
    )

    async def exercise_bot() -> None:
        start = await bot.handle_update({"message": {"chat": {"id": 1}, "text": "/start"}})
        assert start is not None and "/today" in start.text

        today = await bot.handle_update({"message": {"chat": {"id": 1}, "text": "/today"}})
        assert today is not None and "5 Minutes Before Mass" in today.text

        voice = await bot.handle_update({"message": {"chat": {"id": 1}, "text": "/voice"}})
        assert voice is not None and voice.audio_path is not None and voice.audio_path.exists()

        examen = await bot.handle_update(
            {
                "message": {
                    "chat": {"id": 1},
                    "text": "/examen Morning coffee | Patience at work | Tired and impatient",
                }
            }
        )
        assert examen is not None and "Gathering the Day in Gratitude" in examen.text

        conf = await bot.handle_update({"message": {"chat": {"id": 1}, "text": "/confession impatience"}})
        assert conf is not None and "Act of Contrition" in conf.text

        crisis = await bot.handle_update(
            {"message": {"chat": {"id": 1}, "text": "I want to end my life tonight"}}
        )
        assert crisis is not None and "988" in crisis.text

        wipe = await bot.handle_update({"message": {"chat": {"id": 1}, "text": "/wipe"}})
        assert wipe is not None and "Clean slate" in wipe.text

    asyncio.run(exercise_bot())
