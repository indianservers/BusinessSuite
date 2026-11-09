"""Explicit note copies to the caller's own connected cloud account."""
from hashlib import sha256
from html import escape
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.rich_text import PREFIX, rich_text_plain, rich_text_type, sanitize_rich_text
from app.models.file_storage import StorageConnection
from app.models.user import User
from app.services import file_storage_providers as providers

router = APIRouter(prefix="/notes", tags=["Note cloud copies"])
Source = Literal["project_management", "crm"]


def note_company(user, source, db=None):
    from app.access.service import require_module_action
    from app.apps.srm.services.commercial import tenant
    require_module_action(user, source, "export")
    if db is not None and not user.is_superuser and getattr(user, "_suite_grants", None) is None:
        from app.access.service import legacy_grants
        grant = legacy_grants(db, user, tenant(user)).get(source, {})
        if not grant.get("enabled") or "export" not in grant.get("actions", []):
            raise HTTPException(403, f"This operation requires the {source} export action")
    return tenant(user)


def personal_account(db, user, source, ident):
    account = db.query(StorageConnection).filter_by(
        id=ident, organization_id=note_company(user, source, db), created_by=user.id,
        connected=True).with_for_update().first()
    if not account or account.provider not in {"google_drive", "onedrive"}:
        raise HTTPException(404, "Connected note storage account not found")
    return account


class NoteConnect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Source
    provider: Literal["google_drive", "onedrive"]


@router.post("/connect")
def connect_account(data: NoteConnect, request: Request, response: Response,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    import hashlib
    import secrets
    from datetime import timedelta
    from urllib.parse import urlencode, urlsplit
    from app.core.config import settings
    from app.models.file_storage import StorageOAuthState
    from app.apps.power_apps.integrations.vault import CredentialVault
    from app.services.sso_service import generate_pkce_pair
    response.headers["Cache-Control"] = "private, no-store"
    company = note_company(user, data.source, db)
    cfg = providers.app_config(data.provider)
    if not cfg["ready"]:
        raise HTTPException(503, "This storage provider is not configured on the server. Please contact your administrator")
    # The return window must be an explicitly configured app origin, never a supplied URL.
    expected = settings.FRONTEND_PUBLIC_URL.rstrip("/")
    origin = request.headers.get("origin", expected).rstrip("/")
    allowed = {expected, *(str(o).rstrip("/") for o in settings.BACKEND_CORS_ORIGINS)}
    if origin not in allowed or origin == "*":
        raise HTTPException(403, "Notes connection origin is not allowed")
    state, request_id = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()
    account = StorageConnection(organization_id=company, created_by=user.id, provider=data.provider,
                                label=cfg["label"], connected=False,
                                encrypted_value=CredentialVault.encrypt({"notes_owner_id":user.id}))
    db.add(account); db.flush()
    db.add(StorageOAuthState(id=hashlib.sha256(state.encode()).hexdigest(), organization_id=company,
        connection_id=account.id, user_id=user.id,
        encrypted_value=CredentialVault.encrypt({"verifier":verifier, "return_origin":origin,
            "purpose":"notes", "module":data.source, "request_id":request_id,
            "branch":request.headers.get("X-Suite-Branch")}),
        expires_at=providers.now()+timedelta(minutes=10)))
    fields = {"client_id":cfg["client_id"], "redirect_uri":cfg["redirect_uri"], "response_type":"code",
              "state":state, "scope":" ".join(cfg["scopes"]), "code_challenge":challenge, "code_challenge_method":"S256"}
    if data.provider == "google_drive": fields.update(access_type="offline", prompt="consent select_account")
    else: fields.update(prompt="select_account")
    db.commit()
    return {"authorize_url":cfg["authorize"]+"?"+urlencode(fields), "request_id":request_id,
            "callback_origin":urlsplit(cfg["redirect_uri"]).scheme+"://"+urlsplit(cfg["redirect_uri"]).netloc}


def recheck_note_connection(db, actor, row, value):
    """Re-resolve membership, policy and export rights after the external consent."""
    from app.access.service import bind_authorization
    module = value.get("module")
    if module not in {"crm", "project_management"}:
        raise HTTPException(403, "Invalid Notes connection purpose")
    headers = [(b"x-suite-organization", str(row.organization_id).encode())]
    if value.get("branch"): headers.append((b"x-suite-branch", value["branch"].encode()))
    request = Request({"type":"http", "method":"GET", "path":"/api/v1/"+module.replace("_", "-")+"/notes",
                       "headers":headers, "query_string":b""})
    bind_authorization(db, actor, request)
    if note_company(actor, module, db) != row.organization_id:
        raise HTTPException(403, "Notes company access changed")


def connection_completion(value, status, connection_id=None):
    """Notify only the initiating Notes window; no provider tokens enter the browser."""
    import json
    import secrets
    from fastapi.responses import HTMLResponse
    nonce = secrets.token_urlsafe(24)
    message = json.dumps({"type":"suite-note-storage", "request_id":value["request_id"],
                          "status":status, "connection_id":connection_id}).replace("<", "\\u003c")
    origin = json.dumps(value["return_origin"]).replace("<", "\\u003c")
    text = "Account connected. Return to your note." if status == "connected" else "Connection was not completed. Return to your note and try again."
    return HTMLResponse('<!doctype html><meta charset="utf-8"><title>Notes storage connection</title><p>'+text+
        '</p><script nonce="'+nonce+'">if(window.opener){window.opener.postMessage('+message+','+origin+');window.close();}</script>',
        headers={"Cache-Control":"private, no-store", "Referrer-Policy":"no-referrer",
                 "Content-Security-Policy":"default-src 'none'; script-src 'nonce-"+nonce+"'; frame-ancestors 'none'"})


@router.get("/options")
def options(response: Response, source: Source = "project_management",
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "private, no-store"
    company = note_company(user, source, db)
    accounts = db.query(StorageConnection).filter_by(
        organization_id=company, created_by=user.id, connected=True).filter(
        StorageConnection.provider.in_(["google_drive", "onedrive"])).order_by(StorageConnection.id).all()
    return {"accounts": [{"id": a.id, "provider": a.provider, "account": a.account or a.label} for a in accounts]}


@router.get("/accounts/{ident}/folders")
def folders(ident: int, response: Response, source: Source = "project_management",
            parent: str = Query("root", max_length=250), cursor: str | None = Query(None, max_length=4096),
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "private, no-store"
    account = personal_account(db, user, source, ident)
    result = providers.folders(db, account, parent, cursor)
    db.commit()  # Persist any OAuth refresh-token rotation.
    return result


class NoteCopy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Source
    connection_id: int = Field(gt=0)
    folder_id: str = Field(default="root", min_length=1, max_length=250)
    format: Literal["html", "txt"] = "html"
    note_id: int | None = Field(default=None, gt=0)
    note_version: int | None = Field(default=None, gt=0)
    title: str = Field(default="Untitled note", max_length=180)
    content: rich_text_type(200000, 0) = ""


@router.post("/save")
def save_copy(data: NoteCopy, response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "private, no-store"
    note_company(user, data.source, db)
    title, content = data.title, data.content
    if data.source == "project_management":
        from app.apps.project_management.models import PMSNote
        note = db.query(PMSNote).filter_by(id=data.note_id, owner_id=user.id).with_for_update().first()
        if note is None:
            raise HTTPException(404, "Note not found")
        if note.deleted_at:
            raise HTTPException(409, "Restore the note before saving a cloud copy")
        if data.note_version != note.version:
            raise HTTPException(409, "Note changed. Save the latest version before copying it")
        title, content = note.title, note.content
    account = personal_account(db, user, data.source, data.connection_id)
    providers.folder_info(db, account, data.folder_id)
    name = (re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]', "_", title).strip(" .") or "Untitled note")[:140] + "." + data.format
    if data.format == "txt":
        body = (title + "\n\n" + rich_text_plain(content)).encode("utf-8")
        mime = "text/plain; charset=utf-8"
    else:
        safe = sanitize_rich_text(content)
        html = safe[len(PREFIX):] if safe.startswith(PREFIX) else "<pre>" + escape(safe) + "</pre>"
        body = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
                '<title>' + escape(title) + '</title></head><body><h1>' + escape(title) + '</h1>' + html + '</body></html>').encode("utf-8")
        mime = "text/html; charset=utf-8"
    remote = providers.upload(db, account, data.folder_id, name, body, mime)
    if sha256(providers.download(db, account, remote)).digest() != sha256(body).digest():
        raise HTTPException(502, "The cloud copy could not be verified. Your original note is unchanged; check the destination before retrying")
    db.commit()
    return {"saved": True, "provider": account.provider, "filename": name, "remote_id": remote,
            "note_version": data.note_version if data.source == "project_management" else None}
