"""Run the suite's existing PostgreSQL migrations against an explicitly verified database."""
import argparse
from getpass import getpass
from ipaddress import ip_address
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--expected-address", required=True, type=ip_address)
    parser.add_argument("--port", default=5432, type=int)
    parser.add_argument("--database", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--sslmode", choices=("disable", "verify-full"), required=True)
    parser.add_argument("--sslrootcert")
    parser.add_argument("--bootstrap-admin", metavar="EMAIL",
                        help="Initialize the first company and Suite administrator in an empty database.")
    parser.add_argument("--seed-permission-catalog", action="store_true",
                        help="Add missing canonical permission definitions to an existing database.")
    parser.add_argument("--company-name")
    parser.add_argument("--branch-name", default="Head Office")
    args = parser.parse_args()
    if args.sslmode == "disable" and not args.expected_address.is_loopback:
        parser.error("Use certificate verification for a LAN database.")
    if bool(args.bootstrap_admin) != bool(args.company_name):
        parser.error("--bootstrap-admin and --company-name must be supplied together.")

    if args.bootstrap_admin and args.seed_permission_catalog:
        parser.error("Administrator bootstrap already seeds the permission catalog.")

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL
    from sqlalchemy.exc import SQLAlchemyError

    backend = Path(__file__).resolve().parent
    if not (backend / "alembic.ini").is_file():
        backend = backend.parent / "backend"
    sys.path.insert(0, str(backend))

    password = getpass("PostgreSQL migration role password: ")
    query = {"sslmode": args.sslmode}
    if args.sslrootcert:
        query["sslrootcert"] = str(Path(args.sslrootcert).resolve())
    url = URL.create(
        "postgresql+psycopg", username=args.username, password=password,
        host=args.host, port=args.port, database=args.database, query=query,
    )
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    os.environ["SERVERLESS"] = "false"

    engine = create_engine(url, connect_args={"connect_timeout": 10}, hide_parameters=True)
    try:
        with engine.connect() as connection:
            actual = connection.execute(text(
                "SELECT current_database(), current_user, host(inet_server_addr()), inet_server_port()"
            )).one()
            if (actual[0], actual[1], ip_address(actual[2]), actual[3]) != (
                args.database, args.username, args.expected_address, args.port
            ):
                raise SystemExit("The connected database, role, IP or port differs from the requested target.")
            # The baseline migration opens Alembic autocommit blocks. End the
            # read transaction and let Alembic drive transactions on this connection.
            connection.commit()
            config = Config(str(backend / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            if args.bootstrap_admin:
                with connection.begin():
                    bootstrap(connection, args.bootstrap_admin, args.company_name, args.branch_name)
            elif args.seed_permission_catalog:
                with connection.begin():
                    added = seed_permission_catalog(connection)
                print(f"Added {added} missing permission definitions.")
    except (SQLAlchemyError, OSError) as error:
        raise SystemExit(f"Database setup failed ({type(error).__name__}).") from None
    finally:
        engine.dispose()
        os.environ.pop("DATABASE_URL", None)
    print(f"Schema ready in {args.database} at {args.expected_address}:{args.port}.")


def seed_permission_catalog(connection):
    from sqlalchemy.dialects.postgresql import insert

    from app.apps.power_apps.registry import PERMISSIONS as POWER_APPS_PERMISSIONS
    from app.db.init_db import SYSTEM_PERMISSIONS
    from app.models.user import Permission

    definitions = {
        name: {"name": name, "description": name.replace("_", " "), "module": "power_apps"}
        for name in POWER_APPS_PERMISSIONS
    }
    for name, description, module in SYSTEM_PERMISSIONS:
        definitions.setdefault(name, {"name": name, "description": description, "module": module})
    table = Permission.__table__
    statement = insert(table).values(list(definitions.values())).on_conflict_do_nothing(
        index_elements=[table.c.name]
    ).returning(table.c.id)
    return len(connection.execute(statement).all())


def bootstrap(connection, email, company_name, branch_name):
    from secrets import token_urlsafe

    from email_validator import validate_email
    from sqlalchemy import select, text
    from sqlalchemy.orm import Session

    from app.access.models import AccessMembership
    from app.common.models import CommonPerson
    from app.core.config import settings
    from app.db.init_db import init_db
    from app.models.company import Branch, Company
    from app.models.user import User

    email = validate_email(email, check_deliverability=False).normalized.lower()
    company_name, branch_name = company_name.strip(), branch_name.strip()
    if not (0 < len(company_name) <= 150 and 0 < len(branch_name) <= 150):
        raise SystemExit("Enter company and branch names between 1 and 150 characters.")

    role = connection.execute(text(
        "SELECT rolcanlogin AND NOT rolsuper FROM pg_roles WHERE rolname=:email"
    ), {"email": email}).scalar_one_or_none()
    if role is not True:
        raise SystemExit("Provision a non-superuser PostgreSQL login named after the administrator email first.")

    connection.execute(text("LOCK TABLE public.companies, public.users IN SHARE ROW EXCLUSIVE MODE"))
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        if session.scalar(select(User.id).limit(1)) or session.scalar(select(Company.id).limit(1)):
            raise SystemExit("Administrator bootstrap requires an empty company and user directory.")
        company = Company(name=company_name, legal_name=company_name, is_active=True)
        session.add(company)
        session.flush()
        branch = Branch(name=branch_name, code="HQ", company_id=company.id,
                        organization_id=company.id, is_active=True)
        session.add(branch)
        settings.BOOTSTRAP_ADMIN_EMAIL = email
        # The desktop login authenticates in PostgreSQL. Keep this Suite password
        # separate and random so the bootstrap does not create a web credential.
        settings.BOOTSTRAP_ADMIN_PASSWORD = token_urlsafe(48)
        try:
            init_db(session, seed_demo=False)
        finally:
            settings.BOOTSTRAP_ADMIN_EMAIL = settings.BOOTSTRAP_ADMIN_PASSWORD = ""
        actor = session.scalar(select(User).where(User.email == email))
        person = session.scalar(select(CommonPerson).where(CommonPerson.user_id == actor.id))
        person.organization_id = company.id
        session.add(AccessMembership(company_id=company.id, user_id=actor.id, active=True, is_admin=True))
        session.commit()
        print(f"Initialized company {company.id} and branch {branch.id} for {email}.")


if __name__ == "__main__":
    main()
