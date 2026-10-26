"""Retire known fixture credentials, preserving linked business and audit records.

Defaults to a read-only preview. Use --apply after checking the target and a real
replacement administrator. Never prints passwords, tokens or connection strings.
"""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text, bindparam, inspect
from sqlalchemy.engine import make_url
from passlib.context import CryptContext
from app.db.demo_account_registry import DEMO_ACCOUNT_EMAILS


def retire(connection, replacement_admin, *, apply=False):
    emails = sorted(DEMO_ACCOUNT_EMAILS | {"admin@platform.local"})
    owner = connection.execute(text("SELECT id, email, is_active, is_superuser FROM users WHERE lower(email)=:email"), {"email":replacement_admin.strip().lower()}).mappings().first()
    if not owner or not owner["is_active"] or not owner["is_superuser"] or owner["email"].lower() in emails:
        raise RuntimeError("A real active replacement Super Admin must exist before retiring fixture accounts")
    statement = text("SELECT id, email, is_active FROM users WHERE lower(email) IN :emails ORDER BY id").bindparams(bindparam("emails", expanding=True))
    rows = connection.execute(statement, {"emails": emails}).mappings().all()
    report = {"matched":len(rows), "active_before":sum(bool(row["is_active"]) for row in rows), "applied":apply, "replacement_admin_preserved":True, "sessions_revoked":0, "mfa_methods_removed":0}
    if not apply or not rows:
        return report
    context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    ids = [row["id"] for row in rows]
    for row in rows:
        # A random, valid password hash keeps authentication failures uniform;
        # its generated secret is discarded and cannot be recovered or reused.
        connection.execute(text("UPDATE users SET hashed_password=:hash, is_active=false, is_superuser=false, role_id=NULL, password_reset_token=NULL, password_reset_expires=NULL, mfa_enabled=false, mfa_enforced_at=NULL, sso_provider_id=NULL WHERE id=:id"), {"hash":context.hash(secrets.token_urlsafe(32)), "id":row["id"]})
    tables = set(inspect(connection).get_table_names())
    if "user_sessions" in tables:
        statement = text("SELECT id FROM user_sessions WHERE user_id IN :ids").bindparams(bindparam("ids", expanding=True))
        sessions = connection.execute(statement,{"ids":ids}).scalars().all()
        for ident in sessions:
            connection.execute(text("UPDATE user_sessions SET status='revoked', trusted_device=false, session_token_hash=:hash WHERE id=:id"), {"hash":hashlib.sha256(secrets.token_bytes(32)).hexdigest(),"id":ident})
        report["sessions_revoked"] = len(sessions)
    if "mfa_methods" in tables:
        statement=text("DELETE FROM mfa_methods WHERE user_id IN :ids").bindparams(bindparam("ids", expanding=True))
        report["mfa_methods_removed"] = connection.execute(statement,{"ids":ids}).rowcount
    remaining=connection.execute(text("SELECT count(*) FROM users WHERE lower(email) IN :emails AND is_active=true").bindparams(bindparam("emails",expanding=True)),{"emails":emails}).scalar_one()
    if remaining:
        raise RuntimeError("Fixture credential retirement did not complete")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file",type=Path)
    parser.add_argument("--require-admin",required=True)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    if args.env_file:
        from dotenv import dotenv_values
        raw=dotenv_values(args.env_file).get("DATABASE_URL")
        if not raw: raise RuntimeError("Selected environment file has no DATABASE_URL")
    else:
        from app.core.config import settings
        raw=settings.SQLALCHEMY_DATABASE_URI
    url=make_url(raw)
    if url.get_backend_name() not in {"postgresql","postgres"}:
        raise RuntimeError("This operational command requires PostgreSQL")
    engine=create_engine(url.set(drivername="postgresql+psycopg"),connect_args={"connect_timeout":15},pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            report=retire(connection,args.require_admin,apply=args.apply)
        print(json.dumps({"database_host":url.host,**report}))
    finally:
        engine.dispose()

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        # Driver errors can contain secrets in their messages. Keep output bounded.
        print(json.dumps({"status":"failed", "type":type(exc).__name__, "message":str(exc) if isinstance(exc,RuntimeError) else "Database operation failed; no connection details printed"}))
        raise SystemExit(1)
