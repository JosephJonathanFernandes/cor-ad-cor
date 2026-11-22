"""Live smoke test for real-world liturgical sources (Vatican News, Lectionary API, CalAPI, Wikipedia Saint Bio)."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.data_sources.liturgy import (
    fetch_calapi_day,
    fetch_lectionary_citations,
    fetch_saint_biography,
    fetch_vatican_news_readings,
    get_liturgical_day,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test live liturgical endpoints.")
    parser.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today())
    args = parser.parse_args()
    target = args.date
    print(f"=== Live Liturgical Smoke Test ({target.isoformat()}) ===")

    try:
        season, title, saint = fetch_calapi_day(target)
        print(f"[PASS] CalAPI: season={season!r}, title={title!r}, colour={saint.colour if saint else ''!r}")
        if saint and saint.title:
            bio = fetch_saint_biography(saint.title)
            if bio:
                print(f"[PASS] Saint Bio ({saint.title}): {bio[:130]}...")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] CalAPI: {type(exc).__name__}: {exc}")

    try:
        vn_readings, papal = fetch_vatican_news_readings(target)
        print(f"[PASS] Vatican News: readings={len(vn_readings)}, papal_reflection={len(papal)} chars")
        for r in vn_readings:
            print(f"       - {r.label} ({r.citation}): {len(r.text)} chars")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Vatican News: {type(exc).__name__}: {exc}")

    try:
        cites = fetch_lectionary_citations(target)
        print(f"[PASS] Lectionary Citations API: {cites}")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Lectionary Citations API: {type(exc).__name__}: {exc}")

    settings = get_settings()
    day = get_liturgical_day(target, cache_dir=settings.readings_cache_dir, offline=False)
    print(
        f"[END-TO-END] get_liturgical_day -> source={day.source!r}, "
        f"readings={len(day.readings)}, papal={bool(day.papal_reflection)}"
    )


if __name__ == "__main__":
    main()
