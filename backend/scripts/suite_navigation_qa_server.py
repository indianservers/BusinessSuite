"""Loopback-only UI verification against disposable SQLite, never the app database."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import secrets
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
temporary = tempfile.TemporaryDirectory(prefix="suite-navigation-qa-")
os.environ.update(
    ENVIRONMENT="test", DEBUG="false",
    DATABASE_URL="sqlite:///" + str(Path(temporary.name) / "navigation.db"),
    SECRET_KEY=secrets.token_urlsafe(48), REFRESH_SECRET_KEY=secrets.token_urlsafe(48),
    SECRET_KEY_PREVIOUS="", REFRESH_SECRET_KEY_PREVIOUS="",
    INSTALLED_APPS="hrms,crm,project_management,srm,fam,power_apps",
    STORAGE_BACKEND="local", UPLOAD_DIR=str(Path(temporary.name) / "uploads"),
    OPENAI_API_KEY="", ANTHROPIC_API_KEY="", GEMINI_API_KEY="",
    MAIL_USERNAME="", MAIL_PASSWORD="", MAIL_SERVER="",
    FIREBASE_PROJECT_ID="", FIREBASE_WEB_CONFIG="{}",
    BUSINESSSUITE_BACKUP_SCHEDULER="false", SEED_DEMO_DATA="false",
    SECURITY_RATE_LIMIT_ENABLED="false",
)
from app.main import app
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.company import Company
from app.models.user import User, Role
from app.models.notification import Notification
from app.common.models import CommonPerson
from app.access.models import AccessMembership, AccessPolicy
from app.apps.business_os.services.module_service import ensure_business_os_seed
from app.core.security import get_password_hash, pwd_context
from app.api.v1.auth import _hash_reset_token

pwd_context.update(bcrypt__rounds=4)
Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add_all([Company(id=1, name="Indian Servers", is_active=True), Company(id=2, name="Studio Operations", is_active=True)])
    admin_role, employee_role = Role(name="admin"), Role(name="employee")
    db.add_all([admin_role, employee_role]); db.flush()
    users = []
    for email, role, superuser in [("admin@suiteqa.example.com", admin_role, True), ("employee@suiteqa.example.com", employee_role, False), ("reset@suiteqa.example.com", employee_role, False)]:
        user = User(email=email, hashed_password=get_password_hash("SuiteQA@12345"), is_active=True, is_superuser=superuser, role=role,
                    person=CommonPerson(organization_id=1, primary_email=email, display_name=email.split("@")[0].title()))
        db.add(user); users.append(user)
    db.flush()
    db.add(AccessMembership(user_id=users[0].id, company_id=2, active=True, is_admin=True))
    db.add(AccessPolicy(user_id=users[1].id, company_id=1, status="active", grants={"hrms": {"enabled": True, "role": "employee", "scope": "own", "permissions": ["employee_view", "profile_view"], "actions": ["view"]}}))
    users[2].password_reset_token = _hash_reset_token("suite-qa-reset-token")
    users[2].password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    for device in ["desktop", "mobile"]:
        reset_user = User(email=f"reset-{device}@suiteqa.example.com", hashed_password=get_password_hash("SuiteQA@12345"), is_active=True, role=employee_role,
                          person=CommonPerson(organization_id=1, primary_email=f"reset-{device}@suiteqa.example.com", display_name="Reset QA"),
                          password_reset_token=_hash_reset_token(f"suite-qa-reset-{device}-token"), password_reset_expires=datetime.now(timezone.utc) + timedelta(hours=1))
        db.add(reset_user)
    for user in users[:2]:
        for module, url, title, company in [("hrms", "/hrms/profile", "Profile update available", 1), ("crm", "/crm/contacts", "Review your contacts", 1), ("fam", "/fam/ledgers", "Finance update", 1), ("hrms", "/hrms/profile", "Other company private update", 2)]:
            db.add(Notification(user_id=user.id, company_id=company, module=module, action_url=url, title=title, message="A QA notification for navigation verification.", priority="normal", channels=["in_app"], is_read=False))
    for company in [1, 2]: ensure_business_os_seed(db, company)
    db.commit()

# These navigation tests do not need schedulers, external workers, or production
# startup migrations. All tables and test users were created above.
@asynccontextmanager
async def qa_lifespan(application):
    yield
app.router.lifespan_context = qa_lifespan
request_lock = asyncio.Lock()
@app.middleware("http")
async def sqlite_requests(request, call_next):
    async with request_lock:
        return await call_next(request)

if __name__ == "__main__":
    import uvicorn
    try: uvicorn.run(app, host="127.0.0.1", port=1551, log_level="warning")
    finally:
        engine.dispose()
        temporary.cleanup()
