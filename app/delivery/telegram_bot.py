"""Telegram Bot adapter for Cor ad Cor (supports long-polling, webhooks, and daily digests)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.data_sources.hours import get_prayer_for_hour
from app.data_sources.prayers import list_prayers
from app.data_sources.rosary import get_rosary_for_date
from app.delivery.audio import VoiceNoteSynthesizer
from app.services.companion import CompanionService

logger = logging.getLogger(__name__)

TELEGRAM_MAX_MESSAGE_LEN = 4000

WELCOME_MESSAGE = (
    "Peace be with you. Welcome to Cor ad Cor — your Catholic daily liturgical & spiritual companion.\n\n"
    "Commands:\n"
    "• /today — 5 Minutes Before Mass (today's readings, hidden thread, Saint & CCC)\n"
    "• /voice — Calm spoken MP3 voice-note of today's reflection\n"
    "• /examen gratitude | consolation | desolation — 3-Minute Evening Ignatian Examen\n"
    "• /confession [optional focus] — Gentle Examination of Conscience & Confession prep\n"
    "• /rosary — Today's 5 Rosary Mysteries with Fruits & CCC anchors\n"
    "• /angelus — The Angelus (or Regina Caeli in Easter) & Gospel Canticle for this hour\n"
    "• /prayer [morning|evening|trust|confession|eucharist] — Classic Catholic prayers\n"
    "• /ccc <topic> — Search the Catechism of the Catholic Church\n"
    "• /wipe — Clear your saved local season memory (Clean Slate)\n\n"
    "Or simply send any honest sentence about what you're carrying today to bring it alongside today's Mass readings.\n\n"
    "(Pastoral boundary: Cor ad Cor is a prayerful companion, not a substitute for therapy or Confession with a priest.)"
)


def split_telegram_text(text: str, max_len: int = TELEGRAM_MAX_MESSAGE_LEN) -> list[str]:
    """Split long reflections cleanly on paragraph boundaries for Telegram's 4096-char limit."""
    cleaned = text.strip()
    if len(cleaned) <= max_len:
        return [cleaned] if cleaned else []

    chunks: list[str] = []
    current = ""
    for para in cleaned.split("\n\n"):
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(para) <= max_len:
                current = para
            else:
                # Hard-wrap oversized single paragraphs
                for idx in range(0, len(para), max_len):
                    chunks.append(para[idx : idx + max_len])
                current = ""
    if current:
        chunks.append(current)
    return chunks


@dataclass(frozen=True)
class BotAction:
    """Normalized reply produced by handling one Telegram update."""

    chat_id: int | str
    text: str
    audio_path: Path | None = None
    audio_title: str = "Cor ad Cor Daily Reflection"


class TelegramCompanionBot:
    """Processes Telegram updates and dispatches replies via the Telegram Bot HTTP API."""

    def __init__(
        self,
        *,
        bot_token: str,
        service: CompanionService,
        synthesizer: VoiceNoteSynthesizer | None = None,
        offline: bool = False,
        demo_fallback: bool = True,
    ) -> None:
        self.bot_token = bot_token.strip()
        self.service = service
        self.synthesizer = synthesizer
        self.offline = offline
        self.demo_fallback = demo_fallback

    @property
    def api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    def _use_demo(self) -> bool:
        has_keys = bool(
            self.service.settings.get_groq_keys()
            or self.service.settings.gemini_api_key.strip()
        )
        return (not has_keys) and self.demo_fallback

    async def handle_update(self, update: dict[str, Any]) -> BotAction | None:
        """Route one Telegram Update payload into a BotAction."""
        message = update.get("message") or update.get("edited_message")
        if not isinstance(message, dict):
            return None

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        raw_text = str(message.get("text") or "").strip()
        if chat_id is None or not raw_text:
            return None

        lower = raw_text.lower()
        use_demo = self._use_demo()

        if lower.startswith(("/start", "/help")):
            return BotAction(chat_id=chat_id, text=WELCOME_MESSAGE)

        if lower.startswith(("/today", "/mass")):
            reply = self.service.daily_briefing(offline=self.offline, demo=use_demo)
            header = f"{reply.liturgy.date} — {reply.liturgy.celebration_title} ({reply.liturgy.season})\n\n"
            return BotAction(chat_id=chat_id, text=header + reply.reflection)

        if lower.startswith("/voice"):
            reply = self.service.daily_briefing(offline=self.offline, demo=use_demo)
            if self.synthesizer is None:
                return BotAction(
                    chat_id=chat_id,
                    text="Voice synthesizer is not configured on this server.",
                )
            mp3_path, _ = await self.synthesizer.synthesize_mp3(reply.reflection)
            return BotAction(
                chat_id=chat_id,
                text=f"Daily Voice-Note — {reply.liturgy.celebration_title} ({reply.liturgy.date})",
                audio_path=mp3_path,
                audio_title=f"Cor ad Cor — {reply.liturgy.date}",
            )

        if lower.startswith("/examen"):
            body = raw_text[len("/examen") :].strip()
            if not body:
                return BotAction(
                    chat_id=chat_id,
                    text=(
                        "To pray the 3-Minute Evening Examen, reply with:\n"
                        "/examen gratitude | consolation | desolation\n\n"
                        "Example:\n"
                        "/examen Quiet morning coffee | Patience at work | Snapped in evening traffic"
                    ),
                )
            parts = [p.strip() for p in body.split("|")]
            gratitude = parts[0] if len(parts) >= 1 else ""
            consolation = parts[1] if len(parts) >= 2 else ""
            desolation = parts[2] if len(parts) >= 3 else (body if len(parts) == 1 else "")
            reply = self.service.evening_examen(
                gratitude=gratitude,
                consolation=consolation,
                desolation=desolation,
                offline=self.offline,
                demo=use_demo,
                remember=True,
            )
            return BotAction(chat_id=chat_id, text=reply.reflection)

        if lower.startswith("/confession"):
            focus = raw_text[len("/confession") :].strip()
            reply = self.service.confession_prep(
                focus_area=focus,
                offline=self.offline,
                demo=use_demo,
            )
            return BotAction(chat_id=chat_id, text=reply.reflection)

        if lower.startswith("/rosary"):
            rosary = get_rosary_for_date()
            lines = [f"{rosary.weekday} — {rosary.mystery_set} ({rosary.date})"]
            for m in rosary.mysteries:
                lines.append(
                    f"\n{m.number}. {m.title} ({m.scripture}) — Fruit: {m.fruit} [CCC §{m.ccc_paragraph}]\n"
                    f"   {m.intention}"
                )
            return BotAction(chat_id=chat_id, text="\n".join(lines))

        if lower.startswith("/angelus"):
            import datetime as dt

            day = self.service.get_day(offline=self.offline)
            hp = get_prayer_for_hour(dt.datetime.now().hour, season=day.season)
            return BotAction(
                chat_id=chat_id,
                text=(
                    f"{hp.label} — {hp.marian_devotion_title}\n\n"
                    f"{hp.marian_devotion_text}\n\n"
                    f"— {hp.canticle_title} ({hp.canticle_citation}) —\n{hp.canticle_text}"
                ),
            )

        if lower.startswith("/prayer"):
            moment = raw_text[len("/prayer") :].strip() or None
            prayers = list_prayers(moment=moment)
            chosen = prayers[0]
            return BotAction(
                chat_id=chat_id,
                text=f"{chosen.title} ({chosen.attribution})\n\n{chosen.text}",
            )

        if lower.startswith("/ccc"):
            query = raw_text[len("/ccc") :].strip()
            if len(query) < 2:
                return BotAction(chat_id=chat_id, text="Usage: /ccc <theme> (e.g., /ccc dryness in prayer)")
            hits = self.service.ccc_index.search(query, k=3)
            if not hits:
                return BotAction(chat_id=chat_id, text="No Catechism paragraphs matched that search.")
            lines = [f"Catechism matches for '{query}':"]
            for h in hits:
                lines.append(f"\n[{h.citation}] {h.section}\n{h.text}")
            return BotAction(chat_id=chat_id, text="\n".join(lines))

        if lower.startswith("/wipe"):
            deleted = self.service.clear_memory()
            return BotAction(
                chat_id=chat_id,
                text=f"Clean slate: cleared {deleted} saved reflection(s) from local season memory.",
            )

        # Default: Personal "Bring Your Day to Mass" check-in
        reply = self.service.personal_checkin(
            user_message=raw_text,
            offline=self.offline,
            demo=use_demo,
            remember=True,
        )
        return BotAction(chat_id=chat_id, text=reply.reflection)

    async def send_action(self, action: BotAction) -> None:
        """Deliver a BotAction (text chunks and optional MP3 audio) via Telegram Bot API."""
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not configured.")

        async with httpx.AsyncClient(timeout=30.0) as client:
            if action.audio_path and action.audio_path.exists():
                with action.audio_path.open("rb") as audio_file:
                    resp = await client.post(
                        f"{self.api_base}/sendAudio",
                        data={
                            "chat_id": str(action.chat_id),
                            "caption": action.text[:1000],
                            "title": action.audio_title,
                        },
                        files={"audio": (action.audio_path.name, audio_file, "audio/mpeg")},
                    )
                    resp.raise_for_status()
                return

            for chunk in split_telegram_text(action.text):
                resp = await client.post(
                    f"{self.api_base}/sendMessage",
                    json={"chat_id": action.chat_id, "text": chunk},
                )
                resp.raise_for_status()

    async def get_updates(self, *, offset: int | None = None, timeout: int = 25) -> list[dict[str, Any]]:
        """Poll Telegram getUpdates for local bot hosting."""
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not configured.")
        params: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        async with httpx.AsyncClient(timeout=timeout + 10) as client:
            resp = await client.get(f"{self.api_base}/getUpdates", params=params)
            resp.raise_for_status()
            payload = resp.json()
            return list(payload.get("result") or [])
