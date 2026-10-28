"""Backfill pending application receipts: preview by default; --send delivers."""
import argparse
from sqlalchemy import exists
from app.core.config import settings
from app.db.session import SessionLocal
from app.db import base as _models  # Register FK targets for standalone execution.
from app.apps.interns_hub.models import InternApplication
from app.apps.interns_hub.management_models import ApplicationEvent
from app.apps.interns_hub.confirmation_email import ATTEMPTED, send_confirmation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("limit must be from 1 to 1000")
    if args.send and not settings.INTERN_HUB_SES_ENABLED:
        parser.error("Configure SES and enable INTERN_HUB_SES_ENABLED first")
    with SessionLocal() as db:
        items = db.query(InternApplication).filter(
            InternApplication.organization_id == settings.INTERN_HUB_ORGANIZATION_ID,
            InternApplication.status == "Pending",
            ~exists().where(ApplicationEvent.application_id == InternApplication.id,
                            ApplicationEvent.state.in_(ATTEMPTED)),
        ).order_by(InternApplication.id).limit(args.limit).all()
        print(f"Eligible pending applications in this batch: {len(items)}")
        if args.send:
            accepted = sum(send_confirmation(db, item) for item in items)
            print(f"Accepted by SES: {accepted}; not confirmed: {len(items) - accepted}")
        else:
            print("Preview only. Use --send to send confirmations.")


if __name__ == "__main__":
    main()
