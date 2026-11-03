"""Signed adapter contract for email receiving services and mailbox bridges."""
import hashlib
import hmac
import time
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session
from app.core.deps import get_db
from app.shared.integrations import reveal
from app.models.email_outbox import EmailOutbox
from .customer_models import CustomerEmailConnection, CustomerEmailReply, CustomerDelivery, CustomerRecipient

router = APIRouter(prefix='/integrations/customer-email', tags=['Inbound customer email'])


class ReplyInput(BaseModel):
    event_id: str = Field(min_length=1, max_length=180)
    in_reply_to: str = Field(min_length=1, max_length=200)
    from_email: str = Field(min_length=3, max_length=254)
    to_email: str = Field(min_length=3, max_length=254)
    subject: str = Field(default='', max_length=240)
    body: str = Field(min_length=1, max_length=50000)
    authenticated_sender: bool = False


@router.post('/{organization_id}')
async def receive(organization_id: int, request: Request, db: Session = Depends(get_db)):
    connection = db.query(CustomerEmailConnection).filter_by(organization_id=organization_id, active=True).first()
    if not connection or not connection.inbound_secret_ciphertext:
        raise HTTPException(404, 'Email reply receiver is unavailable')
    timestamp = request.headers.get('X-BusinessSuite-Timestamp', '')
    if not timestamp.isascii() or not timestamp.isdigit() or len(timestamp) > 12 or abs(time.time()-int(timestamp)) > 300:
        raise HTTPException(401, 'Invalid or expired receiver signature')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 128000:
            raise HTTPException(413, 'Email reply is too large')
    expected = hmac.new(reveal(connection.inbound_secret_ciphertext).encode(), timestamp.encode()+b'.'+bytes(raw), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get('X-BusinessSuite-Signature', ''), 'sha256='+expected):
        raise HTTPException(401, 'Invalid or expired receiver signature')
    from app.core.request_limits import consume
    if consume(db, [(f'customer-email:{organization_id}', 120, 60)]):
        db.commit()
        raise HTTPException(429, 'Email receiver rate limit reached')
    try:
        data = ReplyInput.model_validate_json(bytes(raw))
    except ValidationError:
        raise HTTPException(422, 'Invalid email reply payload') from None
    if not data.authenticated_sender:
        raise HTTPException(422, 'Receiving adapter must verify sender authentication before ingestion')
    if data.to_email.casefold() not in {connection.from_email.casefold(), (connection.reply_to or '').casefold()}:
        raise HTTPException(422, 'Reply does not belong to this business mailbox')
    outbox = db.query(EmailOutbox).filter_by(organization_id=organization_id, provider_message_id=data.in_reply_to, module='customer_communication').first()
    delivery = db.query(CustomerDelivery).filter_by(organization_id=organization_id, email_outbox_id=outbox.id).first() if outbox else None
    recipient = db.query(CustomerRecipient).filter_by(id=delivery.recipient_id, organization_id=organization_id).first() if delivery else None
    if not recipient or recipient.email.casefold() != data.from_email.casefold():
        raise HTTPException(422, 'Reply could not be matched to an authorized customer conversation')
    from app.core.request_limits import insert_for
    from .customer_service import now
    identity = db.execute(insert_for(db, CustomerEmailReply).values(organization_id=organization_id,
        branch_id=delivery.branch_id, recipient_id=recipient.id, delivery_id=delivery.id,
        provider_event_id=data.event_id, subject=data.subject, body=data.body, received_at=now()).on_conflict_do_nothing(
            index_elements=['organization_id', 'provider_event_id']).returning(CustomerEmailReply.id)).scalar()
    if identity:
        # Verified adapter events inherit the exact conversation's branch.
        from app.branches.models import BranchOwnership
        db.add(BranchOwnership(resource_table=CustomerEmailReply.__tablename__, resource_key=str(identity),
            company_id=organization_id, branch_id=delivery.branch_id, source='verified-email-receiver'))
    db.commit()
    return {'accepted': True, 'duplicate': identity is None}
