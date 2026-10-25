from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.deps import RequirePermission, get_db
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveType
from app.models.payroll import PayrollRecord, PayrollRun
from app.models.user import User
from app.models.whatsapp_ess import (
    WhatsAppESSConfig, WhatsAppESSMessage, WhatsAppESSSession,
    WhatsAppESSTemplate, WhatsAppESSOptIn, WhatsAppESSDeliveryEvent,
)
from app.schemas.whatsapp_ess import (
    WhatsAppESSConfigCreate,
    WhatsAppESSConfigSchema,
    WhatsAppESSMessageSchema,
    WhatsAppInboundMessage,
    WhatsAppTemplateCreate,
    WhatsAppTemplateSchema,
    WhatsAppOptInCreate,
    WhatsAppOptInSchema,
    WhatsAppOutboundMessage,
    WhatsAppDeliveryCallback,
)

router = APIRouter(prefix="/whatsapp-ess", tags=["WhatsApp ESS"])


def _intent_for(text: str) -> str:
    lowered = text.lower()
    if "payslip" in lowered or "salary" in lowered:
        return "payslip"
    if "leave" in lowered or "balance" in lowered:
        return "leave_balance"
    if "attendance" in lowered or "punch" in lowered:
        return "attendance"
    return "help"


def _response_for(db: Session, employee: Employee, intent: str) -> str:
    if intent == "payslip":
        record = (
            db.query(PayrollRecord)
            .join(PayrollRun, PayrollRun.id == PayrollRecord.payroll_run_id)
            .filter(PayrollRecord.employee_id == employee.id)
            .order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
            .first()
        )
        if record:
            return f"Latest payslip net salary is {record.net_salary}. Use ESS portal to download the PDF."
        return "No payslip is available yet for your profile."
    if intent == "leave_balance":
        balances = (
            db.query(LeaveBalance, LeaveType)
            .join(LeaveType, LeaveType.id == LeaveBalance.leave_type_id)
            .filter(LeaveBalance.employee_id == employee.id)
            .all()
        )
        if not balances:
            return "No leave balance is configured yet. Please contact HR."
        parts = [
            f"{leave_type.code}: {(balance.allocated or 0) + (balance.carried_forward or 0) - (balance.used or 0) - (balance.pending or 0)}"
            for balance, leave_type in balances
        ]
        return "Leave balance - " + ", ".join(parts)
    if intent == "attendance":
        return "Attendance request received. Mobile punch/attendance summary can be enabled from ESS policy."
    return "You can ask for payslip, leave balance, or attendance."


def _active_session(db: Session, employee: Employee, phone_number: str, country_code: str) -> WhatsAppESSSession:
    session = db.query(WhatsAppESSSession).filter(
        WhatsAppESSSession.employee_id == employee.id,
        WhatsAppESSSession.phone_number == phone_number,
        WhatsAppESSSession.phone_number_country_code == country_code,
        WhatsAppESSSession.status == "Active",
    ).first()
    if not session:
        session = WhatsAppESSSession(employee_id=employee.id, phone_number=phone_number, phone_number_country_code=country_code)
        db.add(session)
        db.flush()
    return session


@router.post("/configs", response_model=WhatsAppESSConfigSchema, status_code=201)
def create_config(
    data: WhatsAppESSConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("notification_manage")),
):
    config = WhatsAppESSConfig(**data.model_dump(), created_by=current_user.id)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.get("/configs", response_model=List[WhatsAppESSConfigSchema])
def list_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("notification_manage")),
):
    return db.query(WhatsAppESSConfig).order_by(WhatsAppESSConfig.id.desc()).all()


@router.post("/templates", response_model=WhatsAppTemplateSchema, status_code=201)
def create_template(
    data: WhatsAppTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("notification_manage")),
):
    if not db.query(WhatsAppESSConfig).filter(WhatsAppESSConfig.id == data.config_id).first():
        raise HTTPException(status_code=404, detail="WhatsApp config not found")
    template = WhatsAppESSTemplate(**data.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/templates", response_model=List[WhatsAppTemplateSchema])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("notification_view")),
):
    return db.query(WhatsAppESSTemplate).order_by(WhatsAppESSTemplate.id.desc()).all()


@router.post("/opt-ins", response_model=WhatsAppOptInSchema, status_code=201)
def upsert_opt_in(
    data: WhatsAppOptInCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("notification_manage")),
):
    opt_in = db.query(WhatsAppESSOptIn).filter(
        WhatsAppESSOptIn.employee_id == data.employee_id,
        WhatsAppESSOptIn.phone_number == data.phone_number,
        WhatsAppESSOptIn.phone_number_country_code == data.phone_number_country_code,
    ).first()
    if not opt_in:
        opt_in = WhatsAppESSOptIn(employee_id=data.employee_id, phone_number=data.phone_number,phone_number_country_code=data.phone_number_country_code)
        db.add(opt_in)
    opt_in.status = data.status
    opt_in.source = data.source
    opt_in.consent_text = data.consent_text
    db.commit()
    db.refresh(opt_in)
    return opt_in


@router.post("/messages/outbound", response_model=WhatsAppESSMessageSchema, status_code=201)
def send_outbound_message(
    data: WhatsAppOutboundMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("notification_manage")),
):
    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    opt_in = db.query(WhatsAppESSOptIn).filter(
        WhatsAppESSOptIn.employee_id == employee.id,
        WhatsAppESSOptIn.phone_number == data.phone_number,
        WhatsAppESSOptIn.phone_number_country_code == data.phone_number_country_code,
        WhatsAppESSOptIn.status == "Opted In",
    ).first()
    if not opt_in:
        raise HTTPException(status_code=400, detail="Employee has not opted in for WhatsApp ESS")
    template = db.query(WhatsAppESSTemplate).filter(WhatsAppESSTemplate.id == data.template_id).first() if data.template_id else None
    message_text = data.message_text or (template.body_text if template else None)
    if not message_text:
        raise HTTPException(status_code=400, detail="message_text or template_id is required")
    session = _active_session(db, employee, data.phone_number,data.phone_number_country_code)
    message = WhatsAppESSMessage(
        session_id=session.id,
        employee_id=employee.id,
        direction="Outbound",
        phone_number=data.phone_number,
        phone_number_country_code=data.phone_number_country_code,
        message_text=message_text,
        intent=data.intent,
        status="Queued",
        provider_message_id=f"queued-{int(datetime.now(timezone.utc).timestamp())}-{employee.id}",
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.post("/delivery-callbacks", status_code=201)
def receive_delivery_callback(
    data: WhatsAppDeliveryCallback,
    x_hub_signature_256: str | None = Header(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("notification_manage")),
):
    message = db.query(WhatsAppESSMessage).filter(WhatsAppESSMessage.provider_message_id == data.provider_message_id).first()
    if message:
        message.status = data.status
    event = WhatsAppESSDeliveryEvent(
        message_id=message.id if message else None,
        provider_message_id=data.provider_message_id,
        status=data.status,
        raw_payload=data.raw_payload or x_hub_signature_256,
    )
    db.add(event)
    db.commit()
    return {"message": "Callback recorded", "linked": bool(message)}


@router.post("/messages/inbound", response_model=WhatsAppESSMessageSchema, status_code=201)
def receive_inbound_message(
    data: WhatsAppInboundMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("notification_manage")),
):
    employee = db.query(Employee).filter(Employee.phone_number == data.phone_number,Employee.phone_number_country_code == data.phone_number_country_code).first()
    if not employee:
        raise HTTPException(status_code=404, detail="No employee mapped to this WhatsApp phone number")
    session = _active_session(db, employee, data.phone_number,data.phone_number_country_code)
    intent = _intent_for(data.message_text)
    response_text = _response_for(db, employee, intent)
    session.last_intent = intent
    session.last_message_at = datetime.now(timezone.utc)
    message = WhatsAppESSMessage(
        session_id=session.id,
        employee_id=employee.id,
        direction="Inbound",
        phone_number=data.phone_number,
        phone_number_country_code=data.phone_number_country_code,
        message_text=data.message_text,
        intent=intent,
        status="Responded",
        provider_message_id=data.provider_message_id,
        response_text=response_text,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/messages", response_model=List[WhatsAppESSMessageSchema])
def list_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("notification_view")),
):
    return db.query(WhatsAppESSMessage).order_by(WhatsAppESSMessage.id.desc()).limit(200).all()
