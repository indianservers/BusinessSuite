"""Project documents with optimistic version checks and immutable revisions."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import accessible_project_query, can_access_project, get_project_for_action, get_task_project_for_action
from .models import PMSDocument, PMSDocumentRevision, PMSProject

router = APIRouter()


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=180)
    content: str = Field(default="", max_length=200000)
    task_id: int | None = None


class SaveInput(DocumentInput):
    version: int = Field(gt=0)


def authorize(db, document_id, user, write=False):
    doc = db.get(PMSDocument, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    project = get_project_for_action(db, doc.project_id, user, "manage_tasks" if write else "browse")
    return doc, project


def validate(db, project_id, data, user):
    if not data.title.strip():
        raise HTTPException(422, "Document title cannot be blank")
    if data.task_id:
        task, _ = get_task_project_for_action(db, data.task_id, user)
        if task.project_id != project_id:
            raise HTTPException(422, "Link a task in this document's project")


def result(db, doc, project, user):
    author = db.get(User, doc.updated_by)
    return {"id": doc.id, "project_id": doc.project_id, "project_name": project.name,
            "title": doc.title, "content": doc.content, "task_id": doc.task_id, "version": doc.version,
            "updated_at": doc.updated_at, "updated_by": author.email if author else "Former collaborator",
            "can_edit": can_access_project(db, project, user, "manage_tasks")}


@router.get("/docs")
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project_ids = accessible_project_query(db, user).with_entities(PMSProject.id)
    rows = db.query(PMSDocument, PMSProject.name).join(PMSProject, PMSProject.id == PMSDocument.project_id).filter(PMSDocument.project_id.in_(project_ids)).order_by(PMSDocument.updated_at.desc()).all()
    return [{"id": doc.id, "title": doc.title, "project_id": doc.project_id, "project_name": name,
             "version": doc.version, "updated_at": doc.updated_at} for doc, name in rows]


@router.post("/projects/{project_id}/docs", status_code=201)
def create_document(project_id: int, data: DocumentInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = get_project_for_action(db, project_id, user, "manage_tasks")
    validate(db, project_id, data, user)
    doc = PMSDocument(project_id=project_id, task_id=data.task_id, title=data.title.strip(), content=data.content,
                      version=1, author_id=user.id, updated_by=user.id)
    db.add(doc)
    db.flush()
    db.add(PMSDocumentRevision(document_id=doc.id, version=1, title=doc.title, content=doc.content, task_id=doc.task_id, author_id=user.id))
    db.commit()
    return result(db, doc, project, user)


@router.get("/docs/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc, project = authorize(db, document_id, user)
    return result(db, doc, project, user)


@router.put("/docs/{document_id}")
def save_document(document_id: int, data: SaveInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc, project = authorize(db, document_id, user, True)
    validate(db, project.id, data, user)
    changed = db.execute(update(PMSDocument).where(PMSDocument.id == document_id, PMSDocument.version == data.version).values(
        title=data.title.strip(), content=data.content, task_id=data.task_id, version=data.version + 1,
        updated_by=user.id, updated_at=datetime.now(timezone.utc)).execution_options(synchronize_session=False)).rowcount
    if changed != 1:
        db.rollback()
        raise HTTPException(409, "This document changed since you opened it. Your draft is kept; reload the latest version before saving.")
    db.add(PMSDocumentRevision(document_id=document_id, version=data.version + 1, title=data.title.strip(), content=data.content, task_id=data.task_id, author_id=user.id))
    db.commit()
    db.refresh(doc)
    return result(db, doc, project, user)


@router.get("/docs/{document_id}/revisions")
def list_revisions(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    authorize(db, document_id, user)
    rows = db.query(PMSDocumentRevision).filter_by(document_id=document_id).order_by(PMSDocumentRevision.version.desc()).all()
    return [{"version": row.version, "title": row.title, "created_at": row.created_at,
             "author": db.get(User, row.author_id).email} for row in rows]


@router.get("/docs/{document_id}/revisions/{version}")
def get_revision(document_id: int, version: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    authorize(db, document_id, user)
    row = db.query(PMSDocumentRevision).filter_by(document_id=document_id, version=version).first()
    if not row:
        raise HTTPException(404, "Revision not found")
    return {"title": row.title, "content": row.content, "task_id": row.task_id, "version": row.version}
