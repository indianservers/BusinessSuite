"""Preview or apply evidence-only ownership repair; never guess a default branch.

Uses the configured database and rolls back unless --apply is specified.
Reports counts only, with no business records or credentials.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def repair(connection, company, table_names=None):
    from sqlalchemy import select, literal, exists, union_all
    from app.db.base import Base
    from app.models.company import Company
    from app.branches.catalog import SHARED
    from app.branches.migration import backfill

    if not connection.execute(select(Company.id).where(Company.id == company, Company.is_active.is_(True))).first():
        raise RuntimeError("An active company is required")
    tables = [table for table in Base.metadata.tables.values() if table.name not in SHARED and (table_names is None or table.name in table_names)]
    if not tables:
        return {}
    # One round trip instead of querying hundreds of empty module tables on
    # every inference pass. EXISTS does not scan entire populated tables.
    populated = set(connection.execute(union_all(*[
        select(literal(table.name)).where(exists(select(1).select_from(table)))
        for table in tables
    ])).scalars())
    return backfill(connection, company, table_names=populated)


def main():
    from sqlalchemy import create_engine, text
    from app.db.base import Base  # Register all relationships before ORM queries.
    from app.core.config import settings
    from app.models.company import Company
    from sqlalchemy import select
    from sqlalchemy.engine import make_url
    from app.branches.models import BranchAudit
    from app.models.user import User
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--tables", nargs="+", help="Limit repair to named tables and their existing ownership evidence")
    args = parser.parse_args()
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if url.host and "-pooler." in url.host:
        url = url.set(host=url.host.replace("-pooler.", ".", 1))
    engine = create_engine(url, connect_args={"connect_timeout": 10}, hide_parameters=True)
    with engine.connect() as connection:
        connection.execute(text("SET statement_timeout = '60s'"))
        connection.execute(text("SET lock_timeout = '5s'"))
        connection.execute(text("SELECT pg_advisory_xact_lock(827460233)"))
        name = connection.execute(select(Company.name).where(Company.id == args.company_id)).scalar_one()
        if name != args.company_name:
            raise RuntimeError("Company name does not match; no ownership changed")
        actor = connection.execute(select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True)).order_by(User.id)).scalar()
        if not actor:
            raise RuntimeError("An existing active administrator is required")
        assigned = repair(connection, args.company_id, set(args.tables) if args.tables else None)
        result = {"mode": "apply" if args.apply else "preview", "company_id": args.company_id, "assigned": assigned, "total": sum(assigned.values())}
        if args.apply:
            connection.execute(BranchAudit.__table__.insert().values(company_id=args.company_id, actor_id=actor, operation="branch.ownership.backfill", reason="Repair missing ownership from verified existing branch and parent evidence", details=result))
            connection.commit()
        else:
            connection.rollback()
        print(json.dumps(result), flush=True)
    engine.dispose()


if __name__ == "__main__":
    main()
