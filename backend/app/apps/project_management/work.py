"""PMS-owned per-assignee execution, versioned evidence and immutable reviews."""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func
from .models import PMSTask, PMSTaskAssignee, PMSProject, PMSWorkSubmission, PMSWorkReview, PMSActivity, PMSFileAsset
from .access import get_project_for_action, same_organization, can_access_project


def activity(db, task, user, action, entity_id=None, metadata=None):
    db.add(PMSActivity(project_id=task.project_id, task_id=task.id, actor_user_id=user.id,
        action=action, entity_type="work", entity_id=entity_id or task.id,
        summary=action.replace(".", " ")[:300], metadata_json=json.dumps(metadata or {})))


def own_assignment(db, task_id, user, lock=False):
    query = db.query(PMSTaskAssignee).filter_by(task_id=task_id, user_id=user.id)
    task = db.query(PMSTask).filter_by(id=task_id).with_for_update().first() if lock else db.get(PMSTask,task_id)
    row = query.with_for_update().first() if lock else query.first()
    project = db.get(PMSProject, task.project_id) if task else None
    if not row or not task or task.deleted_at or not project or project.deleted_at or not same_organization(project, user):
        raise HTTPException(404, "Assigned PMS task not found")
    if project.is_archived:
        raise HTTPException(409, "Project is archived")
    if project.workspace_id:
        from .workspace_lifecycle import is_archived
        if is_archived(db, project.workspace_id):
            raise HTTPException(409, "Workspace is archived")
    if lock and row.cancelled_at:raise HTTPException(409,"This assignment was cancelled; its history is retained")
    return row, task


def sync_parent(db, task):
    db.flush()
    statuses = {r[0] for r in db.query(PMSTaskAssignee.execution_status).filter(PMSTaskAssignee.task_id==task.id,PMSTaskAssignee.cancelled_at.is_(None))}
    task.status = "Done" if statuses and statuses == {"Done"} else "In Review" if "In Review" in statuses else "In Progress" if statuses - {"To Do"} else "To Do"
    task.completed_at = datetime.now(timezone.utc) if task.status == "Done" else None
    from .api.router import _sync_task_column
    _sync_task_column(db, task)


def start(db, task_id, user):
    assignment, task = own_assignment(db, task_id, user, True)
    if assignment.execution_status in {"To Do", "Revision Requested", "Rejected"}:
        assignment.execution_status = "In Progress"
        assignment.started_at = assignment.started_at or datetime.now(timezone.utc)
        activity(db, task, user, "assignment.started")
        sync_parent(db, task)
    db.commit()
    return assignment


def submit(db, task_id, user, data):
    assignment, task = own_assignment(db, task_id, user, True)
    if assignment.execution_status in {"Done","In Review"}:
        raise HTTPException(409,"This assignment is approved or awaiting a PMS decision")
    if not data.draft and not data.confirmed:
        raise HTTPException(422, "Confirm originality and completion before submitting")
    for file_id in data.files:
        f = db.get(PMSFileAsset, file_id)
        if not f or f.deleted_at or f.task_id != task.id or f.uploaded_by_user_id != user.id:
            raise HTTPException(422, "Evidence must belong to you and this task")
    version = (db.query(func.max(PMSWorkSubmission.version)).filter_by(task_id=task.id, user_id=user.id).scalar() or 0) + 1
    item = PMSWorkSubmission(task_id=task.id, user_id=user.id, version=version, notes=data.notes,
        links=[str(v) for v in data.links], files=data.files, revision_note=data.revision_note,
        status="Draft" if data.draft else "Pending Review")
    db.add(item); db.flush()
    if not data.draft:
        assignment.execution_status = "In Review"
        assignment.completed_at = None
        sync_parent(db, task)
        activity(db, task, user, "work.submitted", item.id, {"version": version, "user_id": user.id})
    db.commit()
    return item


def review(db, submission_id, user, data):
    item = db.query(PMSWorkSubmission).filter_by(id=submission_id).with_for_update().first()
    if not item or item.status == "Draft":
        raise HTTPException(404, "PMS submission not found")
    task = db.query(PMSTask).filter_by(id=item.task_id).with_for_update().first()
    get_project_for_action(db, task.project_id, user, "approve")
    assignment = db.query(PMSTaskAssignee).filter_by(task_id=task.id, user_id=item.user_id).with_for_update().first()
    if not assignment or assignment.cancelled_at:
        raise HTTPException(409, "Assignment is no longer available")
    if assignment.reviewer_user_id and assignment.reviewer_user_id != user.id and not user.is_superuser:
        raise HTTPException(403, "This review is delegated to another PMS reviewer")
    latest = db.query(func.max(PMSWorkSubmission.id)).filter(PMSWorkSubmission.task_id == task.id, PMSWorkSubmission.user_id == item.user_id, PMSWorkSubmission.status != "Draft").scalar()
    if latest != item.id or db.query(PMSWorkReview.id).filter_by(submission_id=item.id).first():
        raise HTTPException(409, "Review the latest unreviewed version; previous decisions are immutable")
    if not data.feedback.strip():raise HTTPException(422,"Review feedback is required")
    if not data.inspected:
        raise HTTPException(422, "Inspect the submission evidence before recording a review")
    maximum = assignment.maximum_score or 100
    if data.score > maximum:
        raise HTTPException(422, "Score exceeds this assignment's maximum")
    record = PMSWorkReview(submission_id=item.id, reviewer_user_id=user.id, decision=data.status,
        score=data.score, maximum_score=maximum, communication_score=getattr(data, "communication_score", None),
        rubric=getattr(data, "rubric", {}), feedback=data.feedback, strengths=data.strengths, improvements=data.improvements)
    db.add(record)
    item.status = data.status
    assignment.execution_status = "Done" if data.status in {"Approved", "Reviewed"} else "Rejected" if data.status == "Rejected" else "Revision Requested"
    assignment.progress_percent = 100 if assignment.execution_status == "Done" else min(assignment.progress_percent or 0,99)
    assignment.completed_at = datetime.now(timezone.utc) if assignment.execution_status == "Done" else None
    activity(db, task, user, "work.reviewed", item.id, {"decision": data.status, "score": data.score, "user_id": item.user_id, "version": item.version})
    sync_parent(db, task)
    if task.status == "Done" and task.recurrence_rule:
        from .recurrence import create_next_occurrence
        create_next_occurrence(db, task)
    from app.models.notification import Notification
    from app.apps.srm.services.commercial import tenant
    db.add(Notification(user_id=item.user_id,company_id=tenant(user),title="PMS work review: "+data.status,message=task.title+" · "+data.feedback[:300],module="hrms",event_type="intern_review",channels=["in_app"],is_read=False))
    db.commit()
    from .api.router import _broadcast_realtime
    _broadcast_realtime(user,"task.work_reviewed",project_id=task.project_id,task_id=task.id,message="PMS work review recorded")
    return record


def payload(db, submissions):
    ids = [s.id for s in submissions]
    reviews = {r.submission_id:r for r in db.query(PMSWorkReview).filter(PMSWorkReview.submission_id.in_(ids)).all()} if ids else {}
    tasks={t.id:t for t in db.query(PMSTask).filter(PMSTask.id.in_({s.task_id for s in submissions}))} if ids else {}
    assignments={(a.task_id,a.user_id):a for a in db.query(PMSTaskAssignee).filter(PMSTaskAssignee.task_id.in_(tasks))} if tasks else {}
    from app.models.user import User
    users={u.id:u.email for u in db.query(User).filter(User.id.in_({s.user_id for s in submissions}))} if ids else {}
    result=[]
    for s in submissions:
        r=reviews.get(s.id)
        result.append({"id":s.id,"task_id":s.task_id,"user_id":s.user_id,"version":s.version,"notes":s.notes,
            "links":s.links,"files":s.files,"revision_note":s.revision_note,"status":s.status,"created_at":s.created_at,
            "score":round(r.score*100/r.maximum_score) if r else None,"raw_score":r.score if r else None,
            "task_title":tasks[s.task_id].title,"user_name":users.get(s.user_id),
            "maximum_score":r.maximum_score if r else getattr(assignments.get((s.task_id,s.user_id)),"maximum_score",100),"feedback":r.feedback if r else None,
            "strengths":r.strengths if r else None,"improvements":r.improvements if r else None,
            "reviewed_by":r.reviewer_user_id if r else None,"reviewed_at":r.created_at if r else None})
    return result


def file_access(db, file_id, user):
    item = db.query(PMSFileAsset).filter_by(id=file_id, deleted_at=None).first()
    if not item or not item.task_id:
        raise HTTPException(404, "PMS evidence not found")
    if item.uploaded_by_user_id == user.id:
        own_assignment(db, item.task_id, user)
    else:
        get_project_for_action(db, item.project_id, user, "approve")
    return item


def upload(db, task_id, user, file):
    assignment, task = own_assignment(db, task_id, user, True)
    from .api.router import PMS_MAX_ATTACHMENT_BYTES, _validate_attachment_upload, _safe_attachment_name
    from app.core.storage import persist_file
    _validate_attachment_upload(file)
    original = _safe_attachment_name(file.filename)
    stored = uuid4().hex + "_" + original
    from app.core.config import settings
    directory = Path(settings.UPLOAD_DIR).resolve() / "pms" / "work" / str(task.id)
    directory.mkdir(parents=True, exist_ok=True)
    path=directory/stored; size=0
    try:
        with path.open("wb") as output:
            while chunk := file.file.read(1024*1024):
                size+=len(chunk)
                if size>PMS_MAX_ATTACHMENT_BYTES: raise HTTPException(413,"Evidence exceeds the configured upload limit")
                output.write(chunk)
        if not size: raise HTTPException(422,"Evidence cannot be empty")
        persist_file(str(path))
        item=PMSFileAsset(project_id=task.project_id,task_id=task.id,uploaded_by_user_id=user.id,file_name=stored,original_name=original,
            mime_type=file.content_type or "application/octet-stream",size_bytes=size,storage_path=str(path),visibility="Work Evidence")
        db.add(item);db.flush();activity(db,task,user,"work.evidence_uploaded",item.id);db.commit()
        return {"id":item.id,"name":item.original_name,"size":size}
    except Exception:
        path.unlink(missing_ok=True);raise
    finally:
        file.file.close()
