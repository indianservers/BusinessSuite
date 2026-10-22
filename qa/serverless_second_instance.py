"""Second API instance over the disposable browser DB; never recreates it."""
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
from app.core.config import settings
from sqlalchemy.engine import make_url

settings.DATABASE_URL = make_url(settings.SQLALCHEMY_DATABASE_URI).set(
    database="business_suite_browser_test").render_as_string(hide_password=False)
settings.ENVIRONMENT = "test"
settings.REALTIME_TRANSPORT = "database"
settings.BACKEND_CORS_ORIGINS = ["http://127.0.0.1:5182"]
from app.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8767)
