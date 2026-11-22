"""Run the Cor ad Cor Telegram Companion Bot using long polling."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.delivery.audio import VoiceNoteSynthesizer
from app.delivery.telegram_bot import TelegramCompanionBot
from app.services.companion import CompanionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cor_ad_cor.telegram")


async def run_polling(*, offline: bool = False) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token.strip():
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is missing in .env. Create a bot with @BotFather and add its token."
        )

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

    logger.info("Cor ad Cor Telegram Bot started (polling). Press Ctrl+C to stop.")
    offset: int | None = None
    while True:
        try:
            updates = await bot.get_updates(offset=offset, timeout=25)
            for update in updates:
                update_id = int(update["update_id"])
                offset = update_id + 1
                action = await bot.handle_update(update)
                if action is not None:
                    await bot.send_action(action)
                    logger.info("Replied to chat_id=%s (audio=%s)", action.chat_id, bool(action.audio_path))
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.error("Polling error: %s", exc)
            await asyncio.sleep(3)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Cor ad Cor Telegram Companion Bot")
    parser.add_argument("--offline", action="store_true", help="Use offline liturgical sample fixture")
    args = parser.parse_args()
    try:
        asyncio.run(run_polling(offline=args.offline))
    except KeyboardInterrupt:
        logger.info("Telegram bot stopped.")


if __name__ == "__main__":
    main()
