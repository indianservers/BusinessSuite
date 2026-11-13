"""Private provenance for complete JSON requests; never stores request bodies.

Canonical JSON fingerprints cover the provider payload, not HTTP wire bytes.
Authentication headers are deliberately excluded. Actor/tenant/scope binding and
a server-keyed MAC prevent cross-user matching and offline prompt guessing.
"""
import hashlib
import hmac
import json
from app.core.config import settings
from app.db.tenant import current_tenant

FORMAT = 'provider-request-v1'


def signing_key():
    return settings.SECRET_KEY.encode('utf-8')


def fingerprint(*, provider, model, purpose, scope_key, user_id, endpoint, body):
    tenant = current_tenant.get()
    value = {
        'format': FORMAT,
        'tenant_uuid': tenant.tenant_uuid if tenant else None,
        'actor_id': user_id,
        'scope_key': scope_key,
        'provider': provider,
        'model': model,
        'purpose': purpose,
        'endpoint': endpoint,
        'body': body,
    }
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    key = signing_key()
    tag = hmac.new(key, FORMAT.encode() + b':' + encoded, hashlib.sha256).hexdigest()
    # A domain-separated opaque epoch distinguishes key rotation without
    # publishing a hash of the signing secret or retaining retired secrets.
    epoch = hmac.new(key, b'provider-request-key-epoch-v1', hashlib.sha256).hexdigest()[:16]
    return {'format': FORMAT, 'algorithm': 'HMAC-SHA256', 'key_epoch': epoch,
            'canonicalization': 'sorted-json-utf8-v1', 'value': tag}
