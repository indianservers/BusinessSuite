"""Workspace overrides fail closed; inheritance is explicit and owner/tenant bound."""
from app.ai_operator.models import OperatorProvider
from app.ai_operator.service import scope_key
from app.apps.project_management.models import PMSWorkspaceMember
from app.apps.project_management.workspaces import workspace_member
from app.models.user import User


def resolve_provider(db, user, provider, workspace_id=None):
    scope = scope_key(db, user, workspace_id)
    direct = db.query(OperatorProvider).filter_by(scope_key=scope, provider=provider).first()
    # A disabled override explicitly blocks inheritance too.
    if direct or not workspace_id or provider != 'gemini':
        return direct
    workspace, _ = workspace_member(db, workspace_id, user)
    owners = db.query(User).join(PMSWorkspaceMember, PMSWorkspaceMember.user_id == User.id).filter(
        PMSWorkspaceMember.workspace_id == workspace_id, PMSWorkspaceMember.role == 'Owner', User.is_active.is_(True)).all()
    sources = set()
    if workspace.organization_id is not None:
        sources.add(f'company:{workspace.organization_id}')
    for owner in owners:
        owner_scope = scope_key(db, owner)
        if workspace.organization_id is None or owner_scope == f'company:{workspace.organization_id}':
            sources.add(owner_scope)
    rows = db.query(OperatorProvider).filter(OperatorProvider.scope_key.in_(sources), OperatorProvider.provider == 'gemini',
        OperatorProvider.allow_workspace_inheritance.is_(True)).all() if sources else []
    # Ambiguous private workspace sponsorship must be resolved by a workspace override.
    return rows[0] if len(rows) == 1 else None


def provider_for_scope(db, user, provider, scope):
    workspace_id = int(scope.split(':')[1]) if scope.startswith('workspace:') else None
    return resolve_provider(db, user, provider, workspace_id)
