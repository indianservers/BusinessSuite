"""Local-only recurring invoice worker; refuses remote and production databases."""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def tick():
    from app.core.config import settings
    from sqlalchemy.engine import make_url
    target = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if target.get_backend_name() != "sqlite" and target.host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Local scheduler requires a loopback database")
    if settings.SERVERLESS or settings.ENVIRONMENT.lower() == "production":
        raise RuntimeError("Local scheduler cannot run in production")
    from app.main import app  # Register the complete ORM model graph without starting HTTP workers.
    from app.db.session import SessionLocal
    from app.apps.srm.services.recurring_jobs import dispatch_due
    with SessionLocal() as db:
        result = dispatch_due(db)
        from app.apps.fam.recurring_purchases import dispatch_due as purchase_drafts_due
        result['recurring_purchases'] = purchase_drafts_due(db)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        try:
            tick()
        except Exception as exc:
            print(json.dumps({"error": type(exc).__name__}), flush=True)
            if args.once: raise SystemExit(1)
        if args.once: break
        time.sleep(60)
