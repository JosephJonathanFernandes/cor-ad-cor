"""Daily Catholic Mass readings and liturgical calendar retrieval with caching."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

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
    papal_reflection: str = ""
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


_LITURGICAL_PREFIX_RE = re.compile(
    r"^(optional memorial of|memorial of|feast of|solemnity of|commemoration of)\s+",
    re.I,
)
_SAINT_ABBREV_RE = re.compile(r"\bSts?\.\s*", re.I)


def clean_saint_query(celebration_title: str) -> str:
    """Normalize a liturgical celebration title into a clean lookup query for a saint biography."""
    cleaned = _LITURGICAL_PREFIX_RE.sub("", celebration_title.strip())
    # Drop trailing liturgical descriptors like ", virgin and martyr" or ", bishop and doctor"
    cleaned = cleaned.split(",")[0].strip()
    cleaned = _SAINT_ABBREV_RE.sub("Saint ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _trim_sentences(text: str, max_sentences: int = 3, max_chars: int = 420) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    out = " ".join(sentences[:max_sentences]).strip()
    if len(out) > max_chars:
        out = out[: max_chars - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return out


def fetch_saint_biography(celebration_title: str, timeout: float = 6.0) -> str:
    """Fetch a concise 2–3 sentence historical biography for a saint/feast via Wikipedia REST API."""
    query = clean_saint_query(celebration_title)
    if not query or any(
        ferial in query.lower()
        for ferial in ("monday of", "tuesday of", "wednesday of", "thursday of", "friday of", "saturday of", "sunday in")
    ):
        return ""

    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        # 1. Direct REST page summary
        direct_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(query.replace(' ', '_'))}"
        resp = client.get(direct_url)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("type") != "disambiguation" and data.get("extract"):
                return _trim_sentences(str(data["extract"]))

        # 2. Search fallback for saints whose Wikipedia title includes a suffix (e.g. "Agnes of Rome")
        search_resp = client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"{query} Catholic saint",
                "srlimit": 1,
                "format": "json",
            },
        )
        if search_resp.status_code == 200:
            hits = search_resp.json().get("query", {}).get("search") or []
            if hits:
                title = str(hits[0].get("title", "")).strip()
                if title:
                    summary_resp = client.get(
                        f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}"
                    )
                    if summary_resp.status_code == 200 and summary_resp.json().get("extract"):
                        return _trim_sentences(str(summary_resp.json()["extract"]))
    return ""


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


def parse_vatican_news_html(html: str) -> tuple[list[Reading], str]:
    """Extract official daily Mass readings and 'The words of the Popes' from Vatican News HTML."""
    soup = BeautifulSoup(html, "html.parser")
    readings: list[Reading] = []
    papal_reflection = ""

    for sec in soup.select("section.section--evidence"):
        head = sec.select_one("h2")
        content = sec.select_one(".section__content")
        if not head or not content:
            continue
        heading = head.get_text(" ", strip=True).lower()
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in content.select("p")
            if p.get_text(strip=True)
        ]
        if not paragraphs:
            raw_lines = [line.strip() for line in content.get_text("\n", strip=True).splitlines() if line.strip()]
            paragraphs = raw_lines
        if not paragraphs:
            continue

        if "popes" in heading:
            papal_reflection = "\n\n".join(paragraphs)
            continue

        if "reading of the day" in heading or "gospel of the day" in heading:
            label = "Gospel" if "gospel" in heading else "First Reading"
            # First paragraph(s) on Vatican News hold the intro + verse citation (e.g. "From the Gospel... 25:31-46")
            first_line = paragraphs[0]
            if len(paragraphs) >= 3 and re.search(r"\d+:\d+", paragraphs[1]):
                citation = f"{first_line} {paragraphs[1]}".strip()
                body = "\n\n".join(paragraphs[2:]).strip()
            elif len(paragraphs) >= 2:
                citation = first_line
                body = "\n\n".join(paragraphs[1:]).strip()
            else:
                citation = ""
                body = first_line
            if body:
                readings.append(Reading(label=label, citation=citation, text=body))

    return readings, papal_reflection


def fetch_vatican_news_readings(target_date: dt.date, timeout: float = 12.0) -> tuple[list[Reading], str]:
    """Fetch official daily Mass readings & Papal reflection from Vatican News Word of the Day."""
    url = (
        f"https://www.vaticannews.va/en/word-of-the-day/"
        f"{target_date.year}/{target_date.month:02d}/{target_date.day:02d}.html"
    )
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return parse_vatican_news_html(resp.text)


def fetch_lectionary_citations(target_date: dt.date, timeout: float = 10.0) -> dict[str, str]:
    """Fetch official daily lectionary citations (First Reading, Psalm, Second Reading, Gospel)."""
    url = (
        f"https://cpbjr.github.io/catholic-readings-api/readings/"
        f"{target_date.year}/{target_date.month:02d}-{target_date.day:02d}.json"
    )
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return dict(data.get("readings") or {})


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


def _strip_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text("\n", strip=True)
    return re.sub(r"\n{2,}", "\n\n", text).strip()


def parse_universalis_jsonp(raw_jsonp: str) -> tuple[str, list[Reading]]:
    """Parse Universalis `jsonpmass.js` payload into a liturgical title and Mass readings."""
    start = raw_jsonp.find("{")
    end = raw_jsonp.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return "", []
    payload = json.loads(raw_jsonp[start : end + 1])

    title = _strip_html(str(payload.get("day", "")))
    mapping = [
        ("Mass_R1", "First Reading"),
        ("Mass_Ps", "Responsorial Psalm"),
        ("Mass_R2", "Second Reading"),
        ("Mass_G", "Gospel"),
    ]
    readings: list[Reading] = []
    for key, label in mapping:
        section = payload.get(key)
        if not isinstance(section, dict):
            continue
        citation = _strip_html(str(section.get("source", "")))
        text = _strip_html(str(section.get("text", "")))
        if text:
            readings.append(Reading(label=label, citation=citation, text=text))
    return title, readings


def fetch_universalis_readings(target_date: dt.date, timeout: float = 12.0) -> tuple[str, list[Reading]]:
    """Secondary live lectionary source via Universalis JSONP if USCCB is unreachable or changes HTML."""
    slug = target_date.strftime("%Y%m%d")
    url = f"https://universalis.com/{slug}/jsonpmass.js"
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return parse_universalis_jsonp(resp.text)


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
    papal_reflection = ""

    try:
        season, celebration_title, saint = fetch_calapi_day(resolved_date)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CalAPI fetch failed for %s: %s", resolved_date, exc)

    if saint is not None and saint.title:
        try:
            bio = fetch_saint_biography(saint.title)
            if bio:
                saint.summary = bio
        except Exception as exc:  # noqa: BLE001
            logger.debug("Saint biography enrichment skipped for %s: %s", saint.title, exc)

    # Primary live source: Official Vatican News Word of the Day (open, reliable, includes Papal commentary)
    try:
        readings, papal_reflection = fetch_vatican_news_readings(resolved_date)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vatican News fetch failed for %s: %s", resolved_date, exc)

    # Enrich with Psalm / Second Reading citations from catholic-readings-api if present
    if readings:
        try:
            cites = fetch_lectionary_citations(resolved_date)
            existing_labels = {r.label.lower() for r in readings}
            if cites.get("psalm") and "responsorial psalm" not in existing_labels:
                readings.insert(
                    1,
                    Reading(
                        label="Responsorial Psalm",
                        citation=cites["psalm"],
                        text=f"Lectionary citation for today's Responsorial Psalm: {cites['psalm']}.",
                    ),
                )
            if cites.get("secondReading") and "second reading" not in existing_labels:
                insert_idx = max(len(readings) - 1, 1)
                readings.insert(
                    insert_idx,
                    Reading(
                        label="Second Reading",
                        citation=cites["secondReading"],
                        text=f"Lectionary citation for today's Second Reading: {cites['secondReading']}.",
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Lectionary citation enrichment skipped for %s: %s", resolved_date, exc)

    # Secondary fallback: USCCB HTML
    if not readings:
        try:
            usccb_title, readings = fetch_usccb_readings(resolved_date)
            if usccb_title and not celebration_title:
                celebration_title = usccb_title
        except Exception as exc:  # noqa: BLE001
            logger.warning("USCCB fetch failed for %s: %s", resolved_date, exc)

    if not readings:
        try:
            uni_title, readings = fetch_universalis_readings(resolved_date)
            if uni_title and not celebration_title:
                celebration_title = uni_title
        except Exception as exc:  # noqa: BLE001
            logger.warning("Universalis fallback fetch failed for %s: %s", resolved_date, exc)

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
        papal_reflection=papal_reflection,
        source="live",
    )
    save_cached_day(cache_dir, day)
    return day
