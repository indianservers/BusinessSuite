"""Check a configured deployment without logging credentials or signed links."""
import argparse
from pathlib import Path
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from sqlalchemy import text
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.config import settings
from app.db.session import engine
from app.core.storage import persist_file, signed_file_url, storage_key, s3_client, blob_session


def check(api_url=None, *, timeout=60):
    expected = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))).get_current_head()
    with engine.connect() as db:
        revisions = db.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if revisions != [expected]:
            raise RuntimeError("Database migration revision does not match application head")
    print("PostgreSQL schema: current")
    check_storage(api_url, timeout=timeout)
    if api_url:
        check_api(api_url, timeout=timeout)


def check_storage(api_url=None, *, timeout=60):
    if settings.STORAGE_BACKEND not in {"s3", "vercel_blob"}:
        raise RuntimeError("Configure private S3-compatible storage or Vercel Blob before running cloud readiness checks")
    probe = Path(settings.UPLOAD_DIR) / "deployment-probes" / f"{uuid.uuid4().hex}.txt"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_bytes(b"business-suite-deployment-probe")
    try:
        persist_file(str(probe))
        link = signed_file_url(str(probe))
        if api_url:
            origin = urlsplit(api_url)
            signed = urlsplit(link)
            link = urlunsplit((origin.scheme, origin.netloc, signed.path, signed.query, ""))
        if settings.STORAGE_BACKEND == "s3":
            direct = s3_client().generate_presigned_url("get_object", Params={
                "Bucket": settings.S3_BUCKET, "Key": storage_key(str(probe)),
            })
        else:
            from vercel.blob.sync import head_blob
            with blob_session():
                direct = head_blob(storage_key(str(probe))).url
        # Fetch through the API after removing local staging, exercising persistence.
        expected = probe.read_bytes()
        probe.unlink()
        with httpx.Client(timeout=timeout) as client:
            response = client.get(link, headers={"Origin": settings.FRONTEND_PUBLIC_URL})
            if response.status_code != 200 or response.content != expected:
                raise RuntimeError("Signed storage download failed")
            if response.headers.get("Access-Control-Allow-Origin") != settings.FRONTEND_PUBLIC_URL:
                raise RuntimeError("Download API CORS does not permit the configured frontend")
            if client.get(link.split("?", 1)[0]).status_code not in {401, 403, 422}:
                raise RuntimeError("Download API does not reject unsigned access")
            if client.get(direct.split("?", 1)[0]).status_code not in {401, 403, 404}:
                raise RuntimeError("Storage does not reject unsigned object access")
        print("Storage persistence, signed API download, private object access and API CORS: passed")
    finally:
        try:
            if settings.STORAGE_BACKEND == "s3":
                s3_client().delete_object(Bucket=settings.S3_BUCKET, Key=storage_key(str(probe)))
            else:
                from vercel.blob.sync import delete_blob
                with blob_session():
                    delete_blob(storage_key(str(probe)))
        finally:
            probe.unlink(missing_ok=True)


def check_api(api_url, *, timeout=60):
    with httpx.Client(base_url=api_url.rstrip("/"), timeout=timeout) as client:
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
    parser.add_argument("--timeout", type=float, default=60, help="HTTP timeout in seconds, including serverless cold starts (default: 60)")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        check(args.api_url, timeout=args.timeout)
    except Exception as exc:
        # Provider exceptions may embed signed links or connection credentials.
        message = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print(f"Deployment readiness failed: {message}", file=sys.stderr)
        raise SystemExit(1) from None
