"""Send a scheduled morning Mass briefing (plus optional MP3 voice-note) or evening Examen prompt to Telegram."""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.delivery.audio import VoiceNoteSynthesizer
from app.delivery.telegram_bot import BotAction, TelegramCompanionBot
from app.services.companion import CompanionService


async def send_digest(
    *,
    mode: str,
    include_voice: bool,
    target_date: dt.date | None,
    offline: bool,
    dry_run: bool,
) -> None:
    settings = get_settings()
    service = CompanionService.from_settings(settings)
    synthesizer = VoiceNoteSynthesizer(
        cache_dir=settings.audio_cache_dir,
        voice=settings.tts_voice,
        rate=settings.tts_rate,
    )
    bot = TelegramCompanionBot(
        bot_token=settings.telegram_bot_token,
        service=service,
        synthesizer=synthesizer,
        offline=offline,
    )
    chat_id = settings.telegram_chat_id.strip() or "dry_run_chat"
    use_demo = not (settings.get_groq_keys() or settings.gemini_api_key.strip())

    if mode == "evening":
        day = service.get_day(target_date, offline=offline)
        action = BotAction(
            chat_id=chat_id,
            text=(
                f"Good evening ({day.date} — {day.celebration_title}).\n\n"
                "Take 3 quiet minutes for tonight's Ignatian Examen. Reply with:\n"
                "/examen gratitude | consolation | desolation\n\n"
                "Where did you notice grace today, and where did you feel stretched or pull away?"
            ),
        )
    else:
        reply = service.daily_briefing(target_date=target_date, offline=offline, demo=use_demo)
        header = f"Good morning — {reply.liturgy.date} ({reply.liturgy.celebration_title})\n\n"
        audio_path = None
        if include_voice:
            audio_path, _ = await synthesizer.synthesize_mp3(reply.reflection)
        action = BotAction(
            chat_id=chat_id,
            text=header + reply.reflection,
            audio_path=audio_path,
            audio_title=f"Cor ad Cor — {reply.liturgy.date}",
        )

    if dry_run:
        print("=== DRY RUN DIGEST ===")
        print(f"Chat ID: {action.chat_id} | Audio: {action.audio_path}")
        print(action.text)
        return

    if not settings.telegram_bot_token.strip() or not settings.telegram_chat_id.strip():
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env (or pass --dry-run).")

    await bot.send_action(action)
    print(f"Sent {mode} digest to Telegram chat {chat_id}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Cor ad Cor daily Telegram digest")
    parser.add_argument("--mode", choices=["morning", "evening"], default="morning")
    parser.add_argument("--voice", action="store_true", help="Attach a spoken MP3 voice-note (morning mode)")
    parser.add_argument("--date", type=dt.date.fromisoformat, default=None, help="YYYY-MM-DD")
    parser.add_argument("--offline", action="store_true", help="Use offline liturgical sample")
    parser.add_argument("--dry-run", action="store_true", help="Print digest locally without calling Telegram")
    args = parser.parse_args()
    asyncio.run(
        send_digest(
            mode=args.mode,
            include_voice=args.voice,
            target_date=args.date,
            offline=args.offline,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
