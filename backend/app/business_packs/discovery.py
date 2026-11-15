"""Minimal control-plane discovery; choices never confer operational authority."""
from fastapi import HTTPException
from sqlalchemy import select
from app.branches.service import BranchContext, access as branch_access, context as branch_context
from app.models.company import Branch
from .access import _has_history, _installed, available_contexts, resolve_context
from .registry import get_pack


def discover_contexts(db, actor, request, *, limit=100):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Pack discovery limit must be between 1 and 100')
    empty = {'state': 'unavailable', 'contexts': [], 'hasMore': False,
        'selectorRequired': False, 'selectedContextId': None, 'selectionState': 'none'}
    try:
        if not _installed(db):
            return {**empty, 'reason': 'not_installed'}
        company = actor.organization_id
        allowed, writable, all_access, manager = branch_access(db, actor, company)
        # A verified union of native branches is used only to enumerate exact
        # user/context grant pairs; it does not assert native all-branch access.
        native = BranchContext(company_id=company, branch_id=None, allowed=frozenset(allowed),
            writable=frozenset(writable), all_branches=all_access, manage_access=manager,
            superuser=actor.is_superuser)
        scopes = available_contexts(db, actor, native)
        required = _has_history(db, company, None)
        try:
            current_branch = branch_context(db, actor, company, request.headers.get('X-Suite-Branch'))
            required = _has_history(db, company, current_branch.branch_id)
        except HTTPException as error:
            if error.status_code not in (403, 404, 503): raise
            # Keep genuine repair choices available for an invalid branch.
            # Only a verified legacy branch may suppress the selector warning.
    except HTTPException as error:
        if error.status_code not in (403, 404, 503): raise
        return {**empty, 'reason': 'schema_unavailable' if error.status_code == 503 else 'authority_unavailable'}
    selected = None
    status = 'none'
    raw = request.headers.get('X-Suite-Pack-Context')
    if raw is not None:
        status = 'invalid'
        try:
            current = branch_context(db, actor, company, request.headers.get('X-Suite-Branch'))
            verified = resolve_context(db, actor, current, requested_context_id=raw)
            if verified is not None:
                selected, status = verified.context_id, 'verified'
        except HTTPException as error:
            if error.status_code not in (403, 404, 503): raise
    visible = scopes[:limit]
    names = dict(db.connection().execute(select(Branch.id, Branch.name).where(
        Branch.company_id == company, Branch.id.in_({scope.branch_id for scope in visible}))).all())
    return {'state': 'ready', 'contexts': [{
        'contextId': scope.context_id, 'branchId': scope.branch_id, 'branchName': names[scope.branch_id],
        'packKey': scope.pack_key, 'packLabel': get_pack(scope.pack_key).label, 'packVersion': scope.pack_version,
        'role': scope.role, 'contextRevision': scope.context_revision, 'grantRevision': scope.grant_revision,
        'activationRevision': scope.activation_revision,
    } for scope in visible], 'hasMore': len(scopes) > limit, 'selectorRequired': required,
        'selectedContextId': selected, 'selectionState': status}
