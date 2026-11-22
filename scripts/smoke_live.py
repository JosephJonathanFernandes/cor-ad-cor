"""Live smoke test for real-world liturgical sources (CalAPI, USCCB, Universalis, Wikipedia Saint Bio)."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.data_sources.liturgy import (
    fetch_calapi_day,
    fetch_saint_biography,
    fetch_universalis_readings,
    fetch_usccb_readings,
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
                print(f"[PASS] Saint Bio ({saint.title}): {bio[:140]}...")
            else:
                print(f"[INFO] Saint Bio: no Wikipedia summary found for {saint.title!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] CalAPI: {type(exc).__name__}: {exc}")

    try:
        usccb_title, usccb_readings = fetch_usccb_readings(target)
        print(f"[PASS] USCCB: title={usccb_title!r}, readings={len(usccb_readings)}")
        for r in usccb_readings:
            print(f"       - {r.label} ({r.citation}): {len(r.text)} chars")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] USCCB: {type(exc).__name__}: {exc}")

    try:
        uni_title, uni_readings = fetch_universalis_readings(target)
        print(f"[PASS] Universalis: title={uni_title!r}, readings={len(uni_readings)}")
        for r in uni_readings:
            print(f"       - {r.label} ({r.citation}): {len(r.text)} chars")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Universalis: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
