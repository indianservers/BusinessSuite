"""Read-only connection readiness over the native vault and bounded journals."""
from fastapi import HTTPException
from sqlalchemy import func
from app.core.deps import RequirePermission
from app.apps.power_apps.integrations.models import Connection, Credential, Operation, ConnectionAudit
from app.apps.power_apps.integrations import account_identity, service, vault
from app.apps.power_apps.integrations.registry import REGISTRY


def permitted(user, permission):
    try:
        RequirePermission(permission)(user)
        return True
    except HTTPException as error:
        if error.status_code != 403:
            raise
        return False


def history(db, ids, company, environment, owner):
    """Three bounded window queries instead of a query per connection."""
    result = {ident: {'last_successful_operation_at': None, 'last_successful_read_at': None,
                      'recent_errors': []} for ident in ids}
    if not ids:
        return result
    base = [Operation.connection_id.in_(ids), Operation.organization_id == company,
            Operation.environment == environment, Operation.owner_user_id == owner]
    for field, extra in [('last_successful_operation_at', []),
                         ('last_successful_read_at', [Operation.mutates.is_(False), Operation.action_id != 'test'])]:
        ranked = db.query(Operation.connection_id.label('connection_id'), Operation.finished_at.label('at'),
            func.row_number().over(partition_by=Operation.connection_id, order_by=Operation.id.desc()).label('rank'))\
            .filter(*base, Operation.status == 'succeeded', *extra).subquery()
        for row in db.query(ranked).filter(ranked.c.rank == 1):
            result[row.connection_id][field] = row.at
    ranked = db.query(Operation.connection_id.label('connection_id'), Operation.id.label('id'),
        Operation.action_id.label('action_id'), Operation.status.label('status'),
        Operation.error_category.label('category'), Operation.finished_at.label('at'),
        func.row_number().over(partition_by=Operation.connection_id, order_by=Operation.id.desc()).label('rank'))\
        .filter(*base, Operation.error_category.is_not(None)).subquery()
    for row in db.query(ranked).filter(ranked.c.rank <= 5).order_by(ranked.c.connection_id, ranked.c.rank):
        result[row.connection_id]['recent_errors'].append({k: getattr(row, k) for k in ('id', 'action_id', 'status', 'category', 'at')})
    return result


def account(conn, credential, audit, live):
    if not credential or credential.revoked_at or not conn.enabled or not live:
        return {'status': 'verification_required'}
    if not audit:
        return {'status': 'not_reported'}
    details = audit.details if isinstance(audit.details, dict) else {}
    stored_identity = details.get('identity') if isinstance(details.get('identity'),dict) else {}
    if details.get('binding') != account_identity.binding(conn, credential):
        return {'status': 'verification_required'}
    # Re-allowlist persisted metadata too. Never forward arbitrary audit fields.
    identity = {k: clean for k, v in stored_identity.items()
                if k in {'id', 'label', 'email', 'workspace', 'workspace_id'}
                and (clean := account_identity.text(v)) is not None}
    if not (identity.get('id') or identity.get('email')):
        return {'status': 'not_reported'}
    return {'status': 'verified', 'identity': identity, 'verified_at': details.get('verified_at'),
            'operation_id': details.get('operation_id')}


def actions(conn, credential, live, can_execute):
    from app.ai_operator.agent_connectors import permitted as agent_permitted
    manifest = REGISTRY.get(conn.connector_id)
    if not manifest:
        return []
    granted = service.effective_scopes(conn)
    values = []
    for action in manifest.actions:
        missing = sorted(set(action.scopes) - granted)
        try:
            agent_permitted(conn, action.id)
            supported = True
        except HTTPException as error:
            if error.status_code != 403:
                raise
            supported = False
        state = ('native_workflow_required' if not supported else
                 'permission_required' if not can_execute else
                 'connection_disabled' if not conn.enabled else
                 'authorization_unavailable' if not credential or credential.revoked_at else
                 'authorization_expired' if conn.expires_at and vault.utc(conn.expires_at) <= vault.now() else
                 'missing_scopes' if missing else
                 'writes_disabled' if action.mutates and not conn.writes_enabled else
                 'verification_required' if not live else
                 'ready_for_review' if action.mutates else 'ready_to_read')
        values.append({'id': action.id, 'name': action.name, 'mutates': action.mutates,
                       'scopes': action.scopes, 'missing_scopes': missing, 'status': state,
                       'requires_agent_binding': True, 'requires_approval': action.mutates})
    return values


def enrich(db, user, rows, company, environment):
    if not rows:
        return []
    ids = [row['id'] for row in rows]
    pairs = db.query(Connection, Credential).outerjoin(Credential, Credential.id == Connection.credential_id)\
        .filter(Connection.id.in_(ids), Connection.organization_id == company,
                Connection.environment == environment, Connection.owner_user_id == user.id).all()
    by_id = {conn.id: (conn, credential if credential and credential.environment == environment
                      and vault.allowed(credential, user) else None) for conn, credential in pairs}
    audit_base = db.query(ConnectionAudit.id.label('id'),
        func.row_number().over(partition_by=ConnectionAudit.connection_id,
                               order_by=ConnectionAudit.id.desc()).label('rank'))\
        .filter(ConnectionAudit.connection_id.in_(ids), ConnectionAudit.organization_id == company,
                ConnectionAudit.environment == environment, ConnectionAudit.owner_user_id == user.id,
                ConnectionAudit.action == account_identity.AUDIT_ACTION).subquery()
    audits = {row.connection_id: row for row in db.query(ConnectionAudit).join(audit_base, audit_base.c.id == ConnectionAudit.id)
              .filter(audit_base.c.rank == 1)}
    can_execute = permitted(user, 'power_apps_execute')
    can_history = permitted(user, 'power_apps_activity_view')
    journal = history(db, ids, company, environment, user.id) if can_history else {}
    safe = []
    for row in rows:
        if row['id'] not in by_id:
            continue
        conn, credential = by_id[row['id']]
        authorization = ('disabled' if not conn.enabled else
            'unavailable' if not credential or credential.revoked_at else
            'expired' if conn.expires_at and vault.utc(conn.expires_at) <= vault.now() else
            'verified' if row.get('live_verified') else 'unverified')
        live = authorization == 'verified'
        item = {k: row.get(k) for k in ('id', 'name', 'connector_id', 'enabled', 'health', 'live_verified',
                'writes_enabled', 'scopes', 'expires_at', 'last_verified_at', 'revision', 'expiry_status')}
        item['authorization_status'] = authorization
        item['live_verified'] = live
        item.update(journal.get(conn.id, {'last_successful_operation_at': None,
                    'last_successful_read_at': None, 'recent_errors': []}))
        item['history_visible'] = can_history
        item['account'] = account(conn, credential, audits.get(conn.id), live)
        item['actions'] = actions(conn, credential, live, can_execute)
        safe.append(item)
    return safe
