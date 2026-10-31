"""Project uploads and folder organization using the existing authenticated storage."""
import uuid
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from .access import get_project_for_action
from .models import PMSFileFolder, PMSFileAsset

router = APIRouter(tags=["PMS Files"])


class FolderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: int
    name: str = Field(min_length=1, max_length=150)


def folder_for_project(db, identity, project_id):
    item = db.query(PMSFileFolder).filter_by(id=identity, project_id=project_id).first()
    if not item: raise HTTPException(404, "Folder not found in this project")
    return item


@router.get("/file-folders")
def list_folders(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_for_action(db, project_id, user, "browse")
    return [{"id": f.id, "name": f.name} for f in db.query(PMSFileFolder).filter_by(project_id=project_id).order_by(PMSFileFolder.name, PMSFileFolder.id)]


@router.post("/file-folders", status_code=201)
def create_folder(data: FolderInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_for_action(db, data.project_id, user, "upload")
    name = data.name.strip()
    if not name: raise HTTPException(422, "Folder name is required")
    item = PMSFileFolder(project_id=data.project_id, name=name)
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "name": item.name}


@router.post("/projects/{project_id}/files/upload", status_code=201)
def upload_project_file(project_id: int, file: UploadFile = File(...), folder_id: int | None = Form(None), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .api.router import _validate_attachment_upload, _safe_attachment_name, PMS_UPLOAD_ROOT, PMS_MAX_ATTACHMENT_BYTES, _file_payload, _record_activity
    from app.core.storage import persist_file
    project = get_project_for_action(db, project_id, user, "upload")
    if folder_id: folder_for_project(db, folder_id, project.id)
    _validate_attachment_upload(file)
    original = _safe_attachment_name(file.filename)
    filename = f"{uuid.uuid4().hex}_{original}"
    directory = PMS_UPLOAD_ROOT / "projects" / str(project.id)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    size = 0
    try:
        with target.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > PMS_MAX_ATTACHMENT_BYTES: raise HTTPException(413, "File exceeds the configured size limit")
                output.write(chunk)
        if not size: raise HTTPException(400, "File cannot be empty")
        persist_file(str(target))
        asset = PMSFileAsset(project_id=project.id, folder_id=folder_id, uploaded_by_user_id=user.id, file_name=filename, original_name=original, storage_path=str(target), mime_type=file.content_type or "application/octet-stream", size_bytes=size, visibility="Project Team")
        db.add(asset); db.flush()
        _record_activity(db, project.id, user, "attachment.added", "file", asset.id, f"Uploaded {original}", metadata={"folder_id": folder_id})
        db.commit(); db.refresh(asset)
        return _file_payload(asset, user)
    except Exception:
        db.rollback(); target.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()
