"""Resolve terminology from fresh operational authority without saving settings."""
from fastapi import HTTPException

from .access import resolve_context
from app.shared.business_profile import check_workspace, effective, resolve


def effective_profile(db, actor, branch_ctx, selected=None, *, workspace_module=None, workspace_id=None):
    if branch_ctx is None:
        if selected is not None:
            raise HTTPException(403, 'A verified branch is required for Business Pack terminology')
        branch_id = None
        scope = None
    else:
        branch_id = branch_ctx.branch_id
        scope = resolve_context(db, actor, branch_ctx, requested_context_id=selected)
        if scope is not None:
            branch_id = scope.branch_id
    check_workspace(db, actor, branch_id, workspace_module, workspace_id)
    if scope is None:
        from .theme_selection import selected_profile
        profile = selected_profile(db, actor.organization_id)
        return {**(profile if profile is not None else effective(db, actor.organization_id, branch_id,
                            workspace_module=workspace_module, workspace_id=workspace_id)),
                'companyId': actor.organization_id, 'branchId': branch_id}
    # Company/branch labels may belong to another pack. Switching contexts must
    # neither inherit those words nor rewrite the shared settings to change them.
    return {**resolve([{'business_type': scope.pack_key}]), 'versions': {},
            'companyId': scope.company_id, 'branchId': scope.branch_id,
            'packContextId': scope.context_id, 'packKey': scope.pack_key,
            'packVersion': scope.pack_version,
            'packRevisions': list(scope.revisions)}
