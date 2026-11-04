"""Route native uploads without replacing existing business URLs or moving old files."""
import hashlib
import mimetypes
from pathlib import Path
from uuid import uuid4
from sqlalchemy import event
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.config import settings
from app.core.audit_context import context
from app.models.file_storage import StoragePolicy, StorageConnection, StorageObject
from app.services import file_storage_providers as providers

MODULES = {"hrms": "HRMS", "crm": "CRM", "pms": "PMS", "sales": "Sales & Inventory", "finance": "Finance & Accounting", "interns": "Recruitment & Interns", "shared": "Shared files & reports"}


def relative(path):
    try: return Path(path).resolve().relative_to(Path(settings.UPLOAD_DIR).resolve()).as_posix()
    except ValueError: raise HTTPException(400, "File is outside upload storage") from None


def server_photo(path):
    try: ref = relative(path)
    except HTTPException: return False
    return ref.startswith(("photos/", "_private/profiles/"))


def scope(db=None, company=None):
    evidence = context.get() or {}
    actor = evidence.get("actor", {})
    db = db or evidence.get("storage_session")
    company = company or (db.info.get("file_download_company") if db is not None else None) or actor.get("access_company")
    return db, company, actor


def module_for(path, actor):
    ref = relative(path)
    if ref.startswith(("crm/",)): return "crm"
    if ref.startswith(("pms/",)): return "pms"
    if ref.startswith(("invoices/", "srm/")): return "sales"
    if ref.startswith(("fam/",)): return "finance"
    if ref.startswith(("_private/applications/", "intern")): return "interns"
    module = actor.get("access_module", "")
    return {"project_management": "pms", "srm": "sales", "fam": "finance", "interns_hub": "interns"}.get(module, module if module in MODULES else "shared")


def locator(path, db=None, company=None):
    db, company, _ = scope(db, company)
    if db is None or company is None: return None
    try: ref = relative(path)
    except HTTPException: return None
    return db.query(StorageObject).filter_by(organization_id=int(company), relative_path=ref).first()


def route_upload(path, *, db=None, company=None, module=None, filename=None):
    db, company, actor = scope(db, company)
    try: relative(path)
    except HTTPException: return False  # Preserve legacy local paths; never send them to a cloud provider.
    if server_photo(path): return True  # Explicitly keep employee/profile photos on this server.
    if db is None or company is None: return False  # Background/legacy paths keep their existing backend.
    module = module or module_for(path, actor)
    policy = db.get(StoragePolicy, int(company))
    route = ((policy.routes or {}).get(module) or (policy.routes or {}).get("default")) if policy and policy.enabled else None
    content = Path(path).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    row = locator(path, db, company)
    if row and row.status == "cloud" and row.sha256 == digest:
        schedule_cleanup(db, path, digest)
        return True
    if not row:
        row = StorageObject(organization_id=int(company), module=module, relative_path=relative(path),
            filename=(filename or Path(path).name)[:255], content_type=mimetypes.guess_type(path)[0] or "application/octet-stream",
            size=len(content), sha256=digest, provider=settings.STORAGE_BACKEND, status="local", uploaded_by=actor.get("user_id"), versions=[])
        db.add(row)
    elif row.remote_id:
        row.versions = [*(row.versions or []), {"provider": row.provider, "connection_id": row.connection_id, "remote_id": row.remote_id, "sha256": row.sha256, "folder_id": row.folder_id}]
    row.sha256, row.size, row.module = digest, len(content), module
    if not route:
        row.provider, row.status, row.remote_id, row.error = settings.STORAGE_BACKEND, "local", None, None
        db.flush()
        return False
    conn = db.query(StorageConnection).filter_by(id=route["connection_id"], organization_id=int(company)).with_for_update().first()
    row.connection_id, row.folder_id = route["connection_id"], route["folder_id"]
    row.remote_id, row.provider, row.status, row.error = None, conn.provider if conn else "google_drive", "pending", None
    try:
        if not conn: raise HTTPException(409, "Storage connection is unavailable")
        remote = providers.upload(db, conn, row.folder_id, row.filename, content, row.content_type)
        row.remote_id = remote  # Retain the locator even if verification fails.
        downloaded = providers.download(db, conn, remote)
        if hashlib.sha256(downloaded).hexdigest() != digest: raise HTTPException(502, "Cloud verification failed")
        row.status = "cloud"
        schedule_cleanup(db, path, digest)
    except Exception:
        # Never discard an accepted attachment because the provider is temporarily unavailable.
        row.error = "Cloud upload or verification failed. The server copy is retained; retry from Files & Storage."
    db.flush()
    return row.status == "cloud"


def schedule_cleanup(db, path, digest):
    db.info.setdefault("verified_cloud_staging", {})[str(Path(path).resolve())] = digest


@event.listens_for(Session, "after_commit")
def clear_staging(db):
    for name, digest in db.info.pop("verified_cloud_staging", {}).items():
        path = Path(name)
        try:
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                path.unlink()
        except OSError: pass  # A stale cache is harmless; the cloud locator remains authoritative.


@event.listens_for(Session, "after_rollback")
def retain_staging(db): db.info.pop("verified_cloud_staging", None)


def materialize(path, db=None, company=None):
    row = locator(path, db, company)
    if not row or row.status != "cloud": return None
    db, company, _ = scope(db, company)
    # Check the actual account attached to this file, never the module's current destination.
    conn = db.query(StorageConnection).filter_by(id=row.connection_id, organization_id=company).with_for_update().first()
    if not conn: raise HTTPException(409, "The original storage account is unavailable")
    content = providers.download(db, conn, row.remote_id)
    if hashlib.sha256(content).hexdigest() != row.sha256: raise HTTPException(409, "Cloud file contents changed; original checksum verification failed")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + "." + uuid4().hex + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(target)
    return str(target)


def retain_generated(db, module, name, content, *, company=None, commit=True):
    """Persist generated binary documents which previously existed only in HTTP responses."""
    from app.core.storage import persist_file
    safe = Path(name.replace("\\", "/")).name
    path = Path(settings.UPLOAD_DIR) / module / "generated" / uuid4().hex / safe
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    persist_file(str(path), db=db, company=company, module=module, filename=safe)
    if commit: db.commit()
    return str(path)
