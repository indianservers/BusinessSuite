"""Serve an isolated, seeded localhost workflow sandbox. Never uses an app DB."""
import json
import os
from pathlib import Path
import secrets
import sys
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")


def main():
    import argparse
    import socket
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=1538)
    parser.add_argument("--frontend-port", type=int, default=5198)
    parser.add_argument("--reuse", action="store_true", help="Reuse the existing isolated localhost test database")
    args = parser.parse_args()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    source = make_url(os.environ["WORKFLOW_PG_ADMIN_URL"])
    assert source.host in {"127.0.0.1", "localhost"} and source.get_backend_name() == "postgresql"
    admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    previous = json.loads((ROOT / ".local/workflow-localhost-session.json").read_text()) if args.reuse else None
    database = previous["database"] if previous else "business_suite_workflow_localhost_" + uuid4().hex[:10] + "_test"
    import re
    assert re.fullmatch(r"business_suite_workflow_localhost_[a-f0-9]+_test", database)
    with admin.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote_identifier
        # This template was migrated and tested in the isolated acceptance cluster.
        template = "business_suite_workflow_final_test"
        if not args.reuse:
            connection.exec_driver_sql(f"CREATE DATABASE {quote(database)} TEMPLATE {quote(template)}")
    admin.dispose()
    target = source.set(database=database)
    scheduler_secret = secrets.token_urlsafe(48)
    os.environ["CRON_SECRET"] = scheduler_secret
    os.environ.update(DATABASE_URL=target.render_as_string(hide_password=False), ENVIRONMENT="test", DEBUG="false",
        SECRET_KEY=secrets.token_urlsafe(48), REFRESH_SECRET_KEY=secrets.token_urlsafe(48),
        SECRET_KEY_PREVIOUS="", REFRESH_SECRET_KEY_PREVIOUS="", SERVERLESS="false", SEED_DEMO_DATA="false",
        DATABASE_AUTO_MIGRATE="false", PLATFORM_DATABASE_URL="", TENANT_DATABASES_ENABLED="false",
        TENANT_REGISTRY_URL="", TENANT_PROVISIONING_URL="", TENANT_ALLOW_REMOTE_OPERATIONS="false",
        STORAGE_BACKEND="local", EMAIL_PROVIDER="smtp", MAIL_SERVER="", MAIL_USERNAME="", MAIL_PASSWORD="",
        SES_SMTP_USERNAME="", SES_SMTP_PASSWORD="", INTERN_HUB_SES_ENABLED="false", OPENAI_API_KEY="", ANTHROPIC_API_KEY="")
    os.environ["BACKEND_CORS_ORIGINS"] = json.dumps([f"http://localhost:{args.frontend_port}", f"http://127.0.0.1:{args.frontend_port}"])
    from app.db.migrations import upgrade_schema
    upgrade_schema()
    from app.main import app
    from app.core.deps import get_db
    from app.db.session import SessionLocal
    from app.core.security import get_password_hash
    from app.models.user import User, Permission
    from app.models.company import Company
    from app.access.models import AccessPolicy
    from app.apps.project_management.models import PMSWorkspaceMember
    from tests.rich_text_test_utils import workflow_seed_scope
    from tests.test_pms_transition_approvals import setup_route
    from fastapi.testclient import TestClient
    password = "WorkflowLocal!2026"
    if not args.reuse:
        with SessionLocal() as db:
            def seed_db(): yield db
            app.dependency_overrides[get_db] = seed_db
            app.state.business_os_session_factory = lambda: db
            app.state.business_os_close_session = False
            app.state.audit_session_factory = lambda: db
            app.state.audit_close_session = False
            app.state.audit_commit = False
            try:
                with workflow_seed_scope(db):
                    from app.db.init_db import SYSTEM_PERMISSIONS
                    for name, description, module in SYSTEM_PERMISSIONS:
                        if not db.query(Permission).filter_by(name=name).first():
                            db.add(Permission(name=name, description=description, module=module))
                    db.flush()
                    company = db.get(Company, 1)
                    company.name = "Workflow localhost acceptance (test only)"
                    db.commit()
                    client = TestClient(app)
                    wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme = setup_route(client, db, sequential=True)
                    reviewer = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, role="Admin").one().user_id
                    for user in db.query(User).all(): user.hashed_password = get_password_hash(password)
                    for uid in [reviewer, member.id]:
                        db.add(AccessPolicy(user_id=uid, company_id=1, status="active", version=1, grants={
                            "project_management": {"enabled": True, "role": "Local PMS tester", "scope": "organization",
                                "permissions": ["pms_view", "pms_manage_tasks"], "actions": ["view", "create", "edit", "approve"]}}))
                    db.commit()
                    owner_email = owner.email
            finally:
                app.dependency_overrides.clear()
                for name in ["business_os_session_factory", "business_os_close_session", "audit_session_factory", "audit_close_session", "audit_commit"]:
                    if hasattr(app.state, name): delattr(app.state, name)
    else:
        wid, pid, tid = previous["workspace_id"], previous["project_id"], previous["task_id"]
        owner_email = previous["accounts"]["owner"]
    info = {"api": f"http://127.0.0.1:{args.port}", "frontend": f"http://localhost:{args.frontend_port}",
            "workspace_id": wid, "project_id": pid, "task_id": tid, "database": database,
            "accounts": {"owner": "auto-owner@test.com", "reviewer": "auto-admin@test.com", "requester": "auto-member@test.com"},
            "password": password, "scheduler_secret": scheduler_secret, "scope": "Isolated localhost test database; no production data or mail"}
    (ROOT / ".local/workflow-localhost-session.json").write_text(json.dumps(info, indent=2))
    (ROOT / ".local/workflow-localhost-admin.json").write_text(json.dumps({"login_url": info["frontend"]+"/login", "email": owner_email, "password": password}))
    print(f"Workflow localhost sandbox: {info['frontend']} ; owner auto-owner@test.com ; password WorkflowLocal!2026", flush=True)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
