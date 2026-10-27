"""Run pending workforce and assignment chunks on a persistent worker host.

Uses the application's configured database. --once performs one bounded tick.
Do not use this as an unbounded serverless HTTP handler.
"""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=2)
    args = parser.parse_args()
    if args.interval < 1:
        parser.error("--interval must be at least one second")
    from app.db.base import Base  # noqa: F401
    from app.db.session import SessionLocal
    from app.apps.interns_hub.operations import scheduled_tick
    from app.apps.interns_hub.distribution import scheduled_tick as assignments_tick
    from app.apps.interns_hub.router import today
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            with SessionLocal() as db:
                result = scheduled_tick(db)
                assignments = assignments_tick(db, today())
                if result["chunks"] or assignments["distribution_chunks"] or assignments["schedule_errors"]:
                    logging.info("workforce=%s assignments=%s", result, assignments)
        except Exception:
            logging.exception("Workforce tick failed; pending work will be retried")
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
