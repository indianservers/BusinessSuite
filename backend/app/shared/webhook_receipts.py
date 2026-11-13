"""Server-owned admission receipts for the existing signed record webhook receiver."""
import hashlib
import hmac
from app.core.config import settings
from app.db.tenant import current_tenant
from app.shared.gateway import digest

FIELD='signed_webhook_receipt'


def binding(endpoint):
    tenant=current_tenant.get()
    return {'endpoint_id':endpoint.id,'tenant_uuid':tenant.tenant_uuid if tenant else None,
        'configuration_sha256':digest({'organization_id':endpoint.organization_id,'target_url':endpoint.target_url,
            'subscription':endpoint.event_types_json,'credential_sha256':hashlib.sha256((endpoint.secret_ref or '').encode()).hexdigest()})}


def body(endpoint,event):
    return {'format':'signed-record-webhook-v1',**binding(endpoint),'event_id':event.id,
        'organization_id':event.organization_id,'module':event.module_key,'event':event.event_type,
        'entity':event.entity_type,'entity_id':event.entity_id,'actor_id':event.actor_id,
        'request_key':event.request_key,'data_sha256':digest((event.payload_json or {}).get('data'))}


def signature(value):
    return hmac.new(settings.SECRET_KEY.encode(),b'signed-record-webhook-v1:'+digest(value).encode(),hashlib.sha256).hexdigest()


def admit(endpoint,event):
    value=body(endpoint,event)
    event.payload_json={**event.payload_json,FIELD:{**value,'signature':signature(value)}}


def verified(endpoint,event):
    value=body(endpoint,event);stored=(event.payload_json or {}).get(FIELD)
    if not isinstance(stored,dict) or set(stored)!=set(value)|{'signature'}:return False
    return all(stored.get(k)==v for k,v in value.items()) and hmac.compare_digest(str(stored.get('signature','')),signature(value))
