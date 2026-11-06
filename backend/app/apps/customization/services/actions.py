"""Custom buttons backed by existing CRM, Approval OS and connector services."""
import hashlib
import json
from urllib.parse import urlsplit

from fastapi import HTTPException

from app.apps.customization.models import CustomizationAuditLog
from app.apps.customization.services.records import Reader, record, module
from app.models.user import User
from app.core.deps import RequirePermission
from app.shared.runtime import mapped_payload


def execute(db, actor, button, data):
    if not data.record_id:
        raise HTTPException(422, 'Select a custom record before running this action')
    module(db, button.module_name, lock=True)
    row = record(db, button.module_name, data.record_id, lock=True)
    fingerprint = hashlib.sha256(json.dumps({'record': row.id, 'input': data.payload}, sort_keys=True).encode()).hexdigest()
    previous = db.query(CustomizationAuditLog).filter_by(entity_type='button', entity_id=button.id, actor_user_id=actor.id).filter(
        CustomizationAuditLog.after_json['request_key'].as_string() == data.request_key,
    ).order_by(CustomizationAuditLog.id.desc()).limit(1).all()
    for log in previous:
        saved = log.after_json or {}
        if saved.get('request_key') == data.request_key:
            if saved.get('fingerprint') != fingerprint:
                raise HTTPException(409, 'Request key was already used with different inputs')
            if saved.get('result'):
                return saved['result']
            raise HTTPException(409, 'Action outcome needs reconciliation; do not retry with another key')
    unresolved = db.query(CustomizationAuditLog).filter(
        CustomizationAuditLog.entity_type == 'button', CustomizationAuditLog.entity_id == button.id,
        CustomizationAuditLog.action.in_(['started', 'reconciliation_required']),
        CustomizationAuditLog.after_json['record_id'].as_integer() == row.id,
    ).first()
    if unresolved:
        raise HTTPException(409, 'An earlier action on this record needs reconciliation before another execution')
    config = mapped_payload(button.action_config_json or {}, {'id': row.id, 'values': Reader(db).values(row), 'input': data.payload or {}})
    result = {'status': 'executed', 'action_type': button.action_type, 'record_id': row.id}
    log = CustomizationAuditLog(entity_type='button', entity_id=button.id, action='started', actor_user_id=actor.id,
        after_json={'request_key': data.request_key, 'fingerprint': fingerprint, 'record_id': row.id})
    db.add(log)
    db.flush()
    if button.action_type == 'webhook':
        # Persist the execution intent before external IO. Ambiguous outcomes are
        # never silently retried, even if the client loses the HTTP response.
        RequirePermission('integration_manage', 'settings_manage')(actor)
        connection = config.get('connection_id')
        if type(connection) is not int or not config.get('operation'):
            raise HTTPException(422, 'Webhook requires a governed connection and registered operation')
        from app.shared.integrations import prepare_operation, invoke
        prepare_operation(db, actor, actor.organization_id, 'customization', connection, config['operation'], config.get('payload', {}))
        db.commit()
        try:
            outcome = invoke(db, actor, actor.organization_id, 'customization', connection, config['operation'], config.get('payload', {}))
        except Exception:
            log.action = 'reconciliation_required'
            db.commit()
            raise HTTPException(502, 'Connector outcome requires reconciliation; execution will not be repeated') from None
        result['result'] = outcome
    elif button.action_type == 'create_task':
        from app.apps.crm.api import router as crm
        from app.apps.crm.models import CRMTask
        crm._assert_entity_permission('tasks', actor, 'manage')
        from app.apps.business_os.services.module_service import assert_module_enabled
        assert_module_enabled(db, 'crm', company_id=actor.organization_id)
        resource = crm._get_resource('tasks')
        allowed = {'title', 'description', 'due_date', 'priority', 'owner_user_id'}
        if set(config) - allowed:
            raise HTTPException(422, 'Unsupported task configuration')
        values = crm._validate_and_build(resource, config, partial=False)
        values.update(organization_id=actor.organization_id, owner_user_id=values.get('owner_user_id') or actor.id)
        crm._assert_write_scope(resource, values, actor, db)
        crm._validate_required_custom_fields(db, 'tasks', None, actor.organization_id, {})
        task = CRMTask(**values, created_by_user_id=actor.id, updated_by_user_id=actor.id,
            task_details={'customModule': button.module_name, 'customRecordId': row.id})
        db.add(task)
        db.flush()
        crm._create_related_timeline_event(db, 'tasks', crm._serialize(task), actor.organization_id, actor.id)
        result['task_id'] = task.id
    elif button.action_type == 'submit_approval':
        RequirePermission('approval_os_create', 'approval_os_admin', 'company_manage')(actor)
        from app.models.approval_os import ApprovalRequest
        from app.api.v1.approval_os import _record_history
        assignee = config.get('assigned_to_user_id')
        if type(assignee) is not int or assignee == actor.id or not db.query(User).filter_by(id=assignee, is_active=True).first():
            raise HTTPException(422, 'Choose a different active approver in your company')
        title = config.get('title')
        if not isinstance(title, str) or not title.strip() or len(title) > 220:
            raise HTTPException(422, 'Approval requires a title of at most 220 characters')
        approval = ApprovalRequest(organization_id=actor.organization_id, source_module='customization',
            approval_type='custom_record', entity_type=button.module_name, entity_id=row.id,
            title=title, description=config.get('description'), requester_user_id=actor.id,
            assigned_to_user_id=assignee, status='Pending', context_json={'values': Reader(db).values(row)})
        db.add(approval)
        db.flush()
        _record_history(db, approval, 'created', actor.id, None, 'Pending')
        result['approval_id'] = approval.id
    elif button.action_type == 'timeline_event':
        title = config.get('title')
        if not isinstance(title, str) or not title.strip() or len(title) > 220:
            raise HTTPException(422, 'Timeline event requires a title of at most 220 characters')
        event = CustomizationAuditLog(entity_type='dynamic_record', entity_id=row.id, action='timeline_event',
            actor_user_id=actor.id, after_json={'module': button.module_name, 'title': title, 'description': config.get('description')})
        db.add(event)
        db.flush()
        result['event_id'] = event.id
    elif button.action_type == 'open_url':
        url = config.get('url', '')
        if not isinstance(url, str) or len(url) > 2048:
            raise HTTPException(422, 'Invalid action URL')
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in url):
            raise HTTPException(422, 'Action URL must be a complete HTTPS URL')
        result.update(status='ready', url=url)
    elif button.action_type == 'noop':
        result['status'] = 'skipped'
    else:
        raise HTTPException(422, 'Unsupported custom action')
    log.action = 'executed'
    log.after_json = {**log.after_json, 'result': result}
    db.flush()
    return result
