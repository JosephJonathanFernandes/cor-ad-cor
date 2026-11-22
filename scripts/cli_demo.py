"""Interactive Phase 1 CLI runner for daily briefing and personal check-in."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.services.companion import CompanionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Cor ad Cor Phase 1 CLI Demo")
    parser.add_argument("--date", type=dt.date.fromisoformat, default=None, help="YYYY-MM-DD")
    parser.add_argument("--offline", action="store_true", help="Use offline liturgical sample")
    parser.add_argument(
        "--checkin",
        type=str,
        default="",
        help="Optional personal check-in sentence to reflect on with today's readings",
    )
    args = parser.parse_args()

    settings = get_settings()
    service = CompanionService.from_settings(settings)

    print("=" * 60)
    print("Cor ad Cor — Daily Mass Companion (Phase 1)")
    print("=" * 60)

    if args.checkin:
        reply = service.personal_checkin(
            user_message=args.checkin,
            target_date=args.date,
            offline=args.offline,
        )
    else:
        reply = service.daily_briefing(target_date=args.date, offline=args.offline)

    print(f"Date: {reply.liturgy.date} | Season: {reply.liturgy.season}")
    print(f"Celebration: {reply.liturgy.celebration_title}")
    if reply.llm:
        print(f"Served by: {reply.llm.provider} ({reply.llm.key_slot}, model={reply.llm.model})")
    print("\nRetrieved CCC Citations:", ", ".join(h.citation for h in reply.ccc_hits))
    print("-" * 60)
    print(reply.reflection)


if __name__ == "__main__":
    main()
