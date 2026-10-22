"""Check a configured deployment without logging credentials or signed links."""
import argparse
from pathlib import Path
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from sqlalchemy import text
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.config import settings
from app.db.session import engine
from app.core.storage import persist_file, signed_file_url, storage_key, s3_client


def check(api_url=None):
    expected = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))).get_current_head()
    with engine.connect() as db:
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if revision != expected:
            raise RuntimeError("Database migration revision does not match application head")
    print("PostgreSQL schema: current")
    if settings.STORAGE_BACKEND != "s3":
        raise RuntimeError("Configure S3-compatible storage before running cloud readiness checks")
    probe = Path(settings.UPLOAD_DIR) / "deployment-probes" / f"{uuid.uuid4().hex}.txt"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_bytes(b"business-suite-deployment-probe")
    try:
        persist_file(str(probe))
        link = signed_file_url(str(probe))
        with httpx.Client(timeout=20) as client:
            response = client.get(link, headers={"Origin": settings.FRONTEND_PUBLIC_URL})
            if response.status_code != 200 or response.content != probe.read_bytes():
                raise RuntimeError("Signed storage download failed")
            if response.headers.get("Access-Control-Allow-Origin") != settings.FRONTEND_PUBLIC_URL:
                raise RuntimeError("Storage CORS does not permit the configured frontend")
            if client.get(link.split("?", 1)[0]).status_code == 200:
                raise RuntimeError("Storage bucket allows unsigned access; disable public access")
        print("Storage persistence, signed download, private access and CORS: passed")
    finally:
        s3_client().delete_object(Bucket=settings.S3_BUCKET, Key=storage_key(str(probe)))
        probe.unlink(missing_ok=True)
    if api_url:
        with httpx.Client(base_url=api_url.rstrip("/"), timeout=30) as client:
            response = client.get("/health")
            if response.status_code != 200:
                raise RuntimeError("Remote health check failed")
            response = client.post("/api/v1/auth/login", json={"email": settings.BOOTSTRAP_ADMIN_EMAIL,
                "password": settings.BOOTSTRAP_ADMIN_PASSWORD})
            if response.status_code != 200:
                raise RuntimeError("Remote administrator login failed")
            headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
            for path in ["/api/v1/business-os/modules", "/api/v1/project-management/workspaces",
                         "/api/v1/project-management/realtime/config", "/api/v1/internal/jobs"]:
                if client.get(path, headers=headers).status_code != 200:
                    raise RuntimeError(f"Remote API smoke check failed: {path}")
        print("Remote health, login, modules, workspace, realtime and job monitoring: passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url")
    args = parser.parse_args()
    check(args.api_url)
