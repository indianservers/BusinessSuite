"""Code-owned activation gates, separate from terminology and draft setup.

Register support only after native record guards and the pack's workflows have
been integrated and verified. Neither a browser request nor a database setting
can declare an unfinished workflow ready.
"""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from sqlalchemy import inspect, select
from .registry import get_pack


SCHEMA_COLUMNS: Mapping[str, frozenset[str]] = MappingProxyType({
    'business_pack_activations': frozenset({'id', 'company_id', 'pack_key', 'pack_version', 'state', 'revision'}),
    'business_pack_contexts': frozenset({'id', 'company_id', 'branch_id', 'activation_id', 'pack_key', 'pack_version', 'state', 'ever_activated', 'revision'}),
    'business_pack_user_grants': frozenset({'id', 'company_id', 'branch_id', 'context_id', 'user_id', 'role', 'active', 'revision'}),
    'business_pack_record_ownership': frozenset({'company_id', 'branch_id', 'context_id', 'resource_table', 'resource_key'}),
    'business_pack_master_availability': frozenset({'company_id', 'branch_id', 'context_id', 'resource_table', 'resource_key', 'active'}),
})


@dataclass(frozen=True)
class PackRuntimeSupport:
    version: int
    isolation_version: int
    workflows: frozenset[str]


# Intentionally empty during framework installation. A registered manifest is
# a definition, not evidence that its operational routes enforce pack ownership.
RUNTIME_SUPPORT: Mapping[str, PackRuntimeSupport] = MappingProxyType({})

# These workflows currently post real native Accounting vouchers. Optional
# module licensing must not be mistaken for a working refund workflow when
# Accounting is unavailable. This grants or enables no application.
WORKFLOW_MODULE_REQUIREMENTS = MappingProxyType({
    ('retail', 'returns'): frozenset({'fam'}),
    ('pharma', 'recalls'): frozenset({'fam'}),
})


def schema_ready(db):
    inspector = inspect(db.connection())
    for name, required in SCHEMA_COLUMNS.items():
        if not inspector.has_table(name):
            return False
        if not required <= {column['name'] for column in inspector.get_columns(name)}:
            return False
    return True


def activation_readiness(db, company_id, pack_key, branch_id=None):
    """Report real schema, license and integration gates without creating rows."""
    from app.models.company import Company, Branch
    from app.access.entitlements import states
    from app.enterprise.controls import disabled_modules
    from app.module_registry import is_app_enabled
    manifest = get_pack(pack_key)
    reasons = []
    company = db.connection().execute(select(Company.id).where(
        Company.id == company_id, Company.is_active.is_(True))).scalar_one_or_none()
    if company is None:
        reasons.append('An active company is required.')
    if branch_id is not None:
        from app.branches.models import BranchLifecycle
        branch = db.connection().execute(select(Branch.id).where(
            Branch.id == branch_id, Branch.company_id == company_id, Branch.is_active.is_(True),
            ~Branch.id.in_(select(BranchLifecycle.branch_id).where(BranchLifecycle.deleted_at.is_not(None))),
        )).scalar_one_or_none()
        if branch is None:
            reasons.append('An active branch belonging to this company is required.')
    installed = schema_ready(db)
    if not installed:
        reasons.append('Business Pack installation must finish before activation.')
    enabled = states(db, company_id)
    unavailable = disabled_modules(db, company_id)
    missing = sorted(key for key in manifest.required_modules
                     if not is_app_enabled(key) or enabled.get(key) is False or key in unavailable)
    if missing:
        reasons.append('Required approved applications are unavailable: ' + ', '.join(missing) + '.')
    workflow_missing = {}
    for workflow in manifest.workflows:
        required = WORKFLOW_MODULE_REQUIREMENTS.get((manifest.key, workflow.key), frozenset())
        absent = sorted(key for key in required
                        if not is_app_enabled(key) or enabled.get(key) is False or key in unavailable)
        if absent:
            workflow_missing[workflow.key] = absent
            reasons.append(workflow.label + ' requires approved applications: ' + ', '.join(absent) + '.')
    support = RUNTIME_SUPPORT.get(manifest.key)
    isolated = bool(support and support.version == manifest.version and support.isolation_version >= 1)
    workflows = bool(support and support.version == manifest.version
                     and {workflow.key for workflow in manifest.workflows} <= support.workflows)
    if not isolated:
        reasons.append('Operational pack isolation is not enabled for this release yet.')
    if not workflows:
        reasons.append('The pack workflows are still being connected and verified.')
    return {'ready': not reasons, 'reasons': reasons, 'schema_ready': installed,
            'isolation_ready': isolated, 'workflows_ready': workflows,
            'workflow_modules_ready': not workflow_missing, 'missing_workflow_modules': workflow_missing,
            'pack_version': manifest.version}
