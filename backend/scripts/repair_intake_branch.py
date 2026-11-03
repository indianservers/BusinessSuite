"""Preview or repair unresolved pending intake ownership in one verified company."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from dotenv import dotenv_values
    from sqlalchemy import create_engine, select
    from sqlalchemy.engine import make_url
    from app.db.base import Base
    from app.models.company import Company
    from app.apps.interns_hub.branch_ownership import repair_pending
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    url = make_url(values.get("DATABASE_URL_UNPOOLED") or values["DATABASE_URL"])
    if url.host != args.expected_host or "-pooler" in url.host:
        raise SystemExit("The supplied connection is not the expected direct database")
    url = url.set(drivername="postgresql+psycopg")
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as connection:
        name = connection.execute(select(Company.name).where(Company.id == args.company_id, Company.is_active.is_(True))).scalar_one()
        if name != args.company_name:
            raise SystemExit("Company verification failed; no ownership changed")
        result = repair_pending(connection, args.company_id, apply=args.apply)
        print(json.dumps({"mode": "apply" if args.apply else "preview", **result}))
    engine.dispose()


if __name__ == "__main__":
    main()
