"""Request-local metadata shared with synchronous route handlers; never stores bodies."""
from contextvars import ContextVar

context = ContextVar('request_audit_context', default=None)


def set_audit_actor(user):
    value = context.get()
    if value is not None:
        value['actor'] = {'user_id': user.id, 'email': user.email, 'role': user.role.name if user.role else 'superuser' if user.is_superuser else 'unassigned', 'authenticated': True}
        if getattr(user, 'organization_id', None) is not None:
            value['actor'].update(access_policy_version=getattr(user, '_suite_policy_version', None), access_role_id=user.role_id, access_permissions=permission_fingerprint(user), access_module=getattr(user, '_suite_current_module', None), access_company=getattr(user, 'organization_id', None), access_session=getattr(user, '_suite_session_id', None))


def set_audit_entity(project_id=None, task_id=None, changed_fields=None):
    value = context.get()
    if value is None:
        return
    if project_id:
        value.setdefault('project_ids', set()).add(project_id)
    if task_id:
        value.setdefault('task_ids', set()).add(task_id)
    if changed_fields:
        value.setdefault('changed_fields', set()).update(str(field)[:80] for field in changed_fields)


def permission_fingerprint(user):
    import hashlib
    names = sorted(permission.name for permission in (user.role.permissions if user.role else []))
    return hashlib.sha256("\n".join(names).encode()).hexdigest()
