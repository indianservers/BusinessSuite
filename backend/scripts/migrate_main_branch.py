"""Rehearse/apply an explicitly approved Main Branch mapping on local Postgres."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.db.base import Base
from app.db.session import engine
from app.models.user import User
from app.branches.models import BranchAudit
from app.branches.default_migration import assign_default, reconcile_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument("--branch-id", type=int, required=True)
    parser.add_argument("--actor-id", type=int, required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if engine.url.get_backend_name() != "postgresql" or engine.url.host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("This approved migration runner is restricted to local PostgreSQL")
    if len(args.reason.strip()) < 5:
        raise RuntimeError("An explicit migration reason is required")
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        transaction = connection.begin()
        try:
            actor_row = connection.execute(select(User.__table__).where(User.id == args.actor_id)).mappings().one()
            actor = SimpleNamespace(id=actor_row["id"], is_active=actor_row["is_active"], is_superuser=actor_row["is_superuser"])
            before = reconcile_snapshot(connection)
            report = assign_default(connection, args.company_id, args.branch_id, actor=actor)
            after = reconcile_snapshot(connection)
            differences = [name for name in before if before[name] != after[name]]
            fingerprint = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
            report.update(mode="apply" if args.apply else "dry-run", created_at=datetime.now(timezone.utc).isoformat(), reason=args.reason,
                          reconciliation={"tables": len(before), "counts_totals_and_links_match": not differences, "differences": differences, "before_digest": fingerprint(before), "after_digest": fingerprint(after)})
            if differences:
                raise RuntimeError("Counts, amounts or business links changed; rolling back")
            if args.apply:
                connection.execute(BranchAudit.__table__.insert().values(company_id=args.company_id, actor_id=actor.id, operation="branch.ownership.approved_default", reason=args.reason, details=report))
                transaction.commit()
            else:
                transaction.rollback()
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({key: value for key, value in report.items() if key not in {"assigned", "inferred", "held"}}, indent=2))
        except BaseException:
            if transaction.is_active: transaction.rollback()
            raise


if __name__ == "__main__": main()
