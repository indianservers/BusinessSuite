"""Real HTTP QA against an isolated temporary database. No worker or application DB."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
qa_port=1547 if "--approvals" in sys.argv else 1545
qa_directory = tempfile.TemporaryDirectory(prefix="power-studio-qa-")
os.environ.update(ENVIRONMENT="test", DEBUG="false", DATABASE_URL="sqlite:///" + str(Path(qa_directory.name) / "qa.db"), SECRET_KEY=secrets.token_urlsafe(48), REFRESH_SECRET_KEY=secrets.token_urlsafe(48), SECRET_KEY_PREVIOUS="", REFRESH_SECRET_KEY_PREVIOUS="", INSTALLED_APPS="hrms,crm,project_management,srm,fam", STORAGE_BACKEND="local", UPLOAD_DIR=str(Path(qa_directory.name) / "uploads"), OPENAI_API_KEY="", ANTHROPIC_API_KEY="", GEMINI_API_KEY="", BUSINESSSUITE_BACKUP_SCHEDULER="false", SEED_DEMO_DATA="false")
from app.main import app
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.company import Company
from app.models.user import User, Role, Permission
from app.common.models import CommonPerson
from app.access.models import AccessPolicy
from app.apps.power_apps.models import PowerEnvironment
from app.apps.power_apps.registry import PERMISSIONS
from app.core.security import create_access_token
from app.apps.business_os.services.module_service import ensure_business_os_seed
from sqlalchemy import event

@event.listens_for(engine, "connect")
def sqlite_configuration(connection, record):
    cursor = connection.cursor(); cursor.execute("PRAGMA journal_mode=WAL"); cursor.execute("PRAGMA busy_timeout=5000"); cursor.close()

request_lock = asyncio.Lock()
@app.middleware("http")
async def isolated_sqlite_requests(request, call_next):
    async with request_lock:
        return await call_next(request)

Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add_all([Company(id=1, name="Studio QA Alpha", is_active=True), Company(id=2, name="Studio QA Beta", is_active=True)])
    permissions = [Permission(name=name, module="power_apps") for name in PERMISSIONS]
    role = Role(name="power_builder", permissions=permissions)
    viewer = Role(name="power_viewer", permissions=[p for p in permissions if p.name in {"power_apps_view", "power_apps_activity_view"}])
    db.add_all([role, viewer]); db.flush()
    users = []
    for index, company in enumerate([1, 1, 2, 1] if "--approvals" in sys.argv else [1, 1, 2]):
        user = User(email=f"studio{index}@qa.invalid", hashed_password="no-password-login", is_active=True, is_superuser=False, role=viewer if index == 1 else role, person=CommonPerson(organization_id=company, primary_email=f"studio{index}@qa.invalid", display_name=["QA Builder", "QA Reviewer", "QA Other tenant", "QA Approver"][index]))
        db.add(user); users.append(user)
    db.flush()
    db.add(AccessPolicy(user_id=users[1].id, company_id=1, status="active", grants={"power_apps": {"enabled":True,"role":"viewer","permissions":["power_apps_view","power_apps_activity_view"],"actions":["view"],"scope":"organization"}}))
    for company in [1,2]:
        db.add(PowerEnvironment(organization_id=company, key="development", enabled=True))
        ensure_business_os_seed(db, company)
    db.commit()
    manifest = {"api":f"http://127.0.0.1:{qa_port}/api/v1", "users":[{"id":u.id,"email":u.email,"role":u.role.name,"is_superuser":False,"token":create_access_token(str(u.id))} for u in users]}
    target = Path(__file__).resolve().parents[2] / (".tmp/power-approvals-live-session.json" if "--approvals" in sys.argv else ".tmp/power-studio-live-session.json")
    target.parent.mkdir(exist_ok=True); target.write_text(json.dumps(manifest), encoding="utf-8")
if '--runtime' in sys.argv:
    from contextlib import asynccontextmanager, suppress
    from app.apps.power_apps.worker import worker_tick
    original_lifespan=app.router.lifespan_context
    def qa_worker_tick():
        with SessionLocal() as db:worker_tick(db,'isolated-runtime-browser-worker')
    async def qa_loop():
        while True:
            async with request_lock:
                await asyncio.to_thread(qa_worker_tick)
            await asyncio.sleep(.2)
    @asynccontextmanager
    async def runtime_lifespan(application):
        async with original_lifespan(application):
            task=asyncio.create_task(qa_loop())
            try:yield
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):await task
    app.router.lifespan_context=runtime_lifespan

print("Isolated Power Apps QA API ready on 127.0.0.1:1545", flush=True)
import uvicorn
try:
    uvicorn.run(app,host="127.0.0.1",port=qa_port,log_level="warning")
finally:
    target.unlink(missing_ok=True)
    engine.dispose()
    qa_directory.cleanup()
