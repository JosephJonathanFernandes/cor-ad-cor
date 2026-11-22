"""Daily Catholic Mass readings and liturgical calendar retrieval with caching."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_USER_AGENT = "CorAdCorCompanion/0.1 (+https://github.com/local/cor-ad-cor)"


class Reading(BaseModel):
    """A single liturgical reading from the day's Mass lectionary."""

    label: str
    citation: str
    text: str


class SaintInfo(BaseModel):
    """Saint or liturgical celebration honored on the given date."""

    title: str
    rank: str = ""
    colour: str = ""
    summary: str = ""


class LiturgicalDay(BaseModel):
    """Complete liturgical snapshot for one calendar date."""

    date: str
    season: str = "Ordinary Time"
    celebration_title: str = ""
    colour: str = ""
    readings: list[Reading] = Field(default_factory=list)
    saint: SaintInfo | None = None
    source: str = "live"

    def theme_query(self) -> str:
        """Build a concise search query from the day's readings and celebration."""
        parts: list[str] = []
        if self.celebration_title:
            parts.append(self.celebration_title)
        if self.saint and self.saint.title:
            parts.append(self.saint.title)
        for reading in self.readings:
            parts.append(f"{reading.label} ({reading.citation}): {reading.text[:350]}")
        return "\n".join(parts)


def parse_usccb_html(html: str) -> tuple[str, list[Reading]]:
    """Extract the liturgical title and Mass readings from USCCB HTML."""
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one("h1.page-title, .b-lectionary h2, h1")
    title = title_el.get_text(" ", strip=True) if title_el else ""

    readings: list[Reading] = []
    # USCCB wraps each reading in .b-verse or .innerblock sections
    blocks = soup.select("div.b-verse, div.content-body")
    if not blocks:
        blocks = [soup]

    seen_labels: set[str] = set()
    for block in blocks:
        header = block.select_one("h3.name, h2, h3")
        if not header:
            continue
        raw_label = header.get_text(" ", strip=True)
        normalized = re.sub(r"\s+", " ", raw_label).strip()
        if not normalized or normalized in seen_labels:
            continue
        if not any(
            kw in normalized.lower()
            for kw in ("reading", "psalm", "gospel", "alleluia", "sequence")
        ):
            continue

        citation_el = block.select_one("div.address, .address a, .b-verse-address")
        citation = citation_el.get_text(" ", strip=True) if citation_el else ""

        body_el = block.select_one("div.content-body") or block
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in body_el.select("p")
            if p.get_text(strip=True)
        ]
        # Avoid re-capturing the header/address if there were no <p> tags
        text = "\n\n".join(paragraphs).strip()
        if not text:
            continue

        seen_labels.add(normalized)
        readings.append(Reading(label=normalized, citation=citation, text=text))

    return title, readings


def parse_calapi_payload(payload: dict[str, Any]) -> tuple[str, str, SaintInfo | None]:
    """Extract season, primary celebration title, and saint info from CalAPI JSON."""
    season = str(payload.get("season", "")).replace("_", " ").title() or "Ordinary Time"
    celebrations = payload.get("celebrations") or []
    if not celebrations:
        return season, "", None

    primary = celebrations[0]
    title = str(primary.get("title", "")).strip()
    rank = str(primary.get("rank", "")).strip()
    colour = str(primary.get("colour", "")).strip()
    saint = SaintInfo(
        title=title,
        rank=rank,
        colour=colour,
        summary=(
            f"Liturgical celebration observed on this day ({rank or 'feast'}, "
            f"liturgical color: {colour or 'default'})."
        ),
    )
    return season, title, saint


def offline_sample_day(target_date: dt.date) -> LiturgicalDay:
    """Return a built-in Catholic liturgical fixture for offline development/tests."""
    return LiturgicalDay(
        date=target_date.isoformat(),
        season="Ordinary Time",
        celebration_title="Sample Liturgical Day (Offline Fixture)",
        colour="white",
        saint=SaintInfo(
            title="Memorial of the Presentation of the Blessed Virgin Mary",
            rank="Memorial",
            colour="white",
            summary=(
                "Honors Mary's wholehearted offering of herself to God from childhood, "
                "modeling quiet trust and availability to God's will."
            ),
        ),
        readings=[
            Reading(
                label="First Reading",
                citation="Zechariah 2:14-17",
                text=(
                    "Sing and rejoice, O daughter Zion! See, I am coming to dwell among you, "
                    "says the LORD. Many nations shall join themselves to the LORD on that day, "
                    "and they shall be his people, and he will dwell among you."
                ),
            ),
            Reading(
                label="Responsorial Psalm",
                citation="Luke 1:46-55",
                text=(
                    "The Almighty has done great things for me, and holy is his Name. "
                    "My soul proclaims the greatness of the Lord; my spirit rejoices in God "
                    "my Savior, for he has looked with favor on his lowly servant."
                ),
            ),
            Reading(
                label="Gospel",
                citation="Matthew 12:46-50",
                text=(
                    "While Jesus was speaking to the crowds, his mother and his brothers appeared "
                    "outside, wishing to speak with him. Someone told him, 'Your mother and your "
                    "brothers are standing outside, asking to speak with you.' But he said in "
                    "reply, 'Who is my mother? Who are my brothers?' And stretching out his hand "
                    "toward his disciples, he said, 'Here are my mother and my brothers. For "
                    "whoever does the will of my heavenly Father is my brother, and sister, and mother.'"
                ),
            ),
        ],
        source="offline_sample",
    )


def _cache_path(cache_dir: Path, target_date: dt.date) -> Path:
    return cache_dir / f"{target_date.isoformat()}.json"


def load_cached_day(cache_dir: Path, target_date: dt.date) -> LiturgicalDay | None:
    """Load a cached LiturgicalDay JSON file if present and valid."""
    path = _cache_path(cache_dir, target_date)
    if not path.exists():
        return None
    try:
        return LiturgicalDay.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed reading liturgical cache %s: %s", path, exc)
        return None


def save_cached_day(cache_dir: Path, day: LiturgicalDay) -> None:
    """Persist a LiturgicalDay JSON snapshot to disk."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{day.date}.json"
    path.write_text(day.model_dump_json(indent=2), encoding="utf-8")


def fetch_calapi_day(target_date: dt.date, timeout: float = 10.0) -> tuple[str, str, SaintInfo | None]:
    """Fetch liturgical calendar metadata from CalAPI."""
    url = (
        f"http://calapi.inadiutorium.cz/api/v0/en/calendars/default/"
        f"{target_date.year}/{target_date.month}/{target_date.day}"
    )
    with httpx.Client(timeout=timeout, headers={"User-Agent": _USER_AGENT}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return parse_calapi_payload(resp.json())


def fetch_usccb_readings(target_date: dt.date, timeout: float = 12.0) -> tuple[str, list[Reading]]:
    """Fetch and parse daily Mass readings from USCCB."""
    slug = target_date.strftime("%m%d%y")
    url = f"https://bible.usccb.org/bible/readings/{slug}.cfm"
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return parse_usccb_html(resp.text)


def get_liturgical_day(
    target_date: dt.date | None = None,
    *,
    cache_dir: Path,
    offline: bool = False,
) -> LiturgicalDay:
    """Retrieve today's Mass readings and celebration using cache, live fetch, or offline fallback."""
    resolved_date = target_date or dt.date.today()

    cached = load_cached_day(cache_dir, resolved_date)
    if cached is not None and (offline or cached.source == "live"):
        return cached

    if offline:
        return offline_sample_day(resolved_date)

    season = "Ordinary Time"
    celebration_title = ""
    saint: SaintInfo | None = None
    readings: list[Reading] = []

    try:
        season, celebration_title, saint = fetch_calapi_day(resolved_date)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CalAPI fetch failed for %s: %s", resolved_date, exc)

    try:
        usccb_title, readings = fetch_usccb_readings(resolved_date)
        if usccb_title and not celebration_title:
            celebration_title = usccb_title
    except Exception as exc:  # noqa: BLE001
        logger.warning("USCCB fetch failed for %s: %s", resolved_date, exc)

    if not readings:
        logger.warning("Falling back to offline sample readings for %s.", resolved_date)
        fallback = offline_sample_day(resolved_date)
        if saint is not None:
            fallback.saint = saint
        if celebration_title:
            fallback.celebration_title = celebration_title
        fallback.season = season
        return fallback

    day = LiturgicalDay(
        date=resolved_date.isoformat(),
        season=season,
        celebration_title=celebration_title or (saint.title if saint else "Daily Mass"),
        colour=saint.colour if saint else "",
        readings=readings,
        saint=saint,
        source="live",
    )
    save_cached_day(cache_dir, day)
    return day
