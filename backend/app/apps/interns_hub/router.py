from app.core.rich_text import rich_text_type
"""Intern-only portal APIs. HRMS remains the source of employee and attendance data."""
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Form, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_db, get_current_user, security
from app.models.user import User
from app.models.employee import Employee
from app.models.attendance import Attendance
from .models import (InternTask, InternSubmission, InternReport, InternCourse, InternEnrollment,
                     InternCertificate, InternFile, InternTicket)

router = APIRouter(prefix="/interns-hub", tags=["Interns Hub"])


def today():
    return datetime.now(ZoneInfo(settings.CELERY_TIMEZONE)).date()


def ensure_intern(user):
    employee = getattr(user, "employee", None)
    role = user.role.name.lower() if user.role else ""
    if (not employee or employee.deleted_at or employee.status not in {"Active", "Probation"}
            or (employee.employment_type or "").strip().lower() != "intern"
            or user.is_superuser or role not in {"intern", "employee"}):
        raise HTTPException(403, "Interns Hub is available only to active HRMS interns with an intern or employee account")
    return employee


def intern(user: User = Depends(get_current_user)):
    return ensure_intern(user)


def admin(user: User = Depends(get_current_user)):
    from .management_access import require_admin
    return require_admin(user)


def managed(db, user, employee_id):
    from .management_access import get_employee
    return get_employee(db,user,employee_id)


def rows(items):
    return [jsonable_encoder({c.name: getattr(item, c.name) for c in item.__table__.columns}) for item in items]


def profile(e):
    fields = ["id", "employee_id", "first_name", "last_name", "gender", "date_of_birth", "father_name", "mother_name",
              "personal_email", "work_email", "phone_number", "phone_number_country_code", "present_address", "present_city", "present_state",
              "present_pincode", "bio", "interests", "profile_photo_url", "date_of_joining", "date_of_exit",
              "employment_type", "status", "department_id", "designation_id", "branch_id", "reporting_manager_id"]
    result = {key: getattr(e, key, None) for key in fields}
    from app.core.orm_validation import contact_issues
    result['phone_validation_issues']=contact_issues(e)
    for key in ["department", "designation", "branch"]:
        result[key] = getattr(getattr(e, key, None), "name", None)
    result["manager"] = f"{e.reporting_manager.first_name} {e.reporting_manager.last_name}" if e.reporting_manager else None
    result["education"] = rows(e.educations)
    result["skills"] = rows(e.skills)
    # Identity numbers and payroll information are intentionally not portal payloads.
    result["documents"] = [{"id": d.id, "name": d.document_name or d.document_type, "status": d.verification_status} for d in e.documents]
    return jsonable_encoder(result)


def summary(db, employee):
    from .pms_adapter import summary as pms_summary
    return pms_summary(db,employee,today())


@router.get("/me")
def me(e=Depends(intern)):
    return profile(e)


class ProfileUpdate(BaseModel):
    phone_number: str | None = Field(None, max_length=20)
    phone_number_country_code: str | None = None
    personal_email: str | None = Field(None, max_length=150)
    present_address: str | None = Field(None, max_length=1000)
    present_city: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=1000)
    interests: str | None = Field(None, max_length=1000)


@router.patch("/me")
def edit_profile(data: ProfileUpdate, e=Depends(intern), db: Session = Depends(get_db)):
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(e, key, value)
    from app.apps.hrms.services.identity import HrmsIdentityService
    HrmsIdentityService.sync_employee_identity(db, e)
    db.commit()
    return profile(e)


@router.get("/profile")
def shared_intern_profile(e=Depends(intern), db: Session = Depends(get_db)):
    from app.common.services.profiles import serialize_profile
    result = serialize_profile(db, e.user, e.user)
    db.commit()
    return result


from app.common.profile_api import ProfileUpdate as SharedProfileUpdate


@router.patch("/profile")
def edit_shared_intern_profile(data: SharedProfileUpdate, e=Depends(intern), db: Session = Depends(get_db)):
    from app.common.services.profiles import update_profile
    return update_profile(db, e.user, e.user, data.values, data.version, data.reason)


@router.post("/profile/photo")
async def intern_profile_photo(file: UploadFile = File(...), e=Depends(intern), db: Session = Depends(get_db)):
    from app.common.services.profiles import upload_photo
    return await upload_photo(db, e.user, e.user, file)


@router.get("/overview")
def overview(e=Depends(intern), db: Session = Depends(get_db)):
    return summary(db, e)


@router.get("/tasks")
def tasks(page: int = Query(1, ge=1), per_page: int = Query(500, ge=1, le=500), e=Depends(intern), db: Session = Depends(get_db)):
    from .pms_adapter import task_rows
    return task_rows(db,e,page=page,per_page=per_page)


def own_task(db, task_id, employee_id):
    raise HTTPException(410, "Legacy HRMS tasks are read-only; use the PMS assignment")


@router.post("/tasks/{task_id}/start")
def start_task(task_id: int, e=Depends(intern), db: Session = Depends(get_db)):
    from app.apps.project_management import work
    from .pms_adapter import task_rows
    work.start(db,task_id,e.user)
    return next((t for t in task_rows(db,e) if t["id"]==task_id), {"id":task_id,"source":"PMS"})


from app.apps.project_management.work_api import SubmissionInput


@router.post("/tasks/{task_id}/submissions", status_code=201)
def submit(task_id: int, data: SubmissionInput, e=Depends(intern), db: Session = Depends(get_db)):
    from app.apps.project_management import work
    return work.payload(db,[work.submit(db,task_id,e.user,data)])[0]


@router.get("/submissions")
def submissions(page: int = Query(1, ge=1), per_page: int = Query(500, ge=1, le=500), e=Depends(intern), db: Session = Depends(get_db)):
    from .pms_adapter import submissions as pms_submissions
    return pms_submissions(db,e,page=page,per_page=per_page)


class TaskTimeInput(BaseModel):
    task_id:int
    minutes:int=Field(ge=0,le=1440)
    notes:rich_text_type(1000, 0) = Field("")


class ReportInput(BaseModel):
    task_entries:list[TaskTimeInput]=Field(default_factory=list,max_length=20)
    evidence:list[int]=Field(default_factory=list,max_length=10)
    in_progress:str=Field("",max_length=2000)
    report_date: date
    work: str = Field(min_length=1, max_length=2000)
    learning: str = Field(min_length=1, max_length=2000)
    blockers: str = Field("", max_length=2000)
    tomorrow: str = Field("", max_length=2000)
    mood: Literal["Great", "Good", "Okay", "Stressed", "Tired"] = "Good"
    minutes: int = Field(0, ge=0, le=1440)
    status: Literal["Draft", "Submitted"] = "Draft"


@router.put("/reports")
def save_report(data: ReportInput, e=Depends(intern), db: Session = Depends(get_db)):
    if data.report_date > today() or data.report_date < e.date_of_joining:
        raise HTTPException(422, "Report date must fall between joining date and today")
    from app.apps.project_management import work
    from app.apps.project_management.models import PMSFileAsset
    if sum(t.minutes for t in data.task_entries)>1440:raise HTTPException(422,"Task time exceeds one day")
    for entry in data.task_entries:work.own_assignment(db,entry.task_id,e.user)
    for fid in data.evidence:
        asset=db.get(PMSFileAsset,fid)
        if not asset or asset.uploaded_by_user_id!=e.user_id or asset.deleted_at:raise HTTPException(403,"Evidence must belong to you")
    report = db.query(InternReport).filter_by(employee_id=e.id, report_date=data.report_date).with_for_update().first()
    if not report:
        report = InternReport(employee_id=e.id)
        db.add(report)
    for key, value in data.model_dump().items():
        setattr(report, key, value)
    if data.status=="Submitted":
        report.submitted_at=datetime.now(timezone.utc)
        for entry in data.task_entries:
            task=work.own_assignment(db,entry.task_id,e.user)[1]
            work.activity(db,task,e.user,"daily_report.submitted",metadata={"employee_id":e.id,"report_date":str(data.report_date),"minutes":entry.minutes,"self_reported":True})
    db.commit()
    return rows([report])[0]


@router.get("/reports")
def reports(e=Depends(intern), db: Session = Depends(get_db)):
    return rows(db.query(InternReport).filter_by(employee_id=e.id).order_by(InternReport.report_date.desc()).all())


@router.get("/attendance")
def attendance(e=Depends(intern), db: Session = Depends(get_db)):
    return rows(db.query(Attendance).filter_by(employee_id=e.id).order_by(Attendance.attendance_date.desc()).limit(366).all())


@router.post("/attendance/{action}")
def mark_attendance(action: Literal["check-in", "check-out"], e=Depends(intern), db: Session = Depends(get_db)):
    # Lock the shared employee row so concurrent requests cannot create duplicate attendance.
    db.query(Employee).filter_by(id=e.id).with_for_update().first()
    record = db.query(Attendance).filter_by(employee_id=e.id, attendance_date=today()).first()
    now = datetime.now(timezone.utc)
    if action == "check-in":
        if record and record.check_in:
            raise HTTPException(409, "Already checked in today")
        if not record:
            record = Attendance(employee_id=e.id, attendance_date=today(), status="Present", source="Interns Hub")
            db.add(record)
        record.check_in = now
    else:
        if not record or not record.check_in or record.check_out:
            raise HTTPException(409, "An open check-in is required")
        start = record.check_in.replace(tzinfo=timezone.utc) if record.check_in.tzinfo is None else record.check_in
        record.check_out = now
        record.total_hours = round((now - start).total_seconds() / 3600, 2)
    db.commit()
    return rows([record])[0]


@router.post("/files", status_code=201)
def upload(file: UploadFile = File(...), task_id: int = Form(...), e=Depends(intern), db: Session = Depends(get_db)):
    from app.apps.project_management import work
    return work.upload(db,task_id,e.user,file)


@router.get("/files/{file_id}")
def download(file_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    from app.apps.project_management import work
    from app.core.storage import FileResponse as StoredFileResponse
    if user.employee and (user.employee.employment_type or "").lower()=="intern":ensure_intern(user)
    item=work.file_access(db,file_id,user)
    return StoredFileResponse(item.storage_path,filename=item.original_name,media_type="application/octet-stream")


@router.get("/learning")
def learning(e=Depends(intern), db: Session = Depends(get_db)):
    from app.apps.srm.services.commercial import tenant
    courses = db.query(InternCourse).filter(InternCourse.organization_id==tenant(e.user),(InternCourse.department_id == None) | (InternCourse.department_id == e.department_id)).all()
    enrollment = {r.course_id: r for r in db.query(InternEnrollment).filter_by(employee_id=e.id).all()}
    result = rows(courses)
    for item in result:
        item["questions"] = [{"prompt": q["prompt"], "options": q["options"]} for q in item["questions"] or []]
        record = enrollment.get(item["id"])
        item["completed_lessons"] = record.completed_lessons if record else []
        item["score"] = record.score if record else None
    return result


class LearningInput(BaseModel):
    lesson: int | None = Field(None, ge=0)
    answers: list[int] | None = None


@router.post("/learning/{course_id}/progress")
def course_progress(course_id: int, data: LearningInput, e=Depends(intern), db: Session = Depends(get_db)):
    course = db.get(InternCourse, course_id)
    from app.apps.srm.services.commercial import tenant
    if not course or course.organization_id!=tenant(e.user) or (course.department_id and course.department_id != e.department_id):
        raise HTTPException(404, "Course not found")
    record = db.query(InternEnrollment).filter_by(employee_id=e.id, course_id=course_id).first()
    if not record:
        record = InternEnrollment(employee_id=e.id, course_id=course_id, completed_lessons=[])
        db.add(record)
    if data.lesson is not None:
        if data.lesson >= len(course.lessons or []):
            raise HTTPException(422, "Lesson not found")
        record.completed_lessons = sorted(set((record.completed_lessons or []) + [data.lesson]))
    if data.answers is not None:
        questions = course.questions or []
        if not questions or len(data.answers) != len(questions):
            raise HTTPException(422, "Answer every assessment question")
        record.score = round(sum(a == q["answer"] for a, q in zip(data.answers, questions)) * 100 / len(questions))
    db.commit()
    return rows([record])[0]


@router.get("/leaderboard")
def leaderboard(e=Depends(intern), db: Session = Depends(get_db)):
    from sqlalchemy import case,func,or_
    from app.models.company import Branch
    from app.apps.project_management.models import PMSWorkSubmission, PMSWorkReview, PMSTaskAssignee, PMSTask, PMSProject
    from app.apps.srm.services.commercial import tenant
    peers=db.query(Employee.id).outerjoin(Branch,Branch.id==Employee.branch_id).filter(Employee.department_id==e.department_id,Employee.employment_type=="Intern",Employee.status.in_(["Active","Probation"]),Employee.deleted_at.is_(None),or_(Branch.company_id==tenant(e.user),(Employee.branch_id.is_(None)) & (tenant(e.user)==1)))
    latest=db.query(PMSWorkSubmission.task_id,PMSWorkSubmission.user_id,func.max(PMSWorkSubmission.id).label("id")).filter(PMSWorkSubmission.status!="Draft").group_by(PMSWorkSubmission.task_id,PMSWorkSubmission.user_id).subquery()
    scored=db.query(PMSWorkSubmission.user_id,func.avg(PMSWorkReview.score*100.0/PMSWorkReview.maximum_score).label("score")).join(latest,latest.c.id==PMSWorkSubmission.id).join(PMSWorkReview,PMSWorkReview.submission_id==PMSWorkSubmission.id).join(PMSTask,PMSTask.id==PMSWorkSubmission.task_id).join(PMSProject,PMSProject.id==PMSTask.project_id).filter(PMSTask.deleted_at.is_(None),PMSProject.deleted_at.is_(None),func.coalesce(PMSProject.organization_id,1)==tenant(e.user)).group_by(PMSWorkSubmission.user_id).subquery()
    counts=db.query(PMSTaskAssignee.user_id,func.count().label("total"),func.sum(case((PMSTaskAssignee.execution_status=="Done",1),else_=0)).label("completed")).join(PMSTask,PMSTask.id==PMSTaskAssignee.task_id).join(PMSProject,PMSProject.id==PMSTask.project_id).filter(PMSTask.deleted_at.is_(None),PMSProject.deleted_at.is_(None),func.coalesce(PMSProject.organization_id,1)==tenant(e.user)).group_by(PMSTaskAssignee.user_id).subquery()
    rows=db.query(Employee,scored.c.score,counts.c.total,counts.c.completed).outerjoin(scored,scored.c.user_id==Employee.user_id).outerjoin(counts,counts.c.user_id==Employee.user_id).filter(Employee.id.in_(peers)).order_by(func.coalesce(scored.c.score,0).desc(),func.coalesce(counts.c.completed,0).desc(),Employee.id).limit(50).all()
    return [{"id":p.id,"name":f"{p.first_name} {p.last_name}","department":getattr(e.department,"name",None),"score":round(float(score),1) if score is not None else None,"total_tasks":total or 0,"completed":completed or 0} for p,score,total,completed in rows]



@router.get("/certificates")
def certificates(e=Depends(intern), db: Session = Depends(get_db)):
    return rows(db.query(InternCertificate).filter_by(employee_id=e.id).all())


@router.get("/certificates/{certificate_id}/download")
def certificate_download(certificate_id: int, e=Depends(intern), db: Session = Depends(get_db)):
    from io import BytesIO
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.colors import HexColor
    item = db.query(InternCertificate).filter_by(id=certificate_id, employee_id=e.id).first()
    if not item:
        raise HTTPException(404, "Certificate not found")
    output = BytesIO()
    width, height = landscape(A4)
    pdf = canvas.Canvas(output, pagesize=(width, height))
    pdf.setTitle(item.title)
    pdf.setAuthor("InternHub")
    pdf.setStrokeColor(HexColor("#5141ff"))
    pdf.setLineWidth(3)
    pdf.rect(28, 28, width - 56, height - 56)
    pdf.setLineWidth(.6)
    pdf.rect(37, 37, width - 74, height - 74)
    def centered(text, y, size=18, font="Helvetica"):
        pdf.setFillColor(HexColor("#181642"))
        while pdf.stringWidth(text, font, size) > width - 130 and size > 10:
            size -= 1
        pdf.setFont(font, size)
        pdf.drawCentredString(width / 2, y, text)
    centered("InternHub", height - 98, 25, "Helvetica-Bold")
    centered(item.certificate_type.upper(), height - 142, 12)
    centered(item.title, height - 205, 31, "Times-Bold")
    centered("This is to certify that", height - 253, 14)
    centered(f"{e.first_name} {e.last_name}", height - 306, 30, "Helvetica-Bold")
    centered("has successfully completed the above program.", height - 348, 14)
    centered(f"Issued {item.issued_at.date()} | {item.verification_id or ('IH-' + str(item.id))}", 105, 11)
    centered("Approved and issued by the HRMS program team", 80, 10)
    pdf.showPage()
    pdf.save()
    return Response(output.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="internhub-certificate-{item.id}.pdf"'})



class TicketInput(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    message: rich_text_type(4000, 1) = Field()


@router.get("/support")
def tickets(e=Depends(intern), db: Session = Depends(get_db)):
    return rows(db.query(InternTicket).filter_by(employee_id=e.id).order_by(InternTicket.id.desc()).all())


@router.post("/support", status_code=201)
def create_ticket(data: TicketInput, e=Depends(intern), db: Session = Depends(get_db)):
    item = InternTicket(employee_id=e.id, **data.model_dump())
    db.add(item)
    db.commit()
    return rows([item])[0]


@router.get("/admin/interns")
def admin_interns(page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=100), user=Depends(admin), db: Session = Depends(get_db)):
    from .management_access import employee_query
    return [{**profile(e),"summary":summary(db,e)} for e in employee_query(db,user).order_by(Employee.id).offset((page-1)*per_page).limit(per_page)]


@router.get("/admin/interns/{employee_id}")
def admin_detail(employee_id: int, user=Depends(admin), db: Session = Depends(get_db)):
    from .pms_adapter import task_rows,submissions as pms_submissions
    e=managed(db,user,employee_id)
    from app.apps.project_management.access import accessible_project_query,can_access_project
    from app.apps.project_management.models import PMSProject,PMSTask,PMSTaskAssignee
    projects=accessible_project_query(db,user).all()
    browse={p.id for p in projects};approve={p.id for p in projects if can_access_project(db,p,user,"approve")}
    task_projects=dict(db.query(PMSTask.id,PMSTask.project_id).filter(PMSTask.id.in_(db.query(PMSTaskAssignee.task_id).filter_by(user_id=e.user_id))))
    return {"profile":profile(e),"tasks":[t for t in task_rows(db,e) if task_projects.get(t["id"]) in browse],"submissions":[s for s in pms_submissions(db,e) if task_projects.get(s["task_id"]) in approve],
        "reports":rows(db.query(InternReport).filter_by(employee_id=e.id).order_by(InternReport.report_date.desc()).limit(100).all()),
        "tickets":rows(db.query(InternTicket).filter_by(employee_id=e.id).limit(100).all()),"certificates":rows(db.query(InternCertificate).filter_by(employee_id=e.id).all())}


class TaskInput(BaseModel):
    project_id: int
    reviewer_user_id: int | None = None
    idempotency_key: str | None = None
    employee_id: int
    title: str = Field(min_length=1, max_length=200)
    description: rich_text_type(10000, 1) = Field()
    category: str = Field("Project", max_length=80)
    priority: Literal["High", "Medium", "Low"] = "Medium"
    points: int = Field(10, ge=0, le=100)
    due_date: date
    instructions: str = Field("", max_length=10000)
    objectives: str = Field("", max_length=5000)
    deliverables: str = Field("", max_length=5000)


@router.post("/admin/tasks", status_code=201)
def assign(data: TaskInput, user=Depends(admin), db: Session = Depends(get_db)):
    from .distribution import publish
    from .pms_adapter import task_rows
    e=managed(db,user,data.employee_id)
    payload=data.model_dump()
    payload.update(target_type="interns",employee_ids=[e.id],reviewer_user_id=data.reviewer_user_id or user.id,maximum_score=100,idempotency_key=data.idempotency_key or uuid4().hex)
    job=publish(db,user,payload)
    return next(t for t in task_rows(db,e) if t["id"]==job.task_id)


from app.apps.project_management.work_api import ReviewInput


@router.post("/admin/submissions/{submission_id}/review")
def review(submission_id: int, data: ReviewInput, user=Depends(admin), db: Session = Depends(get_db)):
    from app.apps.project_management.models import PMSWorkSubmission
    from app.apps.project_management import work
    s=db.get(PMSWorkSubmission,submission_id)
    if not s:raise HTTPException(404,"PMS submission not found")
    employee=db.query(Employee).filter_by(user_id=s.user_id).first()
    if not employee:raise HTTPException(404,"Intern not found")
    managed(db,user,employee.id)
    work.review(db,submission_id,user,data)
    return work.payload(db,[s])[0]


class Lesson(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    url: HttpUrl


class Question(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=6)
    answer: int = Field(ge=0, le=5)


class CourseInput(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: rich_text_type(5000, 0) = Field("")
    level: str = Field("Beginner", max_length=40)
    department_id: int | None = None
    lessons: list[Lesson] = Field(default_factory=list, max_length=50)
    questions: list[Question] = Field(default_factory=list, max_length=50)


@router.post("/admin/learning", status_code=201)
def add_course(data: CourseInput, user=Depends(admin), db: Session = Depends(get_db)):
    from .management_access import organization_admin
    from app.apps.srm.services.commercial import tenant
    from app.models.company import Department,Branch
    if data.department_id:
        department=db.query(Department).join(Branch,Branch.id==Department.branch_id).filter(Department.id==data.department_id,Branch.company_id==tenant(user)).first()
        if not department:raise HTTPException(403,"Department is outside your organization")
    if not organization_admin(user) and (not user.employee or data.department_id!=user.employee.department_id or not data.department_id):
        raise HTTPException(403,"Choose your own department")
    if any(q.answer >= len(q.options) for q in data.questions):
        raise HTTPException(422, "Assessment answer must match an option")
    item = InternCourse(**jsonable_encoder(data.model_dump()), created_by=user.id,organization_id=tenant(user))
    db.add(item)
    db.commit()
    return rows([item])[0]


class CertificateInput(BaseModel):
    employee_id: int
    title: str = Field(min_length=1, max_length=180)
    certificate_type: Literal["Module Completion", "Skill Assessment", "Project Completion", "Internship"] = "Module Completion"


@router.post("/admin/certificates", status_code=201)
def issue(data: CertificateInput, user=Depends(admin), db: Session = Depends(get_db)):
    e=managed(db,user,data.employee_id)
    if data.certificate_type=="Internship":raise HTTPException(409,"Use Performance & Completion: manager approval is required before final certificate issuance")
    item=InternCertificate(**data.model_dump(),issued_by=user.id,verification_id="IH-CERT-"+uuid4().hex.upper());db.add(item);db.commit();return rows([item])[0]


class TicketReply(BaseModel):
    reply: str = Field(min_length=1, max_length=4000)
    status: Literal["Open", "Resolved"] = "Resolved"


@router.post("/admin/support/{ticket_id}/reply")
def reply_ticket(ticket_id: int, data: TicketReply, user=Depends(admin), db: Session = Depends(get_db)):
    item = db.get(InternTicket, ticket_id)
    if not item:
        raise HTTPException(404, "Ticket not found")
    managed(db, user, item.employee_id)
    item.reply, item.status = data.reply, data.status
    db.commit()
    return rows([item])[0]


@router.post("/logout")
def logout(user=Depends(get_current_user), credentials=Depends(security), db: Session = Depends(get_db)):
    from app.core.security import verify_access_token
    from app.models.user import UserSession
    payload = verify_access_token(credentials.credentials) or {}
    try:
        session_id = int(payload.get("sid"))
    except (TypeError, ValueError):
        raise HTTPException(401, "Invalid session")
    session = db.query(UserSession).filter_by(id=session_id, user_id=user.id).first()
    if session:
        session.status = "Revoked"
        db.commit()
    return {"ok": True}


from app.schemas.auth import ChangePasswordRequest


@router.post("/password")
def update_password(data: ChangePasswordRequest, request: Request, e=Depends(intern), user=Depends(get_current_user), db: Session = Depends(get_db)):
    from app.api.v1.auth import change_password
    return change_password(data, request, user, db)


from .applications import router as application_router
router.include_router(application_router)

from .signup import router as signup_router
router.include_router(signup_router)

from .management_api import router as management_router
router.include_router(management_router)

from .operations import router as operations_router
router.include_router(operations_router)

from .onboarding import router as onboarding_router
router.include_router(onboarding_router)


from app.apps.project_management.work_api import ProgressInput

@router.post('/tasks/{task_id}/progress')
def task_progress(task_id:int,data:ProgressInput,e=Depends(intern),db:Session=Depends(get_db)):
    from app.apps.project_management.work_api import progress
    return progress(task_id,data,e.user,db)


@router.put('/employee-reports')
def employee_report(data:ReportInput,user=Depends(get_current_user),db:Session=Depends(get_db)):
    if not user.employee or user.employee.deleted_at or user.employee.status not in {'Active','Probation'}:raise HTTPException(403,'Active approved employee account required')
    return save_report(data,user.employee,db)
