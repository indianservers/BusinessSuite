from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.employee import Employee
from app.models.engagement import Announcement, AnnouncementAcknowledgement, EngagementSurvey, EngagementSurveyResponse, Recognition, RecognitionReaction
from app.models.user import User
from app.schemas.engagement import (
    AnnouncementAcknowledgementSchema, AnnouncementCreate, AnnouncementSchema, EngagementSurveyCreate, EngagementSurveyResponseCreate,
    EngagementSurveyResponseSchema, EngagementSurveySchema, RecognitionCreate, RecognitionReactionCreate, RecognitionSchema,
)

router = APIRouter(prefix="/engagement", tags=["Engagement"])


@router.post("/announcements", response_model=AnnouncementSchema, status_code=201)
def create_announcement(data: AnnouncementCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("notification_manage"))):
    item = Announcement(**data.model_dump(), created_by=current_user.id)
    if data.is_published:
        item.published_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/announcements", response_model=list[AnnouncementSchema])
def list_announcements(published_only: bool = Query(True), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Announcement)
    if published_only:
        query = query.filter(Announcement.is_published == True)
    now = datetime.now(timezone.utc)
    query = query.filter((Announcement.expires_at.is_(None)) | (Announcement.expires_at >= now))
    if current_user.employee:
        employee = current_user.employee
        query = query.filter(
            (Announcement.audience.in_(["All", "all"])) |
            (Announcement.target_department_id.is_(None)) |
            (Announcement.target_department_id == employee.department_id)
        ).filter(
            (Announcement.target_location_id.is_(None)) |
            (Announcement.target_location_id == employee.location_id)
        )
    return query.order_by(Announcement.created_at.desc()).limit(100).all()


@router.post("/announcements/{announcement_id}/acknowledge", response_model=AnnouncementAcknowledgementSchema, status_code=201)
def acknowledge_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="Employee profile is required")
    announcement = db.get(Announcement, announcement_id)
    if not announcement or not announcement.is_published:
        raise HTTPException(status_code=404, detail="Announcement not found")
    existing = db.query(AnnouncementAcknowledgement).filter(
        AnnouncementAcknowledgement.announcement_id == announcement_id,
        AnnouncementAcknowledgement.employee_id == current_user.employee.id,
    ).first()
    if existing:
        return existing
    acknowledgement = AnnouncementAcknowledgement(announcement_id=announcement_id, employee_id=current_user.employee.id)
    db.add(acknowledgement)
    db.commit()
    db.refresh(acknowledgement)
    return acknowledgement


@router.post("/surveys", response_model=EngagementSurveySchema, status_code=201)
def create_survey(data: EngagementSurveyCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_manage"))):
    survey = EngagementSurvey(**data.model_dump(), created_by=current_user.id)
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return survey


@router.get("/surveys", response_model=list[EngagementSurveySchema])
def list_surveys(active_only: bool = Query(False), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(EngagementSurvey)
    if active_only:
        query = query.filter(EngagementSurvey.status.in_(["Active", "Published", "Open"]))
    return query.order_by(EngagementSurvey.created_at.desc()).limit(100).all()


@router.get("/surveys/{survey_id}/results")
def survey_results(survey_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    survey = db.get(EngagementSurvey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    rows = (
        db.query(EngagementSurveyResponse.comments, func.count(EngagementSurveyResponse.id))
        .filter(EngagementSurveyResponse.survey_id == survey_id)
        .group_by(EngagementSurveyResponse.comments)
        .all()
    )
    total = sum(row[1] for row in rows)
    return {
        "survey_id": survey_id,
        "title": survey.title,
        "question": survey.question or survey.title,
        "total_responses": total,
        "results": [
            {"option": row[0] or "No comment", "count": row[1], "percent": round((row[1] / total) * 100, 2) if total else 0}
            for row in rows
        ],
    }


@router.post("/survey-responses", response_model=EngagementSurveyResponseSchema, status_code=201)
def submit_survey_response(data: EngagementSurveyResponseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee_id = data.employee_id or (current_user.employee.id if current_user.employee else None)
    if not employee_id:
        raise HTTPException(status_code=400, detail="No employee profile")
    response = EngagementSurveyResponse(**data.model_dump(exclude={"employee_id"}), employee_id=employee_id)
    db.add(response)
    db.commit()
    db.refresh(response)
    return response


@router.post("/recognitions", response_model=RecognitionSchema, status_code=201)
def create_recognition(data: RecognitionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from_employee_id = current_user.employee.id if current_user.employee else None
    recognition = Recognition(**data.model_dump(), from_employee_id=from_employee_id)
    db.add(recognition)
    db.commit()
    db.refresh(recognition)
    return recognition


@router.get("/recognitions", response_model=list[RecognitionSchema])
def list_recognitions(employee_id: int | None = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Recognition).filter(Recognition.is_public == True)
    if employee_id:
        query = query.filter(Recognition.to_employee_id == employee_id)
    return query.order_by(Recognition.created_at.desc()).limit(100).all()


@router.get("/recognition-wall")
def recognition_wall(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    recognitions = db.query(Recognition).filter(Recognition.is_public == True).order_by(Recognition.created_at.desc()).limit(100).all()
    employee_ids = list({rid for row in recognitions for rid in [row.from_employee_id, row.to_employee_id] if rid})
    employees = {
        item.id: f"{item.first_name} {item.last_name}"
        for item in db.query(Employee).filter(Employee.id.in_(employee_ids or [0]), Employee.deleted_at.is_(None)).all()
    }
    reaction_rows = (
        db.query(RecognitionReaction.recognition_id, RecognitionReaction.emoji, func.count(RecognitionReaction.id))
        .filter(RecognitionReaction.recognition_id.in_([row.id for row in recognitions] or [0]))
        .group_by(RecognitionReaction.recognition_id, RecognitionReaction.emoji)
        .all()
    )
    reactions: dict[int, dict[str, int]] = {}
    for recognition_id, emoji, count in reaction_rows:
        reactions.setdefault(recognition_id, {})[emoji] = count
    return [
        {
            "id": row.id,
            "title": row.title,
            "message": row.message,
            "badge": row.badge,
            "points": row.points,
            "from_employee_id": row.from_employee_id,
            "from_employee_name": employees.get(row.from_employee_id, "HR"),
            "to_employee_id": row.to_employee_id,
            "to_employee_name": employees.get(row.to_employee_id, "Employee"),
            "created_at": row.created_at,
            "reactions": reactions.get(row.id, {}),
        }
        for row in recognitions
    ]


@router.post("/recognitions/{recognition_id}/reactions", status_code=201)
def react_to_recognition(
    recognition_id: int,
    data: RecognitionReactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    recognition = db.get(Recognition, recognition_id)
    if not recognition:
        raise HTTPException(status_code=404, detail="Recognition not found")
    reaction = db.query(RecognitionReaction).filter(
        RecognitionReaction.recognition_id == recognition_id,
        RecognitionReaction.employee_id == current_user.employee.id,
        RecognitionReaction.emoji == data.emoji,
    ).first()
    if not reaction:
        reaction = RecognitionReaction(recognition_id=recognition_id, employee_id=current_user.employee.id, emoji=data.emoji)
        db.add(reaction)
        db.commit()
        db.refresh(reaction)
    return {"id": reaction.id, "recognition_id": recognition_id, "emoji": reaction.emoji}
