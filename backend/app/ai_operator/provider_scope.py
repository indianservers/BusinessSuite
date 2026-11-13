"""Workspace overrides fail closed; inheritance is explicit and owner/tenant bound."""
from app.ai_operator.models import OperatorProvider
from app.ai_operator.service import scope_key
from app.apps.project_management.models import PMSWorkspaceMember
from app.apps.project_management.workspaces import workspace_member
from app.models.user import User
from sqlalchemy import select
from types import SimpleNamespace


def _configurations(db, scopes, provider, *, inherited=False):
    """Consume exact authorized control-plane scopes, never business-record scope.

    Returned snapshots are server-only; public endpoints use public_provider.
    Scope candidates must be established by scope_key/workspace_member above.
    Admin mutations continue through the existing guarded ORM endpoint.
    """
    if not scopes:return []
    db.flush()
    table=OperatorProvider.__table__
    query=select(table).where(table.c.scope_key.in_(scopes),table.c.provider==provider)
    if inherited:query=query.where(table.c.allow_workspace_inheritance.is_(True))
    return [SimpleNamespace(**row) for row in db.connection().execute(query).mappings()]


def resolve_provider(db, user, provider, workspace_id=None):
    scope = scope_key(db, user, workspace_id)
    candidates = _configurations(db, {scope}, provider)
    direct = candidates[0] if candidates else None
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
    rows = _configurations(db, sources, 'gemini', inherited=True)
    # Ambiguous private workspace sponsorship must be resolved by a workspace override.
    if workspace.organization_id is None:
        owner_ids={owner.id for owner in owners}
        rows=[row for row in rows if not row.scope_key.startswith("company:") or row.updated_by in owner_ids]
    return rows[0] if len(rows) == 1 else None


def provider_for_scope(db, user, provider, scope):
    workspace_id = int(scope.split(':')[1]) if scope.startswith('workspace:') else None
    return resolve_provider(db, user, provider, workspace_id)
