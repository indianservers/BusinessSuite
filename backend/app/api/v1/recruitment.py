from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user, RequirePermission
from app.models.user import User
from app.crud.crud_employee import crud_employee
from app.models.recruitment import Job, RecruitmentRequisition, Candidate, Interview, InterviewFeedback, OfferLetter
from app.schemas.employee import EmployeeCreate, EmployeeSchema
from app.schemas.recruitment import (
    JobCreate, JobUpdate, JobSchema,
    RecruitmentRequisitionCreate, RecruitmentRequisitionReview, RecruitmentRequisitionSchema,
    CandidateCreate, CandidateUpdate, CandidateSchema,
    InterviewCreate, InterviewFeedbackCreate, OfferLetterCreate, CandidateConversionCreate,
)

router = APIRouter(prefix="/recruitment", tags=["Recruitment ATS"])


@router.post("/requisitions", response_model=RecruitmentRequisitionSchema, status_code=201)
def create_requisition(
    data: RecruitmentRequisitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    number = f"REQ{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    req = RecruitmentRequisition(requisition_number=number, requested_by=current_user.id, **data.model_dump())
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/requisitions", response_model=List[RecruitmentRequisitionSchema])
def list_requisitions(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_view")),
):
    query = db.query(RecruitmentRequisition)
    if status:
        query = query.filter(RecruitmentRequisition.status == status)
    return query.order_by(RecruitmentRequisition.id.desc()).limit(200).all()


@router.put("/requisitions/{requisition_id}/review", response_model=RecruitmentRequisitionSchema)
def review_requisition(
    requisition_id: int,
    data: RecruitmentRequisitionReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    req = db.query(RecruitmentRequisition).filter(RecruitmentRequisition.id == requisition_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requisition not found")
    action = data.action.lower()
    if action == "approve":
        job = Job(
            title=req.title,
            code=f"JOB-{req.requisition_number}",
            department_id=req.department_id,
            designation_id=req.designation_id,
            branch_id=req.branch_id,
            openings=req.openings,
            description=req.justification,
            status="Open",
            posted_date=datetime.now(timezone.utc).date(),
        )
        db.add(job)
        db.flush()
        req.status = "Approved"
        req.approved_by = current_user.id
        req.approved_at = datetime.now(timezone.utc)
        req.job_id = job.id
    elif action == "reject":
        req.status = "Rejected"
    else:
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    db.commit()
    db.refresh(req)
    return req


# ── Jobs ──────────────────────────────────────────────────────────────────────

@router.get("/jobs", response_model=List[JobSchema])
def list_jobs(
    status: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_view")),
):
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    if department_id:
        q = q.filter(Job.department_id == department_id)
    return q.order_by(Job.id.desc()).all()


@router.post("/jobs", response_model=JobSchema, status_code=201)
def create_job(
    data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    job = Job(**data.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs/{job_id}", response_model=JobSchema)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_view")),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/jobs/{job_id}", response_model=JobSchema)
def update_job(
    job_id: int,
    data: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(job, k, v)
    db.commit()
    db.refresh(job)
    return job


# ── Candidates ────────────────────────────────────────────────────────────────

@router.get("/candidates", response_model=List[CandidateSchema])
def list_candidates(
    job_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_view")),
):
    from sqlalchemy import or_
    q = db.query(Candidate)
    if job_id:
        q = q.filter(Candidate.job_id == job_id)
    if status:
        q = q.filter(Candidate.status == status)
    if search:
        term = f"%{search}%"
        q = q.filter(or_(
            Candidate.first_name.ilike(term),
            Candidate.last_name.ilike(term),
            Candidate.email.ilike(term),
        ))
    return q.order_by(Candidate.applied_at.desc()).offset((page-1)*per_page).limit(per_page).all()


@router.get("/applications", response_model=List[CandidateSchema])
def list_applications(
    job_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_view")),
):
    query = db.query(Candidate)
    if job_id:
        query = query.filter(Candidate.job_id == job_id)
    if status:
        query = query.filter(Candidate.status == status)
    return query.order_by(Candidate.applied_at.desc()).limit(300).all()


@router.post("/candidates", response_model=CandidateSchema, status_code=201)
def create_candidate(
    data: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    candidate = Candidate(**data.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.post("/applications", response_model=CandidateSchema, status_code=201)
def create_application(
    data: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    return create_candidate(data, db, current_user)


@router.get("/candidates/{candidate_id}", response_model=CandidateSchema)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_view")),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.put("/candidates/{candidate_id}/status")
def update_candidate_status(
    candidate_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.status = status
    db.commit()
    return {"message": f"Status updated to {status}"}


@router.post("/candidates/{candidate_id}/convert", response_model=EmployeeSchema, status_code=201)
def convert_candidate_to_employee(
    candidate_id: int,
    data: CandidateConversionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_create")),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    employee = crud_employee.create_with_user(db, obj_in=EmployeeCreate(
        employee_id=data.employee_id,
        first_name=candidate.first_name,
        last_name=candidate.last_name,
        personal_email=candidate.email,
        phone_number=candidate.phone,
        date_of_joining=data.date_of_joining,
        branch_id=candidate.job.branch_id if candidate.job else None,
        department_id=candidate.job.department_id if candidate.job else None,
        designation_id=candidate.job.designation_id if candidate.job else None,
        employment_type=data.employment_type,
        create_user_account=data.create_user_account,
        user_email=candidate.email if data.create_user_account else None,
    ))
    candidate.status = "Hired"
    db.commit()
    return employee


@router.post("/candidates/{candidate_id}/resume")
async def upload_resume(
    candidate_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    import shutil, os, uuid
    from app.core.config import settings

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    upload_path = os.path.join(settings.UPLOAD_DIR, "resumes")
    os.makedirs(upload_path, exist_ok=True)
    filename = f"{candidate_id}_{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(upload_path, filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    candidate.resume_url = f"/uploads/resumes/{filename}"
    db.commit()
    return {"resume_url": candidate.resume_url, "message": "Resume uploaded. Use /ai/parse-resume to parse."}


# ── Interviews ────────────────────────────────────────────────────────────────

@router.post("/interviews", status_code=201)
def schedule_interview(
    data: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    interview = Interview(**data.model_dump())
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.get("/candidates/{candidate_id}/interviews")
def get_interviews(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_view")),
):
    return db.query(Interview).filter(Interview.candidate_id == candidate_id).order_by(Interview.round_number).all()


@router.put("/interviews/{interview_id}/result")
def update_interview_result(
    interview_id: int,
    result: str,
    status: str,
    overall_rating: Optional[float] = None,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    interview.result = result
    interview.status = status
    if overall_rating:
        interview.overall_rating = overall_rating
    if remarks:
        interview.remarks = remarks
    db.commit()
    return {"message": "Interview updated"}


@router.post("/interviews/{interview_id}/feedback", status_code=201)
def add_feedback(
    interview_id: int,
    data: InterviewFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    feedback = InterviewFeedback(
        interview_id=interview_id,
        interviewer_id=current_user.employee.id,
        **data.model_dump(),
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


# ── Offer Letters ─────────────────────────────────────────────────────────────

@router.post("/offers", status_code=201)
def create_offer(
    data: OfferLetterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    offer = OfferLetter(**data.model_dump())
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


@router.put("/offers/{offer_id}/status")
def update_offer_status(
    offer_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    offer.status = status
    if status == "Accepted":
        from datetime import datetime, timezone
        offer.accepted_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": f"Offer {status}"}
