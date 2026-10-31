import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.core.config import settings
from app.core.storage import persist_file, upload_exists, FileResponse
from app.models.user import User
from .models import CRMFileAsset, CRMFileFolder
from .api.router import CRM_ANY_PERMISSIONS

router = APIRouter()


class FolderInput(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class MoveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    folder_id: int | None = None
    previous_folder_id: int | None = None


def access(db, user, action="view"):
    from .api.router import _organization_id, _assert_entity_permission
    _assert_entity_permission("files", user, action)
    return _organization_id(db, user)


def folder(db, identity, organization):
    if identity is None: return None
    item = db.query(CRMFileFolder).filter_by(id=identity, organization_id=organization).first()
    if not item: raise HTTPException(404, "Folder not found")
    return item


@router.get("/file-workspace")
def cabinet(db: Session = Depends(get_db), user: User = Depends(RequirePermission(*CRM_ANY_PERMISSIONS))):
    organization = access(db, user)
    from .api.router import _apply_record_visibility, _base_query, _get_resource
    files = _apply_record_visibility(_base_query(db, _get_resource("files"), organization), _get_resource("files"), user, db)
    return {"folders": [{"id": f.id, "name": f.name} for f in db.query(CRMFileFolder).filter_by(organization_id=organization).order_by(CRMFileFolder.name)], "files": [{"id": f.id, "name": f.original_name, "folder_id": f.folder_id, "size": f.size_bytes} for f in files.order_by(CRMFileAsset.id.desc()).limit(200)]}


@router.post("/file-workspace/folders", status_code=201)
def create_folder(data: FolderInput, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*CRM_ANY_PERMISSIONS))):
    organization = access(db, user, "manage")
    if not data.name.strip(): raise HTTPException(422, "Folder name required")
    item = CRMFileFolder(organization_id=organization, owner_user_id=user.id, name=data.name.strip())
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "name": item.name}


@router.put("/file-workspace/files/{file_id}/folder")
def move_file(file_id: int, data: MoveInput, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*CRM_ANY_PERMISSIONS))):
    from .api.router import _get_record, _get_resource, _create_crm_audit_log, _assert_record_visible
    organization = access(db, user, "manage")
    _assert_record_visible(db, _get_resource("files"), file_id, organization, user)
    item = _get_record(db, _get_resource("files"), file_id, organization)
    db.query(CRMFileAsset).filter_by(id=item.id).with_for_update().one()
    db.refresh(item)
    if item.folder_id != data.previous_folder_id: raise HTTPException(409, "This file moved. Refresh before moving again.")
    folder(db, data.folder_id, organization)
    item.folder_id = data.folder_id
    _create_crm_audit_log(db, user_id=user.id, entity_type="files", entity_id=item.id, action="UPDATE", new_values={"folder_id": data.folder_id}, description="File moved to folder")
    db.commit()
    return {"id": item.id, "folder_id": item.folder_id}


@router.post("/file-workspace/upload", status_code=201)
def upload(file: UploadFile = File(...), folder_id: int | None = Form(None), db: Session = Depends(get_db), user: User = Depends(RequirePermission(*CRM_ANY_PERMISSIONS))):
    from app.apps.project_management.api.router import _validate_attachment_upload, _safe_attachment_name, PMS_MAX_ATTACHMENT_BYTES
    organization = access(db, user, "manage")
    folder(db, folder_id, organization)
    _validate_attachment_upload(file)
    original = _safe_attachment_name(file.filename)
    filename = f"{uuid.uuid4().hex}_{original}"
    directory = Path(settings.UPLOAD_DIR).resolve() / "crm" / "files" / str(organization)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    size = 0
    try:
        with target.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > PMS_MAX_ATTACHMENT_BYTES: raise HTTPException(413, "File exceeds the configured size limit")
                output.write(chunk)
        if not size: raise HTTPException(400, "Empty files cannot be uploaded")
        persist_file(str(target))
        item = CRMFileAsset(organization_id=organization, uploaded_by_user_id=user.id, created_by_user_id=user.id, folder_id=folder_id, file_name=filename, original_name=original, mime_type=file.content_type, size_bytes=size, storage_path=str(target), visibility="Internal")
        db.add(item); db.commit(); db.refresh(item)
        return {"id": item.id}
    except Exception:
        db.rollback(); target.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()


@router.get("/file-workspace/files/{file_id}/download")
def download(file_id: int, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*CRM_ANY_PERMISSIONS))):
    from .api.router import _get_record, _get_resource, _assert_record_visible
    organization = access(db, user)
    _assert_record_visible(db, _get_resource("files"), file_id, organization, user)
    item = _get_record(db, _get_resource("files"), file_id, organization)
    path = Path(item.storage_path).resolve()
    root = Path(settings.UPLOAD_DIR).resolve() / "crm" / "files"
    if not path.is_relative_to(root) or not upload_exists(str(path)): raise HTTPException(404, "Stored file not found")
    return FileResponse(path=str(path), filename=item.original_name, media_type=item.mime_type or "application/octet-stream")
