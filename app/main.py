"""FastAPI entry point for Cor ad Cor (Phases 1–4 Web App, Core API, Audio & Telegram)."""

from __future__ import annotations

import datetime as dt
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.data_sources.rosary import get_rosary_for_date
from app.delivery.audio import (
    VoiceNoteSynthesizer,
    estimate_duration_seconds,
    prepare_spoken_script,
)
from app.delivery.telegram_bot import TelegramCompanionBot
from app.llm.router import AllProvidersExhaustedError
from app.middleware import SecurityAndRateLimitMiddleware
from app.rag.catechism import CatechismHit
from app.services.companion import CompanionReply, CompanionService

STATIC_DIR = Path(__file__).resolve().parent / "static"


class CheckInTurn(BaseModel):
    """One prior turn in an in-session check-in spiritual dialogue."""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=2500)


class CheckInRequest(BaseModel):
    """Payload for a personal 'Bring Your Day to Today's Mass' check-in."""

    message: str = Field(..., min_length=2, max_length=2000)
    date: dt.date | None = None
    offline: bool = False
    demo: bool = False
    remember: bool = False
    history: list[CheckInTurn] = Field(default_factory=list, max_length=8)


class ExamenRequest(BaseModel):
    """Payload for the 3-minute nightly Ignatian Examen."""

    gratitude: str = Field(default="", max_length=1500)
    consolation: str = Field(default="", max_length=1500)
    desolation: str = Field(default="", max_length=1500)
    date: dt.date | None = None
    offline: bool = False
    demo: bool = False
    remember: bool = True


class ConfessionPrepRequest(BaseModel):
    """Payload for the gentle Confession & Examination of Conscience helper."""

    focus_area: str = Field(default="", max_length=1500)
    date: dt.date | None = None
    offline: bool = False
    demo: bool = False


class AudioVoiceNoteRequest(BaseModel):
    """Payload for converting a reflection into a calm spoken script or MP3 voice-note."""

    text: str = Field(..., min_length=2, max_length=8000)
    voice: str | None = None


class LectioRequest(BaseModel):
    """Payload for guided 4-step Lectio Divina anchored to today's Gospel."""

    selected_phrase: str = Field(default="", max_length=500)
    date: dt.date | None = None
    offline: bool = False
    demo: bool = False


def _serialize_ccc_hits(hits: list[CatechismHit]) -> list[dict[str, Any]]:
    return [
        {
            "citation": hit.citation,
            "paragraph": hit.paragraph,
            "section": hit.section,
            "text": hit.text,
            "source_type": hit.source_type,
        }
        for hit in hits
    ]


def _serialize_reply(reply: CompanionReply) -> dict[str, Any]:
    verification = None
    if reply.verification is not None:
        verification = {
            "cited_paragraphs": reply.verification.cited_paragraphs,
            "verified_paragraphs": reply.verification.verified_paragraphs,
            "hydrated_paragraphs": reply.verification.hydrated_paragraphs,
            "unverified_paragraphs": reply.verification.unverified_paragraphs,
            "all_valid": reply.verification.all_valid,
        }
    return {
        "liturgy": reply.liturgy.model_dump(),
        "ccc_citations": _serialize_ccc_hits(reply.ccc_hits),
        "reflection": reply.reflection,
        "crisis_escalated": reply.crisis_escalated,
        "saved_entry_id": reply.saved_entry_id,
        "citation_verification": verification,
        "llm": asdict(reply.llm) if reply.llm else None,
    }


def create_app(
    service_override: CompanionService | None = None,
    synthesizer_override: VoiceNoteSynthesizer | None = None,
    rate_limit_per_minute: int | None = None,
) -> FastAPI:
    """Application factory supporting dependency injection in tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if service_override is not None:
            app.state.companion_service = service_override
            settings = service_override.settings
        else:
            settings = get_settings()
            app.state.companion_service = CompanionService.from_settings(settings)

        app.state.voice_synthesizer = synthesizer_override or VoiceNoteSynthesizer(
            cache_dir=settings.audio_cache_dir,
            voice=settings.tts_voice,
            rate=settings.tts_rate,
        )
        yield

    application = FastAPI(
        title="Cor ad Cor — Catholic Daily Liturgical Companion",
        version="0.5.0",
        lifespan=lifespan,
    )

    rpm = (
        rate_limit_per_minute
        if rate_limit_per_minute is not None
        else (
            service_override.settings.rate_limit_per_minute
            if service_override is not None
            else get_settings().rate_limit_per_minute
        )
    )
    application.add_middleware(SecurityAndRateLimitMiddleware, requests_per_minute=rpm)

    if STATIC_DIR.exists():
        application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def get_service() -> CompanionService:
        return application.state.companion_service

    def get_synthesizer() -> VoiceNoteSynthesizer:
        return application.state.voice_synthesizer

    @application.get("/", include_in_schema=False)
    def serve_index() -> FileResponse:
        index_file = STATIC_DIR / "index.html"
        if not index_file.exists():
            raise HTTPException(status_code=404, detail="Web UI static index.html not found.")
        return FileResponse(index_file)

    @application.get("/health")
    def health(service: CompanionService = Depends(get_service)) -> dict[str, Any]:
        settings = service.settings
        return {
            "status": "ok",
            "groq_keys_configured": len(settings.get_groq_keys()),
            "gemini_fallback_configured": bool(settings.gemini_api_key.strip()),
            "embedding_provider": settings.resolved_embedding_provider(),
            "ccc_index_ready": (settings.ccc_index_dir / "index.faiss").exists(),
            "telegram_configured": bool(settings.telegram_bot_token.strip()),
            "tts_voice": settings.tts_voice,
        }

    @application.get("/api/v1/liturgy")
    def get_liturgy_context(
        date: dt.date | None = Query(default=None),
        offline: bool = Query(default=False),
        service: CompanionService = Depends(get_service),
    ) -> dict[str, Any]:
        day, ccc_hits = service.liturgy_context(target_date=date, offline=offline)
        return {
            "liturgy": day.model_dump(),
            "ccc_citations": _serialize_ccc_hits(ccc_hits),
        }

    @application.get("/api/v1/rosary")
    def get_daily_rosary(date: dt.date | None = Query(default=None)) -> dict[str, Any]:
        return get_rosary_for_date(date).to_dict()

    @application.get("/api/v1/daily")
    def get_daily_briefing(
        date: dt.date | None = Query(default=None),
        offline: bool = Query(default=False),
        demo: bool = Query(default=False),
        service: CompanionService = Depends(get_service),
    ) -> dict[str, Any]:
        try:
            reply = service.daily_briefing(target_date=date, offline=offline, demo=demo)
        except AllProvidersExhaustedError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return _serialize_reply(reply)

    @application.get("/api/v1/daily/stream")
    def stream_daily_briefing(
        date: dt.date | None = Query(default=None),
        offline: bool = Query(default=False),
        demo: bool = Query(default=False),
        service: CompanionService = Depends(get_service),
    ) -> StreamingResponse:
        def event_stream():
            try:
                for event_name, payload in service.stream_daily_briefing(
                    target_date=date,
                    offline=offline,
                    demo=demo,
                ):
                    if event_name == "context":
                        day, hits = payload
                        body = {
                            "liturgy": day.model_dump(),
                            "ccc_citations": _serialize_ccc_hits(hits),
                        }
                    elif event_name == "chunk":
                        body = {"delta": payload}
                    else:
                        body = _serialize_reply(payload)
                    yield f"event: {event_name}\ndata: {json.dumps(body, ensure_ascii=False)}\n\n"
            except AllProvidersExhaustedError as exc:
                yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @application.post("/api/v1/checkin")
    def post_checkin(
        payload: CheckInRequest,
        service: CompanionService = Depends(get_service),
    ) -> dict[str, Any]:
        try:
            reply = service.personal_checkin(
                user_message=payload.message,
                target_date=payload.date,
                offline=payload.offline,
                demo=payload.demo,
                remember=payload.remember,
                history=[turn.model_dump() for turn in payload.history],
            )
        except AllProvidersExhaustedError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return _serialize_reply(reply)

    @application.post("/api/v1/examen")
    def post_examen(
        payload: ExamenRequest,
        service: CompanionService = Depends(get_service),
    ) -> dict[str, Any]:
        if not any(
            part.strip() for part in (payload.gratitude, payload.consolation, payload.desolation)
        ):
            raise HTTPException(
                status_code=422,
                detail="Provide at least one Examen reflection note (gratitude, consolation, or desolation).",
            )
        try:
            reply = service.evening_examen(
                gratitude=payload.gratitude,
                consolation=payload.consolation,
                desolation=payload.desolation,
                target_date=payload.date,
                offline=payload.offline,
                demo=payload.demo,
                remember=payload.remember,
            )
        except AllProvidersExhaustedError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return _serialize_reply(reply)

    @application.post("/api/v1/confession-prep")
    def post_confession_prep(
        payload: ConfessionPrepRequest,
        service: CompanionService = Depends(get_service),
    ) -> dict[str, Any]:
        try:
            reply = service.confession_prep(
                focus_area=payload.focus_area,
                target_date=payload.date,
                offline=payload.offline,
                demo=payload.demo,
            )
        except AllProvidersExhaustedError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return _serialize_reply(reply)

    @application.get("/api/v1/memory")
    def get_season_memory(
        season: str | None = Query(default=None),
        service: CompanionService = Depends(get_service),
    ) -> dict[str, Any]:
        summary = service.get_memory_summary(season=season)
        return {
            "total_entries": summary.total_entries,
            "season": summary.season,
            "distinct_days": summary.distinct_days,
            "last_entry_date": summary.last_entry_date,
            "top_themes": [
                {"theme": theme, "count": count} for theme, count in summary.top_themes
            ],
            "recent_entries": [asdict(entry) for entry in summary.recent_entries],
        }

    @application.delete("/api/v1/memory")
    def delete_season_memory(
        service: CompanionService = Depends(get_service),
    ) -> dict[str, Any]:
        deleted = service.clear_memory()
        return {"status": "cleared", "deleted_entries": deleted}

    @application.get("/api/v1/memory/export")
    def export_season_memory(
        service: CompanionService = Depends(get_service),
    ) -> JSONResponse:
        entries = service.export_memory_entries()
        payload = {
            "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "total_entries": len(entries),
            "entries": [asdict(entry) for entry in entries],
        }
        return JSONResponse(
            content=payload,
            headers={"Content-Disposition": 'attachment; filename="cor_ad_cor_journal.json"'},
        )

    @application.post("/api/v1/lectio")
    def post_lectio_divina(
        payload: LectioRequest,
        service: CompanionService = Depends(get_service),
    ) -> dict[str, Any]:
        try:
            reply = service.lectio_divina(
                selected_phrase=payload.selected_phrase,
                target_date=payload.date,
                offline=payload.offline,
                demo=payload.demo,
            )
        except AllProvidersExhaustedError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return _serialize_reply(reply)

    @application.get("/api/v1/ccc/search")
    def search_ccc(
        q: str = Query(..., min_length=2),
        k: int = Query(default=3, ge=1, le=10),
        service: CompanionService = Depends(get_service),
    ) -> dict[str, Any]:
        hits = service.ccc_index.search(q, k=k)
        return {
            "query": q,
            "results": _serialize_ccc_hits(hits),
        }

    @application.get("/api/v1/ccc/{paragraph}")
    def get_ccc_paragraph(
        paragraph: int,
        service: CompanionService = Depends(get_service),
    ) -> dict[str, Any]:
        hit = service.ccc_index.get_by_paragraph(paragraph)
        if hit is None:
            raise HTTPException(status_code=404, detail=f"CCC §{paragraph} not found in current index.")
        return _serialize_ccc_hits([hit])[0]

    @application.post("/api/v1/audio/script")
    def build_audio_script(payload: AudioVoiceNoteRequest) -> dict[str, Any]:
        spoken = prepare_spoken_script(payload.text)
        return {
            "spoken_script": spoken,
            "estimated_seconds": estimate_duration_seconds(spoken),
        }

    @application.post("/api/v1/audio/voice-note")
    async def synthesize_voice_note(
        payload: AudioVoiceNoteRequest,
        synthesizer: VoiceNoteSynthesizer = Depends(get_synthesizer),
    ) -> FileResponse:
        try:
            mp3_path, _ = await synthesizer.synthesize_mp3(payload.text, voice=payload.voice)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return FileResponse(
            path=mp3_path,
            media_type="audio/mpeg",
            filename="cor_ad_cor_voice_note.mp3",
        )

    @application.post("/api/v1/telegram/webhook")
    async def telegram_webhook(
        update: dict[str, Any],
        send: bool = Query(default=True),
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
        service: CompanionService = Depends(get_service),
        synthesizer: VoiceNoteSynthesizer = Depends(get_synthesizer),
    ) -> dict[str, Any]:
        expected_secret = service.settings.telegram_webhook_secret.strip()
        if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
            raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret token.")

        bot = TelegramCompanionBot(
            bot_token=service.settings.telegram_bot_token,
            service=service,
            synthesizer=synthesizer,
            offline=False,
        )
        action = await bot.handle_update(update)
        if action is None:
            return {"status": "ignored"}

        dispatched = False
        if send and bot.bot_token:
            await bot.send_action(action)
            dispatched = True

        return {
            "status": "ok",
            "dispatched": dispatched,
            "chat_id": action.chat_id,
            "has_audio": action.audio_path is not None,
            "reply_preview": action.text[:240],
        }

    return application


app = create_app()
