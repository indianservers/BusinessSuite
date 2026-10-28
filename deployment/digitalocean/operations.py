"""Droplet operations. Run from a release's backend working directory."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))
SHARED = Path("/srv/business-suite/shared")


def preflight():
    from app.core.config import settings
    from sqlalchemy.engine import make_url

    if (settings.ENVIRONMENT != "production" or settings.SERVERLESS
            or settings.DATABASE_AUTO_MIGRATE or settings.SEED_DEMO_DATA
            or settings.STORAGE_BACKEND != "local"
            or settings.UPLOAD_DIR != str(SHARED / "uploads")):
        raise RuntimeError("Use the documented Droplet production settings")
    for name in ("SECRET_KEY", "REFRESH_SECRET_KEY", "CRON_SECRET", "BOOTSTRAP_ADMIN_PASSWORD"):
        value = getattr(settings, name)
        if not value or value.startswith("REPLACE_"):
            raise RuntimeError(f"Configure {name} before deployment")
    if len(settings.CRON_SECRET) < 32:
        raise RuntimeError("CRON_SECRET must have at least 32 random characters")
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if url.get_backend_name() != "postgresql" or url.password == "URL_ENCODED_PASSWORD":
        raise RuntimeError("Configure PostgreSQL credentials before deployment")
    for name in ("backend.env", "frontend.env", "interns.env", "backup.env", "interns-config.js"):
        path = SHARED / name
        if not path.is_file() or path.stat().st_mode & 0o077:
            raise RuntimeError(f"shared/{name} must exist with private file permissions (0600)")
    print("Production configuration validated")


def backup():
    import boto3
    from dotenv import dotenv_values
    from postgres_backup import postgres_environment, postgres_tool
    from app.core.config import settings

    values = dotenv_values(SHARED / "backup.env")
    required = ("BACKUP_BUCKET", "BACKUP_ENDPOINT", "BACKUP_REGION",
                "BACKUP_ACCESS_KEY_ID", "BACKUP_SECRET_ACCESS_KEY")
    if any(not values.get(key) or values[key].startswith("replace-") for key in required):
        raise RuntimeError("Configure shared/backup.env: an off-Droplet backup is required")
    client = boto3.client("s3", endpoint_url=values["BACKUP_ENDPOINT"],
                          region_name=values["BACKUP_REGION"],
                          aws_access_key_id=values["BACKUP_ACCESS_KEY_ID"],
                          aws_secret_access_key=values["BACKUP_SECRET_ACCESS_KEY"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    prefix = f'{values.get("BACKUP_PREFIX", "business-suite/recovery").strip("/")}/{stamp}'
    # Serializes timer, manual and pre-deployment copies. No automatic deletion.
    with (SHARED / "backup.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(prefix="backup-", dir=SHARED) as temp:
            folder = Path(temp)
            dump = folder / "database.dump"
            subprocess.run([postgres_tool("pg_dump"), "--format=custom", "--no-owner",
                            "--no-acl", "--file", str(dump)],
                           env=postgres_environment(), check=True)
            subprocess.run([postgres_tool("pg_restore"), "--list", str(dump)],
                           stdout=subprocess.DEVNULL, check=True)
            archive = folder / "files.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(settings.UPLOAD_DIR, arcname="uploads")
                # Session/encryption secrets must survive disaster recovery too.
                for name in ("backend.env", "frontend.env", "interns.env", "interns-config.js"):
                    tar.add(SHARED / name, arcname=f"config/{name}")
            release_info = BACKEND.parent / "frontend/dist/release.json"
            commit = json.loads(release_info.read_text())["commit"] if release_info.exists() else None
            manifest = {"created_at": stamp, "release": BACKEND.parent.name, "commit": commit, "files": {}}
            for path in (dump, archive):
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                manifest["files"][path.name] = {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}
                client.upload_file(str(path), values["BACKUP_BUCKET"], f"{prefix}/{path.name}",
                                   ExtraArgs={"ACL": "private"})
            # A manifest is the completion marker; partial uploads are not recovery sets.
            client.put_object(Bucket=values["BACKUP_BUCKET"], Key=f"{prefix}/manifest.json",
                              Body=json.dumps(manifest).encode(), ContentType="application/json", ACL="private")
    print(f"Recovery copy completed: {prefix}")


def jobs():
    import httpx
    from app.core.config import settings

    if len(settings.CRON_SECRET) < 32:
        raise RuntimeError("Set CRON_SECRET to a random secret of at least 32 characters")
    headers = {"Authorization": f"Bearer {settings.CRON_SECRET}"}
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=240) as client:
        for route in ("cron", "intern-correction-reminders"):
            response = client.get(f"{settings.API_V1_STR}/internal/{route}", headers=headers)
            response.raise_for_status()
    print("Scheduled work completed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("backup", "jobs", "preflight"))
    args = parser.parse_args()
    {"backup": backup, "jobs": jobs, "preflight": preflight}[args.operation]()
