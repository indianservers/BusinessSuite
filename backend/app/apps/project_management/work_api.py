from app.core.rich_text import rich_text_type
from typing import Literal
from datetime import date
from fastapi import APIRouter, Depends, Query, File, UploadFile
from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.core.storage import FileResponse
from .models import PMSWorkSubmission, PMSTask, PMSProject, PMSTaskAssignee
from .access import get_project_for_action, accessible_project_query, can_access_project
from . import work

router=APIRouter(prefix="/work",tags=["PMS Work Submissions"])


class SubmissionInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    notes:rich_text_type(5000, 1) = Field()
    links:list[HttpUrl]=Field(default_factory=list,max_length=5)
    files:list[int]=Field(default_factory=list,max_length=10)
    revision_note:str|None=Field(None,max_length=2000)
    draft:bool=False
    confirmed:bool=False


class ReviewInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    status:Literal["Approved","Needs Revision","Rejected"]
    score:int=Field(ge=0,le=1000)
    communication_score:int|None=Field(None,ge=0,le=100)
    rubric:dict=Field(default_factory=dict)
    feedback:rich_text_type(5000, 1) = Field()
    strengths:str=Field("",max_length=2000)
    improvements:str=Field("",max_length=2000)
    inspected:bool=False


@router.get("/submissions")
def submissions(submission_id:int|None=None,task_id:int|None=None,status:str="",page:int=Query(1,ge=1),per_page:int=Query(50,ge=1,le=200),user=Depends(get_current_user),db:Session=Depends(get_db)):
    from sqlalchemy import or_
    from app.apps.srm.services.commercial import tenant
    projects=accessible_project_query(db,user).all()
    approve={p.id for p in projects if can_access_project(db,p,user,"approve")}
    # Scope before count/pagination. Ordinary viewers cannot infer others' evidence.
    q=db.query(PMSWorkSubmission).join(PMSTask,PMSTask.id==PMSWorkSubmission.task_id).join(PMSProject,PMSProject.id==PMSTask.project_id).filter(
        PMSTask.deleted_at.is_(None),PMSProject.deleted_at.is_(None),
        __import__('sqlalchemy').func.coalesce(PMSProject.organization_id,1)==tenant(user),
        or_(PMSTask.project_id.in_(approve),PMSWorkSubmission.user_id==user.id),PMSWorkSubmission.status!="Draft")
    if submission_id:q=q.filter(PMSWorkSubmission.id==submission_id)
    if task_id:q=q.filter(PMSWorkSubmission.task_id==task_id)
    if status:q=q.filter(PMSWorkSubmission.status==status)
    items=q.order_by(PMSWorkSubmission.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    assignments={(a.task_id,a.user_id):a for a in db.query(PMSTaskAssignee).filter(PMSTaskAssignee.task_id.in_({i.task_id for i in items}))}
    tasks={t.id:t for t in db.query(PMSTask).filter(PMSTask.id.in_({i.task_id for i in items}))}
    result=work.payload(db,items)
    for r in result:
        assignment=assignments.get((r["task_id"],r["user_id"]))
        r["can_review"]=tasks[r["task_id"]].project_id in approve and bool(assignment) and (not assignment.reviewer_user_id or assignment.reviewer_user_id==user.id or user.is_superuser)
    return {"items":result,"total":q.count()}



@router.post("/tasks/{task_id}/start")
def start(task_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    row=work.start(db,task_id,user);return {"task_id":task_id,"user_id":user.id,"status":row.execution_status}


@router.post("/tasks/{task_id}/submissions",status_code=201)
def submit(task_id:int,data:SubmissionInput,user=Depends(get_current_user),db:Session=Depends(get_db)):
    return work.payload(db,[work.submit(db,task_id,user,data)])[0]


@router.post("/tasks/{task_id}/files",status_code=201)
def upload(task_id:int,file:UploadFile=File(...),user=Depends(get_current_user),db:Session=Depends(get_db)):
    return work.upload(db,task_id,user,file)


@router.get("/files/{file_id}")
def file(file_id:int,user=Depends(get_current_user),db:Session=Depends(get_db)):
    item=work.file_access(db,file_id,user)
    return FileResponse(item.storage_path,filename=item.original_name,media_type="application/octet-stream")


@router.post("/submissions/{submission_id}/review")
def review(submission_id:int,data:ReviewInput,user=Depends(get_current_user),db:Session=Depends(get_db)):
    row=work.review(db,submission_id,user,data);return {"id":row.id,"submission_id":row.submission_id,"decision":row.decision,"score":row.score}


class ReviewerInput(BaseModel):
    reviewer_user_id:int


@router.get('/assignments')
def my_assignments(page:int=Query(1,ge=1),per_page:int=Query(50,ge=1,le=200),user=Depends(get_current_user),db:Session=Depends(get_db)):
    from sqlalchemy import func
    from app.apps.srm.services.commercial import tenant
    q=db.query(PMSTaskAssignee,PMSTask).join(PMSTask,PMSTask.id==PMSTaskAssignee.task_id).join(PMSProject,PMSProject.id==PMSTask.project_id).filter(PMSTaskAssignee.user_id==user.id,PMSTask.deleted_at.is_(None),PMSProject.deleted_at.is_(None),func.coalesce(PMSProject.organization_id,1)==tenant(user))
    rows=q.order_by(PMSTask.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    details=work.plan_details_many(db,[(t.id,a.user_id) for a,t in rows])
    return {'items':[{'id':t.id,'title':t.title,'description':t.description,'project_id':t.project_id,'status':'Cancelled' if a.cancelled_at else a.execution_status,'due_date':a.due_date or t.due_date,'start_date':t.start_date,'progress':a.progress_percent,'notes':a.work_notes,'reviewer_user_id':a.reviewer_user_id,'maximum_score':a.maximum_score,**details[(t.id,a.user_id)]} for a,t in rows],'total':q.count()}

class ProgressInput(BaseModel):
    progress_percent:int=Field(ge=0,le=99)
    notes:rich_text_type(5000, 0) = Field('')

@router.post('/tasks/{task_id}/progress')
def progress(task_id:int,data:ProgressInput,user=Depends(get_current_user),db:Session=Depends(get_db)):
    from fastapi import HTTPException
    a,t=work.own_assignment(db,task_id,user,True)
    if a.execution_status in {'Done','In Review'}:raise HTTPException(409,'Approved or submitted work cannot be edited')
    a.progress_percent=data.progress_percent;a.work_notes=data.notes;a.execution_status='In Progress'
    work.activity(db,t,user,'assignment.progress',metadata={'user_id':user.id,'percent':a.progress_percent});work.sync_parent(db,t);db.commit()
    return {'progress_percent':a.progress_percent,'notes':a.work_notes}

class AssignmentControl(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['deadline','cancel','restore','reassign']
    due_date:date|None=None
    new_user_id:int|None=None
    reason:str=Field(min_length=1,max_length=2000)

@router.post('/tasks/{task_id}/assignees/{assignee_id}/control')
def control(task_id:int,assignee_id:int,data:AssignmentControl,user=Depends(get_current_user),db:Session=Depends(get_db)):
    from fastapi import HTTPException
    from datetime import datetime,timezone
    from app.models.user import User
    from app.apps.interns_hub.management_access import require_admin,get_employee
    task=db.query(PMSTask).filter_by(id=task_id,deleted_at=None).with_for_update().first()
    if not task:raise HTTPException(404,'Task not found')
    get_project_for_action(db,task.project_id,user,'manage_tasks');require_admin(user)
    actor=db.get(User,assignee_id)
    if not actor or not actor.employee:raise HTTPException(404,'Assignee not found')
    get_employee(db,user,actor.employee.id)
    a=db.query(PMSTaskAssignee).filter_by(task_id=task_id,user_id=assignee_id).with_for_update().first()
    if not a:raise HTTPException(404,'Assignment not found')
    if a.execution_status=='Done':raise HTTPException(409,'Completed assignments are historical records')
    if data.action=='deadline':
        if not data.due_date:raise HTTPException(422,'Choose the individual deadline')
        a.due_date=data.due_date
    elif data.action=='cancel':a.cancelled_at=datetime.now(timezone.utc)
    elif data.action=='restore':a.cancelled_at=None
    else:
        from .models import PMSInternAssignmentPlan
        if db.get(PMSInternAssignmentPlan, (task_id, assignee_id)):
            raise HTTPException(409, 'Publish a new task pack for reassignment so dependencies and rubric remain consistent')
        target=db.get(User,data.new_user_id) if data.new_user_id else None
        if not target or not target.is_active or not target.employee:raise HTTPException(422,'Choose an active approved account')
        get_employee(db,user,target.employee.id)
        if db.get(PMSTaskAssignee,(task_id,target.id)):raise HTTPException(409,'Target already has this task')
        db.add(PMSTaskAssignee(task_id=task_id,user_id=target.id,due_date=a.due_date,reviewer_user_id=a.reviewer_user_id,maximum_score=a.maximum_score,source_key=a.source_key))
        a.cancelled_at=datetime.now(timezone.utc)
    work.activity(db,task,user,'assignment.'+data.action,metadata={'user_id':assignee_id,'new_user_id':data.new_user_id,'due_date':str(data.due_date) if data.due_date else None,'reason':data.reason});work.sync_parent(db,task);db.commit()
    return {'task_id':task_id,'user_id':assignee_id,'due_date':a.due_date,'cancelled':bool(a.cancelled_at),'history_preserved':True}


@router.post("/tasks/{task_id}/assignees/{user_id}/reviewer")
def reviewer(task_id:int,user_id:int,data:ReviewerInput,user=Depends(get_current_user),db:Session=Depends(get_db)):
    from app.models.user import User
    from fastapi import HTTPException
    task=db.get(PMSTask,task_id)
    if not task:raise HTTPException(404,"Task not found")
    project=get_project_for_action(db,task.project_id,user,"manage_tasks")
    actor=db.get(User,data.reviewer_user_id)
    if not actor or not actor.is_active or not can_access_project(db,project,actor,"approve"):raise HTTPException(403,"Reviewer lacks PMS approval permission")
    from .models import PMSInternAssignmentPlan
    if db.get(PMSInternAssignmentPlan, (task_id, user_id)):
        from app.apps.interns_hub.management_access import require_admin
        from app.apps.srm.services.commercial import tenant
        require_admin(actor)
        if tenant(actor) != tenant(user):
            raise HTTPException(403, "Reviewer must belong to your company")
    row=db.query(PMSTaskAssignee).filter_by(task_id=task_id,user_id=user_id).first()
    if not row:raise HTTPException(404,"Assignee not found")
    row.reviewer_user_id=actor.id;work.activity(db,task,user,"work.reviewer_changed",metadata={"user_id":user_id,"reviewer_user_id":actor.id});db.commit();return {"reviewer_user_id":actor.id}
