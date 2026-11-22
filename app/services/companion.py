"""Core orchestration service tying liturgy, CCC RAG, guardrails, and LLM routing."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.config import Settings
from app.data_sources.liturgy import LiturgicalDay, get_liturgical_day
from app.llm.router import GroqGeminiRouter, LLMResult
from app.memory.journal import JournalStore, SeasonMemorySummary
from app.prompts.companion import (
    COMPANION_SYSTEM_PROMPT,
    PASTORAL_CRISIS_RESPONSE,
    build_checkin_prompt,
    build_confession_prep_prompt,
    build_daily_briefing_prompt,
    build_examen_prompt,
    build_lectio_divina_prompt,
    build_preview_checkin_reflection,
    build_preview_confession_prep_reflection,
    build_preview_daily_reflection,
    build_preview_examen_reflection,
    build_preview_lectio_divina,
    detect_distress_signal,
)
from app.rag.catechism import CatechismHit, CatechismIndex, build_embeddings
from app.rag.verifier import CitationVerification, verify_and_hydrate_citations


def _preview_llm_result() -> LLMResult:
    return LLMResult(
        content="",
        provider="preview",
        model="deterministic-citation-preview",
        key_slot="demo_mode",
        attempts=1,
    )


@dataclass(frozen=True)
class CompanionReply:
    """Structured response returned by both the FastAPI layer and CLI demo."""

    liturgy: LiturgicalDay
    ccc_hits: list[CatechismHit]
    reflection: str
    llm: LLMResult | None
    crisis_escalated: bool = False
    saved_entry_id: int | None = None
    verification: CitationVerification | None = None


class CompanionService:
    """Coordinates liturgical retrieval, CCC search, season memory, and companion generation."""

    def __init__(
        self,
        *,
        settings: Settings,
        router: GroqGeminiRouter,
        ccc_index: CatechismIndex,
        journal_store: JournalStore | None = None,
    ) -> None:
        self.settings = settings
        self.router = router
        self.ccc_index = ccc_index
        self.journal = journal_store or JournalStore(settings.journal_db_path)

    @classmethod
    def from_settings(cls, settings: Settings) -> CompanionService:
        """Construct the default service graph from application settings."""
        provider = settings.resolved_embedding_provider()
        embeddings = build_embeddings(
            provider,
            gemini_api_key=settings.gemini_api_key,
            gemini_embedding_model=settings.gemini_embedding_model,
        )
        source_path = (
            settings.ccc_full_path
            if settings.ccc_full_path.exists()
            else settings.ccc_seed_path
        )
        ccc_index = CatechismIndex.load_or_build(
            index_dir=settings.ccc_index_dir,
            source_path=source_path,
            embeddings=embeddings,
        )
        router = GroqGeminiRouter(
            groq_keys=settings.get_groq_keys(),
            groq_model=settings.groq_model,
            gemini_api_key=settings.gemini_api_key,
            gemini_model=settings.gemini_model,
            cooldown_seconds=settings.groq_cooldown_seconds,
        )
        return cls(settings=settings, router=router, ccc_index=ccc_index)

    def get_day(self, target_date: dt.date | None = None, *, offline: bool = False) -> LiturgicalDay:
        """Fetch or load the liturgical day."""
        return get_liturgical_day(
            target_date,
            cache_dir=self.settings.readings_cache_dir,
            offline=offline,
        )

    def liturgy_context(
        self,
        *,
        target_date: dt.date | None = None,
        offline: bool = False,
        ccc_k: int = 3,
    ) -> tuple[LiturgicalDay, list[CatechismHit]]:
        """Retrieve the liturgical day and top-k matching CCC paragraphs without calling an LLM."""
        day = self.get_day(target_date, offline=offline)
        ccc_hits = self.ccc_index.search(day.theme_query(), k=ccc_k)
        return day, ccc_hits

    def _finalize_reply(
        self,
        *,
        liturgy: LiturgicalDay,
        ccc_hits: list[CatechismHit],
        reflection: str,
        llm: LLMResult | None,
        crisis_escalated: bool = False,
        saved_entry_id: int | None = None,
    ) -> CompanionReply:
        """Run post-generation CCC citation verification and auto-hydration."""
        hydrated_hits, verification = verify_and_hydrate_citations(
            reflection,
            ccc_hits,
            self.ccc_index,
        )
        return CompanionReply(
            liturgy=liturgy,
            ccc_hits=hydrated_hits,
            reflection=reflection,
            llm=llm,
            crisis_escalated=crisis_escalated,
            saved_entry_id=saved_entry_id,
            verification=verification,
        )

    def daily_briefing(
        self,
        *,
        target_date: dt.date | None = None,
        offline: bool = False,
        ccc_k: int = 3,
        demo: bool = False,
    ) -> CompanionReply:
        """Generate today's grounded pre-Mass briefing and reflection."""
        day, ccc_hits = self.liturgy_context(
            target_date=target_date,
            offline=offline,
            ccc_k=ccc_k,
        )
        if demo:
            return self._finalize_reply(
                liturgy=day,
                ccc_hits=ccc_hits,
                reflection=build_preview_daily_reflection(day, ccc_hits),
                llm=_preview_llm_result(),
            )
        prompt = build_daily_briefing_prompt(day, ccc_hits)
        result = self.router.generate(COMPANION_SYSTEM_PROMPT, prompt, temperature=0.35)
        return self._finalize_reply(
            liturgy=day,
            ccc_hits=ccc_hits,
            reflection=result.content,
            llm=result,
        )

    def stream_daily_briefing(
        self,
        *,
        target_date: dt.date | None = None,
        offline: bool = False,
        ccc_k: int = 3,
        demo: bool = False,
    ):
        """Yield ('context' | 'chunk' | 'done', payload) events for SSE streaming."""
        day, ccc_hits = self.liturgy_context(
            target_date=target_date,
            offline=offline,
            ccc_k=ccc_k,
        )
        yield "context", (day, ccc_hits)

        if demo:
            full_text = build_preview_daily_reflection(day, ccc_hits)
            words = full_text.split(" ")
            step = 10
            for idx in range(0, len(words), step):
                chunk = " ".join(words[idx : idx + step])
                if idx + step < len(words):
                    chunk += " "
                yield "chunk", chunk
            yield "done", self._finalize_reply(
                liturgy=day,
                ccc_hits=ccc_hits,
                reflection=full_text,
                llm=_preview_llm_result(),
            )
            return

        prompt = build_daily_briefing_prompt(day, ccc_hits)
        accumulated: list[str] = []
        last_meta: LLMResult | None = None
        for piece, meta in self.router.stream(COMPANION_SYSTEM_PROMPT, prompt, temperature=0.35):
            accumulated.append(piece)
            last_meta = meta
            yield "chunk", piece

        full_text = "".join(accumulated).strip()
        yield "done", self._finalize_reply(
            liturgy=day,
            ccc_hits=ccc_hits,
            reflection=full_text,
            llm=last_meta,
        )

    def personal_checkin(
        self,
        *,
        user_message: str,
        target_date: dt.date | None = None,
        offline: bool = False,
        ccc_k: int = 3,
        demo: bool = False,
        remember: bool = False,
        history: list[dict[str, str]] | None = None,
    ) -> CompanionReply:
        """Generate a grounded reflection connecting the user's day to today's liturgy."""
        day = self.get_day(target_date, offline=offline)

        if detect_distress_signal(user_message):
            ccc_hits = self.ccc_index.search("human life sacred dignity despair hope", k=2)
            return CompanionReply(
                liturgy=day,
                ccc_hits=ccc_hits,
                reflection=PASTORAL_CRISIS_RESPONSE,
                llm=None,
                crisis_escalated=True,
            )

        combined_query = f"{user_message}\n\n{day.theme_query()}"
        ccc_hits = self.ccc_index.search(combined_query, k=ccc_k)
        memory_ctx = self.journal.season_summary(season=day.season).prompt_context()

        saved_id: int | None = None
        if remember:
            entry = self.journal.add_entry(
                liturgical_date=day.date,
                season=day.season,
                entry_type="checkin",
                user_note=user_message,
                ccc_citations=[h.citation for h in ccc_hits],
            )
            saved_id = entry.id

        if demo:
            return self._finalize_reply(
                liturgy=day,
                ccc_hits=ccc_hits,
                reflection=build_preview_checkin_reflection(user_message, day, ccc_hits),
                llm=_preview_llm_result(),
                saved_entry_id=saved_id,
            )
        prompt = build_checkin_prompt(
            user_message,
            day,
            ccc_hits,
            memory_context=memory_ctx,
            history=history,
        )
        result = self.router.generate(COMPANION_SYSTEM_PROMPT, prompt, temperature=0.45)
        return self._finalize_reply(
            liturgy=day,
            ccc_hits=ccc_hits,
            reflection=result.content,
            llm=result,
            saved_entry_id=saved_id,
        )

    def evening_examen(
        self,
        *,
        gratitude: str,
        consolation: str,
        desolation: str,
        target_date: dt.date | None = None,
        offline: bool = False,
        ccc_k: int = 3,
        demo: bool = False,
        remember: bool = True,
    ) -> CompanionReply:
        """Run the 3-minute nightly Ignatian Examen tied to the morning's readings."""
        day = self.get_day(target_date, offline=offline)
        combined_notes = " ".join(p for p in (gratitude, consolation, desolation) if p).strip()

        if detect_distress_signal(combined_notes):
            ccc_hits = self.ccc_index.search("human life sacred dignity despair hope", k=2)
            return CompanionReply(
                liturgy=day,
                ccc_hits=ccc_hits,
                reflection=PASTORAL_CRISIS_RESPONSE,
                llm=None,
                crisis_escalated=True,
            )

        search_query = f"prayer examen {combined_notes}\n{day.theme_query()}"
        ccc_hits = self.ccc_index.search(search_query, k=ccc_k)
        memory_ctx = self.journal.season_summary(season=day.season).prompt_context()

        saved_id: int | None = None
        if remember and combined_notes:
            entry = self.journal.add_entry(
                liturgical_date=day.date,
                season=day.season,
                entry_type="examen",
                user_note=gratitude,
                consolation=consolation,
                desolation=desolation,
                ccc_citations=[h.citation for h in ccc_hits],
            )
            saved_id = entry.id

        if demo:
            return self._finalize_reply(
                liturgy=day,
                ccc_hits=ccc_hits,
                reflection=build_preview_examen_reflection(
                    day=day,
                    ccc_hits=ccc_hits,
                    gratitude=gratitude,
                    consolation=consolation,
                    desolation=desolation,
                    memory_context=memory_ctx,
                ),
                llm=_preview_llm_result(),
                saved_entry_id=saved_id,
            )

        prompt = build_examen_prompt(
            day=day,
            ccc_hits=ccc_hits,
            gratitude=gratitude,
            consolation=consolation,
            desolation=desolation,
            memory_context=memory_ctx,
        )
        result = self.router.generate(COMPANION_SYSTEM_PROMPT, prompt, temperature=0.4)
        return self._finalize_reply(
            liturgy=day,
            ccc_hits=ccc_hits,
            reflection=result.content,
            llm=result,
            saved_entry_id=saved_id,
        )

    def confession_prep(
        self,
        *,
        focus_area: str = "",
        target_date: dt.date | None = None,
        offline: bool = False,
        demo: bool = False,
    ) -> CompanionReply:
        """Generate a gentle, non-scrupulous Examination of Conscience & Confession guide."""
        day = self.get_day(target_date, offline=offline)

        if detect_distress_signal(focus_area):
            ccc_hits = self.ccc_index.search("human life sacred dignity despair hope", k=2)
            return CompanionReply(
                liturgy=day,
                ccc_hits=ccc_hits,
                reflection=PASTORAL_CRISIS_RESPONSE,
                llm=None,
                crisis_escalated=True,
            )

        summary = self.journal.season_summary(season=day.season)
        theme_words = " ".join(theme for theme, _ in summary.top_themes)
        query = (
            f"penance reconciliation interior repentance conscience forgiveness mercy "
            f"{focus_area} {theme_words}"
        )
        ccc_hits = self.ccc_index.search(query, k=4)
        memory_ctx = summary.prompt_context()

        if demo:
            return self._finalize_reply(
                liturgy=day,
                ccc_hits=ccc_hits,
                reflection=build_preview_confession_prep_reflection(
                    day=day,
                    ccc_hits=ccc_hits,
                    focus_area=focus_area,
                    memory_context=memory_ctx,
                ),
                llm=_preview_llm_result(),
            )

        prompt = build_confession_prep_prompt(
            day=day,
            ccc_hits=ccc_hits,
            focus_area=focus_area,
            memory_context=memory_ctx,
        )
        result = self.router.generate(COMPANION_SYSTEM_PROMPT, prompt, temperature=0.35)
        return self._finalize_reply(
            liturgy=day,
            ccc_hits=ccc_hits,
            reflection=result.content,
            llm=result,
        )

    def get_memory_summary(self, season: str | None = None) -> SeasonMemorySummary:
        """Return aggregated season continuity themes and recent opt-in entries."""
        return self.journal.season_summary(season=season)

    def export_memory_entries(self, limit: int = 500):
        """Return all saved journal entries for user-owned JSON export."""
        return self.journal.list_entries(limit=limit)

    def clear_memory(self) -> int:
        """Delete all saved local reflection entries."""
        return self.journal.clear_all()

    def lectio_divina(
        self,
        *,
        selected_phrase: str = "",
        target_date: dt.date | None = None,
        offline: bool = False,
        demo: bool = False,
    ) -> CompanionReply:
        """Guide a 4-step Catholic Lectio Divina anchored to today's Gospel."""
        day = self.get_day(target_date, offline=offline)
        query = f"contemplative prayer word of god meditation {selected_phrase}\n{day.theme_query()}"
        ccc_hits = self.ccc_index.search(query, k=3)
        # Ensure CCC §2709 (Contemplative Prayer) is available when present in the corpus
        contemplative = self.ccc_index.get_by_paragraph(2709)
        if contemplative is not None and all(h.paragraph != 2709 for h in ccc_hits):
            ccc_hits = [contemplative, *ccc_hits[:2]]

        if demo:
            return self._finalize_reply(
                liturgy=day,
                ccc_hits=ccc_hits,
                reflection=build_preview_lectio_divina(
                    day=day,
                    ccc_hits=ccc_hits,
                    selected_phrase=selected_phrase,
                ),
                llm=_preview_llm_result(),
            )

        prompt = build_lectio_divina_prompt(
            day=day,
            ccc_hits=ccc_hits,
            selected_phrase=selected_phrase,
        )
        result = self.router.generate(COMPANION_SYSTEM_PROMPT, prompt, temperature=0.4)
        return self._finalize_reply(
            liturgy=day,
            ccc_hits=ccc_hits,
            reflection=result.content,
            llm=result,
        )
