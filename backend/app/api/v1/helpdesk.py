from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user, RequirePermission
from app.models.user import User
from app.models.helpdesk import (
    HelpdeskCategory, HelpdeskTicket, HelpdeskReply,
    HelpdeskKnowledgeArticle, HelpdeskEscalationRule,
)
from app.schemas.helpdesk import (
    HelpdeskEscalationRuleCreate, HelpdeskEscalationRuleSchema,
    HelpdeskKnowledgeArticleCreate, HelpdeskKnowledgeArticleSchema,
    HelpdeskTicketAssign,
    HelpdeskTicketCreate,
    HelpdeskTicketEscalation,
    HelpdeskTicketStatusUpdate,
)

router = APIRouter(prefix="/helpdesk", tags=["HR Helpdesk"])


@router.get("/categories")
def list_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(HelpdeskCategory).filter(HelpdeskCategory.is_active == True).all()


@router.post("/categories", status_code=201)
def create_category(
    name: str,
    sla_hours: int = 24,
    assigned_team: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    cat = HelpdeskCategory(name=name, sla_hours=sla_hours, assigned_team=assigned_team)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def _create_ticket_record(
    subject: str,
    description: str,
    category_id: Optional[int],
    priority: str,
    db: Session,
    current_user: User,
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")

    ticket_number = f"TKT{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{current_user.employee.id:04d}"
    category = db.query(HelpdeskCategory).filter(HelpdeskCategory.id == category_id).first() if category_id else None
    sla_hours = category.sla_hours if category else 24
    now = datetime.now(timezone.utc)

    ticket = HelpdeskTicket(
        ticket_number=ticket_number,
        employee_id=current_user.employee.id,
        category_id=category_id,
        subject=subject,
        description=description,
        priority=priority,
        first_response_due_at=now + timedelta(hours=min(4, sla_hours)),
        resolution_due_at=now + timedelta(hours=sla_hours),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/tickets", status_code=201)
def create_ticket(
    subject: str,
    description: str,
    category_id: Optional[int] = None,
    priority: str = "Medium",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _create_ticket_record(subject, description, category_id, priority, db, current_user)


@router.post("/tickets/json", status_code=201)
def create_ticket_json(data: HelpdeskTicketCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _create_ticket_record(data.subject, data.description, data.category_id, data.priority, db, current_user)


@router.get("/tickets")
def list_tickets(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to_me: bool = Query(False),
    my_tickets: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(HelpdeskTicket)
    if my_tickets and current_user.employee:
        q = q.filter(HelpdeskTicket.employee_id == current_user.employee.id)
    if assigned_to_me:
        q = q.filter(HelpdeskTicket.assigned_to == current_user.id)
    if status:
        q = q.filter(HelpdeskTicket.status == status)
    if priority:
        q = q.filter(HelpdeskTicket.priority == priority)
    return q.order_by(HelpdeskTicket.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(HelpdeskTicket).filter(HelpdeskTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.put("/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    ticket = db.query(HelpdeskTicket).filter(HelpdeskTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.status = status
    if status in ["Resolved", "Closed"]:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if status == "Resolved":
            ticket.resolved_at = now
        else:
            ticket.closed_at = now
    db.commit()
    return {"message": f"Ticket {status}"}


@router.put("/tickets/{ticket_id}/status/json")
def update_ticket_status_json(
    ticket_id: int,
    data: HelpdeskTicketStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    return update_ticket_status(ticket_id, data.status, db, current_user)


@router.put("/tickets/{ticket_id}/assign")
def assign_ticket(
    ticket_id: int,
    assign_to_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    ticket = db.query(HelpdeskTicket).filter(HelpdeskTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.assigned_to = assign_to_user_id
    ticket.status = "In Progress"
    db.commit()
    return {"message": "Ticket assigned"}


@router.put("/tickets/{ticket_id}/assign/json")
def assign_ticket_json(
    ticket_id: int,
    data: HelpdeskTicketAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    return assign_ticket(ticket_id, data.assign_to_user_id, db, current_user)


@router.put("/tickets/{ticket_id}/escalate")
def escalate_ticket(
    ticket_id: int,
    data: HelpdeskTicketEscalation,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    ticket = db.query(HelpdeskTicket).filter(HelpdeskTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.escalated_at = datetime.now(timezone.utc)
    ticket.escalated_to = data.escalated_to
    ticket.escalation_reason = data.escalation_reason
    ticket.priority = "Critical" if ticket.priority != "Critical" else ticket.priority
    db.commit()
    return {"message": "Ticket escalated"}


@router.get("/sla/breaches")
def list_sla_breaches(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    now = datetime.now(timezone.utc)
    return db.query(HelpdeskTicket).filter(
        HelpdeskTicket.status.notin_(["Resolved", "Closed"]),
        HelpdeskTicket.resolution_due_at.isnot(None),
        HelpdeskTicket.resolution_due_at < now,
    ).order_by(HelpdeskTicket.resolution_due_at.asc()).limit(200).all()


@router.get("/analytics")
def helpdesk_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    now = datetime.now(timezone.utc)
    total = db.query(func.count(HelpdeskTicket.id)).scalar() or 0
    open_count = db.query(func.count(HelpdeskTicket.id)).filter(
        HelpdeskTicket.status.in_(["Open", "In Progress", "Pending"])
    ).scalar() or 0
    resolved_count = db.query(func.count(HelpdeskTicket.id)).filter(
        HelpdeskTicket.status.in_(["Resolved", "Closed"])
    ).scalar() or 0
    breached_count = db.query(func.count(HelpdeskTicket.id)).filter(
        HelpdeskTicket.status.notin_(["Resolved", "Closed"]),
        HelpdeskTicket.resolution_due_at.isnot(None),
        HelpdeskTicket.resolution_due_at < now,
    ).scalar() or 0
    due_soon_count = db.query(func.count(HelpdeskTicket.id)).filter(
        HelpdeskTicket.status.notin_(["Resolved", "Closed"]),
        HelpdeskTicket.resolution_due_at.isnot(None),
        HelpdeskTicket.resolution_due_at >= now,
        HelpdeskTicket.resolution_due_at <= now + timedelta(hours=8),
    ).scalar() or 0
    csat_row = db.query(
        func.avg(HelpdeskTicket.satisfaction_rating),
        func.count(HelpdeskTicket.satisfaction_rating),
    ).filter(HelpdeskTicket.satisfaction_rating.isnot(None)).first()
    priority_rows = db.query(
        HelpdeskTicket.priority,
        func.count(HelpdeskTicket.id),
    ).group_by(HelpdeskTicket.priority).all()
    status_rows = db.query(
        HelpdeskTicket.status,
        func.count(HelpdeskTicket.id),
    ).group_by(HelpdeskTicket.status).all()
    response_sla_breached = db.query(func.count(HelpdeskTicket.id)).filter(
        HelpdeskTicket.status.notin_(["Resolved", "Closed"]),
        HelpdeskTicket.first_response_due_at.isnot(None),
        HelpdeskTicket.first_response_due_at < now,
        ~HelpdeskTicket.replies.any(HelpdeskReply.is_internal == False),
    ).scalar() or 0
    return {
        "total": total,
        "open": open_count,
        "resolved": resolved_count,
        "sla_breached": breached_count,
        "due_soon": due_soon_count,
        "first_response_breached": response_sla_breached,
        "csat_average": round(float(csat_row[0] or 0), 2),
        "csat_responses": csat_row[1] or 0,
        "by_priority": {priority or "Unspecified": count for priority, count in priority_rows},
        "by_status": {status or "Unspecified": count for status, count in status_rows},
    }


@router.put("/tickets/{ticket_id}/csat")
def submit_csat(
    ticket_id: int,
    rating: int = Query(..., ge=1, le=5),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(HelpdeskTicket).filter(HelpdeskTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if not current_user.is_superuser and current_user.employee and ticket.employee_id != current_user.employee.id:
        raise HTTPException(status_code=403, detail="Only the requester can rate this ticket")
    if ticket.status not in ["Resolved", "Closed"]:
        raise HTTPException(status_code=400, detail="CSAT can be submitted after resolution")
    ticket.satisfaction_rating = rating
    db.commit()
    return {"message": "CSAT submitted", "rating": rating}


@router.get("/escalation-rules", response_model=list[HelpdeskEscalationRuleSchema])
def list_escalation_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    return db.query(HelpdeskEscalationRule).filter(HelpdeskEscalationRule.is_active == True).order_by(HelpdeskEscalationRule.priority).all()


@router.post("/escalation-rules", response_model=HelpdeskEscalationRuleSchema, status_code=201)
def create_escalation_rule(
    data: HelpdeskEscalationRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    rule = HelpdeskEscalationRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/knowledge", response_model=list[HelpdeskKnowledgeArticleSchema])
def list_knowledge_articles(
    category_id: Optional[int] = Query(None),
    published_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(HelpdeskKnowledgeArticle)
    if category_id:
        query = query.filter(HelpdeskKnowledgeArticle.category_id == category_id)
    if published_only:
        query = query.filter(HelpdeskKnowledgeArticle.is_published == True)
    return query.order_by(HelpdeskKnowledgeArticle.updated_at.desc().nullslast(), HelpdeskKnowledgeArticle.created_at.desc()).limit(200).all()


@router.post("/knowledge", response_model=HelpdeskKnowledgeArticleSchema, status_code=201)
def create_knowledge_article(
    data: HelpdeskKnowledgeArticleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("helpdesk_manage")),
):
    article = HelpdeskKnowledgeArticle(**data.model_dump(), created_by=current_user.id)
    if data.is_published:
        article.published_at = datetime.now(timezone.utc)
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


@router.post("/tickets/{ticket_id}/reply", status_code=201)
def add_reply(
    ticket_id: int,
    message: str,
    is_internal: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reply = HelpdeskReply(
        ticket_id=ticket_id,
        user_id=current_user.id,
        message=message,
        is_internal=is_internal,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply


@router.get("/tickets/{ticket_id}/replies")
def get_replies(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(HelpdeskReply).filter(
        HelpdeskReply.ticket_id == ticket_id,
        HelpdeskReply.is_internal == False,
    ).order_by(HelpdeskReply.created_at).all()
