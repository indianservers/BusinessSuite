"""Private server-side routing preferences and scoped, sanitized provider health."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.ai_agents.security import company, verify
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_operator.models import OperatorApiLog
from app.ai_operator.provider_scope import resolve_provider
from app.ai_operator.suite_tools import Strict

router = APIRouter(prefix='/suite/intelligence', tags=['AI intelligence'])
Provider = Literal['preferred', 'gemini', 'openai', 'claude', 'local']
Module = Literal['CRM', 'PMS', 'HRMS', 'SRM', 'FAM']


def preference_row(db, user, scope, module, workspace_id):
    row = db.query(AssistantConversation).filter_by(user_id=user.id, organization_id=company(user),
        workspace_id=workspace_id, deleted_at=None).filter(
        AssistantConversation.references['intelligence_preference'].as_boolean() == True,
        AssistantConversation.references['scope_key'].as_string() == scope,
        AssistantConversation.references['module'].as_string() == (module or 'CROSS')).order_by(AssistantConversation.id.desc()).first()
    if row:
        verify(db, user, row.security_context, history=True)
    return row


def select_default(db, user, scope, module, workspace_id):
    row = preference_row(db, user, scope, module, workspace_id)
    preferred = (row.references if row else {}).get('provider', 'preferred')
    choices = ['gemini', 'openai', 'claude', 'local'] if preferred == 'preferred' else [preferred]
    for name in choices:
        if name == 'local':
            if module != 'FAM':
                return 'local', None
            continue
        config = resolve_provider(db, user, name, workspace_id)
        if config and config.enabled and config.data_sharing_allowed and config.encrypted_key:
            return name, config
    raise HTTPException(409, 'Your selected intelligence is unavailable in this scope. Choose another provider in bot intelligence.')


def status(db, user, scope, module, workspace_id):
    row = preference_row(db, user, scope, module, workspace_id)
    items = []
    for name in ('gemini', 'openai', 'claude'):
        config = resolve_provider(db, user, name, workspace_id)
        if not config:
            continue
        logs = db.query(OperatorApiLog).filter_by(user_id=user.id, scope_key=scope, provider=name, model=config.model)
        def health(test):
            query = logs.filter(OperatorApiLog.purpose == 'test') if test else logs.filter(OperatorApiLog.purpose != 'test')
            last = query.order_by(OperatorApiLog.id.desc()).first()
            return {'status': last.status, 'error_code': last.error_code, 'http_status': last.http_status,
                    'at': last.created_at} if last else {'status': 'untested'}
        items.append({'provider': name, 'model': config.model, 'enabled': config.enabled,
            'data_sharing_allowed': config.data_sharing_allowed, 'has_key': bool(config.encrypted_key),
            'connectivity': health(True), 'planning': health(False)})
    try:
        selected, config = select_default(db, user, scope, module, workspace_id)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        selected, config = None, None
    return {'scope_key':scope,'preference': (row.references if row else {}).get('provider', 'preferred'),
            'selected_provider': selected, 'model': config.model if config else None, 'items': items}


@router.get('')
def get_intelligence(module: Module | None = None, workspace_id: int | None = None,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    scope = authorize(db, user, workspace_id, module)
    return status(db, user, scope, module, workspace_id)


class Preference(Strict):
    provider: Provider
    module: Module | None = None
    workspace_id: int | None = Field(default=None,gt=0)


@router.put('')
def put_intelligence(data: Preference, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    scope = authorize(db, user, data.workspace_id, data.module)
    if data.provider == 'local' and data.module == 'FAM':
        raise HTTPException(422, 'Finance requires a connected provider')
    row = preference_row(db, user, scope, data.module, data.workspace_id)
    if not row:
        row = AssistantConversation(user_id=user.id, organization_id=company(user), workspace_id=data.workspace_id,
                                    title='Bot intelligence preference')
        db.add(row)
    row.references = {'intelligence_preference': True, 'scope_key': scope,
                      'module': data.module or 'CROSS', 'provider': data.provider}
    db.commit()
    return status(db, user, scope, data.module, data.workspace_id)
