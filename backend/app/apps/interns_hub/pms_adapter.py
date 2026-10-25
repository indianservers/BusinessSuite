from datetime import timedelta
from sqlalchemy import func, case
from fastapi import HTTPException
from app.apps.project_management.models import PMSTask, PMSTaskAssignee, PMSWorkSubmission, PMSWorkReview, PMSProject
from app.apps.project_management import work
from app.apps.srm.services.commercial import tenant
from app.models.attendance import Attendance
from .models import InternReport, InternCertificate, InternTask
from .management_models import InternLegacyTaskMap

STATUS={"To Do":"Pending","In Progress":"In Progress","In Review":"In Review","Done":"Completed","Revision Requested":"In Progress","Rejected":"In Progress"}


def task_rows(db,employee,*,page=1,per_page=500):
    q=db.query(PMSTask,PMSTaskAssignee).join(PMSTaskAssignee,PMSTaskAssignee.task_id==PMSTask.id).join(PMSProject,PMSProject.id==PMSTask.project_id).filter(PMSTaskAssignee.user_id==employee.user_id,PMSTask.deleted_at.is_(None),PMSProject.deleted_at.is_(None),func.coalesce(PMSProject.organization_id,1)==tenant(employee.user))
    return [{"id":t.id,"pms_task_id":t.id,"project_id":t.project_id,"task_key":t.task_key,"employee_id":employee.id,"title":t.title,
        "description":t.description or "","category":t.component or "Project","priority":t.priority,"points":a.maximum_score,
        "progress_percent":a.progress_percent,"work_notes":a.work_notes,"status":"Cancelled" if a.cancelled_at else STATUS.get(a.execution_status,"Pending"),"due_date":a.due_date or t.due_date,"created_at":t.created_at,
        "reviewer_user_id":a.reviewer_user_id,"source":"PMS"} for t,a in q.order_by(func.coalesce(PMSTaskAssignee.due_date,PMSTask.due_date),PMSTask.id).offset((page-1)*per_page).limit(per_page)]


def submissions(db,employee,*,page=1,per_page=500):
    q=db.query(PMSWorkSubmission).join(PMSTask,PMSTask.id==PMSWorkSubmission.task_id).join(PMSProject,PMSProject.id==PMSTask.project_id).filter(PMSWorkSubmission.user_id==employee.user_id,func.coalesce(PMSProject.organization_id,1)==tenant(employee.user),PMSTask.deleted_at.is_(None))
    return [{**r,"employee_id":employee.id,"source":"PMS"} for r in work.payload(db,q.order_by(PMSWorkSubmission.id.desc()).offset((page-1)*per_page).limit(per_page).all())]


def summary(db,employee,day):
    q=db.query(PMSTaskAssignee).join(PMSTask,PMSTask.id==PMSTaskAssignee.task_id).join(PMSProject,PMSProject.id==PMSTask.project_id).filter(PMSTaskAssignee.user_id==employee.user_id,PMSTaskAssignee.cancelled_at.is_(None),PMSTask.deleted_at.is_(None),PMSProject.deleted_at.is_(None),func.coalesce(PMSProject.organization_id,1)==tenant(employee.user))
    total=q.count();completed=q.filter(PMSTaskAssignee.execution_status=="Done").count()
    latest=db.query(PMSWorkSubmission.task_id,func.max(PMSWorkSubmission.id).label("id")).filter(PMSWorkSubmission.user_id==employee.user_id,PMSWorkSubmission.status!="Draft",PMSWorkSubmission.task_id.in_(q.with_entities(PMSTaskAssignee.task_id))).group_by(PMSWorkSubmission.task_id).subquery()
    score=db.query(func.avg(PMSWorkReview.score*100.0/PMSWorkReview.maximum_score)).filter(PMSWorkReview.submission_id.in_(db.query(latest.c.id))).scalar()
    attendances=db.query(Attendance.status).filter_by(employee_id=employee.id).all();present=sum(a[0] in {"Present","WFH","Half-day"} for a in attendances)
    days={r[0] for r in db.query(InternReport.report_date).filter_by(employee_id=employee.id,status="Submitted")};cursor=day if day in days else day-timedelta(days=1);streak=0
    while cursor in days:streak+=1;cursor-=timedelta(days=1)
    legacy=db.query(InternTask.id).filter(InternTask.employee_id==employee.id,InternTask.id.notin_(db.query(InternLegacyTaskMap.legacy_task_id))).count()
    return {"total_tasks":total,"completed":completed,"pending":q.filter(PMSTaskAssignee.execution_status=="To Do").count(),"in_progress":q.filter(PMSTaskAssignee.execution_status.in_(["In Progress","Revision Requested"])).count(),
        "overdue":q.filter(func.coalesce(PMSTaskAssignee.due_date,PMSTask.due_date)<day,PMSTaskAssignee.execution_status!="Done").count(),"score":round(float(score)) if score is not None else None,
        "progress":round(completed*100/total) if total else 0,"submission_rate":round(db.query(latest).count()*100/total) if total else 0,
        "attendance_rate":round(present*100/len(attendances)) if attendances else 0,"present_days":present,"absent_days":sum(a[0]=="Absent" for a in attendances),"reports":len(days),"streak":streak,
        "certificates":db.query(InternCertificate).filter_by(employee_id=employee.id).count(),"legacy_tasks_pending":legacy,"task_source":"PMS"}
