"""Quoted replies use the existing canonical WhatsApp messages and payload JSON."""
from fastapi import HTTPException
from app.shared.whatsapp_models import WhatsAppMessage


def snapshot(row):
    return {'id':row.id,'providerMessageId':row.provider_message_id,'body':row.body[:500],'direction':row.direction}


def metadata(row):
    payload=row.template_json
    return payload.get('replyTo') if row.kind!='template' and isinstance(payload,dict) else None


def target(db,contact,connection,ident):
    row=db.query(WhatsAppMessage).filter_by(id=ident,organization_id=contact.organization_id,contact_id=contact.id,connection_id=connection.id).first()
    if not row or not row.provider_message_id or row.status in {'failed','submitting','reserved','reconciliation_required'}:
        raise HTTPException(422,'Choose a recorded message with a confirmed provider ID in this conversation')
    return snapshot(row)


def inbound(db,contact,connection,event):
    context=event.get('context')
    reference=context.get('id') if isinstance(context,dict) else None
    if not isinstance(reference,str) or not reference or len(reference)>200:return None
    row=db.query(WhatsAppMessage).filter_by(organization_id=contact.organization_id,contact_id=contact.id,connection_id=connection.id,provider_message_id=reference).first()
    return snapshot(row) if row else {'providerMessageId':reference,'body':'Original message unavailable'}
