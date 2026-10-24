"""Full database and local upload archives. Run on durable, trusted infrastructure."""

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import tempfile
import zipfile
from contextlib import contextmanager, closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/data-backups", tags=["Recovery"])
logger = logging.getLogger(__name__)


def backup_root():
    if settings.SERVERLESS:
        raise HTTPException(
            503,
            "Full backups require a durable worker with database access. Run scripts/data_recovery.py on that worker; serverless temporary storage is not a backup destination.",
        )
    root = Path(
        os.environ.get("BUSINESSSUITE_BACKUP_DIR")
        or settings.BUSINESSSUITE_BACKUP_DIR
        or Path(__file__).resolve().parents[3] / "recovery_backups"
    ).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def require_system_admin(user=Depends(get_current_user)):
    if not user.is_superuser:
        raise HTTPException(403, "System administrator required for all-module backups")
    return user


@contextmanager
def backup_lock(root):
    path = root / ".backup.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise HTTPException(
            409,
            "Another backup is running. A lock left by a crashed worker must be inspected by an administrator.",
        )
    try:
        os.write(
            fd,
            f"pid={os.getpid()} started={datetime.now(timezone.utc).isoformat()}".encode(),
        )
        yield
    finally:
        os.close(fd)
        path.unlink(missing_ok=True)


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def postgres_args(url):
    # Import the existing credential-safe PostgreSQL helpers.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "backup_pg_tools",
        Path(__file__).resolve().parents[2] / "scripts/postgres_backup.py",
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    env = dict(os.environ)
    env.update(
        PGHOST=url.host or "127.0.0.1",
        PGPORT=str(url.port or 5432),
        PGDATABASE=url.database,
        PGUSER=url.username or "",
        PGPASSWORD=url.password or "",
    )
    for key in ("sslmode", "sslrootcert"):
        value = url.query.get(key) or (
            settings.POSTGRES_SSLROOTCERT
            if key == "sslrootcert"
            else settings.POSTGRES_SSLMODE
        )
        if value:
            env["PG" + key.upper()] = str(value)
    return helper, env


def upload_sources():
    """Yield authoritative storage bytes, including configured cloud object stores."""
    from app.core import storage

    prefix = settings.S3_PREFIX.strip("/") + "/"
    if settings.STORAGE_BACKEND == "vercel_blob":
        from vercel.blob.sync import query_blobs, stream_blob

        with storage.blob_session():
            for blob in query_blobs(prefix=prefix, page_size=1000):
                if not blob.pathname.startswith(prefix):
                    raise ValueError(
                        "Storage returned a key outside the configured prefix"
                    )
                with stream_blob(blob.pathname, access="private") as stream:
                    yield "uploads/" + blob.pathname[len(prefix) :], iter(stream)
    elif settings.STORAGE_BACKEND == "s3":
        client = storage.s3_client()
        for page in client.get_paginator("list_objects_v2").paginate(
            Bucket=settings.S3_BUCKET, Prefix=prefix
        ):
            for item in page.get("Contents", []):
                key = item["Key"]
                if key.endswith("/"):
                    continue
                if not key.startswith(prefix):
                    raise ValueError(
                        "Storage returned a key outside the configured prefix"
                    )
                body = client.get_object(Bucket=settings.S3_BUCKET, Key=key)["Body"]
                try:
                    yield "uploads/" + key[len(prefix) :], iter(
                        lambda: body.read(1024 * 1024), b""
                    )
                finally:
                    body.close()
    elif settings.STORAGE_BACKEND == "local":
        uploads = Path(settings.UPLOAD_DIR).resolve()
        if uploads.exists():
            for path in uploads.rglob("*"):
                if path.is_symlink() or (
                    path.resolve() != uploads and uploads not in path.resolve().parents
                ):
                    raise ValueError(
                        "Upload symlinks or external paths are not supported"
                    )
                if path.is_file():
                    with path.open("rb") as stream:
                        yield "uploads/" + path.relative_to(uploads).as_posix(), iter(
                            lambda: stream.read(1024 * 1024), b""
                        )
    else:
        raise ValueError("Unknown storage backend")


def safe_member(name):
    from pathlib import PurePosixPath

    member = PurePosixPath(name)
    if member.is_absolute() or ".." in member.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe archive member")
    return name


def archive_info(path):
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    return {
        key: manifest[key]
        for key in (
            "id",
            "created_at",
            "automatic",
            "database",
            "actor_id",
            "file_count",
            "local_uploads_only",
        )
    } | {"bytes": path.stat().st_size}


def archive_catalog(root):
    items = []
    for path in root.glob("*.zip"):
        if len(path.stem) != 32 or any(c not in "0123456789abcdef" for c in path.stem):
            continue
        try:
            items.append({**archive_info(path), "state": "available"})
        except (ValueError, KeyError, OSError, zipfile.BadZipFile):
            items.append(
                {
                    "id": path.stem,
                    "state": "unreadable",
                    "created_at": datetime.fromtimestamp(
                        path.stat().st_mtime, timezone.utc
                    ).isoformat(),
                    "bytes": path.stat().st_size,
                    "file_count": 0,
                    "database": "unknown",
                    "automatic": False,
                }
            )
    return sorted(items, key=lambda row: row["created_at"], reverse=True)


def create_archive(engine=None, *, actor_id=None, automatic=False):
    from app.db.session import engine as default_engine

    engine = engine or default_engine
    root = backup_root()
    with backup_lock(root), tempfile.TemporaryDirectory(
        prefix="backup-", dir=root
    ) as temp:
        temp = Path(temp)
        key = uuid4().hex
        dialect = engine.url.get_backend_name()
        if dialect == "sqlite":
            database = temp / "database.sqlite3"
            source = engine.raw_connection()
            try:
                with closing(sqlite3.connect(database)) as target:
                    source.driver_connection.backup(target)
                    if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise RuntimeError("Database integrity check failed")
            finally:
                source.close()
        elif dialect == "postgresql":
            database = temp / "database.dump"
            helper, env = postgres_args(engine.url)
            subprocess.run(
                [
                    helper.postgres_tool("pg_dump"),
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                    "--file",
                    str(database),
                ],
                env=env,
                check=True,
                capture_output=True,
                timeout=1800,
            )
            subprocess.run(
                [helper.postgres_tool("pg_restore"), "--list", str(database)],
                env=env,
                check=True,
                capture_output=True,
                timeout=120,
            )
        else:
            raise HTTPException(422, "Full backup supports SQLite and PostgreSQL")
        manifest = {
            "format": "businesssuite-full-v1",
            "id": key,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "automatic": automatic,
            "actor_id": actor_id,
            "database": dialect,
            "local_uploads_only": settings.STORAGE_BACKEND == "local",
            "storage_backend": settings.STORAGE_BACKEND,
            "files": {},
        }
        pending = temp / "archive.zip"
        with zipfile.ZipFile(
            pending, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:

            def add_chunks(name, chunks):
                # Hash the exact archived bytes, avoiding a hash/write race.
                safe_member(name)
                if name in manifest["files"]:
                    raise ValueError("Duplicate upload key")
                h = hashlib.sha256()
                size = 0
                with archive.open(name, "w", force_zip64=True) as dest:
                    for block in chunks:
                        dest.write(block)
                        h.update(block)
                        size += len(block)
                manifest["files"][name] = {"sha256": h.hexdigest(), "bytes": size}

            with database.open("rb") as stream:
                add_chunks(database.name, iter(lambda: stream.read(1024 * 1024), b""))
            uploads = Path(settings.UPLOAD_DIR).resolve()
            # Backups must never recurse into themselves when deployments misconfigure storage.
            if root == uploads or uploads in root.parents or root in uploads.parents:
                raise HTTPException(
                    422, "Backup and upload directories must be separate"
                )
            for name, chunks in upload_sources():
                add_chunks(name, chunks)
            manifest["file_count"] = len(manifest["files"])
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        verify_archive(pending)
        target = root / (key + ".zip")
        os.replace(pending, target)
        os.chmod(target, 0o600)
        return archive_info(target)


def verify_archive(path):
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != "businesssuite-full-v1":
            raise ValueError("Unknown backup format")
        expected = set(manifest["files"]) | {"manifest.json"}
        if set(archive.namelist()) != expected or len(archive.namelist()) != len(
            expected
        ):
            raise ValueError("Unexpected archive files")
        for name, item in manifest["files"].items():
            if name not in {
                "database.sqlite3",
                "database.dump",
            } and not name.startswith("uploads/"):
                raise ValueError("Unexpected archive member")
            safe_member(name)
            h, size = hashlib.sha256(), 0
            with archive.open(name) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
                    size += len(block)
            if h.hexdigest() != item["sha256"] or size != item["bytes"]:
                raise ValueError("Backup checksum mismatch")
        if (
            "database.sqlite3" if manifest["database"] == "sqlite" else "database.dump"
        ) not in expected:
            raise ValueError("Missing database")
    return manifest


def extract_archive(path, target):
    """Restore into a NEW offline directory, never overwrite live files/database."""
    verify_archive(path)
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=False, mode=0o700)
    try:
        with zipfile.ZipFile(path) as archive:
            archive.extractall(target)
    except Exception:
        shutil.rmtree(target)
        raise
    return target


class FullPolicy(BaseModel):
    enabled: bool = False
    interval_hours: int = Field(default=24, ge=1, le=720)
    retain_automatic: int = Field(default=14, ge=2, le=90)


def read_policy(root):
    path = root / "policy.json"
    return (
        json.loads(path.read_text())
        if path.exists()
        else {**FullPolicy().model_dump(), "last_success_at": None}
    )


def write_policy(root, data):
    temp = root / (uuid4().hex + ".tmp")
    temp.write_text(json.dumps(data), encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, root / "policy.json")


def run_full_due(engine=None):
    root = backup_root()
    # Separate scheduler lease prevents two workers deciding the same policy is due.
    lease = root / "scheduler"
    lease.mkdir(exist_ok=True, mode=0o700)
    with backup_lock(lease):
        policy = read_policy(root)
        now = datetime.now(timezone.utc)
        if not policy["enabled"] or (
            policy.get("last_success_at")
            and now - datetime.fromisoformat(policy["last_success_at"])
            < timedelta(hours=policy["interval_hours"])
        ):
            return None
        result = create_archive(engine, automatic=True, actor_id=policy.get("actor_id"))
        policy["last_success_at"] = now.isoformat()
        write_policy(root, policy)
        automatic = [
            item
            for item in archive_catalog(root)
            if item["automatic"] and item["state"] == "available"
        ]
        for item in automatic[policy["retain_automatic"] :]:
            (root / (item["id"] + ".zip")).unlink()
        return result


@router.get("")
def list_archives(user: User = Depends(require_system_admin)):
    root = backup_root()
    return {
        "archives": archive_catalog(root),
        "policy": read_policy(root),
        "scheduler_enabled": settings.BUSINESSSUITE_BACKUP_SCHEDULER,
        "restore_mode": "Verified offline restore to a new directory / empty database. Configured local/S3/Vercel Blob uploads are included. Store application encryption keys separately.",
    }


@router.post("", status_code=201)
def manual_archive(user: User = Depends(require_system_admin)):
    try:
        return create_archive(actor_id=user.id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Full backup failed")
        raise HTTPException(
            503,
            "Backup failed. No successful archive was published; inspect admin server logs.",
        )


@router.put("/policy")
def full_policy(data: FullPolicy, user: User = Depends(require_system_admin)):
    root = backup_root()
    lease = root / "scheduler"
    lease.mkdir(exist_ok=True, mode=0o700)
    with backup_lock(lease):
        current = read_policy(root)
        write_policy(root, {**current, **data.model_dump(), "actor_id": user.id})
    return {"saved": True}


@router.get("/{key}/download")
def full_download(key: str, user: User = Depends(require_system_admin)):
    if len(key) != 32 or any(c not in "0123456789abcdef" for c in key):
        raise HTTPException(404, "Backup not found")
    path = backup_root() / (key + ".zip")
    if not path.is_file():
        raise HTTPException(404, "Backup not found")
    try:
        verify_archive(path)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile):
        raise HTTPException(
            409,
            "Archive integrity verification failed. This backup cannot be used for recovery.",
        )
    return FileResponse(
        path,
        filename=f"businesssuite-{key}.zip",
        media_type="application/zip",
        headers={"Cache-Control": "private, no-store"},
    )
