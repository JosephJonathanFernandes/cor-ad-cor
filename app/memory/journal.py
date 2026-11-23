"""Opt-in local SQLite journal for season-aware continuity and Confession prep."""

from __future__ import annotations

import collections
import datetime as dt
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

EntryType = Literal["checkin", "examen"]

_THEME_PATTERNS: dict[str, re.Pattern[str]] = {
    "prayer dryness & distraction": re.compile(
        r"\b(dry|dryness|distract\w*|distant|numb|going through the motions|silence)\b", re.I
    ),
    "work burnout & exhaustion": re.compile(
        r"\b(burn\w*\s*out|exhaust\w*|tired|overwhelm\w*|overwork\w*|drained|deadline\w*)\b", re.I
    ),
    "impatience, anger & resentment": re.compile(
        r"\b(resent\w*|ang(er|ry)|impatient|irritat\w*|bitter\w*|snap\w*|frustrat\w*)\b", re.I
    ),
    "anxiety, fear & uncertainty": re.compile(
        r"\b(anxi(ous|ety)|afraid|fear\w*|worr(y|ied)|uncertain\w*|decision|panic)\b", re.I
    ),
    "guilt, habit & need for mercy": re.compile(
        r"\b(guilt\w*|shame|confess\w*|sin\w*|fail\w*|habit|tempt\w*|forgiv\w*)\b", re.I
    ),
    "family & relationship tension": re.compile(
        r"\b(family|spouse|marriage|child\w*|parent\w*|friend\w*|argued|conflict|lonely)\b", re.I
    ),
    "gratitude, peace & consolation": re.compile(
        r"\b(grateful|thank\w*|peace\w*|joy|grace|consol\w*|blessed|kindness)\b", re.I
    ),
    "trust & surrender": re.compile(
        r"\b(trust\w*|surrender\w*|will of god|letting go|patience|hope)\b", re.I
    ),
}


def extract_themes(text: str) -> list[str]:
    """Identify spiritual and emotional themes present in a reflection note."""
    cleaned = text.strip()
    if not cleaned:
        return []
    matched = [label for label, pattern in _THEME_PATTERNS.items() if pattern.search(cleaned)]
    return matched or ["general daily reflection"]


@dataclass(frozen=True)
class JournalEntry:
    """Single opt-in reflection entry stored locally on the user's device."""

    id: int
    created_at: str
    liturgical_date: str
    season: str
    entry_type: EntryType
    user_note: str
    consolation: str = ""
    desolation: str = ""
    themes: list[str] = field(default_factory=list)
    ccc_citations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BookmarkEntry:
    """A saved companion reflection bookmarked by the user for later prayer."""

    id: int
    created_at: str
    liturgical_date: str
    category: str
    title: str
    content: str
    ccc_citations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SeasonMemorySummary:
    """Aggregated spiritual continuity patterns across a liturgical season."""

    total_entries: int
    season: str
    top_themes: list[tuple[str, int]]
    recent_entries: list[JournalEntry]
    distinct_days: int = 0
    last_entry_date: str = ""

    def prompt_context(self) -> str:
        """Render a concise, privacy-respecting summary for the companion LLM prompt."""
        if self.total_entries == 0:
            return "No prior saved reflections in local season memory."

        themes_str = ", ".join(f"{theme} ({count}x)" for theme, count in self.top_themes[:4])
        lines = [
            f"Saved entries in current memory ({self.season or 'All Seasons'}): {self.total_entries}",
            f"Recurring themes noticed across days: {themes_str or 'None yet'}",
            "Recent brief notes from the user:",
        ]
        for entry in self.recent_entries[:4]:
            if entry.entry_type == "examen":
                detail = (
                    f"Examen — Consolation: '{entry.consolation[:90]}' | "
                    f"Desolation/Resistance: '{entry.desolation[:90]}'"
                )
            else:
                detail = f"Check-In — '{entry.user_note[:120]}'"
            lines.append(f"- [{entry.liturgical_date} / {entry.season}] {detail}")
        return "\n".join(lines)


class JournalStore:
    """Local SQLite store for opt-in personal check-ins and evening Examens."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    liturgical_date TEXT NOT NULL,
                    season TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    user_note TEXT NOT NULL,
                    consolation TEXT NOT NULL DEFAULT '',
                    desolation TEXT NOT NULL DEFAULT '',
                    themes_json TEXT NOT NULL DEFAULT '[]',
                    ccc_citations_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    liturgical_date TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ccc_citations_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.commit()

    def add_entry(
        self,
        *,
        liturgical_date: str,
        season: str,
        entry_type: EntryType,
        user_note: str,
        consolation: str = "",
        desolation: str = "",
        ccc_citations: list[str] | None = None,
    ) -> JournalEntry:
        """Persist an opt-in check-in or Examen entry and tag its themes."""
        combined_text = " ".join(part for part in (user_note, consolation, desolation) if part)
        themes = extract_themes(combined_text)
        citations = ccc_citations or []
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO journal_entries (
                    created_at, liturgical_date, season, entry_type,
                    user_note, consolation, desolation, themes_json, ccc_citations_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_iso,
                    liturgical_date,
                    season,
                    entry_type,
                    user_note.strip(),
                    consolation.strip(),
                    desolation.strip(),
                    json.dumps(themes),
                    json.dumps(citations),
                ),
            )
            conn.commit()
            entry_id = int(cursor.lastrowid or 0)

        return JournalEntry(
            id=entry_id,
            created_at=now_iso,
            liturgical_date=liturgical_date,
            season=season,
            entry_type=entry_type,
            user_note=user_note.strip(),
            consolation=consolation.strip(),
            desolation=desolation.strip(),
            themes=themes,
            ccc_citations=citations,
        )

    def list_entries(self, *, limit: int = 20, season: str | None = None) -> list[JournalEntry]:
        """Return recent saved entries, optionally filtered by liturgical season."""
        query = "SELECT * FROM journal_entries"
        params: list[object] = []
        if season:
            query += " WHERE LOWER(season) = LOWER(?)"
            params.append(season)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        entries: list[JournalEntry] = []
        for row in rows:
            entries.append(
                JournalEntry(
                    id=int(row["id"]),
                    created_at=str(row["created_at"]),
                    liturgical_date=str(row["liturgical_date"]),
                    season=str(row["season"]),
                    entry_type=row["entry_type"],
                    user_note=str(row["user_note"]),
                    consolation=str(row["consolation"]),
                    desolation=str(row["desolation"]),
                    themes=json.loads(row["themes_json"] or "[]"),
                    ccc_citations=json.loads(row["ccc_citations_json"] or "[]"),
                )
            )
        return entries

    def season_summary(
        self,
        *,
        season: str | None = None,
        limit: int = 20,
    ) -> SeasonMemorySummary:
        """Summarize recurring themes and recent entries for continuity & Confession prep."""
        entries = self.list_entries(limit=limit, season=season)
        if not entries and season:
            # Fall back to all entries if none match the specific season string yet
            entries = self.list_entries(limit=limit, season=None)

        counter: collections.Counter[str] = collections.Counter()
        for entry in entries:
            counter.update(entry.themes)

        distinct_days = len({entry.liturgical_date for entry in entries if entry.liturgical_date})
        last_entry_date = entries[0].liturgical_date if entries else ""

        return SeasonMemorySummary(
            total_entries=len(entries),
            season=season or (entries[0].season if entries else "Ordinary Time"),
            top_themes=counter.most_common(6),
            recent_entries=entries[:6],
            distinct_days=distinct_days,
            last_entry_date=last_entry_date,
        )

    def clear_all(self) -> int:
        """Delete all stored journal entries (e.g., after Confession or on user request)."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM journal_entries")
            conn.commit()
            return int(cursor.rowcount or 0)

    def add_bookmark(
        self,
        *,
        liturgical_date: str,
        category: str,
        title: str,
        content: str,
        ccc_citations: list[str] | None = None,
    ) -> BookmarkEntry:
        """Save a meaningful reflection to the user's local spiritual treasury."""
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        citations = ccc_citations or []
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO bookmarks (
                    created_at, liturgical_date, category, title, content, ccc_citations_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    now_iso,
                    liturgical_date.strip(),
                    category.strip(),
                    title.strip(),
                    content.strip(),
                    json.dumps(citations),
                ),
            )
            conn.commit()
            bookmark_id = int(cursor.lastrowid or 0)
        return BookmarkEntry(
            id=bookmark_id,
            created_at=now_iso,
            liturgical_date=liturgical_date.strip(),
            category=category.strip(),
            title=title.strip(),
            content=content.strip(),
            ccc_citations=citations,
        )

    def list_bookmarks(self, *, limit: int = 50) -> list[BookmarkEntry]:
        """Return saved reflections ordered newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM bookmarks ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            BookmarkEntry(
                id=int(row["id"]),
                created_at=str(row["created_at"]),
                liturgical_date=str(row["liturgical_date"]),
                category=str(row["category"]),
                title=str(row["title"]),
                content=str(row["content"]),
                ccc_citations=json.loads(row["ccc_citations_json"] or "[]"),
            )
            for row in rows
        ]

    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Remove a single saved bookmark by ID."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
            conn.commit()
            return int(cursor.rowcount or 0) > 0
