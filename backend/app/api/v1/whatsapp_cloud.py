"""Deployment-scoped Meta webhook and authenticated connection status."""
import hashlib
import hmac
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_db, RequirePermission
from app.apps.crm.models import CRMMessage

router = APIRouter(prefix="/integrations/whatsapp", tags=["WhatsApp Cloud"])


@router.get("/status")
def connection_status(user=Depends(RequirePermission("crm_manage", "crm_admin"))):
    return {
        "provider": settings.CRM_WHATSAPP_PROVIDER,
        "configured": bool(settings.CRM_WHATSAPP_ACCESS_TOKEN and settings.CRM_WHATSAPP_PHONE_NUMBER_ID and settings.CRM_WHATSAPP_ORGANIZATION_ID),
        "webhookConfigured": bool(settings.CRM_WHATSAPP_VERIFY_TOKEN and settings.CRM_WHATSAPP_APP_SECRET and settings.CRM_WHATSAPP_ORGANIZATION_ID),
        "webhookPath": "/api/v1/integrations/whatsapp/webhook",
    }


@router.get("/webhook", response_class=PlainTextResponse)
def verify(request: Request):
    query = request.query_params
    expected = settings.CRM_WHATSAPP_VERIFY_TOKEN
    if not expected:
        raise HTTPException(503, "WhatsApp webhook verification is not configured")
    if query.get("hub.mode") != "subscribe" or not hmac.compare_digest(query.get("hub.verify_token", "").encode(), expected.encode()):
        raise HTTPException(403, "Invalid webhook verification")
    challenge = query.get("hub.challenge")
    if not challenge:
        raise HTTPException(400, "Missing challenge")
    return challenge


def apply_statuses(db, payload):
    rank = {"accepted": 0, "sent": 1, "delivered": 2, "read": 3}
    updated = 0
    if payload.get("object") != "whatsapp_business_account":
        return updated
    for entry in payload.get("entry", []):
        if str(entry.get("id")) != settings.CRM_WHATSAPP_BUSINESS_ACCOUNT_ID:
            continue
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if str(value.get("metadata", {}).get("phone_number_id")) != settings.CRM_WHATSAPP_PHONE_NUMBER_ID:
                continue
            for event in value.get("statuses", []):
                state = event.get("status")
                if state not in {*rank, "failed"} or not event.get("id"):
                    continue
                rows = db.query(CRMMessage).filter(
                    CRMMessage.organization_id == settings.CRM_WHATSAPP_ORGANIZATION_ID,
                    CRMMessage.channel == "whatsapp", CRMMessage.provider == "meta",
                    CRMMessage.provider_message_id == event["id"], CRMMessage.deleted_at.is_(None),
                ).with_for_update().all()
                for row in rows:
                    if state == "failed":
                        if row.status in {"accepted", "sent"}:
                            row.status = "failed"
                            row.failure_reason = "Meta reported delivery failure"
                    elif rank[state] > rank.get(row.status, -1):
                        row.status = state
                        row.failure_reason = None
                    updated += 1
    return updated


@router.post("/webhook")
async def receive(request: Request, db: Session = Depends(get_db)):
    if not settings.CRM_WHATSAPP_APP_SECRET or not settings.CRM_WHATSAPP_ORGANIZATION_ID or not settings.CRM_WHATSAPP_BUSINESS_ACCOUNT_ID or not settings.CRM_WHATSAPP_PHONE_NUMBER_ID:
        raise HTTPException(503, "WhatsApp webhook is not configured")
    body = await request.body()
    expected = "sha256=" + hmac.new(settings.CRM_WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected.encode(), request.headers.get("x-hub-signature-256", "").encode()):
        raise HTTPException(403, "Invalid webhook signature")
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError()
        apply_statuses(db, payload)
    except (ValueError, TypeError, AttributeError):
        db.rollback()
        raise HTTPException(400, "Invalid webhook payload") from None
    db.commit()
    return {"status": "received"}
