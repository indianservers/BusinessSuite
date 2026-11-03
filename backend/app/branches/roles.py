"""Branch roles narrow company authorization; company revocation always wins."""
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import select, inspect
from app.branches.models import BranchGrant


def writable_actions(ctx, grants, user=None):
    if grants is None or ctx.branch_id is None or ctx.branch_id in ctx.writable:
        return grants
    masked = {key: {**grant, "actions": [action for action in grant.get("actions", []) if action in {"view", "export"}]} for key, grant in grants.items()}
    if user is not None:
        import hashlib, json
        user._suite_branch_roles_fingerprint = hashlib.sha256(json.dumps(masked, sort_keys=True).encode()).hexdigest()
    return masked


def effective_grants(db, user, company, selected, base=None):
    user._suite_branch_roles_fingerprint = None
    if user.is_superuser or not inspect(db.connection()).has_table(BranchGrant.__tablename__):
        return base
    from app.branches.service import context
    from app.access.service import legacy_grants, resolved_grants
    ctx = context(db, user, company, selected)
    if not ctx.allowed:
        ceiling = base if base is not None else legacy_grants(db, user, company)
        return {key: {**grant, 'enabled': False, 'permissions': [], 'actions': []} for key, grant in ceiling.items()}
    rows = db.connection().execute(select(BranchGrant.branch_id, BranchGrant.module_grants).where(
        BranchGrant.user_id == user.id, BranchGrant.company_id == company,
        BranchGrant.branch_id.in_(ctx.allowed))).all()
    restricted = {r.branch_id: r.module_grants for r in rows if r.module_grants is not None}
    if not restricted:
        return writable_actions(ctx, base, user)
    if ctx.branch_id is None:
        # Different record scopes cannot safely be unioned under a single ORM scope.
        raise HTTPException(403, "Select a branch to use its assigned module roles")
    if ctx.branch_id not in restricted:
        return writable_actions(ctx, base, user)
    ceiling = base if base is not None else legacy_grants(db, user, company)
    branch = resolved_grants(db, SimpleNamespace(grants=restricted[ctx.branch_id], company_id=company))
    result = {}
    for module, limit in ceiling.items():
        grant = dict(branch.get(module, {}))
        grant['enabled'] = bool(limit.get('enabled') and grant.get('enabled'))
        grant['permissions'] = sorted(set(grant.get('permissions', [])) & set(limit.get('permissions', [])))
        grant['actions'] = sorted(set(grant.get('actions', [])) & set(limit.get('actions', [])))
        # The company record scope remains a ceiling. Branch may narrow it further.
        scope = limit.get('scope', 'own')
        if scope not in {'all', 'organization'} and grant.get('scope') != scope:
            if grant.get('scope') in {'all', 'organization'}:
                grant['scope'] = scope
            elif grant.get('scope') != 'own' or scope not in {'team', 'department', 'branch'}:
                grant['enabled'] = False  # Incomparable scopes cannot be widened.
        result[module] = grant
    import hashlib, json
    user._suite_branch_roles_fingerprint = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return writable_actions(ctx, result, user)
