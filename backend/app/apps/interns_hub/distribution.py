"""Orchestration only: PMS retains the shared task and every execution record."""
import hashlib
import json
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.models.employee import Employee
from app.models.user import User
from app.apps.project_management.models import PMSTask, PMSTaskAssignee, PMSProject
from app.apps.project_management.access import get_project_for_action, can_access_project
from app.apps.project_management.schemas import PMSTaskCreate
from app.apps.srm.services.commercial import tenant
from .management_access import employee_query, get_batch, require_admin
from .management_models import InternBatchMembership, InternDistribution, InternTaskSchedule


def recipients(db,user,data):
    q=employee_query(db,user,include_employees=True).filter(Employee.status.in_(["Active","Probation"]),Employee.user_id.isnot(None))
    scope=data.get("target_type","interns")
    if scope=="batches":
        for bid in data.get("batch_ids",[]):
            b=get_batch(db,user,bid)
            if b.status not in {"Upcoming","Active","Evaluation"}: raise HTTPException(409,"Select a live batch")
        members=db.query(InternBatchMembership.employee_id).filter(InternBatchMembership.batch_id.in_(data.get("batch_ids",[])),InternBatchMembership.status=="Active")
        q=q.filter(Employee.id.in_(members))
    elif scope=="department": q=q.filter(Employee.department_id==data.get("department_id"))
    elif scope=="interns": q=q.filter(Employee.id.in_(data.get("employee_ids",[])))
    elif scope!="all": raise HTTPException(422,"Invalid target scope")
    if data.get("program"):
        from .management_models import InternBatch
        q=q.filter(Employee.id.in_(db.query(InternBatchMembership.employee_id).join(InternBatch,InternBatchMembership.batch_id==InternBatch.id).filter(InternBatch.program==data["program"],InternBatchMembership.status=="Active")))
    if scope=="interns":
        selected=set(data.get("employee_ids",[]))-set(data.get("exclude_ids",[]))
        permitted={r[0] for r in q.with_entities(Employee.id)}
        if not selected.issubset(permitted):raise HTTPException(403,"Selected interns are outside your scope or are not eligible")
    active_users=db.query(User.id).filter(User.is_active==True)
    q=q.filter(Employee.user_id.in_(active_users),Employee.id.notin_(data.get("exclude_ids",[])))
    if data.get("search"):q=q.filter((Employee.first_name+" "+Employee.last_name).ilike("%"+data["search"]+"%"))
    return q


def publish(db,user,data,*,process=True):
    require_admin(user)
    digest=hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()
    previous=db.query(InternDistribution).filter_by(organization_id=tenant(user),idempotency_key=data["idempotency_key"]).first()
    if previous:
        if previous.payload_hash!=digest:raise HTTPException(409,"Idempotency key was already used for a different assignment")
        get_project_for_action(db,db.get(PMSTask,previous.task_id).project_id,user,"manage_tasks")
        return previous
    project=get_project_for_action(db,data["project_id"],user,"manage_tasks")
    if project.is_archived:raise HTTPException(409,"Project is archived")
    reviewer=db.get(User,data["reviewer_user_id"])
    if not reviewer or not reviewer.is_active or not can_access_project(db,project,reviewer,"approve"):
        raise HTTPException(403,"The reviewer must already have PMS approval permission on this project")
    selected=recipients(db,user,data).with_entities(Employee.id,Employee.user_id).order_by(Employee.id).all()
    if not selected:raise HTTPException(422,"No authorized active interns match this selection")
    task=db.get(PMSTask,data.get("task_id")) if data.get("task_id") else None
    if data.get("task_id") and not task:raise HTTPException(404,"PMS task not found")
    if task and (task.project_id!=project.id or task.deleted_at):raise HTTPException(422,"Task does not belong to this PMS project")
    if not task:
        if not data.get("title") or not data.get("description"):raise HTTPException(422,"A new PMS task requires a title and description")
        from app.apps.project_management.api.router import create_task_operation
        description=data["description"]
        for key in ["instructions","deliverables","review_instructions"]:
            if data.get(key):description+="\n\n"+key.replace("_"," ").title()+":\n"+data[key]
        key="IH-"+hashlib.sha256((str(user.id)+data["idempotency_key"]).encode()).hexdigest()[:20].upper()
        task=create_task_operation(project.id,PMSTaskCreate(title=data["title"],description=description,task_key=key,
            priority=data.get("priority","Medium"),due_date=data["due_date"],start_date=data.get("start_date"),estimated_hours=data.get("estimated_hours"),component=data.get("category")),db,user,commit=False)
    job=InternDistribution(organization_id=tenant(user),task_id=task.id,created_by=user.id,idempotency_key=data["idempotency_key"],payload_hash=digest,
        recipients=[r[1] for r in selected],batch_ids=data.get("batch_ids",[]),reviewer_user_id=reviewer.id,maximum_score=data.get("maximum_score",100),due_date=data["due_date"])
    db.add(job)
    try:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"Assignment is being published concurrently; retry with the same key")
    if data.get("recurrence"):
        if not data.get("recurrence_until") or data["recurrence_until"]<data["due_date"]:raise HTTPException(422,"Set a valid recurrence end date")
        db.add(InternTaskSchedule(organization_id=tenant(user),task_id=task.id,created_by=user.id,recipients=job.recipients,batch_ids=job.batch_ids,
            reviewer_user_id=reviewer.id,maximum_score=job.maximum_score,frequency=data["recurrence"],interval_days=data.get("recurrence_interval",1),next_run=data["due_date"]+timedelta(days=data.get("recurrence_interval",1) if data["recurrence"]=="custom" else 1 if data["recurrence"]=="daily" else 7),until=data["recurrence_until"]))
    db.commit()
    if process:process_job(db,job.id)
    return db.get(InternDistribution,job.id)


def process_job(db,job_id,chunk_size=500):
    job=db.query(InternDistribution).filter_by(id=job_id).with_for_update().first()
    if not job or job.status=="Completed":return job
    try:
        user=db.get(User,job.created_by);require_admin(user)
        task=db.get(PMSTask,job.task_id);project=get_project_for_action(db,task.project_id,user,"manage_tasks")
        reviewer=db.get(User,job.reviewer_user_id)
        if not reviewer or not reviewer.is_active or not can_access_project(db,project,reviewer,"approve"):raise HTTPException(403,"PMS reviewer access was revoked")
        window=job.recipients[job.cursor:job.cursor+chunk_size]
        permitted={r[0] for r in employee_query(db,user,include_employees=True).join(User,User.id==Employee.user_id).filter(User.is_active==True,Employee.user_id.in_(window),Employee.status.in_(["Active","Probation"])).with_entities(Employee.user_id)}
        if permitted!=set(window):raise HTTPException(403,"Recipient eligibility or manager scope changed; review this job")
        existing={r[0] for r in db.query(PMSTaskAssignee.user_id).filter(PMSTaskAssignee.task_id==job.task_id,PMSTaskAssignee.user_id.in_(window))}
        db.bulk_insert_mappings(PMSTaskAssignee,[dict(task_id=job.task_id,user_id=uid,execution_status="To Do",due_date=job.due_date,
            reviewer_user_id=job.reviewer_user_id,maximum_score=job.maximum_score,source_key=f"intern-distribution:{job.id}") for uid in window if uid not in existing])
        from app.models.notification import Notification
        db.bulk_insert_mappings(Notification,[dict(user_id=uid,company_id=job.organization_id,title="New PMS assignment",message=task.title,module="hrms",event_type="intern_assignment",channels=["in_app"],is_read=False) for uid in window if uid not in existing])
        from app.apps.project_management.work import sync_parent
        sync_parent(db,task)
        job.cursor+=len(window);job.attempts+=1;job.status="Completed" if job.cursor>=len(job.recipients) else "Pending";job.error=None
        from app.apps.project_management.work import activity
        activity(db,task,user,"assignments.distributed",metadata={"job_id":job.id,"new":len(window)-len(existing),"cursor":job.cursor})
        db.commit();return job
    except Exception as exc:
        db.rollback();job=db.get(InternDistribution,job_id);job.status="Failed";job.error=str(getattr(exc,"detail",type(exc).__name__))[:500];job.attempts+=1;db.commit();return job


def scheduled_tick(db,day):
    completed=0; errors=[]
    for job in db.query(InternDistribution).filter_by(status="Pending").order_by(InternDistribution.id).limit(10).all():
        process_job(db,job.id);completed+=1
    for schedule in db.query(InternTaskSchedule).filter(InternTaskSchedule.active==1,InternTaskSchedule.next_run<=day).with_for_update(skip_locked=True).limit(10).all():
        if schedule.next_run>schedule.until:schedule.active=0;db.commit();continue
        user=db.get(User,schedule.created_by);task=db.get(PMSTask,schedule.task_id)
        ids=[r[0] for r in db.query(Employee.id).filter(Employee.user_id.in_(schedule.recipients))]
        try:
            publish(db,user,dict(project_id=task.project_id,title=task.title,description=task.description,category=task.component,priority=task.priority,
                target_type="interns",employee_ids=ids,batch_ids=schedule.batch_ids,exclude_ids=[],reviewer_user_id=schedule.reviewer_user_id,
                maximum_score=schedule.maximum_score,due_date=schedule.next_run,idempotency_key=f"schedule:{schedule.id}:{schedule.next_run}"))
            schedule=db.get(InternTaskSchedule,schedule.id);schedule.last_error=None;schedule.next_run+=timedelta(days=schedule.interval_days if schedule.frequency=="custom" else 1 if schedule.frequency=="daily" else 7)
            db.commit()
        except HTTPException as exc:
            db.rollback()
            schedule=db.get(InternTaskSchedule,schedule.id);schedule.last_error=str(exc.detail)[:500];db.commit()
            errors.append({"schedule_id":schedule.id,"error":str(exc.detail)})
            # Keep the due occurrence pending for a retry after access/eligibility is fixed.
            import logging
            logging.getLogger(__name__).warning("intern_schedule_retry_required id=%s reason=%s",schedule.id,exc.detail)
    return {"distribution_chunks":completed,"schedule_errors":errors}
