"""Application intake paging and durable bulk decisions with per-person results."""
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_db
from app.models.user import User
from app.apps.srm.services.commercial import tenant
from .applications import application_admin, DecisionInput, decide_application
from .models import InternApplication
from .operations_models import WorkforceJob, WorkforceJobFailure

router = APIRouter(prefix="/admin", tags=["Bulk onboarding"])


def application_query(db, user, search="", status=""):
    q = db.query(InternApplication).filter_by(organization_id=tenant(user))
    if status:
        q = q.filter(InternApplication.status == status)
    if search.strip():
        term = "%" + search.strip() + "%"
        q = q.filter(or_(InternApplication.full_name.ilike(term), InternApplication.email.ilike(term), InternApplication.reference.ilike(term)))
    return q


@router.get("/application-intake")
def intake(search: str = Query("", max_length=150), status: str = "", page: int = Query(1, ge=1),
           per_page: int = Query(50, ge=1, le=100), user=Depends(application_admin), db: Session = Depends(get_db)):
    from .applications import receipt
    from .management_models import ApplicationDocument
    q = application_query(db, user, search, status)
    rows = q.order_by(InternApplication.created_at.desc(), InternApplication.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    documents = {}
    for document in db.query(ApplicationDocument).filter(ApplicationDocument.application_id.in_([r.id for r in rows])):
        documents.setdefault(document.application_id, []).append({"id": document.id, "name": document.name, "category": document.category, "size": document.size})
    return {"items": [{"id": row.id, "reference": row.reference, "email": row.email, "full_name": row.full_name,
        "details": row.details, "documents": documents.get(row.id, []), "identity_last4": row.identity_last4,
        "created_at": row.created_at, **receipt(row, db)} for row in rows], "total": q.count(), "page": page,
        "reviewable_total": q.filter(InternApplication.status.in_(["Pending", "Correction Requested"])).count(),
        "counts": dict(application_query(db, user, search).with_entities(InternApplication.status, func.count()).group_by(InternApplication.status))}


class BulkDecision(BaseModel):
    application_ids: list[int] = Field(default_factory=list, max_length=20000)
    all_filtered: bool = False
    search: str = Field("", max_length=150)
    status: str = ""
    decision: DecisionInput
    request_key: str = Field(min_length=8, max_length=100)


@router.post("/application-jobs", status_code=201)
def start_job(data: BulkDecision, user=Depends(application_admin), db: Session = Depends(get_db)):
    from .operations import job_result
    payload = data.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    previous = db.query(WorkforceJob).filter_by(organization_id=tenant(user), request_key=data.request_key).first()
    if previous:
        if previous.payload_hash != digest or previous.created_by != user.id:
            raise HTTPException(409, "Request key was used for a different intake operation")
        return job_result(previous)
    q = application_query(db, user, data.search, data.status).filter(InternApplication.status.in_(["Pending", "Correction Requested"]))
    if not data.all_filtered:
        q = q.filter(InternApplication.id.in_(data.application_ids))
        if q.count() != len(set(data.application_ids)):
            raise HTTPException(409, "Some applications are outside your scope or already reviewed; refresh the selection")
    ids = [r[0] for r in q.with_entities(InternApplication.id).order_by(InternApplication.id).limit(20001)]
    if not ids or len(ids) > 20000:
        raise HTTPException(422, "Select between 1 and 20,000 reviewable applications")
    decision = data.decision
    if decision.status == "Approved" and not all([decision.branch_id, decision.department_id, decision.designation_id,
        decision.reporting_manager_id or decision.reporting_manager_user_id, decision.date_of_joining]):
        raise HTTPException(422, "Assign branch, department, designation, supervisor and joining date")
    if decision.status != "Approved" and not decision.review_note.strip():
        raise HTTPException(422, "Enter a reason for rejection or correction")
    job = WorkforceJob(organization_id=tenant(user), created_by=user.id, request_key=data.request_key, payload_hash=digest,
        operation="onboard", payload=payload, recipients=ids, result={"succeeded": 0, "failed_count": 0, "failed": []})
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Intake operation is being created; retry with the same request key")
    process_onboarding(db, job)
    return job_result(db.get(WorkforceJob, job.id))


@router.get("/application-jobs")
def jobs(page: int = Query(1, ge=1), user=Depends(application_admin), db: Session = Depends(get_db)):
    from .operations import job_result
    q = db.query(WorkforceJob).filter_by(organization_id=tenant(user), operation="onboard", created_by=user.id)
    return {"items": [job_result(j) for j in q.order_by(WorkforceJob.id.desc()).offset((page-1)*10).limit(10)], "total": q.count()}


@router.post("/application-jobs/{job_id}/continue")
def continue_job(job_id: int, user=Depends(application_admin), db: Session = Depends(get_db)):
    from .operations import job_result
    job = db.query(WorkforceJob).filter_by(id=job_id, organization_id=tenant(user), operation="onboard", created_by=user.id).with_for_update().first()
    if not job:
        raise HTTPException(404, "Intake operation not found")
    return job_result(process_onboarding(db, job))


@router.get("/application-jobs/{job_id}/errors")
def errors(job_id: int, page: int = Query(1, ge=1), user=Depends(application_admin), db: Session = Depends(get_db)):
    if not db.query(WorkforceJob.id).filter_by(id=job_id, organization_id=tenant(user), operation="onboard", created_by=user.id).first():
        raise HTTPException(404, "Intake operation not found")
    q = db.query(WorkforceJobFailure).filter_by(job_id=job_id)
    return {"items": [{"id": row.record_id, "message": row.message} for row in q.order_by(WorkforceJobFailure.id).offset((page-1)*50).limit(50)], "total": q.count()}


def process_onboarding(db, job, chunk_size=25):
    job_id = job.id
    for _ in range(chunk_size):
        job = db.query(WorkforceJob).filter_by(id=job_id).with_for_update().one()
        if job.status == "Completed":
            return job
        user = db.get(User, job.created_by)
        try:
            if not user or not user.is_active or tenant(user) != job.organization_id:
                raise HTTPException(403, "Approver account or organization changed")
            application_admin(user)
        except HTTPException as exc:
            job.status = "Failed"; job.error = str(exc.detail); db.commit(); return job
        application_id = job.recipients[job.cursor]
        result = dict(job.result or {"succeeded": 0, "failed": []})
        point = db.begin_nested()
        approved = False
        try:
            decide_application(application_id, DecisionInput.model_validate(job.payload["decision"]), user, db, commit=False)
            point.commit()
            approved = job.payload["decision"]["status"] == "Approved"
            result["succeeded"] = result.get("succeeded", 0) + 1
        except (HTTPException, IntegrityError) as exc:
            point.rollback()
            failure = {"id": application_id, "message": str(getattr(exc, "detail", "The account changed concurrently"))[:300]}
            result["failed_count"] = result.get("failed_count", 0) + 1
            # Keep the job response small; full failures have their own paged records.
            if len(result.get("failed", [])) < 50:
                result["failed"] = [*result.get("failed", []), failure]
            db.add(WorkforceJobFailure(job_id=job_id, record_id=application_id, message=failure["message"]))
        except Exception:
            point.rollback()
            job = db.get(WorkforceJob, job_id)
            job.status = "Failed"; job.error = "Processing failed; review server logs and retry this chunk"; db.commit()
            import logging
            logging.getLogger(__name__).exception("workforce_onboarding_failed job=%s application=%s", job_id, application_id)
            return job
        job = db.get(WorkforceJob, job_id)
        job.result = result
        job.cursor += 1
        job.attempts += 1
        job.error = None
        job.status = "Completed" if job.cursor >= len(job.recipients) else "Pending"
        # The approval and cursor advance commit together, so retries cannot duplicate onboarding.
        db.commit()
        if approved:
            from .approval_email import notify_approval
            notify_approval(db, db.get(InternApplication, application_id))
    return db.get(WorkforceJob, job_id)
