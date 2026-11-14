"""Files & Storage belongs to company Settings, independently of Power Apps."""
import hashlib
import json
import secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.file_storage import StorageConnection, StoragePolicy, StorageOAuthState, StorageObject
from app.access.settings_hub import require_option
from app.services import file_storage_providers as provider
from app.services.file_storage import MODULES, relative, route_upload
from app.apps.power_apps.integrations.vault import CredentialVault
from app.services.sso_service import generate_pkce_pair

router = APIRouter(prefix="/files-storage", tags=["Files & Storage"])
from .note_cloud import router as note_cloud_router
router.include_router(note_cloud_router)


def admin(db, user):
    _, ctx = require_option(db, user, "files-storage")
    return ctx["company"]


def notes_owner(row):
    return CredentialVault.decrypt(row).get("notes_owner_id") if row.encrypted_value else None


def connection(db, company, ident, notes_user_id=None):
    row = db.query(StorageConnection).filter_by(id=ident, organization_id=company).with_for_update().first()
    if not row: raise HTTPException(404, "Storage account not found")
    if notes_owner(row) not in {None, notes_user_id}:
        raise HTTPException(404, "Storage account not found")
    return row


def public_connection(row):
    return {"id": row.id, "provider": row.provider, "label": row.label, "account": row.account, "connected": row.connected}


@router.get("")
def configuration(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    company = admin(db, user)
    policy = db.get(StoragePolicy, company)
    return {"enabled": bool(policy and policy.enabled), "default_provider": policy.default_provider if policy else "google_drive",
        "routes": policy.routes if policy else {}, "revision": policy.revision if policy else 0,
        "modules": [{"id": k, "label": v} for k, v in MODULES.items()],
        "connections": [public_connection(c) for c in db.query(StorageConnection).filter_by(organization_id=company).order_by(StorageConnection.id).all() if notes_owner(c) is None],
        "providers": [{"id": key, "label": info["label"], "configured": provider.app_config(key)["ready"],
            "callback_uri": provider.app_config(key)["redirect_uri"], "scopes": info["scopes"],
            "required_settings": [f"FILES_{info['family']}_CLIENT_ID", f"FILES_{info['family']}_CLIENT_SECRET"]} for key, info in provider.PROVIDERS.items()],
        "server_photos": True}


class Connect(BaseModel):
    provider: str
    connection_id: int | None = None


@router.post("/connect")
def connect(data: Connect, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    company = admin(db, user)
    cfg = provider.app_config(data.provider)
    if not cfg["ready"]: raise HTTPException(503, "OAuth application is not configured. Add the client ID/secret and register the callback shown in Settings. No login is needed until that setup is complete.")
    conn = connection(db, company, data.connection_id) if data.connection_id else StorageConnection(
        organization_id=company, provider=data.provider, label=cfg["label"], created_by=user.id, connected=False)
    if conn.provider != data.provider: raise HTTPException(422, "Reconnect the same provider to preserve its file references")
    db.add(conn)
    db.flush()
    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()
    origin = request.headers.get("origin", settings.FRONTEND_PUBLIC_URL).rstrip("/")
    expected = settings.FRONTEND_PUBLIC_URL.rstrip("/")
    parsed = urlsplit(origin)
    if origin != expected and not (settings.ENVIRONMENT != "production" and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
        origin = expected
    db.add(StorageOAuthState(id=hashlib.sha256(state.encode()).hexdigest(), organization_id=company, connection_id=conn.id,
        user_id=user.id, encrypted_value=CredentialVault.encrypt({"verifier": verifier, "return_origin": origin}), expires_at=provider.now()+timedelta(minutes=10)))
    fields = {"client_id": cfg["client_id"], "redirect_uri": cfg["redirect_uri"], "response_type": "code", "state": state}
    if data.provider != "box": fields.update(scope=" ".join(cfg["scopes"]), code_challenge=challenge, code_challenge_method="S256")
    if data.provider == "google_drive": fields.update(access_type="offline", prompt="consent")
    if data.provider == "dropbox": fields.update(token_access_type="offline")
    db.commit()
    return {"authorize_url": cfg["authorize"] + "?" + urlencode(fields)}


@router.get("/oauth/callback")
def callback(state: str = "", code: str = "", error: str | None = None, db: Session = Depends(get_db)):
    if not state or len(state) > 200: raise HTTPException(400, "Invalid storage authorization state")
    row = db.query(StorageOAuthState).filter_by(id=hashlib.sha256(state.encode()).hexdigest()).with_for_update().first()
    if not row or row.consumed_at or provider.utc(row.expires_at) <= provider.now(): raise HTTPException(400, "Storage authorization expired or was already used")
    actor = db.get(User, row.user_id)
    if not actor or not actor.is_active: raise HTTPException(403, "Storage administrator is no longer active")
    value = CredentialVault.decrypt(row)
    notes = value.get("purpose") == "notes"
    if notes:
        from .note_cloud import recheck_note_connection
        recheck_note_connection(db, actor, row, value)
    else:
        actor.organization_id = row.organization_id
        admin(db, actor)  # Recheck administrator access after the external login.
    row.consumed_at = provider.now()
    db.commit()  # A failed/denied callback cannot be replayed.
    if error:
        if notes:
            from .note_cloud import connection_completion
            return connection_completion(value, "denied")
        return RedirectResponse(value["return_origin"] + "/settings/files-storage?authorization=denied", status_code=303)
    if not code or len(code) > 4096: raise HTTPException(400, "Invalid authorization code")
    conn = connection(db, row.organization_id, row.connection_id, actor.id if notes else None)
    if notes and (conn.created_by != actor.id or conn.provider not in {"google_drive", "onedrive"}):
        raise HTTPException(403, "This Notes connection belongs to another account")
    cfg = provider.app_config(conn.provider)
    fields = {"grant_type": "authorization_code", "code": code, "redirect_uri": cfg["redirect_uri"]}
    if conn.provider != "box": fields["code_verifier"] = value["verifier"]
    data = provider.tokens(conn.provider, fields)
    previous = CredentialVault.decrypt(conn) if conn.encrypted_value else {}
    conn.encrypted_value = CredentialVault.encrypt({"access_token": data["access_token"], "refresh_token": data.get("refresh_token") or previous.get("refresh_token"), **({"notes_owner_id":actor.id} if notes else {})})
    conn.expires_at = provider.now()+timedelta(seconds=int(data.get("expires_in", 3600)))
    conn.connected = True
    conn.account = provider.account_info(db, conn)
    if previous and previous.get("account") and previous["account"] != conn.account:
        db.rollback()
        raise HTTPException(409, "Reconnect the original account. Add a separate connection for a different account so existing files stay accessible.")
    token_data = CredentialVault.decrypt(conn)
    token_data["account"] = conn.account
    conn.encrypted_value = CredentialVault.encrypt(token_data)
    db.commit()
    if notes:
        from .note_cloud import connection_completion
        return connection_completion(value, "connected", conn.id)
    return RedirectResponse(value["return_origin"] + "/settings/files-storage?authorization=connected", status_code=303)


@router.get("/connections/{ident}/folders")
def folders(ident: int, parent: str | None = None, cursor: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    company = admin(db, user)
    result = provider.folders(db, connection(db, company, ident), parent, cursor)
    db.commit()  # Persist refresh-token rotation, including Box's single-use refresh token.
    return result


class Folder(BaseModel):
    parent: str = Field(max_length=250)
    name: str = Field(min_length=1, max_length=120)


@router.post("/connections/{ident}/folders", status_code=201)
def create_folder(ident: int, data: Folder, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    company = admin(db, user)
    result = provider.create_folder(db, connection(db, company, ident), data.parent, data.name)
    db.commit()
    return result


class Destination(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: int
    folder_id: str = Field(min_length=1, max_length=250)
    folder_name: str = Field(default="", max_length=250)


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int
    enabled: bool
    default_provider: str = "google_drive"
    routes: dict[str, Destination] = Field(default_factory=dict)


@router.put("")
def save(data: Policy, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    company = admin(db, user)
    if data.default_provider not in provider.PROVIDERS: raise HTTPException(422, "Invalid default provider")
    from app.models.company import Company
    db.query(Company).filter_by(id=company).with_for_update().one()
    row = db.query(StoragePolicy).filter_by(organization_id=company).with_for_update().first()
    if data.revision != (row.revision if row else 0): raise HTTPException(409, "Storage settings changed. Reload before saving.")
    if set(data.routes) - ({"default"} | set(MODULES)): raise HTTPException(422, "Unknown storage module")
    routes = {}
    for module, dest in data.routes.items():
        conn = connection(db, company, dest.connection_id)
        if not conn.connected: raise HTTPException(409, "Connect the selected account before enabling its destination")
        verified = provider.folder_info(db, conn, dest.folder_id)
        routes[module] = {"connection_id": conn.id, "folder_id": verified["id"], "folder_name": verified["name"]}
    if data.enabled and "default" not in routes: raise HTTPException(422, "Choose a default cloud folder before enabling storage")
    if "default" in routes and connection(db, company, routes["default"]["connection_id"]).provider != data.default_provider:
        raise HTTPException(422, "Default folder must use the selected default provider")
    if not row:
        row = StoragePolicy(organization_id=company, revision=0)
        db.add(row)
    row.enabled, row.default_provider, row.routes, row.revision = data.enabled, data.default_provider, routes, row.revision+1
    db.commit()
    return configuration(db, user)


@router.get("/files")
def files(module: str = "", search: str = Query("", max_length=160), page: int = Query(1, ge=1), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    company = admin(db, user)
    query = db.query(StorageObject).filter_by(organization_id=company)
    if module: query = query.filter_by(module=module)
    if search: query = query.filter(StorageObject.filename.icontains(search, autoescape=True))
    count = query.count()
    rows = query.order_by(StorageObject.id.desc()).offset((page-1)*30).limit(30).all()
    return {"total": count, "page": page, "items": [{"id": r.id, "module": r.module, "filename": r.filename, "size": r.size, "content_type": r.content_type,
        "provider": r.provider, "status": r.status, "folder_id": r.folder_id, "remote_id": r.remote_id,
        "sha256": r.sha256, "error": r.error, "created_at": r.created_at, "version_count": len(r.versions or [])+1} for r in rows]}


@router.post("/files/{ident}/retry")
def retry(ident: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    company = admin(db, user)
    row = db.query(StorageObject).filter_by(id=ident, organization_id=company).first()
    if not row: raise HTTPException(404, "File not found")
    if row.status == "cloud": return {"status": "cloud"}
    path = str(Path(settings.UPLOAD_DIR) / row.relative_path)
    if relative(path) != row.relative_path: raise HTTPException(400, "Invalid stored file path")
    from app.core.storage import materialize_file
    materialize_file(path, db=db)
    if not Path(path).is_file(): raise HTTPException(404, "Original server file is unavailable; it has not been deleted by storage migration")
    route_upload(path, db=db, company=company, module=row.module)
    status = row.status
    db.commit()
    return {"status": status}
