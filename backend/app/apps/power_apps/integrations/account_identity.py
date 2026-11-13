"""Allowlisted account facts from native provider verification, never credentials."""
import hashlib
import json
import re
from app.apps.power_apps.integrations.transport import scrub

AUDIT_ACTION = 'provider_account_verified'


def binding(conn, credential):
    value = {'connection': conn.id, 'revision': conn.revision, 'provider': conn.connector_id,
             'provider_version': conn.connector_version, 'organization': conn.organization_id,
             'environment': conn.environment, 'owner': conn.owner_user_id,
             'config': conn.config, 'scopes': conn.scopes, 'enabled': conn.enabled,
             'writes_enabled': conn.writes_enabled, 'vault_reference': credential.id,
             'vault_version': credential.version}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def text(value):
    if type(value) is int and value > 0:
        value = str(value)
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        return None
    value = value.strip()
    if any(ord(c) < 32 or ord(c) == 127 for c in value) or '[REDACTED]' in value or value.lower().startswith('bearer '):
        return None
    return value


def extract(provider, output):
    if not isinstance(output, dict):
        return None
    if output.get('http_status') == 200 and isinstance(output.get('data'), dict):
        output = output['data']  # Native provider adapter envelope.
    # Only documented verification results enter this allowlist. Resource tests
    # (e.g. a spreadsheet title) must not masquerade as an account identity.
    selected = {}
    if provider == 'gmail':
        selected = {'email': output.get('emailAddress')}
    elif provider == 'outlook':
        selected = {'id': output.get('id'), 'label': output.get('displayName')}
    elif provider == 'github':
        selected = {'id': output.get('id') or output.get('login'), 'label': output.get('login')}
    elif provider == 'slack' and output.get('ok') is True:
        selected = {'id': output.get('user_id'), 'label': output.get('user'),
                    'workspace': output.get('team'), 'workspace_id': output.get('team_id')}
    elif provider == 'dropbox':
        name = output.get('name') if isinstance(output.get('name'), dict) else {}
        selected = {'id': output.get('account_id'), 'label': name.get('display_name'), 'email': output.get('email')}
    elif provider == 'box':
        selected = {'id': output.get('id'), 'label': output.get('name'), 'email': output.get('login')}
    elif provider == 'jira':
        selected = {'id': output.get('accountId'), 'label': output.get('displayName'), 'email': output.get('emailAddress')}
    selected = {k: clean for k, v in selected.items() if (clean := text(v)) is not None}
    if 'email' in selected and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', selected['email']):
        selected.pop('email')
    return selected if selected.get('id') or selected.get('email') else None


def capture(db, user, conn, credential, operation, output, dispatched_binding):
    if operation.action_id != 'test' or operation.status != 'succeeded' or credential.revoked_at:
        return
    if binding(conn, credential) != dispatched_binding:
        return  # Settings or credentials changed while the provider was responding.
    identity = extract(conn.connector_id, output)
    if not identity:
        return
    from app.apps.power_apps.integrations.vault import audit
    audit(db, conn, user, AUDIT_ACTION, {'binding': dispatched_binding,
          'identity': scrub(identity), 'operation_id': operation.id,
          'verified_at': operation.finished_at.isoformat()})
