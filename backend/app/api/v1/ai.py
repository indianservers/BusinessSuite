from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user, RequirePermission
from app.models.user import User
from app.services.ai import hr_assistant, resume_parser, attrition_predictor, payroll_anomaly

router = APIRouter(prefix="/ai", tags=["AI Services"])


# ── HR Assistant ──────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    history: Optional[List[dict]] = None


@router.post("/assistant")
async def chat_with_assistant(
    data: ChatMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("ai_assistant")),
):
    response = await hr_assistant.get_hr_response(data.message, data.history, db=db, current_user=current_user)
    return {"response": response, "model": "claude", "grounded": True}


# ── Policy Q&A ────────────────────────────────────────────────────────────────

class PolicyQuestion(BaseModel):
    question: str


@router.post("/policy-qa")
async def policy_qa(
    data: PolicyQuestion,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("ai_assistant")),
):
    from app.models.document import CompanyPolicy
    policies = db.query(CompanyPolicy).filter(CompanyPolicy.is_published == True).limit(10).all()
    policy_docs = [{"title": p.title, "content": p.content or ""} for p in policies]

    response = await hr_assistant.answer_policy_question(data.question, policy_docs)
    return {"response": response}


# ── Resume Parsing ────────────────────────────────────────────────────────────

@router.post("/parse-resume/{candidate_id}")
async def parse_resume(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("recruitment_manage")),
):
    from app.models.recruitment import Candidate
    from app.core.config import settings
    import os

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not candidate.resume_url:
        raise HTTPException(status_code=400, detail="No resume uploaded for this candidate")

    # Get file path from URL
    from app.core.storage import materialize_file
    from app.core.config import settings
    file_path = os.path.join(settings.UPLOAD_DIR, candidate.resume_url.removeprefix("/uploads/"))
    materialize_file(file_path)

    text = await resume_parser.extract_text_from_file(file_path)
    if not text:
        raise HTTPException(status_code=400, detail="Could not extract text from resume")

    parsed_data = await resume_parser.parse_resume(text)

    # Store parsed data
    import json
    candidate.resume_parsed_data = json.dumps(parsed_data)
    candidate.ai_summary = parsed_data.get("summary", "")

    # Score against job if available
    if candidate.job and candidate.job.description:
        skills = []
        if candidate.job.skills_required:
            try:
                skills = json.loads(candidate.job.skills_required)
            except Exception:
                skills = [s.strip() for s in candidate.job.skills_required.split(",")]

        score_data = await resume_parser.score_resume_for_job(
            parsed_data,
            candidate.job.description,
            skills,
        )
        candidate.ai_score = score_data.get("score", 0)

    db.commit()
    return {"parsed_data": parsed_data, "ai_score": candidate.ai_score}


# ── Attrition Prediction ──────────────────────────────────────────────────────

@router.get("/attrition-risk")
async def attrition_risk(
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    results = await attrition_predictor.bulk_attrition_analysis(db, department_id)
    high_risk = [r for r in results if r["risk_level"] == "High"]
    medium_risk = [r for r in results if r["risk_level"] == "Medium"]

    return {
        "summary": {
            "total_analyzed": len(results),
            "high_risk": len(high_risk),
            "medium_risk": len(medium_risk),
            "low_risk": len(results) - len(high_risk) - len(medium_risk),
        },
        "employees": results[:50],  # Top 50 by risk score
    }


@router.get("/attrition-risk/{employee_id}")
async def employee_attrition_risk(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    from datetime import date
    from app.models.employee import Employee

    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    tenure_years = 0
    if emp.date_of_joining:
        delta = date.today() - emp.date_of_joining
        tenure_years = delta.days / 365.25

    features = {
        "employee_id": employee_id,
        "tenure_years": round(tenure_years, 1),
        "leave_days_used_last_quarter": 5,
        "last_performance_rating": 3.5,
        "salary_market_percentile": 50,
        "attendance_rate": 0.9,
        "open_helpdesk_tickets": 0,
    }
    return attrition_predictor.predict_attrition_risk(features)


# ── Payroll Anomaly Detection ─────────────────────────────────────────────────

@router.post("/payroll-anomaly/{payroll_run_id}")
async def detect_payroll_anomalies(
    payroll_run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_approve")),
):
    return await payroll_anomaly.run_anomaly_detection(db, payroll_run_id)


# ── Helpdesk AI Reply ─────────────────────────────────────────────────────────

@router.post("/helpdesk-reply/{ticket_id}")
async def generate_helpdesk_reply(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    from app.models.helpdesk import HelpdeskTicket
    ticket = db.query(HelpdeskTicket).filter(HelpdeskTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    suggested_reply = await hr_assistant.suggest_helpdesk_reply(ticket.subject, ticket.description)

    # Save the suggestion
    ticket.ai_suggested_reply = suggested_reply
    db.commit()

    return {"suggested_reply": suggested_reply}
