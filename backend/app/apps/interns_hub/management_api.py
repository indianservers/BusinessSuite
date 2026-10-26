from app.core.rich_text import rich_text_type
from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4
import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, ConfigDict, model_validator
from sqlalchemy import func, or_, case
from sqlalchemy.orm import Session, joinedload
from app.core.deps import get_db
from app.models.user import User
from app.models.employee import Employee
from app.models.company import Branch, Department
from app.models.notification import Notification
from app.apps.srm.services.commercial import tenant
from app.apps.project_management.models import PMSProject, PMSTask, PMSTaskAssignee, PMSWorkSubmission, PMSWorkReview, PMSActivity
from app.apps.project_management.access import accessible_project_query, can_access_project, get_project_for_action
from app.apps.project_management import work
from .management_access import require_admin, organization_admin, batch_query, employee_query, get_batch, get_employee
from .management_models import InternBatch, InternBatchMembership, InternDistribution, InternCompletionReview, InternReportReview, InternTaskSchedule
from .models import InternReport, InternApplication, InternCertificate
from .performance import filtered_employees, performance, task_aggregates, WEIGHTS
from .distribution import recipients, publish, process_job

router=APIRouter(prefix="/management",tags=["HRMS Intern Management"])


def today():
    from .router import today as day
    return day()


def encoded(row):
    return {c.name:getattr(row,c.name) for c in row.__table__.columns}


def filters(include_employees:bool=False,search: str="",department_id:int|None=None,batch_id:int|None=None,reporting_manager_id:int|None=None,mentor_id:int|None=None,program:str="",internship_status:str="",college:str="",skill:str="",date_from:date|None=None,date_to:date|None=None):
    if date_from and date_to and date_from>date_to:raise HTTPException(422,"Date range is reversed")
    return dict(include_employees=include_employees,search=search,department_id=department_id,batch_id=batch_id,reporting_manager_id=reporting_manager_id,mentor_id=mentor_id,program=program,status=internship_status,college=college,skill=skill,date_from=date_from,date_to=date_to)


@router.get("/access")
def access(user=Depends(require_admin)):
    return {"allowed":True,"organization_id":tenant(user),"organization_admin":organization_admin(user)}


@router.get("/options")
def options(user=Depends(require_admin),db:Session=Depends(get_db)):
    projects=accessible_project_query(db,user).order_by(PMSProject.id).limit(200).all()
    departments=db.query(Department).join(Branch,Department.branch_id==Branch.id).filter(Branch.company_id==tenant(user)).all()
    from app.models.user import Role
    staff=db.query(User).outerjoin(Role,Role.id==User.role_id).options(joinedload(User.role),joinedload(User.employee)).filter(User.is_active==True,or_(User.is_superuser==True,func.lower(Role.name).notin_(["intern","employee"]))).order_by(User.id).limit(1000).all()
    staff=[u for u in staff if tenant(u)==tenant(user) and (u.is_superuser or u.role and u.role.name.lower() not in {"intern","employee"})]
    return {"projects":[{"id":p.id,"name":p.name,"can_assign":can_access_project(db,p,user,"manage_tasks"),"can_review":can_access_project(db,p,user,"approve")} for p in projects],
        "departments":[{"id":d.id,"name":d.name} for d in departments],"staff":[{"id":u.id,"name":f"{u.employee.first_name} {u.employee.last_name}" if u.employee else u.email} for u in staff],
        "batches":[{"id":b.id,"name":b.name,"code":b.code} for b in batch_query(db,user).order_by(InternBatch.id).limit(1000)]}


@router.get("/interns")
def interns(f=Depends(filters),page:int=Query(1,ge=1),per_page:int=Query(50,ge=1,le=200),user=Depends(require_admin),db:Session=Depends(get_db)):
    return performance(db,user,f,today(),page=page,per_page=per_page)


@router.get("/batches")
def batches(mentor_id:int|None=None,date_from:date|None=None,date_to:date|None=None,batch_type:str="",search:str="",status:str="",department_id:int|None=None,page:int=Query(1,ge=1),per_page:int=Query(50,ge=1,le=200),user=Depends(require_admin),db:Session=Depends(get_db)):
    q=batch_query(db,user)
    if search:q=q.filter(or_(InternBatch.name.ilike("%"+search+"%"),InternBatch.code.ilike("%"+search+"%")))
    if status:q=q.filter(InternBatch.status==status)
    if department_id:q=q.filter(InternBatch.department_id==department_id)
    if mentor_id:q=q.filter(InternBatch.mentor_user_id==mentor_id)
    if date_from:q=q.filter(InternBatch.end_date>=date_from)
    if date_to:q=q.filter(InternBatch.start_date<=date_to)
    if batch_type:q=q.filter(InternBatch.batch_type==batch_type)
    total=q.count();items=q.order_by(InternBatch.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    counts=dict(db.query(InternBatchMembership.batch_id,func.count(InternBatchMembership.id)).filter(InternBatchMembership.batch_id.in_([b.id for b in items]),InternBatchMembership.status=="Active").group_by(InternBatchMembership.batch_id))
    names={u.id:u.email for u in db.query(User).filter(User.id.in_({b.manager_user_id for b in items}|{b.mentor_user_id for b in items}))}
    return {"items":[{**encoded(b),"members":counts.get(b.id,0),"manager":names.get(b.manager_user_id),"mentor":names.get(b.mentor_user_id)} for b in items],"total":total,"page":page,"per_page":per_page}


class BatchInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name:str=Field(min_length=1,max_length=180)
    code:str=Field(min_length=1,max_length=40)
    department_id:int
    manager_user_id:int
    mentor_user_id:int
    additional_mentors:list[int]=Field(default_factory=list,max_length=30)
    project_id:int
    batch_type:Literal["Intern","Employee","Training","Mixed"]="Intern"
    coordinator_user_id:int|None=None
    project_ids:list[int]=Field(default_factory=list,max_length=100)
    task_templates:list[int]=Field(default_factory=list,max_length=100)
    program:str=Field("Internship",max_length=100)
    specialization:str=Field("",max_length=160)
    description:rich_text_type(10000, 0) = Field("")
    start_date:date
    end_date:date
    capacity:int=Field(ge=1,le=20000)
    expected_hours:float=Field(8,gt=0,le=24)
    reporting_frequency:Literal["Daily","Weekly"]="Daily"
    policy:dict=Field(default_factory=lambda:{"weights":WEIGHTS,"completion":{"minimum_days":90,"minimum_tasks":1,"minimum_reports_percent":80}})

    @model_validator(mode="after")
    def validate_policy(self):
        if self.end_date<self.start_date:raise ValueError("End date must follow start date")
        weights=self.policy.get("weights",WEIGHTS)
        if set(weights)!=set(WEIGHTS) or any(not isinstance(v,(int,float)) or v<0 for v in weights.values()) or sum(weights.values())!=100:raise ValueError("Five performance weights must sum to 100")
        c=self.policy.get("completion",{})
        if any(not isinstance(c.get(k,0),(int,float)) or not 0<=c.get(k,0)<=100 for k in ["minimum_reports_percent","minimum_attendance_percent"]):raise ValueError("Completion percentages must be between 0 and 100")
        if c.get("minimum_days",0)<0 or c.get("minimum_tasks",0)<0:raise ValueError("Completion minimums cannot be negative")
        return self


def validate_batch(db,user,data):
    d=db.get(Department,data.department_id);branch=db.get(Branch,d.branch_id) if d else None
    if not branch or branch.company_id!=tenant(user):raise HTTPException(403,"Department is outside this organization")
    if not organization_admin(user) and (not user.employee or user.employee.department_id!=d.id or data.manager_user_id!=user.id):raise HTTPException(403,"Managers may create batches only in their assigned department and ownership")
    project=get_project_for_action(db,data.project_id,user,"manage_tasks")
    for uid in [data.manager_user_id,data.mentor_user_id,*data.additional_mentors]:
        actor=db.get(User,uid)
        if not actor or not actor.is_active or tenant(actor)!=tenant(user):raise HTTPException(422,"Choose staff from this organization")
        if uid!=data.manager_user_id and not can_access_project(db,project,actor,"approve"):raise HTTPException(403,"Mentors require existing PMS approval access")
    if data.coordinator_user_id:
        coordinator=db.get(User,data.coordinator_user_id)
        if not coordinator or tenant(coordinator)!=tenant(user):raise HTTPException(403,"Coordinator is outside this organization")
        require_admin(coordinator)
    for pid in data.project_ids:get_project_for_action(db,pid,user,"manage_tasks")
    for tid in data.task_templates:
        template=db.get(PMSTask,tid)
        if not template or template.deleted_at or template.project_id not in {data.project_id,*data.project_ids}:raise HTTPException(422,"Task template must belong to an associated PMS project")
    manager=db.get(User,data.manager_user_id);require_admin(manager)


@router.post("/batches",status_code=201)
def create_batch(data:BatchInput,user=Depends(require_admin),db:Session=Depends(get_db)):
    validate_batch(db,user,data)
    if db.query(InternBatch.id).filter_by(organization_id=tenant(user),code=data.code).first():raise HTTPException(409,"Batch code already exists")
    b=InternBatch(**data.model_dump(),organization_id=tenant(user));db.add(b);db.commit();return encoded(b)


@router.put("/batches/{batch_id}")
def edit_batch(batch_id:int,data:BatchInput,user=Depends(require_admin),db:Session=Depends(get_db)):
    b=get_batch(db,user,batch_id);db.query(InternBatch).filter_by(id=b.id).with_for_update().first();validate_batch(db,user,data)
    if db.query(InternBatch.id).filter(InternBatch.organization_id==tenant(user),InternBatch.code==data.code,InternBatch.id!=b.id).first():raise HTTPException(409,"Batch code already exists")
    if data.capacity<db.query(InternBatchMembership).filter_by(batch_id=b.id,status="Active").count():raise HTTPException(409,"Capacity cannot be below current membership")
    for key,value in data.model_dump().items():setattr(b,key,value)
    db.commit();return encoded(b)


class Transition(BaseModel):
    status:Literal["Draft","Upcoming","Active","Evaluation","Completed","Archived"]


@router.post("/batches/{batch_id}/transition")
def transition(batch_id:int,data:Transition,user=Depends(require_admin),db:Session=Depends(get_db)):
    b=get_batch(db,user,batch_id)
    allowed={"Draft":{"Upcoming","Archived"},"Upcoming":{"Active","Archived"},"Active":{"Evaluation","Archived"},"Evaluation":{"Active","Completed","Archived"},"Completed":{"Archived"},"Archived":set()}
    if data.status not in allowed.get(b.status,set()):raise HTTPException(409,"Invalid batch lifecycle transition")
    if data.status=="Completed":
        active=db.query(InternBatchMembership.employee_id).filter_by(batch_id=b.id,status="Active")
        approved=db.query(InternCompletionReview.employee_id).filter_by(batch_id=b.id,decision="Approved")
        if active.filter(InternBatchMembership.employee_id.notin_(approved)).first():raise HTTPException(409,"Review every active intern's completion first")
    b.status=data.status;db.commit();return encoded(b)


class MembershipInput(BaseModel):
    employee_ids:list[int]=Field(default_factory=list,max_length=20000)
    select_filter:dict|None=None
    action:Literal["add","remove","transfer","deactivate","reactivate"]="add"
    target_batch_id:int|None=None
    reason:str=Field("",max_length=2000)


@router.post("/batches/{batch_id}/members")
def membership(batch_id:int,data:MembershipInput,user=Depends(require_admin),db:Session=Depends(get_db)):
    source=get_batch(db,user,batch_id)
    target=get_batch(db,user,data.target_batch_id) if data.action=="transfer" and data.target_batch_id else source
    if data.action=="transfer" and target.id==source.id:raise HTTPException(422,"Choose a different target batch")
    for bid in sorted({source.id,target.id}):db.query(InternBatch).filter_by(id=bid).with_for_update().first()
    if target.status in {"Completed","Archived"}:raise HTTPException(409,"Cannot change a closed batch")
    q=filtered_employees(db,user,data.select_filter) if data.select_filter is not None else employee_query(db,user,include_employees=True).filter(Employee.id.in_(data.employee_ids))
    ids=[r[0] for r in q.with_entities(Employee.id).order_by(Employee.id)]
    if data.select_filter is None and set(ids)!=set(data.employee_ids):raise HTTPException(403,"One or more interns are outside your scope")
    if not ids:raise HTTPException(422,"Select at least one authorized intern")
    chosen=employee_query(db,user,include_employees=True).filter(Employee.id.in_(ids)).all()
    if any(e.status not in {"Active","Probation"} or not e.user or not e.user.is_active for e in chosen):raise HTTPException(409,"Batch members require an approved active account")
    if target.batch_type=="Intern" and any((e.employment_type or "").lower()!="intern" for e in chosen):raise HTTPException(422,"This batch accepts interns only")
    if target.batch_type=="Employee" and any((e.employment_type or "").lower()=="intern" for e in chosen):raise HTTPException(422,"This batch accepts regular employees only")
    existing={m.employee_id:m for m in db.query(InternBatchMembership).filter_by(batch_id=source.id,status="Active").filter(InternBatchMembership.employee_id.in_(ids))}
    target_existing={r[0] for r in db.query(InternBatchMembership.employee_id).filter_by(batch_id=target.id,status="Active")}
    add=set(ids)-target_existing if data.action in {"add","transfer","reactivate"} else set()
    if data.action=="transfer" and set(existing)!=set(ids):raise HTTPException(409,"Transfer only active source members")
    if len(target_existing)+len(add)>target.capacity:raise HTTPException(409,"Batch capacity would be exceeded")
    now=datetime.now(timezone.utc)
    if data.action in {"remove","transfer","deactivate"}:
        for m in existing.values():m.status="Transferred" if data.action=="transfer" else "Inactive";m.active_slot=None;m.left_at=now;m.reason=data.reason
    db.flush()
    db.bulk_insert_mappings(InternBatchMembership,[dict(batch_id=target.id,employee_id=eid,status="Active",active_slot=1,assigned_by=user.id,previous_batch_id=source.id if data.action=="transfer" else None,reason=data.reason) for eid in add])
    db.commit();return {"processed":len(ids),"added":len(add),"history_retained":True}


@router.get("/memberships/{employee_id}")
def membership_history(employee_id:int,user=Depends(require_admin),db:Session=Depends(get_db)):
    get_employee(db,user,employee_id)
    return [encoded(m) for m in db.query(InternBatchMembership).join(InternBatch,InternBatch.id==InternBatchMembership.batch_id).filter(InternBatchMembership.employee_id==employee_id,InternBatch.organization_id==tenant(user)).order_by(InternBatchMembership.id.desc())]


class DistributionInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    project_id:int
    task_id:int|None=None
    title:str=Field("",max_length=220)
    description:rich_text_type(20000, 0) = Field("")
    category:str=Field("Project",max_length=80)
    instructions:str=Field("",max_length=10000)
    deliverables:str=Field("",max_length=10000)
    review_instructions:str=Field("",max_length=5000)
    priority:Literal["Low","Medium","High","Critical"]="Medium"
    target_type:Literal["interns","batches","department","all"]="interns"
    employee_ids:list[int]=Field(default_factory=list,max_length=20000)
    batch_ids:list[int]=Field(default_factory=list,max_length=500)
    exclude_ids:list[int]=Field(default_factory=list,max_length=20000)
    department_id:int|None=None
    program:str=""
    search:str=""
    reviewer_user_id:int
    maximum_score:int=Field(100,ge=1,le=1000)
    start_date:date|None=None
    due_date:date
    estimated_hours:float|None=Field(None,ge=0,le=10000)
    idempotency_key:str=Field(min_length=1,max_length=100)
    recurrence:Literal["daily","weekly","custom"]|None=None
    recurrence_interval:int=Field(1,ge=1,le=365)
    recurrence_until:date|None=None


@router.get("/projects/{project_id}/tasks")
def project_tasks(project_id:int,search:str="",page:int=Query(1,ge=1),per_page:int=Query(50,ge=1,le=100),user=Depends(require_admin),db:Session=Depends(get_db)):
    get_project_for_action(db,project_id,user,"manage_tasks")
    q=db.query(PMSTask).filter_by(project_id=project_id,deleted_at=None)
    if search:q=q.filter(PMSTask.title.ilike("%"+search+"%"))
    return {"items":[{"id":t.id,"title":t.title,"task_key":t.task_key,"status":t.status,"due_date":t.due_date} for t in q.order_by(PMSTask.id.desc()).offset((page-1)*per_page).limit(per_page)],"total":q.count()}


@router.post("/distributions/preview")
def preview(data:DistributionInput,user=Depends(require_admin),db:Session=Depends(get_db)):
    get_project_for_action(db,data.project_id,user,"manage_tasks")
    q=recipients(db,user,data.model_dump());return {"total":q.count(),"sample":[{"id":e.id,"name":f"{e.first_name} {e.last_name}","intern_id":e.employee_id} for e in q.order_by(Employee.id).limit(20)]}


@router.post("/distributions",status_code=201)
def distribute(data:DistributionInput,user=Depends(require_admin),db:Session=Depends(get_db)):
    return encoded(publish(db,user,data.model_dump()))


@router.get("/distributions")
def distributions(page:int=Query(1,ge=1),per_page:int=Query(30,ge=1,le=100),user=Depends(require_admin),db:Session=Depends(get_db)):
    projects=accessible_project_query(db,user).with_entities(PMSProject.id)
    q=db.query(InternDistribution).join(PMSTask,PMSTask.id==InternDistribution.task_id).filter(InternDistribution.organization_id==tenant(user),PMSTask.project_id.in_(projects))
    if not organization_admin(user):q=q.filter(InternDistribution.created_by==user.id)
    jobs=q.order_by(InternDistribution.id.desc()).offset((page-1)*per_page).limit(per_page).all();taskids=[j.task_id for j in jobs]
    tasks={t.id:t for t in db.query(PMSTask).filter(PMSTask.id.in_(taskids))}
    counts={(r[0],r[1]):r[2] for r in db.query(PMSTaskAssignee.task_id,PMSTaskAssignee.execution_status,func.count()).filter(PMSTaskAssignee.task_id.in_(taskids)).group_by(PMSTaskAssignee.task_id,PMSTaskAssignee.execution_status)}
    submitted=dict(db.query(PMSWorkSubmission.task_id,func.count(func.distinct(PMSWorkSubmission.user_id))).filter(PMSWorkSubmission.task_id.in_(taskids),PMSWorkSubmission.status!="Draft").group_by(PMSWorkSubmission.task_id))
    return {"items":[{**{k:v for k,v in encoded(j).items() if k not in {"recipients","payload_hash"}},"title":tasks[j.task_id].title,"project_id":tasks[j.task_id].project_id,"recipients":len(j.recipients),"started":sum(counts.get((j.task_id,s),0) for s in ["In Progress","In Review","Done","Revision Requested"]),"submitted":submitted.get(j.task_id,0),"execution_scope":"shared_pms_task","approved":counts.get((j.task_id,"Done"),0)} for j in jobs],"total":q.count()}


@router.post("/distributions/{job_id}/retry")
def retry(job_id:int,user=Depends(require_admin),db:Session=Depends(get_db)):
    j=db.get(InternDistribution,job_id)
    if not j or j.organization_id!=tenant(user) or not organization_admin(user) and j.created_by!=user.id:raise HTTPException(404,"Distribution job not found")
    get_project_for_action(db,db.get(PMSTask,j.task_id).project_id,user,"manage_tasks")
    return encoded(process_job(db,j.id))


@router.get("/reviews")
def reviews(f=Depends(filters),status:str="",project_id:int|None=None,page:int=Query(1,ge=1),per_page:int=Query(50,ge=1,le=200),user=Depends(require_admin),db:Session=Depends(get_db)):
    people=filtered_employees(db,user,f).with_entities(Employee.user_id)
    q=db.query(PMSWorkSubmission).join(PMSTask,PMSTask.id==PMSWorkSubmission.task_id).filter(PMSWorkSubmission.user_id.in_(people),PMSWorkSubmission.status!="Draft",PMSTask.deleted_at.is_(None))
    if status:q=q.filter(PMSWorkSubmission.status==status)
    if project_id:q=q.filter(PMSTask.project_id==project_id)
    # Listing requires existing PMS project visibility; decisions still require approve.
    q=q.filter(PMSTask.project_id.in_([p.id for p in accessible_project_query(db,user) if can_access_project(db,p,user,"approve")]))
    if f.get("date_from"):q=q.filter(func.date(PMSWorkSubmission.created_at)>=f["date_from"])
    if f.get("date_to"):q=q.filter(func.date(PMSWorkSubmission.created_at)<=f["date_to"])
    items=q.order_by(PMSWorkSubmission.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    tasks={t.id:t for t in db.query(PMSTask).filter(PMSTask.id.in_([s.task_id for s in items]))};people={e.user_id:e for e in employee_query(db,user).filter(Employee.user_id.in_([s.user_id for s in items]))}
    return {"items":[{**r,"employee_id":people[r["user_id"]].id,"intern":f'{people[r["user_id"]].first_name} {people[r["user_id"]].last_name}',"task":tasks[r["task_id"]].title,"project_id":tasks[r["task_id"]].project_id,"can_review":can_access_project(db,db.get(PMSProject,tasks[r["task_id"]].project_id),user,"approve")} for r in work.payload(db,items)],"total":q.count()}


@router.get("/reports")
def reports(f=Depends(filters),missing:bool=False,report_date:date|None=None,page:int=Query(1,ge=1),per_page:int=Query(50,ge=1,le=200),user=Depends(require_admin),db:Session=Depends(get_db)):
    day=report_date or today();people=filtered_employees(db,user,f)
    if missing:
        # Missing eligible working-day reports; approved leave is not an exception.
        from app.models.leave import LeaveRequest
        if day.weekday()>=5:return {"items":[],"total":0}
        leave=db.query(LeaveRequest.employee_id).filter(LeaveRequest.status=="Approved",LeaveRequest.deleted_at.is_(None),LeaveRequest.from_date<=day,LeaveRequest.to_date>=day)
        done=db.query(InternReport.employee_id).filter_by(report_date=day,status="Submitted")
        q=people.filter(Employee.status.in_(["Active","Probation"]),Employee.date_of_joining<=day,Employee.id.notin_(done),Employee.id.notin_(leave))
        weekly=db.query(InternBatchMembership.employee_id).join(InternBatch,InternBatch.id==InternBatchMembership.batch_id).filter(InternBatchMembership.status=="Active",InternBatch.organization_id==tenant(user),InternBatch.reporting_frequency=="Weekly")
        daily=db.query(InternBatchMembership.employee_id).join(InternBatch,InternBatch.id==InternBatchMembership.batch_id).filter(InternBatchMembership.status=="Active",InternBatch.organization_id==tenant(user),InternBatch.reporting_frequency=="Daily")
        if f.get("batch_id"):
            weekly=weekly.filter(InternBatch.id==f["batch_id"]);daily=daily.filter(InternBatch.id==f["batch_id"])
        weekly_only=weekly.filter(InternBatchMembership.employee_id.notin_(daily))
        if day.weekday()<4:q=q.filter(Employee.id.notin_(weekly_only))
        else:
            from datetime import timedelta
            week_reports=db.query(InternReport.employee_id).filter(InternReport.status=="Submitted",InternReport.report_date>=day-timedelta(days=day.weekday()),InternReport.report_date<=day)
            q=q.filter(or_(Employee.id.notin_(weekly_only),Employee.id.notin_(week_reports)))
        return {"items":[{"employee_id":e.id,"intern":f"{e.first_name} {e.last_name}","report_date":day,"status":"Missing"} for e in q.order_by(Employee.id).offset((page-1)*per_page).limit(per_page)],"total":q.count()}
    q=db.query(InternReport,Employee).join(Employee,Employee.id==InternReport.employee_id).filter(InternReport.employee_id.in_(people.with_entities(Employee.id)),InternReport.status=="Submitted")
    if report_date:q=q.filter(InternReport.report_date==day)
    if f.get("date_from"):q=q.filter(InternReport.report_date>=f["date_from"])
    if f.get("date_to"):q=q.filter(InternReport.report_date<=f["date_to"])
    rows=q.order_by(InternReport.report_date.desc(),InternReport.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    ids=[r.id for r,e in rows];history={}
    for r in db.query(InternReportReview).filter(InternReportReview.report_id.in_(ids)).order_by(InternReportReview.id):history[r.report_id]=encoded(r)
    return {"items":[{**encoded(r),"intern":f"{e.first_name} {e.last_name}","review":history.get(r.id)} for r,e in rows],"total":q.count()}


class ReportDecision(BaseModel):
    decision:Literal["Reviewed","Correction Requested"]
    note:str=Field(min_length=1,max_length=3000)


@router.post("/reports/{report_id}/review")
def review_report(report_id:int,data:ReportDecision,user=Depends(require_admin),db:Session=Depends(get_db)):
    r=db.get(InternReport,report_id)
    if not r:raise HTTPException(404,"Report not found")
    get_employee(db,user,r.employee_id)
    item=InternReportReview(report_id=r.id,reviewer_user_id=user.id,report_snapshot=__import__("fastapi.encoders",fromlist=["jsonable_encoder"]).jsonable_encoder(encoded(r)),**data.model_dump());db.add(item);db.commit();return encoded(item)


class NoticeInput(BaseModel):
    employee_ids:list[int]=Field(min_length=1,max_length=20000)
    title:str=Field(min_length=1,max_length=200)
    message:rich_text_type(3000, 1) = Field()


@router.post("/announcements")
def announce(data:NoticeInput,user=Depends(require_admin),db:Session=Depends(get_db)):
    people=employee_query(db,user).filter(Employee.id.in_(data.employee_ids)).all()
    if len(people)!=len(set(data.employee_ids)):raise HTTPException(403,"Recipients are outside your authorized scope")
    db.bulk_insert_mappings(Notification,[dict(user_id=e.user_id,company_id=tenant(user),title=data.title,message=data.message,module="hrms",event_type="intern_program",channels=["in_app"],is_read=False) for e in people if e.user_id]);db.commit();return {"notified":sum(bool(e.user_id) for e in people)}


@router.get("/dashboard")
def dashboard(f=Depends(filters),user=Depends(require_admin),db:Session=Depends(get_db)):
    people=filtered_employees(db,user,f);uids=people.with_entities(Employee.user_id);ids=people.with_entities(Employee.id)
    assignments=db.query(PMSTaskAssignee).join(PMSTask,PMSTask.id==PMSTaskAssignee.task_id).join(PMSProject,PMSProject.id==PMSTask.project_id).filter(PMSTaskAssignee.user_id.in_(uids),PMSTask.deleted_at.is_(None),func.coalesce(PMSProject.organization_id,1)==tenant(user))
    if f.get("batch_id"):
        selected_batch=get_batch(db,user,f["batch_id"])
        assignments=assignments.filter(PMSTask.project_id==selected_batch.project_id)
    if f.get("date_from"):assignments=assignments.filter(PMSTask.due_date>=f["date_from"])
    if f.get("date_to"):assignments=assignments.filter(PMSTask.due_date<=f["date_to"])
    bq=batch_query(db,user)
    if f.get("batch_id"):bq=bq.filter(InternBatch.id==f["batch_id"])
    if f.get("department_id"):bq=bq.filter(InternBatch.department_id==f["department_id"])
    day=today()
    task_ids=assignments.with_entities(PMSTaskAssignee.task_id)
    subs=db.query(PMSWorkSubmission).filter(PMSWorkSubmission.user_id.in_(uids),PMSWorkSubmission.task_id.in_(task_ids),PMSWorkSubmission.status!="Draft")
    if f.get("date_from"):subs=subs.filter(func.date(PMSWorkSubmission.created_at)>=f["date_from"])
    if f.get("date_to"):subs=subs.filter(func.date(PMSWorkSubmission.created_at)<=f["date_to"])
    latest=subs.with_entities(func.max(PMSWorkSubmission.id).label("id")).group_by(PMSWorkSubmission.task_id,PMSWorkSubmission.user_id).subquery()
    pending=subs.filter(PMSWorkSubmission.id.in_(db.query(latest.c.id)),PMSWorkSubmission.status=="Pending Review").count()
    average=db.query(func.avg(PMSWorkReview.score*100.0/PMSWorkReview.maximum_score)).filter(PMSWorkReview.submission_id.in_(db.query(latest.c.id))).scalar()
    distribution=db.query(Department.name,func.count(Employee.id)).join(Employee,Employee.department_id==Department.id).filter(Employee.id.in_(ids)).group_by(Department.name).all()
    growth=db.query(func.date(Employee.created_at),func.count(Employee.id)).filter(Employee.id.in_(ids)).group_by(func.date(Employee.created_at)).order_by(func.date(Employee.created_at)).limit(180).all()
    due=assignments.filter(PMSTaskAssignee.execution_status!="Done").with_entities(PMSTask.id,PMSTask.title,PMSTask.due_date).distinct().order_by(PMSTask.due_date).limit(8).all()
    apps=db.query(InternApplication).filter(InternApplication.status=="Pending").count() if organization_admin(user) and tenant(user)==1 else 0
    recent=db.query(PMSActivity).filter(PMSActivity.task_id.in_(assignments.with_entities(PMSTaskAssignee.task_id))).order_by(PMSActivity.id.desc()).limit(8).all()
    workload=db.query(PMSTaskAssignee.reviewer_user_id,func.count(PMSTaskAssignee.task_id)).filter(PMSTaskAssignee.user_id.in_(uids),PMSTaskAssignee.execution_status=="In Review").group_by(PMSTaskAssignee.reviewer_user_id).all()
    return {"total_interns":people.count(),"active_interns":people.filter(Employee.status.in_(["Active","Probation"])).count(),"pending_applications":apps,
        "active_batches":bq.filter(InternBatch.status=="Active").count(),"upcoming_batches":bq.filter(InternBatch.status=="Upcoming").count(),"completed_batches":bq.filter(InternBatch.status=="Completed").count(),
        "assigned_tasks":assignments.count(),"completed_tasks":assignments.filter(PMSTaskAssignee.execution_status=="Done").count(),"overdue":assignments.filter(func.coalesce(PMSTaskAssignee.due_date,PMSTask.due_date)<day,PMSTaskAssignee.execution_status!="Done").count(),
        "submissions_today":subs.filter(func.date(PMSWorkSubmission.created_at)==day).count(),"pending_reviews":pending,"average_score":round(float(average),1) if average is not None else None,
        "reports_today":db.query(InternReport).filter(InternReport.employee_id.in_(ids),InternReport.report_date==day,InternReport.status=="Submitted").count(),
        "completions":db.query(InternCompletionReview).filter(InternCompletionReview.employee_id.in_(ids),InternCompletionReview.decision=="Approved").count(),
        "distribution":[{"name":name,"count":count} for name,count in distribution],"growth":[{"date":str(day),"count":count} for day,count in growth],
        "deadlines":[{"task_id":r.id,"title":r.title,"due_date":r.due_date} for r in due],"activity":[encoded(r) for r in recent],"mentor_workload":[{"reviewer_id":uid,"pending":count} for uid,count in workload]}


class CompletionInput(BaseModel):
    batch_id:int
    employee_id:int
    decision:Literal["Approved","Improvements Requested","Incomplete"]
    note:str=Field(min_length=1,max_length=3000)


@router.post("/completions")
def complete(data:CompletionInput,user=Depends(require_admin),db:Session=Depends(get_db)):
    batch=get_batch(db,user,data.batch_id);e=get_employee(db,user,data.employee_id)
    db.query(InternBatch).filter_by(id=batch.id).with_for_update().first()
    if not db.query(InternBatchMembership.id).filter_by(batch_id=batch.id,employee_id=e.id,status="Active").first():raise HTTPException(409,"Intern is not active in this batch")
    if db.query(InternCompletionReview.id).filter_by(batch_id=batch.id,employee_id=e.id,decision="Approved").first():raise HTTPException(409,"Completion is already approved")
    snapshot=performance(db,user,{"batch_id":batch.id,"employee_id":e.id},today(),per_page=1)["items"]
    if not snapshot or snapshot[0]["id"]!=e.id:raise HTTPException(404,"Completion candidate not found")
    if data.decision=="Approved" and not snapshot[0]["eligible"]:raise HTTPException(409,"; ".join(snapshot[0]["eligibility_reasons"]))
    item=InternCompletionReview(**data.model_dump(exclude={"note"}),reviewer_user_id=user.id,note=data.note,snapshot=snapshot[0])
    if data.decision=="Approved":item.verification_id="IH-CERT-"+uuid4().hex.upper()
    db.add(item);db.commit();return encoded(item)


@router.get("/completions")
def completions(page:int=Query(1,ge=1),per_page:int=Query(50,ge=1,le=200),user=Depends(require_admin),db:Session=Depends(get_db)):
    q=db.query(InternCompletionReview).filter(InternCompletionReview.batch_id.in_(batch_query(db,user).with_entities(InternBatch.id)))
    return {"items":[encoded(r) for r in q.order_by(InternCompletionReview.id.desc()).offset((page-1)*per_page).limit(per_page)],"total":q.count()}


@router.post("/completions/{review_id}/certificate")
def certificate(review_id:int,user=Depends(require_admin),db:Session=Depends(get_db)):
    item=db.query(InternCompletionReview).filter_by(id=review_id).with_for_update().first()
    if not item:raise HTTPException(404,"Completion review not found")
    b=get_batch(db,user,item.batch_id);e=get_employee(db,user,item.employee_id)
    if item.decision!="Approved":raise HTTPException(409,"Manager completion approval is required")
    if item.certificate_id:return encoded(db.get(InternCertificate,item.certificate_id))
    c=InternCertificate(employee_id=e.id,title=b.name+" · Internship Completion",certificate_type="Internship",issued_by=user.id,verification_id=item.verification_id)
    db.add(c);db.flush()
    # Reuse the existing HRMS document storage and EmployeeCertificate catalog.
    from .router import certificate_download
    from app.api.v1.documents import _save_upload
    from app.models.document import EmployeeCertificate
    from starlette.datastructures import UploadFile, Headers
    pdf=certificate_download(c.id,e,db)
    f=UploadFile(io.BytesIO(pdf.body),filename="internship-certificate.pdf",headers=Headers({"content-type":"application/pdf"}))
    file_url,mime,size=_save_upload(f,f"certificates/{e.id}",prefix="intern_")
    document=EmployeeCertificate(employee_id=e.id,category="Professional",certificate_type="Internship",title=c.title,issuing_entity=b.program,
        certificate_number=item.verification_id,issue_date=today(),file_url=file_url,original_filename="internship-certificate.pdf",content_type=mime,file_size_bytes=size,
        verification_status="Verified",verified_by_user_id=user.id,verified_at=datetime.now(timezone.utc),uploaded_by=user.id)
    db.add(document);db.flush();c.document_certificate_id=document.id;item.certificate_id=c.id;db.commit();return encoded(c)


@router.get("/export")
def export(f=Depends(filters),page:int=Query(1,ge=1),user=Depends(require_admin),db:Session=Depends(get_db)):
    records=performance(db,user,f,today(),page=page,per_page=200)
    stream=io.StringIO();writer=csv.writer(stream);writer.writerow(["Intern ID","Name","Department","Assigned","Accepted","Overdue","Score","Reporting %","Attendance %"])
    def safe(v):return "'"+v if isinstance(v,str) and v.startswith(("=","+","-","@")) else v
    for r in records["items"]:writer.writerow([safe(r["intern_id"]),safe(r["name"]),safe(r["department"] or ""),r["assigned"],r["accepted"],r["overdue"],r["score"],r["parts"]["reports"],r["attendance"]])
    return Response(stream.getvalue(),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="intern-performance-page-{page}.csv"',"X-Total-Records":str(records["total"])})


@router.get("/legacy")
def legacy(user=Depends(require_admin),db:Session=Depends(get_db)):
    from .legacy_import import pending_query
    return {"pending":pending_query(db,user).count(),"legacy_writes_enabled":False,"source":"PMS"}


class ImportInput(BaseModel):
    project_id:int
    reviewer_user_id:int


@router.post("/legacy/import")
def legacy_import(data:ImportInput,user=Depends(require_admin),db:Session=Depends(get_db)):
    from .legacy_import import import_history
    return import_history(db,user,data.project_id,data.reviewer_user_id)


@router.get("/batch-analytics")
def batch_analytics(f=Depends(filters),user=Depends(require_admin),db:Session=Depends(get_db)):
    scoped=batch_query(db,user)
    if f.get("batch_id"):scoped=scoped.filter(InternBatch.id==f["batch_id"])
    if f.get("department_id"):scoped=scoped.filter(InternBatch.department_id==f["department_id"])
    if f.get("program"):scoped=scoped.filter(InternBatch.program==f["program"])
    selected=scoped.order_by(InternBatch.id).limit(200).all();bids=[b.id for b in selected]
    people=filtered_employees(db,user,f).with_entities(Employee.id)
    memberships=db.query(InternBatchMembership.batch_id,Employee.user_id).join(Employee,Employee.id==InternBatchMembership.employee_id).filter(InternBatchMembership.batch_id.in_(bids),InternBatchMembership.status=="Active",Employee.id.in_(people)).subquery()
    members=dict(db.query(memberships.c.batch_id,func.count()).group_by(memberships.c.batch_id))
    base=db.query(memberships.c.batch_id,PMSTaskAssignee.execution_status).join(PMSTaskAssignee,PMSTaskAssignee.user_id==memberships.c.user_id).join(PMSTask,PMSTask.id==PMSTaskAssignee.task_id).join(InternBatch,InternBatch.id==memberships.c.batch_id).filter(PMSTask.project_id==InternBatch.project_id,PMSTask.deleted_at.is_(None))
    if f.get("date_from"):base=base.filter(PMSTask.due_date>=f["date_from"])
    if f.get("date_to"):base=base.filter(PMSTask.due_date<=f["date_to"])
    counts={(r[0],r[1]):r[2] for r in base.with_entities(memberships.c.batch_id,PMSTaskAssignee.execution_status,func.count()).group_by(memberships.c.batch_id,PMSTaskAssignee.execution_status)}
    latest=db.query(PMSWorkSubmission.task_id,PMSWorkSubmission.user_id,func.max(PMSWorkSubmission.id).label("id")).filter(PMSWorkSubmission.status!="Draft").group_by(PMSWorkSubmission.task_id,PMSWorkSubmission.user_id).subquery()
    quality=dict(db.query(memberships.c.batch_id,func.avg(PMSWorkReview.score*100.0/PMSWorkReview.maximum_score)).join(PMSWorkSubmission,PMSWorkSubmission.user_id==memberships.c.user_id).join(latest,latest.c.id==PMSWorkSubmission.id).join(PMSWorkReview,PMSWorkReview.submission_id==PMSWorkSubmission.id).join(PMSTask,PMSTask.id==PMSWorkSubmission.task_id).join(InternBatch,InternBatch.id==memberships.c.batch_id).filter(PMSTask.project_id==InternBatch.project_id,PMSTask.deleted_at.is_(None)).group_by(memberships.c.batch_id))
    return [{"id":b.id,"name":b.name,"members":members.get(b.id,0),"assigned":sum(v for (bid,status),v in counts.items() if bid==b.id),"accepted":counts.get((b.id,"Done"),0),"score":round(float(quality[b.id]),1) if b.id in quality else None} for b in selected]


@router.get("/schedules")
def schedules(user=Depends(require_admin),db:Session=Depends(get_db)):
    q=db.query(InternTaskSchedule).join(PMSTask,PMSTask.id==InternTaskSchedule.task_id).filter(InternTaskSchedule.organization_id==tenant(user),PMSTask.project_id.in_(accessible_project_query(db,user).with_entities(PMSProject.id)))
    if not organization_admin(user):q=q.filter(InternTaskSchedule.created_by==user.id)
    return [{**{k:v for k,v in encoded(s).items() if k!="recipients"},"recipients":len(s.recipients)} for s in q.order_by(InternTaskSchedule.id.desc()).limit(100)]

class ScheduleState(BaseModel):
    active:bool

@router.post("/schedules/{schedule_id}/state")
def schedule_state(schedule_id:int,data:ScheduleState,user=Depends(require_admin),db:Session=Depends(get_db)):
    s=db.get(InternTaskSchedule,schedule_id)
    if not s or s.organization_id!=tenant(user) or not organization_admin(user) and s.created_by!=user.id:raise HTTPException(404,"Schedule not found")
    task=db.get(PMSTask,s.task_id);get_project_for_action(db,task.project_id,user,"manage_tasks")
    if data.active and s.next_run>s.until:raise HTTPException(409,"This schedule has ended")
    s.active=int(data.active);db.commit();return {"active":s.active}


@router.get("/interns/{employee_id}/performance")
def individual_performance(employee_id:int,batch_id:int|None=None,user=Depends(require_admin),db:Session=Depends(get_db)):
    get_employee(db,user,employee_id)
    if batch_id:get_batch(db,user,batch_id)
    records=performance(db,user,{"employee_id":employee_id,"batch_id":batch_id},today(),per_page=1)["items"]
    if not records:raise HTTPException(404,"Intern is not active in the selected batch")
    return records[0]


@router.get('/batches/{batch_id}/members/export')
def membership_export(batch_id:int,user=Depends(require_admin),db:Session=Depends(get_db)):
    get_batch(db,user,batch_id)
    q=db.query(InternBatchMembership,Employee).join(Employee,Employee.id==InternBatchMembership.employee_id).filter(InternBatchMembership.batch_id==batch_id,Employee.id.in_(employee_query(db,user,include_employees=True).with_entities(Employee.id)))
    stream=io.StringIO();writer=csv.writer(stream);writer.writerow(['Employee ID','Name','Membership','Joined','Left'])
    for m,e in q.order_by(InternBatchMembership.id).yield_per(500):
        writer.writerow(["'"+e.employee_id,"'"+e.first_name+' '+e.last_name,m.status,m.joined_at,m.left_at])
    return Response(stream.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="batch-membership.csv"'})
