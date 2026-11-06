"""Provision the explicitly requested LOCAL platform store and migrate its queue.

Run from backend: venv/Scripts/python scripts/setup_local_platform_owner.py
Uses the existing privileged local connection only during setup. Runtime roles
have separate random passwords and cannot connect to each other's database.
"""
from pathlib import Path
import sys
import secrets
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from psycopg import sql, connect
from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.platform_owner.models import PlatformAdmin, PlatformSignupRequest, PlatformAudit
from app.access.models import SignupRequest as LegacySignup
from app.models.user import User
from app.db.base import Base  # Register customer relationships before querying users.


def main():
    source_url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if source_url.host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("This setup command only operates on local PostgreSQL")
    if settings.PLATFORM_DATABASE_URL:
        raise RuntimeError("Already configured; use alembic_platform.ini for subsequent migrations")
    admin_engine = create_engine(source_url)
    with Session(admin_engine) as source:
        bootstrap = source.query(User).filter_by(email=settings.BOOTSTRAP_ADMIN_EMAIL, is_active=True, is_superuser=True).one()
        password_hash, old_admin_id = bootstrap.hashed_password, bootstrap.id
        legacy = source.query(LegacySignup).all()
        if any(row.reviewed_by not in {None, old_admin_id} for row in legacy):
            raise RuntimeError("Legacy reviewers need explicit platform identity mapping")
        snapshots = [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in legacy]
    platform_password, customer_password = secrets.token_urlsafe(36), secrets.token_urlsafe(36)
    role_owner, role_customer = "indian_servers_owner", "business_suite_runtime"
    db_owner = "indian_servers_platform"
    with connect(source_url.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True) as connection:
        for role, password in [(role_owner, platform_password), (role_customer, customer_password)]:
            exists = connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
            if exists:
                raise RuntimeError(f"Role {role} already exists; inspect setup before retrying")
            connection.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT").format(sql.Identifier(role), sql.Literal(password)))
        connection.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(db_owner), sql.Identifier(role_owner)))
        connection.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(sql.Identifier(db_owner)))
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(source_url.database), sql.Identifier(role_customer)))
        # Platform runtime must not be able to enter the business database either.
        connection.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(sql.Identifier(source_url.database)))
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role_customer)))
        connection.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(role_customer)))
        connection.execute(sql.SQL("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {}").format(sql.Identifier(role_customer)))
        connection.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}").format(sql.Identifier(role_customer)))
        connection.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {}").format(sql.Identifier(role_customer)))
    owner_url = source_url.set(username=role_owner, password=platform_password, database=db_owner)
    customer_url = source_url.set(username=role_customer, password=customer_password)
    settings.PLATFORM_DATABASE_URL = owner_url.render_as_string(hide_password=False)
    settings.PLATFORM_SECRET_KEY = secrets.token_urlsafe(64)
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic_platform.ini")), "head")
    owner_engine = create_engine(owner_url)
    with Session(owner_engine) as target:
        admin = PlatformAdmin(email="owner@indianservers.com", hashed_password=password_hash)
        target.add(admin); target.flush()
        for snapshot in snapshots:
            if snapshot["reviewed_by"]:
                snapshot["reviewed_by"] = admin.id
            target.add(PlatformSignupRequest(**snapshot))
            if snapshot["status"] in {"approved", "rejected"}:
                target.add(PlatformAudit(signup_id=snapshot["id"], admin_id=admin.id,
                    decision="approve" if snapshot["status"] == "approved" else "reject",
                    reason=snapshot["review_reason"] or "Migrated legacy review"))
        target.commit()
        target.execute(text("SELECT setval(pg_get_serial_sequence('platform_signup_requests','id'), COALESCE((SELECT max(id) FROM platform_signup_requests),1), EXISTS(SELECT 1 FROM platform_signup_requests))"))
        target.commit()
        copied = target.query(PlatformSignupRequest).count()
        if copied != len(snapshots):
            raise RuntimeError("Signup migration count mismatch")
    # Empty the retired queue only after a successful, verified owner DB commit.
    with admin_engine.begin() as connection:
        connection.execute(text("DELETE FROM suite_signup_requests"))
    env_path = Path(__file__).resolve().parents[1] / ".env"
    content = env_path.read_text(encoding="utf-8")
    changes = {"DATABASE_URL": customer_url.render_as_string(hide_password=False),
               "DATABASE_AUTO_MIGRATE": "false",
               "PLATFORM_DATABASE_URL": settings.PLATFORM_DATABASE_URL,
               "PLATFORM_SECRET_KEY": settings.PLATFORM_SECRET_KEY}
    lines = content.splitlines()
    for key, value in changes.items():
        lines = [line for line in lines if not line.startswith(key + "=")]
        lines.append(key + "='" + value + "'")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Created {db_owner}; migrated {copied} signups; independent runtime roles configured.")
    print("Platform login: owner@indianservers.com (existing local bootstrap password).")


if __name__ == "__main__":
    main()
