from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.apps.communication.models import (
    CommunicationAutoResponseRule,
    CommunicationCampaign,
    CommunicationCampaignMember,
    CommunicationCampaignSend,
    CommunicationConsent,
    CommunicationDeliveryLog,
    CommunicationEmailMessage,
    CommunicationEmailTemplate,
    CommunicationOptOut,
    CommunicationTimelineEvent,
    CommunicationWebform,
    CommunicationWebformSubmission,
    CommunicationWhatsAppTemplate,
)
from app.apps.communication.schemas import (
    AutoResponseRulePayload,
    CampaignPayload,
    CampaignSchedulePayload,
    ConsentPayload,
    EmailDraftPayload,
    EmailSendPayload,
    EmailTemplatePayload,
    OptOutPayload,
    WebformPayload,
    WebformSubmitPayload,
    WhatsAppTemplatePayload,
)
from app.apps.communication.services.delivery import (
    MAX_CAMPAIGN_SENDS_PER_REQUEST,
    deliver_email,
    is_opted_out,
    merge_template,
    normalize_email,
    validate_email,
)
from app.apps.crm.models import CRMContact, CRMLead
from app.core.deps import RequirePermission, get_db
from app.models.user import User


router = APIRouter(tags=["Communication Hub"])
communication_router = APIRouter(prefix="/communication", tags=["Communication Hub"])
public_router = APIRouter(prefix="/public/webforms", tags=["Public Webforms"])


def _serialize(item) -> dict[str, Any] | None:
    if item is None:
        return None
    data: dict[str, Any] = {}
    for column in item.__table__.columns:
        value = getattr(item, column.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.name] = value
    return data


def _list_payload(items: list[Any]) -> dict[str, Any]:
    return {"items": [_serialize(item) for item in items], "total": len(items)}


def _timeline(db: Session, record_type: str, record_id: int, channel: str, event_type: str, subject: str, summary: str, actor_user_id: int | None = None, metadata: dict[str, Any] | None = None) -> None:
    db.add(
        CommunicationTimelineEvent(
            record_type=record_type,
            record_id=record_id,
            channel=channel,
            event_type=event_type,
            subject=subject,
            summary=summary,
            metadata_json=metadata,
            actor_user_id=actor_user_id,
        )
    )


def _log_whatsapp_placeholder(db: Session, record_type: str, record_id: int, phone: str, body: str, template: CommunicationWhatsAppTemplate | None = None) -> None:
    db.add(
        CommunicationDeliveryLog(
            channel="whatsapp",
            related_message_id=None,
            provider="placeholder",
            status="queued",
            request_json={
                "to_phone": phone,
                "related_record_type": record_type,
                "related_record_id": record_id,
                "template_id": template.id if template else None,
                "template_key": template.template_key if template else None,
                "body": body,
            },
            response_json={"placeholder_only": True, "next_action": "Configure a WhatsApp provider adapter to send this queued response."},
        )
    )
    _timeline(
        db,
        record_type,
        record_id,
        "whatsapp",
        "queued",
        template.name if template else "Webform WhatsApp auto-response",
        f"WhatsApp auto-response queued for {phone}",
        None,
        {"template_id": template.id if template else None, "placeholder_only": True},
    )


def _require_template(db: Session, template_id: int | None) -> CommunicationEmailTemplate | None:
    if not template_id:
        return None
    template = db.query(CommunicationEmailTemplate).filter(CommunicationEmailTemplate.id == template_id, CommunicationEmailTemplate.active == True).first()
    if not template:
        raise HTTPException(status_code=404, detail="Email template not found or inactive")
    return template


def _create_email_message(db: Session, data: EmailDraftPayload | EmailSendPayload, current_user: User, status: str = "draft") -> CommunicationEmailMessage:
    to_email = normalize_email(str(data.to_email))
    validate_email(to_email)
    message = CommunicationEmailMessage(
        related_record_type=data.related_record_type,
        related_record_id=data.related_record_id,
        to_email=to_email,
        cc=data.cc,
        bcc=data.bcc,
        subject=data.subject,
        body=data.body,
        status=status,
        sent_by=current_user.id,
    )
    db.add(message)
    db.flush()
    _timeline(db, data.related_record_type, data.related_record_id, "email", status, data.subject, f"Email {status} for {to_email}", current_user.id, {"message_id": message.id})
    return message


def _recipient_records(db: Session, segment: dict[str, Any] | None) -> list[dict[str, Any]]:
    segment = segment or {}
    source = str(segment.get("source") or segment.get("module") or "lead").lower()
    limit = min(int(segment.get("limit") or MAX_CAMPAIGN_SENDS_PER_REQUEST), MAX_CAMPAIGN_SENDS_PER_REQUEST)
    status = segment.get("status")

    rows: list[Any]
    if source == "contact":
        query = db.query(CRMContact).filter(CRMContact.email.isnot(None), CRMContact.deleted_at.is_(None))
        if status:
            query = query.filter(CRMContact.status == status)
        rows = query.order_by(CRMContact.id.desc()).limit(limit).all()
        return [{"record_type": "contact", "record_id": item.id, "email": item.email, "name": item.full_name} for item in rows if item.email]

    query = db.query(CRMLead).filter(CRMLead.email.isnot(None), CRMLead.deleted_at.is_(None))
    if status:
        query = query.filter(CRMLead.status == status)
    rows = query.order_by(CRMLead.id.desc()).limit(limit).all()
    return [{"record_type": "lead", "record_id": item.id, "email": item.email, "name": item.full_name} for item in rows if item.email]


@communication_router.get("/module-info")
def module_info(current_user: User = Depends(RequirePermission("communication_view", "communication_email_send"))):
    return {
        "module": "communication",
        "title": "Communication Hub",
        "permissions": [
            "communication_view",
            "communication_email_send",
            "communication_templates_manage",
            "communication_webforms_manage",
            "communication_campaigns_view",
            "communication_campaigns_manage",
            "communication_campaigns_send",
            "communication_consents_manage",
            "communication_logs_view",
        ],
    }


@communication_router.get("/email-templates")
def list_email_templates(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_view", "communication_templates_manage"))):
    return _list_payload(db.query(CommunicationEmailTemplate).order_by(CommunicationEmailTemplate.created_at.desc()).all())


@communication_router.post("/email-templates", status_code=201)
def create_email_template(data: EmailTemplatePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_templates_manage"))):
    item = CommunicationEmailTemplate(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.flush()
    _timeline(db, "template", item.id, "email", "created", item.subject, f"Template {item.name} created", current_user.id)
    db.commit()
    return _serialize(item)


@communication_router.get("/email-templates/{template_id}")
def get_email_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_view", "communication_templates_manage"))):
    item = db.query(CommunicationEmailTemplate).filter(CommunicationEmailTemplate.id == template_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Email template not found")
    return _serialize(item)


@communication_router.put("/email-templates/{template_id}")
def update_email_template(template_id: int, data: EmailTemplatePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_templates_manage"))):
    item = db.query(CommunicationEmailTemplate).filter(CommunicationEmailTemplate.id == template_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Email template not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    _timeline(db, "template", item.id, "email", "updated", item.subject, f"Template {item.name} updated", current_user.id)
    db.commit()
    return _serialize(item)


@communication_router.delete("/email-templates/{template_id}", status_code=204)
def delete_email_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_templates_manage"))):
    item = db.query(CommunicationEmailTemplate).filter(CommunicationEmailTemplate.id == template_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Email template not found")
    item.active = False
    _timeline(db, "template", item.id, "email", "disabled", item.subject, f"Template {item.name} disabled", current_user.id)
    db.commit()
    return None


@communication_router.post("/emails/draft", status_code=201)
def create_email_draft(data: EmailDraftPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_email_send"))):
    message = _create_email_message(db, data, current_user, "draft")
    db.commit()
    return _serialize(message)


@communication_router.post("/emails/send", status_code=201)
def send_email(data: EmailSendPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_email_send"))):
    template = _require_template(db, data.template_id)
    payload = data.model_copy()
    if template:
        merge_data = data.merge_data or {}
        payload.subject = merge_template(template.subject, merge_data)
        payload.body = merge_template(template.body_html or template.body_text or "", merge_data)
    message = _create_email_message(db, payload, current_user, "queued")
    deliver_email(db, message, current_user)
    db.commit()
    return _serialize(message)


@communication_router.get("/emails/{message_id}")
def get_email(message_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_view", "communication_email_send"))):
    item = db.query(CommunicationEmailMessage).filter(CommunicationEmailMessage.id == message_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Email message not found")
    return _serialize(item)


@communication_router.get("/timeline/{record_type}/{record_id}")
def get_timeline(record_type: str, record_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_view", "communication_email_send"))):
    items = db.query(CommunicationTimelineEvent).filter(CommunicationTimelineEvent.record_type == record_type, CommunicationTimelineEvent.record_id == record_id).order_by(CommunicationTimelineEvent.created_at.desc()).all()
    return _list_payload(items)


@communication_router.get("/webforms")
def list_webforms(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_view", "communication_webforms_manage"))):
    return _list_payload(db.query(CommunicationWebform).order_by(CommunicationWebform.created_at.desc()).all())


@communication_router.post("/webforms", status_code=201)
def create_webform(data: WebformPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_webforms_manage"))):
    if db.query(CommunicationWebform).filter(CommunicationWebform.public_slug == data.public_slug).first():
        raise HTTPException(status_code=400, detail="Public slug already exists")
    item = CommunicationWebform(**data.model_dump())
    db.add(item)
    db.flush()
    _timeline(db, "webform", item.id, "webform", "created", item.name, "Webform created", current_user.id)
    db.commit()
    return _serialize(item)


@communication_router.get("/webforms/{webform_id}")
def get_webform(webform_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_view", "communication_webforms_manage"))):
    item = db.query(CommunicationWebform).filter(CommunicationWebform.id == webform_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Webform not found")
    return _serialize(item)


@communication_router.put("/webforms/{webform_id}")
def update_webform(webform_id: int, data: WebformPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_webforms_manage"))):
    item = db.query(CommunicationWebform).filter(CommunicationWebform.id == webform_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Webform not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    _timeline(db, "webform", item.id, "webform", "updated", item.name, "Webform updated", current_user.id)
    db.commit()
    return _serialize(item)


@communication_router.delete("/webforms/{webform_id}", status_code=204)
def delete_webform(webform_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_webforms_manage"))):
    item = db.query(CommunicationWebform).filter(CommunicationWebform.id == webform_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Webform not found")
    item.active = False
    db.commit()
    return None


@public_router.get("/{slug}")
def public_webform(slug: str, db: Session = Depends(get_db)):
    item = db.query(CommunicationWebform).filter(CommunicationWebform.public_slug == slug, CommunicationWebform.active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Webform not found")
    return _serialize(item)


@public_router.post("/{slug}/submit", status_code=201)
def submit_public_webform(slug: str, data: WebformSubmitPayload, request: Request, db: Session = Depends(get_db)):
    if data.anti_spam:
        raise HTTPException(status_code=400, detail="Spam check failed")
    webform = db.query(CommunicationWebform).filter(CommunicationWebform.public_slug == slug, CommunicationWebform.active == True).first()
    if not webform:
        raise HTTPException(status_code=404, detail="Webform not found")
    values = data.values
    mapping = webform.mapping_json or {}
    email = normalize_email(str(values.get(mapping.get("email", "email"), "") or ""))
    phone = str(values.get(mapping.get("phone", "phone"), "") or "")
    first_name = str(values.get(mapping.get("first_name", "first_name"), "") or values.get("name", "Website")).strip() or "Website"
    last_name = str(values.get(mapping.get("last_name", "last_name"), "") or "Lead").strip()
    duplicate = bool(email and db.query(CRMLead).filter(CRMLead.email == email, CRMLead.deleted_at.is_(None)).first())
    created_type = None
    created_id = None
    if webform.target_module == "contact":
        contact = CRMContact(first_name=first_name, last_name=last_name, full_name=f"{first_name} {last_name}".strip(), email=email or None, phone=phone or None, source="Webform", created_by_user_id=None)
        db.add(contact)
        db.flush()
        created_type = "contact"
        created_id = contact.id
    else:
        lead = CRMLead(first_name=first_name, last_name=last_name, full_name=f"{first_name} {last_name}".strip(), email=email or None, phone=phone or None, source="Webform", status="New", created_by_user_id=None)
        db.add(lead)
        db.flush()
        created_type = "lead"
        created_id = lead.id
    submission = CommunicationWebformSubmission(webform_id=webform.id, payload_json=values, created_record_type=created_type, created_record_id=created_id, duplicate_detected=duplicate, ip_address=request.client.host if request.client else None)
    db.add(submission)
    _timeline(db, created_type, created_id, "webform", "submitted", webform.name, "Webform submission created CRM record", None, {"webform_id": webform.id, "duplicate_detected": duplicate})
    auto_responses: list[dict[str, Any]] = []
    if webform.auto_response_rule_id:
        rule = db.query(CommunicationAutoResponseRule).filter(CommunicationAutoResponseRule.id == webform.auto_response_rule_id, CommunicationAutoResponseRule.active == True).first()
        template = _require_template(db, rule.template_id if rule and rule.template_id else None)
        if template and email:
            message = CommunicationEmailMessage(related_record_type=created_type, related_record_id=created_id, to_email=email, subject=merge_template(template.subject, values), body=merge_template(template.body_html or template.body_text or "", values), status="queued")
            db.add(message)
            db.flush()
            deliver_email(db, message, None)
            auto_responses.append({"channel": "email", "status": message.status, "message_id": message.id})
        whatsapp_template_id = (rule.condition_json or {}).get("whatsapp_template_id") if rule else None
        if whatsapp_template_id and phone:
            whatsapp_template = db.query(CommunicationWhatsAppTemplate).filter(CommunicationWhatsAppTemplate.id == int(whatsapp_template_id), CommunicationWhatsAppTemplate.active == True).first()
            if whatsapp_template:
                _log_whatsapp_placeholder(db, created_type, created_id, phone, merge_template(whatsapp_template.body_text, values), whatsapp_template)
                auto_responses.append({"channel": "whatsapp", "status": "queued", "template_id": whatsapp_template.id})
    db.commit()
    return {"status": "accepted", "created_record_type": created_type, "created_record_id": created_id, "duplicate_detected": duplicate, "auto_responses": auto_responses}


@communication_router.get("/auto-response-rules")
def list_auto_rules(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_view", "communication_webforms_manage"))):
    return _list_payload(db.query(CommunicationAutoResponseRule).order_by(CommunicationAutoResponseRule.created_at.desc()).all())


@communication_router.post("/auto-response-rules", status_code=201)
def create_auto_rule(data: AutoResponseRulePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_webforms_manage"))):
    item = CommunicationAutoResponseRule(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.commit()
    return _serialize(item)


@communication_router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_campaigns_view", "communication_campaigns_manage"))):
    return _list_payload(db.query(CommunicationCampaign).order_by(CommunicationCampaign.created_at.desc()).all())


@communication_router.post("/campaigns", status_code=201)
def create_campaign(data: CampaignPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_campaigns_manage"))):
    _require_template(db, data.template_id)
    item = CommunicationCampaign(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.commit()
    return _serialize(item)


@communication_router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_campaigns_view", "communication_campaigns_manage"))):
    item = db.query(CommunicationCampaign).filter(CommunicationCampaign.id == campaign_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Campaign not found")
    data = _serialize(item) or {}
    data["members"] = [_serialize(member) for member in db.query(CommunicationCampaignMember).filter(CommunicationCampaignMember.campaign_id == item.id).all()]
    return data


@communication_router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, data: CampaignPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_campaigns_manage"))):
    item = db.query(CommunicationCampaign).filter(CommunicationCampaign.id == campaign_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return _serialize(item)


@communication_router.post("/campaigns/{campaign_id}/preview")
def preview_campaign(campaign_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_campaigns_view", "communication_campaigns_manage"))):
    campaign = db.query(CommunicationCampaign).filter(CommunicationCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    recipients = _recipient_records(db, campaign.segment_json)
    for recipient in recipients:
        recipient["blocked"] = is_opted_out(db, recipient["email"])
    return {"recipients": recipients, "total": len(recipients), "blocked_count": len([item for item in recipients if item["blocked"]]), "rate_limit": MAX_CAMPAIGN_SENDS_PER_REQUEST}


@communication_router.post("/campaigns/{campaign_id}/send")
def send_campaign(campaign_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_campaigns_send"))):
    campaign = db.query(CommunicationCampaign).filter(CommunicationCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    template = _require_template(db, campaign.template_id)
    if not template:
        raise HTTPException(status_code=400, detail="Campaign requires an active email template")
    campaign.status = "running"
    sent = failed = blocked = 0
    for recipient in _recipient_records(db, campaign.segment_json):
        member = CommunicationCampaignMember(campaign_id=campaign.id, record_type=recipient["record_type"], record_id=recipient["record_id"], email=normalize_email(recipient["email"]))
        db.add(member)
        db.flush()
        message = CommunicationEmailMessage(related_record_type=recipient["record_type"], related_record_id=recipient["record_id"], to_email=member.email, subject=merge_template(template.subject, recipient), body=merge_template(template.body_html or template.body_text or "", recipient), status="queued", sent_by=current_user.id)
        db.add(message)
        db.flush()
        deliver_email(db, message, current_user)
        member.status = message.status
        db.add(CommunicationCampaignSend(campaign_id=campaign.id, member_id=member.id, email_message_id=message.id, status=message.status, error_message=message.error_message))
        if message.status == "sent":
            sent += 1
        elif message.status == "blocked":
            blocked += 1
        else:
            failed += 1
    campaign.sent_count = sent
    campaign.failed_count = failed
    campaign.blocked_count = blocked
    campaign.status = "completed"
    db.commit()
    return _serialize(campaign)


@communication_router.post("/campaigns/{campaign_id}/schedule")
def schedule_campaign(campaign_id: int, data: CampaignSchedulePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_campaigns_manage"))):
    campaign = db.query(CommunicationCampaign).filter(CommunicationCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "scheduled"
    campaign.scheduled_at = data.scheduled_at
    db.commit()
    return _serialize(campaign)


@communication_router.post("/campaigns/{campaign_id}/cancel")
def cancel_campaign(campaign_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_campaigns_manage"))):
    campaign = db.query(CommunicationCampaign).filter(CommunicationCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "cancelled"
    db.commit()
    return _serialize(campaign)


@communication_router.get("/consents")
def list_consents(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_view", "communication_consents_manage"))):
    return _list_payload(db.query(CommunicationConsent).order_by(CommunicationConsent.updated_at.desc()).all())


@communication_router.post("/consents", status_code=201)
def create_consent(data: ConsentPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_consents_manage"))):
    item = CommunicationConsent(**data.model_dump())
    if item.email:
        item.email = normalize_email(item.email)
    db.add(item)
    db.commit()
    return _serialize(item)


@communication_router.post("/opt-out", status_code=201)
def opt_out(data: OptOutPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_consents_manage"))):
    email = normalize_email(str(data.email))
    existing = db.query(CommunicationOptOut).filter(CommunicationOptOut.email == email, CommunicationOptOut.channel == data.channel).first()
    if existing:
        return _serialize(existing)
    item = CommunicationOptOut(email=email, channel=data.channel, reason=data.reason, source=data.source)
    db.add(item)
    db.add(CommunicationConsent(email=email, consent_type=data.channel, status="opted_out", source=data.source))
    db.commit()
    return _serialize(item)


@communication_router.get("/whatsapp-templates")
def list_whatsapp_templates(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_view", "communication_templates_manage"))):
    return _list_payload(db.query(CommunicationWhatsAppTemplate).order_by(CommunicationWhatsAppTemplate.created_at.desc()).all())


@communication_router.post("/whatsapp-templates", status_code=201)
def create_whatsapp_template(data: WhatsAppTemplatePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_templates_manage"))):
    item = CommunicationWhatsAppTemplate(**data.model_dump(), created_by=current_user.id, provider_status="placeholder_only")
    db.add(item)
    db.commit()
    return _serialize(item)


@communication_router.get("/delivery-logs")
def list_delivery_logs(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("communication_logs_view", "communication_view"))):
    return _list_payload(db.query(CommunicationDeliveryLog).order_by(CommunicationDeliveryLog.created_at.desc()).limit(250).all())


router.include_router(communication_router)
router.include_router(public_router)
