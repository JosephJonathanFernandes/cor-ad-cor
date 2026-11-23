"""Liturgical Month Calendar view (upcoming Sundays, Solemnities, and Feast days with local cache)."""

from __future__ import annotations

import calendar
import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_FIXED_SOLEMNITIES: dict[tuple[int, int], tuple[str, str]] = {
    (1, 1): ("Solemnity of Mary, Mother of God", "white"),
    (1, 6): ("Epiphany of the Lord", "white"),
    (3, 19): ("Solemnity of Saint Joseph", "white"),
    (3, 25): ("Annunciation of the Lord", "white"),
    (6, 24): ("Nativity of Saint John the Baptist", "white"),
    (6, 29): ("Saints Peter and Paul, Apostles", "red"),
    (8, 15): ("Assumption of the Blessed Virgin Mary", "white"),
    (11, 1): ("All Saints' Day", "white"),
    (11, 2): ("All Souls' Day", "violet"),
    (12, 8): ("Immaculate Conception of the Blessed Virgin Mary", "white"),
    (12, 25): ("Nativity of the Lord (Christmas)", "white"),
}


def build_offline_month_calendar(year: int, month: int) -> list[dict[str, Any]]:
    """Generate a clean fallback month calendar highlighting Sundays and major fixed feasts."""
    _, num_days = calendar.monthrange(year, month)
    days: list[dict[str, Any]] = []
    for day_num in range(1, num_days + 1):
        d = dt.date(year, month, day_num)
        fixed = _FIXED_SOLEMNITIES.get((month, day_num))
        if fixed:
            title, colour = fixed
            rank = "solemnity"
        elif d.weekday() == 6:
            title = "Sunday in the Liturgical Year"
            colour = "green"
            rank = "sunday"
        else:
            title = "Ferial Weekday"
            colour = "green"
            rank = "ferial"
        days.append(
            {
                "date": d.isoformat(),
                "day": day_num,
                "weekday": d.strftime("%a"),
                "title": title,
                "rank": rank,
                "colour": colour,
                "is_sunday": d.weekday() == 6,
                "is_major": rank in ("solemnity", "feast", "sunday"),
            }
        )
    return days


def parse_calapi_month_payload(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize CalAPI's monthly JSON array into compact calendar day objects."""
    days: list[dict[str, Any]] = []
    for item in payload:
        date_str = str(item.get("date", "")).strip()
        if not date_str:
            continue
        d = dt.date.fromisoformat(date_str)
        celebrations = item.get("celebrations") or []
        primary = celebrations[0] if celebrations else {}
        title = str(primary.get("title") or "Ferial Weekday").strip()
        rank = str(primary.get("rank") or "ferial").strip().lower()
        colour = str(primary.get("colour") or "green").strip().lower()
        days.append(
            {
                "date": date_str,
                "day": d.day,
                "weekday": d.strftime("%a"),
                "title": title,
                "rank": rank,
                "colour": colour,
                "is_sunday": d.weekday() == 6,
                "is_major": d.weekday() == 6 or any(r in rank for r in ("solemnity", "feast")),
            }
        )
    return days


def get_liturgical_month(
    year: int,
    month: int,
    *,
    cache_dir: Path,
    offline: bool = False,
) -> dict[str, Any]:
    """Return a month's liturgical calendar using local cache, CalAPI, or offline fallback."""
    cal_dir = cache_dir / "calendar"
    cache_file = cal_dir / f"{year:04d}-{month:02d}.json"

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if offline or cached.get("source") == "live":
                return cached
        except Exception:  # noqa: BLE001
            pass

    if not offline:
        url = f"http://calapi.inadiutorium.cz/api/v0/en/calendars/default/{year}/{month}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                days = parse_calapi_month_payload(resp.json())
            if days:
                result = {
                    "year": year,
                    "month": month,
                    "month_name": calendar.month_name[month],
                    "source": "live",
                    "days": days,
                }
                cal_dir.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
                return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("CalAPI month fetch failed for %04d-%02d: %s", year, month, exc)

    return {
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "source": "offline_fallback",
        "days": build_offline_month_calendar(year, month),
    }
