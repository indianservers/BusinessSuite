"""Explicit, idempotent conversion of old Hub history into an authorized PMS project.

Original rows and files are never deleted. No runtime task write uses these tables.
"""
import shutil
from pathlib import Path
from fastapi import HTTPException
from app.core.config import settings
from app.core.storage import persist_file
from app.models.user import User
from app.models.employee import Employee
from app.apps.project_management.models import PMSTaskAssignee, PMSWorkSubmission, PMSWorkReview, PMSFileAsset
from app.apps.project_management.access import get_project_for_action, can_access_project
from app.apps.project_management.schemas import PMSTaskCreate
from app.apps.project_management.work import activity
from .models import InternTask, InternSubmission, InternFile
from .management_models import InternLegacyTaskMap, InternLegacyFileMap
from .management_access import employee_query


def pending_query(db,user):
    return db.query(InternTask).filter(InternTask.employee_id.in_(employee_query(db,user).with_entities(Employee.id)),InternTask.id.notin_(db.query(InternLegacyTaskMap.legacy_task_id)))


def import_history(db,user,project_id,reviewer_user_id,limit=100):
    project=get_project_for_action(db,project_id,user,"manage_tasks")
    reviewer=db.get(User,reviewer_user_id)
    if not reviewer or not can_access_project(db,project,reviewer,"approve"):raise HTTPException(403,"Select a PMS-authorized reviewer")
    ids=[r[0] for r in pending_query(db,user).with_entities(InternTask.id).order_by(InternTask.id).limit(limit)]
    converted=0;errors=[]
    for legacy_id in ids:
        try:
            old=db.query(InternTask).filter_by(id=legacy_id).with_for_update().one()
            if db.get(InternLegacyTaskMap,old.id):continue
            employee=db.get(Employee,old.employee_id)
            if not employee.user_id:raise HTTPException(409,"Link an intern login account before importing this history")
            from app.apps.project_management.api.router import create_task_operation,PMS_UPLOAD_ROOT
            description=old.description or ""
            for name in ["objectives","instructions","deliverables"]:
                if getattr(old,name,None):description+="\n\n"+name.title()+":\n"+getattr(old,name)
            task=create_task_operation(project.id,PMSTaskCreate(title=old.title,description=description,task_key=f"IH-LEGACY-{old.id}",priority=old.priority,due_date=old.due_date,component=old.category),db,user,commit=False)
            task.created_at=old.created_at
            assignment=PMSTaskAssignee(task_id=task.id,user_id=employee.user_id,execution_status={"Completed":"Done","In Review":"In Review","In Progress":"In Progress"}.get(old.status,"To Do"),
                due_date=old.due_date,reviewer_user_id=reviewer.id,maximum_score=100,source_key=f"legacy-intern-task:{old.id}")
            db.add(assignment);db.flush()
            history=db.query(InternSubmission).filter_by(task_id=old.id).order_by(InternSubmission.id).all()
            for version,s in enumerate(history,1):
                files=[]
                for fid in s.files or []:
                    mapping=db.get(InternLegacyFileMap,(fid,task.id))
                    if not mapping:
                        old_file=db.get(InternFile,fid)
                        if not old_file or old_file.employee_id!=employee.id:raise HTTPException(409,"Legacy evidence ownership requires reconciliation")
                        source=Path(settings.UPLOAD_DIR).resolve().parent/"intern-hub-private"/old_file.storage_key
                        target=PMS_UPLOAD_ROOT/"legacy"/old_file.storage_key
                        if not source.is_file() and not target.is_file():raise HTTPException(409,f"Restore legacy evidence file {fid} before importing this task")
                        target.parent.mkdir(parents=True,exist_ok=True)
                        if not target.is_file():shutil.copy2(source,target)
                        persist_file(str(target))
                        asset=PMSFileAsset(project_id=project.id,task_id=task.id,uploaded_by_user_id=employee.user_id,file_name=old_file.storage_key,original_name=old_file.name,size_bytes=old_file.size,storage_path=str(target),visibility="Work Evidence")
                        db.add(asset);db.flush();mapping=InternLegacyFileMap(legacy_file_id=fid,task_id=task.id,file_id=asset.id);db.add(mapping)
                    files.append(mapping.file_id)
                item=PMSWorkSubmission(task_id=task.id,user_id=employee.user_id,version=version,notes=s.notes,links=s.links or [],files=files,revision_note=s.revision_note,status=s.status,legacy_submission_id=s.id,created_at=s.created_at)
                db.add(item);db.flush()
                if s.score is not None:
                    db.add(PMSWorkReview(submission_id=item.id,reviewer_user_id=s.reviewed_by,decision=s.status,score=s.score,maximum_score=100,feedback=s.feedback or "Imported historical review",strengths=s.strengths,improvements=s.improvements,created_at=s.reviewed_at or s.created_at))
            db.add(InternLegacyTaskMap(legacy_task_id=old.id,task_id=task.id))
            task.status="Done" if assignment.execution_status=="Done" else "In Review" if assignment.execution_status=="In Review" else "In Progress" if assignment.execution_status=="In Progress" else "To Do"
            activity(db,task,user,"legacy.intern_history_imported",metadata={"legacy_task_id":old.id,"versions":len(history)})
            db.commit();converted+=1
        except Exception as exc:
            db.rollback();errors.append({"legacy_task_id":legacy_id,"reason":str(getattr(exc,"detail",type(exc).__name__))})
    return {"converted":converted,"remaining":pending_query(db,user).count(),"errors":errors}
