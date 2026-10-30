"""Read models over authoritative PMS evaluations and HRMS attendance/reports."""
from datetime import date, timedelta
from sqlalchemy import func, case, or_
from app.models.employee import Employee, EmployeeEducation, EmployeeSkill
from app.models.company import Department
from app.models.attendance import Attendance
from app.models.leave import LeaveRequest
from app.apps.project_management.models import PMSTask, PMSTaskAssignee, PMSWorkSubmission, PMSWorkReview, PMSProject
from app.apps.srm.services.commercial import tenant
from .models import InternReport, InternEnrollment, InternCourse
from .management_models import InternBatch, InternBatchMembership, InternCompletionReview
from .management_access import employee_query

WEIGHTS={"quality":40,"timeliness":20,"reports":15,"completion":15,"communication":10}


def filtered_employees(db,user,filters):
    q=employee_query(db,user,include_employees=bool(filters.get("include_employees")))
    if filters.get("employee_id"):q=q.filter(Employee.id==filters["employee_id"])
    if filters.get("search"):
        term="%"+filters["search"]+"%";q=q.filter(or_(Employee.first_name.ilike(term),Employee.last_name.ilike(term),Employee.employee_id.ilike(term),Employee.personal_email.ilike(term)))
    for field in ["department_id","reporting_manager_id","status"]:
        if filters.get(field):q=q.filter(getattr(Employee,field)==filters[field])
    members=db.query(InternBatchMembership.employee_id).join(InternBatch,InternBatch.id==InternBatchMembership.batch_id).filter(InternBatchMembership.status=="Active")
    if filters.get("batch_id"):q=q.filter(Employee.id.in_(members.filter(InternBatch.id==filters["batch_id"])))
    if filters.get("program"):q=q.filter(Employee.id.in_(members.filter(InternBatch.program==filters["program"])))
    if filters.get("mentor_id"):q=q.filter(Employee.id.in_(members.filter(InternBatch.mentor_user_id==filters["mentor_id"])))
    if filters.get("college"):q=q.filter(Employee.id.in_(db.query(EmployeeEducation.employee_id).filter(EmployeeEducation.institution.ilike("%"+filters["college"]+"%"))))
    if filters.get("skill"):q=q.filter(Employee.id.in_(db.query(EmployeeSkill.employee_id).filter(EmployeeSkill.skill_name.ilike("%"+filters["skill"]+"%"))))
    return q


def task_aggregates(db,user_ids,day,organization_id,task_ids=None):
    q=db.query(PMSTaskAssignee.user_id,
        func.count(PMSTaskAssignee.task_id).label("assigned"),
        func.sum(case((PMSTaskAssignee.execution_status=="Done",1),else_=0)).label("accepted"),
        func.sum(case(((func.coalesce(PMSTaskAssignee.due_date,PMSTask.due_date)<day)&(PMSTaskAssignee.execution_status!="Done"),1),else_=0)).label("overdue")
    ).join(PMSTask,PMSTask.id==PMSTaskAssignee.task_id).join(PMSProject,PMSProject.id==PMSTask.project_id).filter(PMSTaskAssignee.cancelled_at.is_(None),PMSTask.deleted_at.is_(None),PMSProject.deleted_at.is_(None),func.coalesce(PMSProject.organization_id,1)==organization_id,PMSTaskAssignee.user_id.in_(user_ids)).group_by(PMSTaskAssignee.user_id)
    if task_ids is not None:q=q.filter(PMSTask.id.in_(task_ids))
    return {r.user_id:r for r in q}


def performance(db,user,filters,day,*,page=1,per_page=50):
    q=filtered_employees(db,user,filters);total=q.count()
    employees=q.order_by(Employee.id).offset((page-1)*per_page).limit(per_page).all()
    if not employees:return {"items":[],"total":total,"page":page,"per_page":per_page}
    ids=[e.id for e in employees];uids=[e.user_id for e in employees if e.user_id]
    scoped_tasks=db.query(PMSTask.id).join(PMSProject,PMSProject.id==PMSTask.project_id).filter(PMSTask.deleted_at.is_(None),PMSProject.deleted_at.is_(None),func.coalesce(PMSProject.organization_id,1)==tenant(user))
    if filters.get("batch_id"):
        selected_batch=db.get(InternBatch,filters["batch_id"])
        if selected_batch:scoped_tasks=scoped_tasks.filter(PMSTask.project_id==selected_batch.project_id)
    if filters.get("date_from"):scoped_tasks=scoped_tasks.filter(PMSTask.due_date>=filters["date_from"])
    if filters.get("date_to"):scoped_tasks=scoped_tasks.filter(PMSTask.due_date<=filters["date_to"])
    stats=task_aggregates(db,uids,day,tenant(user),scoped_tasks)
    latest=db.query(PMSWorkSubmission.task_id,PMSWorkSubmission.user_id,func.max(PMSWorkSubmission.id).label("id")).filter(PMSWorkSubmission.user_id.in_(uids),PMSWorkSubmission.task_id.in_(scoped_tasks),PMSWorkSubmission.status!="Draft").group_by(PMSWorkSubmission.task_id,PMSWorkSubmission.user_id).subquery()
    reviews={r.user_id:r for r in db.query(PMSWorkSubmission.user_id,func.avg(PMSWorkReview.score*100.0/PMSWorkReview.maximum_score).label("quality"),func.avg(PMSWorkReview.communication_score).label("communication"),func.count(PMSWorkSubmission.id).label("submitted"),func.sum(case((func.date(PMSWorkSubmission.created_at)<=func.coalesce(PMSTaskAssignee.due_date,PMSTask.due_date),1),else_=0)).label("ontime"))
        .join(latest,latest.c.id==PMSWorkSubmission.id).join(PMSTask,PMSTask.id==PMSWorkSubmission.task_id)
        .join(PMSTaskAssignee,(PMSTaskAssignee.task_id==PMSWorkSubmission.task_id)&(PMSTaskAssignee.user_id==PMSWorkSubmission.user_id))
        .outerjoin(PMSWorkReview,PMSWorkReview.submission_id==PMSWorkSubmission.id).group_by(PMSWorkSubmission.user_id)}
    report_dates={};attendance_dates={}
    for employee_id,report_date in db.query(InternReport.employee_id,InternReport.report_date).filter(InternReport.employee_id.in_(ids),InternReport.status=="Submitted",InternReport.report_date<=day):
        report_dates.setdefault(employee_id,set()).add(report_date)
    for employee_id,attendance_date,status in db.query(Attendance.employee_id,Attendance.attendance_date,Attendance.status).filter(Attendance.employee_id.in_(ids),Attendance.attendance_date<=day):
        if status not in {"Holiday","Leave","On Leave","Weekend"}:attendance_dates.setdefault(employee_id,[]).append((attendance_date,status))
    training={}
    for eid,completed,score,questions,lessons in db.query(InternEnrollment.employee_id,InternEnrollment.completed_lessons,InternEnrollment.score,InternCourse.questions,InternCourse.lessons).join(InternCourse,InternCourse.id==InternEnrollment.course_id).filter(InternEnrollment.employee_id.in_(ids)):
        training.setdefault(eid,[]).append(len(completed or [])>=len(lessons or []) and (not questions or score is not None and score>=70))
    departments={r.id:r.name for r in db.query(Department).filter(Department.id.in_([e.department_id for e in employees if e.department_id]))}
    educations={r.employee_id:r for r in db.query(EmployeeEducation).filter(EmployeeEducation.employee_id.in_(ids)).order_by(EmployeeEducation.id)}
    skills={};members={};leave={}
    for r in db.query(EmployeeSkill).filter(EmployeeSkill.employee_id.in_(ids)):skills.setdefault(r.employee_id,[]).append(r.skill_name)
    for m,b in db.query(InternBatchMembership,InternBatch).join(InternBatch,InternBatch.id==InternBatchMembership.batch_id).filter(InternBatchMembership.employee_id.in_(ids),InternBatchMembership.status=="Active",InternBatch.organization_id==tenant(user)):
        members.setdefault(m.employee_id,[]).append(b)
    for r in db.query(LeaveRequest).filter(LeaveRequest.employee_id.in_(ids),LeaveRequest.status=="Approved",LeaveRequest.deleted_at.is_(None),LeaveRequest.from_date<=day):
        leave.setdefault(r.employee_id,set()).update(r.from_date+timedelta(days=i) for i in range((min(r.to_date,day)-r.from_date).days+1))
    final_done={uid for uid, in db.query(PMSTaskAssignee.user_id).join(PMSTask,PMSTask.id==PMSTaskAssignee.task_id).filter(PMSTaskAssignee.user_id.in_(uids),PMSTaskAssignee.execution_status=="Done",PMSTask.id.in_(scoped_tasks),func.lower(PMSTask.component)=="final project").distinct()}
    output=[]
    for e in employees:
        s=stats.get(e.user_id);r=reviews.get(e.user_id);batches=members.get(e.id,[]);batch=next((b for b in batches if b.id==filters.get("batch_id")),None) or (batches[0] if batches else None)
        policy=(batch.policy or {}) if batch else {};weights=policy.get("weights",WEIGHTS)
        start=max(e.date_of_joining,batch.start_date) if batch else e.date_of_joining
        end=min(day,batch.end_date) if batch else day
        if filters.get("date_from"):start=max(start,filters["date_from"])
        if filters.get("date_to"):end=min(end,filters["date_to"])
        eligible_days={start+timedelta(days=i) for i in range(max(0,(end-start).days+1)) if (start+timedelta(days=i)).weekday()<5 and start+timedelta(days=i) not in leave.get(e.id,set())}
        def period(d):return d-timedelta(days=d.weekday()) if batch and batch.reporting_frequency=="Weekly" else d
        expected=len({period(d) for d in eligible_days})
        count=len({period(d) for d in report_dates.get(e.id,set()) if d in eligible_days});report_percent=min(100,round(count*100/expected)) if expected else None
        assigned=s.assigned if s else 0;accepted=int(s.accepted or 0) if s else 0;completed=round(accepted*100/assigned) if assigned else None
        parts={"quality":float(r.quality) if r and r.quality is not None else None,"timeliness":round(r.ontime*100/r.submitted) if r and r.submitted else None,"reports":report_percent,"completion":completed,"communication":float(r.communication) if r and r.communication is not None else None}
        known={k:v for k,v in parts.items() if v is not None};weight=sum(weights.get(k,0) for k in known)
        overall=round(sum(v*weights.get(k,0) for k,v in known.items())/weight,1) if assigned and weight else None
        attended=[status for d,status in attendance_dates.get(e.id,[]) if d in eligible_days]
        attendance_percent=round(sum(1 if v in {"Present","WFH"} else .5 if v=="Half-day" else 0 for v in attended)*100/len(attended)) if attended else None
        requirements=policy.get("completion",{});reasons=[]
        if (day-start).days<requirements.get("minimum_days",90):reasons.append("Minimum internship duration not met")
        if assigned<requirements.get("minimum_tasks",1) or accepted<assigned:reasons.append("Assigned PMS tasks still require approval")
        if expected and (report_percent or 0)<requirements.get("minimum_reports_percent",80):reasons.append("Daily report requirement not met")
        if requirements.get("minimum_attendance_percent",0) and (attendance_percent or 0)<requirements["minimum_attendance_percent"]:reasons.append("Attendance requirement not met")
        if requirements.get("training_required") and (not training.get(e.id) or not all(training[e.id])):reasons.append("Required learning assessments are not passed")
        if requirements.get("final_project_required"):
            if e.user_id not in final_done:reasons.append("Final project still requires PMS approval")
        risks=[]
        if s and s.overdue:risks.append(f"{s.overdue} overdue PMS assignments")
        if expected-count>=3:risks.append("Missing eligible-day reports (approved leave excluded)")
        if parts["quality"] is not None and parts["quality"]<50:risks.append("Reviewed work quality below 50")
        edu=educations.get(e.id)
        output.append({"id":e.id,"user_id":e.user_id,"intern_id":e.employee_id,"name":f"{e.first_name} {e.last_name}","email":e.work_email or e.personal_email,"profile_photo_url":e.profile_photo_url,
            "department_id":e.department_id,"department":departments.get(e.department_id),"manager_id":e.reporting_manager_id,
            "college":edu.institution if edu else None,"degree":edu.degree if edu else None,"skills":skills.get(e.id,[]),"status":e.status,
            "batches":[{"id":b.id,"name":b.name,"code":b.code,"mentor_id":b.mentor_user_id} for b in batches],"assigned":assigned,"accepted":accepted,"overdue":int(s.overdue or 0) if s else 0,
            "submitted":r.submitted if r else 0,"submission_rate":round(r.submitted*100/assigned) if r and assigned else 0,
            "reports":count,"expected_reports":expected,"attendance":attendance_percent,"parts":parts,"score":overall,"risks":risks,"eligible":not reasons,"eligibility_reasons":reasons})
    return {"items":output,"total":total,"page":page,"per_page":per_page}
