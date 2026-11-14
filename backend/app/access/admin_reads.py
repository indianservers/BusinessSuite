"""Company-wide, request-local administrative read authority.

Membership is resolved by bind_authorization on every request. This never
promotes a user to a platform administrator or changes mutation permissions.
"""
from types import SimpleNamespace
from app.access.catalog import catalog, MODULE_PERMISSIONS, permission_module


def allowed(user):
    return bool(getattr(user, '_suite_admin_read', False))


def definitions(db):
    from app.db.init_db import SYSTEM_PERMISSIONS
    modules = catalog(db)
    result = {m['key']:{p['name'] for p in m['permissions']} | set(MODULE_PERMISSIONS[m['key']]) for m in modules}
    for name, description, source in SYSTEM_PERMISSIONS:
        key = permission_module(SimpleNamespace(name=name, module=source))
        if key in result:
            result[key].add(name)
    return result


def grants(db, user, base=None):
    from app.access.entitlements import states
    disabled = {key for key, enabled in states(db, user.organization_id).items() if not enabled}
    names = definitions(db)
    result = {}
    roles = {'hrms':'hr_company_admin', 'crm':'crm_org_admin',
             'project_management':'pms_org_admin', 'srm':'srm_admin', 'fam':'fam_admin'}
    for module in catalog(db):
        key = module['key']
        previous = (base or {}).get(key, {})
        result[key] = {**previous, 'enabled':True, 'role':previous.get('role', 'super_admin') if user.is_superuser else roles.get(key, 'admin'),
            'permissions':sorted(names[key]),
            'actions':sorted((set(previous.get('actions', [])) if key not in disabled else set()) | {'view', 'export'}),
            'scope':'organization'}
    return result


def permission_objects(db):
    return [SimpleNamespace(name=name, module=key, description=name)
            for key, names in definitions(db).items() for name in names]


def company_clause(model, user):
    from sqlalchemy import func, or_, select
    from app.apps.srm.services.commercial import tenant
    company = tenant(user)
    if hasattr(model, 'organization_id'):
        return func.coalesce(model.organization_id, 1) == company
    if model.__tablename__ in {'ai_messages', 'pms_assistant_messages'}:
        from app.ai_agents.models import AiConversation
        from app.ai_operator.assistant_models import AssistantConversation
        parent = AiConversation if model.__tablename__ == 'ai_messages' else AssistantConversation
        return model.conversation_id.in_(select(parent.__table__.c.id).where(func.coalesce(parent.__table__.c.organization_id, 1) == company))
    if model.__tablename__ == 'ai_suite_runs':
        from app.apps.project_management.models import PMSWorkspace
        return or_(model.security_context['company_id'].as_integer() == company,
                   model.scope_key == f'company:{company}',
                   model.workspace_id.in_(select(PMSWorkspace.__table__.c.id).where(func.coalesce(PMSWorkspace.__table__.c.organization_id,1)==company)))
    raise ValueError('Administrative read requires a verified company anchor')


def owner_clause(model, user):
    return company_clause(model, user) if allowed(user) else model.user_id == user.id
