"""Resume an explicitly identified disposable SQLite QA workspace on loopback."""
import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import tempfile

root = Path(os.environ["PROJECTS_QA_RESUME_DIR"]).resolve()
temp_root = Path(tempfile.gettempdir()).resolve()
if not root.is_relative_to(temp_root) or not root.name.startswith("suite-navigation-qa-"):
    raise RuntimeError("Resume target must be an existing disposable navigation QA directory")
database = root / "navigation.db"
if database.resolve().parent != root or not (root / "uploads").resolve().is_relative_to(root):
    raise RuntimeError("QA database and uploads must remain inside the disposable directory")
with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
    if not connection.execute("SELECT 1 FROM users WHERE email=?", ("admin@suiteqa.example.com",)).fetchone():
        raise RuntimeError("Missing synthetic QA administrator")
    if not connection.execute("SELECT 1 FROM pms_workspaces WHERE name=?", ("Portfolio acceptance workspace",)).fetchone():
        raise RuntimeError("Missing synthetic QA portfolio")

os.environ.update(
    ENVIRONMENT="test", DEBUG="false", DATABASE_URL="sqlite:///" + str(database),
    SECRET_KEY=secrets.token_urlsafe(48), REFRESH_SECRET_KEY=secrets.token_urlsafe(48),
    SECRET_KEY_PREVIOUS="", REFRESH_SECRET_KEY_PREVIOUS="",
    INSTALLED_APPS="hrms,crm,project_management,srm,fam,power_apps",
    STORAGE_BACKEND="local", UPLOAD_DIR=str(root / "uploads"),
    OPENAI_API_KEY="", ANTHROPIC_API_KEY="", GEMINI_API_KEY="",
    MAIL_USERNAME="", MAIL_PASSWORD="", MAIL_SERVER="",
    FIREBASE_PROJECT_ID="", FIREBASE_WEB_CONFIG="{}",
    CRM_WHATSAPP_PROVIDER="mock", CRM_WHATSAPP_ACCESS_TOKEN="",
    CRM_WHATSAPP_PHONE_NUMBER_ID="", CRM_WHATSAPP_BUSINESS_ACCOUNT_ID="",
    CRM_WHATSAPP_APP_ID="", CRM_WHATSAPP_EMBEDDED_CONFIG_ID="",
    BUSINESSSUITE_BACKUP_SCHEDULER="false", SEED_DEMO_DATA="false",
    SECURITY_RATE_LIMIT_ENABLED="false",
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app
from app.db.session import engine
from fastapi import HTTPException
from fastapi.responses import FileResponse

workspace = Path(__file__).resolve().parents[2]
frontend = Path(os.environ["PROJECTS_QA_FRONTEND"]).resolve()
if not frontend.is_relative_to(workspace):
    raise RuntimeError("QA frontend must remain in the workspace")

@app.get("/{path:path}", include_in_schema=False)
def serve_frontend(path: str):
    candidate = (frontend / path).resolve()
    if path.startswith("api/") or not candidate.is_relative_to(frontend):
        raise HTTPException(404)
    return FileResponse(candidate if candidate.is_file() else frontend / "index.html")

@asynccontextmanager
async def qa_lifespan(application):
    yield

app.router.lifespan_context = qa_lifespan
request_lock = asyncio.Lock()
inside_request = ContextVar("inside_resumed_qa_request", default=False)

@app.middleware("http")
async def serialize_sqlite(request, call_next):
    if inside_request.get():
        return await call_next(request)
    async with request_lock:
        token = inside_request.set(True)
        try:
            return await call_next(request)
        finally:
            inside_request.reset(token)

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PROJECTS_QA_PORT", "1569")), log_level="warning")
    finally:
        engine.dispose()
