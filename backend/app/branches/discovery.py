"""Admin navigation metadata; opening a record still binds its company/branch."""
import re
from fastapi import HTTPException
from sqlalchemy import select, func, cast, String
from app.models.company import Branch, Company
from app.branches.models import BranchLifecycle, BranchOwnership
from app.branches.service import company_administrator


def branch_choices(db, user):
    query = select(Branch.id, Branch.name, Branch.code, Branch.is_active,
        Branch.company_id, Company.name.label('company_name'), Company.is_active.label('company_active'),
        BranchLifecycle.deleted_at).join(Company, Company.id == Branch.company_id).outerjoin(BranchLifecycle, BranchLifecycle.branch_id == Branch.id)
    if not user.is_superuser:
        query = query.where(Branch.company_id == user.organization_id)
    rows = db.connection().execute(query.order_by(Company.name, Branch.name, Branch.id)).mappings()
    return [{k: v for k, v in row.items() if k != 'deleted_at'} |
        {'is_deleted': row['deleted_at'] is not None,
         'can_write': bool(row['is_active'] and row['company_active'] and row['deleted_at'] is None)} for row in rows]


def workspace_choices(db, user):
    if not user.is_superuser and not company_administrator(db, user, user.organization_id):
        raise HTTPException(403, 'Company administration access is required')
    from app.shared.models import ServicePolicy
    from app.apps.project_management.models import PMSWorkspace
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    connection = db.connection()
    companies = dict(connection.execute(select(Company.id, Company.name)).all())
    branches = {b['id']: b for b in branch_choices(db, user)}
    query = select(ServicePolicy.organization_id, ServicePolicy.scope_key, ServicePolicy.values_json).where(ServicePolicy.kind == 'module_workspace')
    if not user.is_superuser:
        query = query.where(ServicePolicy.organization_id == user.organization_id)
    items, metadata = [], {}

    def item(company, module, ref, name, branch, status):
        if company not in companies or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', ref):
            return None
        choice = branches.get(branch)
        if choice and choice['company_id'] != company:
            return None
        return {'id': ref, 'key': f'{company}:{module}:{ref}', 'name': name, 'module': module,
            'company_id': company, 'company_name': companies[company], 'branch_id': branch if choice else None,
            'branch_name': choice['name'] if choice else 'All branches', 'status': status}

    for row in connection.execute(query).mappings():
        parts = row['scope_key'].split(':')
        if len(parts) != 5 or parts[0] != 'workspace' or parts[1] not in {'hrms', 'crm', 'pms', 'srm', 'fam'}:
            continue
        if not parts[2].isdigit() or not parts[3].isdigit() or int(parts[2]) != row['organization_id']:
            continue
        data = row['values_json'] or {}
        result = item(row['organization_id'], parts[1], parts[4], data.get('name', 'Workspace'), int(parts[3]), data.get('status', 'Active'))
        if result is None:
            continue
        if parts[1] == 'pms':
            metadata[(row['organization_id'], parts[4])] = result
        else:
            items.append(result)
    native = select(PMSWorkspace.id, PMSWorkspace.name, func.coalesce(PMSWorkspace.organization_id, 1).label('company_id'),
        BranchOwnership.branch_id, WorkspaceArchive.deleted_at).outerjoin(WorkspaceArchive, WorkspaceArchive.workspace_id == PMSWorkspace.id).outerjoin(
        BranchOwnership, (BranchOwnership.resource_table == 'pms_workspaces') &
        (BranchOwnership.resource_key == cast(PMSWorkspace.id, String)) &
        (BranchOwnership.company_id == func.coalesce(PMSWorkspace.organization_id, 1)))
    if not user.is_superuser:
        native = native.where(func.coalesce(PMSWorkspace.organization_id, 1) == user.organization_id)
    for row in connection.execute(native).mappings():
        previous = metadata.get((row['company_id'], str(row['id'])), {})
        result = item(row['company_id'], 'pms', str(row['id']), row['name'], row['branch_id'] or previous.get('branch_id'),
            'Archived' if row['deleted_at'] else 'Active')
        if result:
            items.append(result)
    return {'items': sorted(items, key=lambda r: (r['company_name'].casefold(), r['module'], r['name'].casefold(), r['id'])),
        'all_companies': bool(user.is_superuser)}
