from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.employee import Employee
from app.models.notification import Notification
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.notification import NotificationCreate, NotificationSchema
from app.services.notifications import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def create_notification(db: Session, data: NotificationCreate) -> Notification:
    return NotificationService.create_notification(db, data)


@router.get("/", response_model=PaginatedResponse[NotificationSchema])
def list_notifications(
    unread_only: bool = Query(False),
    module: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Notification)
        .options(joinedload(Notification.delivery_logs))
        .filter(Notification.user_id == current_user.id)
    )
    current_company_id = current_user.employee.branch.company_id if current_user.employee and current_user.employee.branch else None
    if current_company_id:
        query = query.filter(or_(Notification.company_id == current_company_id, Notification.company_id.is_(None)))
    if unread_only:
        query = query.filter(Notification.is_read == False)
    if module:
        query = query.filter(Notification.module == module)

    total = query.count()
    items = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    import math

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    )
    current_company_id = current_user.employee.branch.company_id if current_user.employee and current_user.employee.branch else None
    if current_company_id:
        query = query.filter(or_(Notification.company_id == current_company_id, Notification.company_id.is_(None)))
    count = query.scalar()
    return {"unread": count or 0}


@router.post("/", response_model=NotificationSchema, status_code=status.HTTP_201_CREATED)
def create_manual_notification(
    data: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("notification_manage")),
):
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return create_notification(db, data)


@router.put("/{notification_id}/read", response_model=NotificationSchema)
@router.patch("/{notification_id}/read", response_model=NotificationSchema)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = (
        db.query(Notification)
        .options(joinedload(Notification.delivery_logs))
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification


@router.put("/mark-all-read")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    )
    current_company_id = current_user.employee.branch.company_id if current_user.employee and current_user.employee.branch else None
    if current_company_id:
        query = query.filter(or_(Notification.company_id == current_company_id, Notification.company_id.is_(None)))
    query.update({"is_read": True, "read_at": datetime.now(timezone.utc)}, synchronize_session=False)
    db.commit()
    return {"message": "Notifications marked as read"}


@router.post("/people-moments/run")
def run_people_moment_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("notification_manage")),
):
    today = datetime.now(timezone.utc).date()
    users = db.query(User).filter(User.is_active == True).all()
    employees = db.query(Employee).filter(Employee.status == "Active").all()
    moments = []
    for employee in employees:
        if employee.date_of_birth and employee.date_of_birth.month == today.month and employee.date_of_birth.day == today.day:
            moments.append(("birthday", employee))
        if employee.date_of_joining and employee.date_of_joining.month == today.month and employee.date_of_joining.day == today.day:
            moments.append(("anniversary", employee))
    created = 0
    for moment_type, employee in moments:
        title = "Birthday today" if moment_type == "birthday" else "Work anniversary today"
        message = f"{employee.first_name} {employee.last_name} has a {moment_type} today."
        for user in users:
            exists = db.query(Notification).filter(
                Notification.user_id == user.id,
                Notification.event_type == f"people_moment_{moment_type}",
                Notification.related_entity_type == "employee",
                Notification.related_entity_id == employee.id,
                func.date(Notification.created_at) == today,
            ).first()
            if not exists:
                create_notification(db, NotificationCreate(
                    user_id=user.id,
                    title=title,
                    message=message,
                    module="engagement",
                    event_type=f"people_moment_{moment_type}",
                    related_entity_type="employee",
                    related_entity_id=employee.id,
                    action_url="/dashboard",
                    priority="normal",
                    channels=["in_app"],
                ))
                created += 1
    return {"moments": len(moments), "notifications_created": created}
