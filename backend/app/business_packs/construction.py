"""Source-certified native Construction project authorization.

The native PMS permission function runs in a private read-only Session on the
request transaction. Only primitive results escape; the operational pack
Session and its boundary remain installed throughout.
"""
from dataclasses import dataclass
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import and_, event, exists, inspect, select, String, bindparam, case
from sqlalchemy.orm import Session, with_loader_criteria

from .boundary import _current
from .common_core import _native_authority
from .common_queries import assert_mapped_sources

_PROJECT_PROOFS = WeakKeyDictionary()


def _project_epoch(db, scope, project_id):
    from app.apps.project_management.models import PMSProject, PMSProjectMember, PMSWorkspaceMember
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    p, member, workspace, archive = (m.__table__ for m in
        (PMSProject, PMSProjectMember, PMSWorkspaceMember, WorkspaceArchive))
    connection = db.connection()
    row = connection.execute(select(p.c.organization_id, p.c.workspace_id, p.c.manager_user_id,
        p.c.owner_user_id, p.c.department_id, p.c.branch_id, p.c.is_task_collection,
        p.c.is_client_visible, p.c.deleted_at).where(p.c.id == project_id)).first()
    if row is None:
        return None
    membership = tuple(connection.execute(select(member.c.id, member.c.role).where(
        member.c.project_id == project_id, member.c.user_id == scope.user_id)).all())
    workspace_membership = tuple(connection.execute(select(workspace.c.id, workspace.c.role).where(
        workspace.c.workspace_id == row.workspace_id, workspace.c.user_id == scope.user_id)).all())
    lifecycle = connection.execute(select(archive.c.deleted_at, archive.c.restored_at).where(
        archive.c.workspace_id == row.workspace_id)).first()
    return tuple(row), membership, workspace_membership, tuple(lifecycle) if lifecycle else None


@dataclass(frozen=True)
class _ProjectProof:
    scope: object
    authority: str
    project_epoch: tuple


def native_parent_access(db, actor, company, model, native_access):
    """Late-bound certificate for native Construction records' actual PMS parent.

    This lets native SRM retain its parent gate without granting ordinary PMS
    ORM reads. Unselected/other-pack predicates keep their original semantics.
    """
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm.commercial_models import InvoiceContext
    if model not in {IndustryRecord, InvoiceContext}:
        return native_access

    def required():
        scope = db.info.get('business_pack_scope')
        return bool(scope is not None and scope.pack_key == 'construction')

    def certified_ids():
        scope = db.info.get('business_pack_scope')
        if not required():
            return ()
        if scope.user_id != actor.id or scope.company_id != company:
            _deny('Construction native parent authority changed', 403)
        _current(scope, db.connection())
        authority = _native_authority(db, actor, company)
        ids = []
        for project_id, proof in _PROJECT_PROOFS.get(db, {}).items():
            if proof.scope is not scope:
                continue
            if proof.authority != authority or proof.project_epoch != _project_epoch(db, scope, project_id):
                _deny('Construction native project authority changed', 403)
            ids.append(project_id)
        return tuple(ids)

    return case((bindparam('construction_parent_required', callable_=required, unique=True),
        model.project_id.in_(bindparam('construction_parent_certified_ids', callable_=certified_ids,
                                     expanding=True, unique=True))), else_=native_access)


@dataclass(frozen=True)
class ProjectSource:
    id: int
    name: str
    currency: str


@dataclass(frozen=True)
class ProjectBillingSource:
    customer_id: int
    seller_id: int
    currency: str


def project_billing_source(db, actor, project_id):
    """Only the certified project's existing native commercial identity."""
    from app.apps.srm.commercial_models import ProjectCommercial
    from app.apps.srm.services.commercial import require
    scope = db.info.get('business_pack_scope')
    if (scope is None or scope.pack_key != 'construction' or scope.user_id != actor.id
            or scope.company_id != actor.organization_id
            or 'construction.billing.prepare' not in scope.capabilities):
        _deny('Construction billing authority is required', 403)
    require(actor, 'srm_invoice_create', 'srm_admin')
    project = project_for_action(db, actor, project_id)
    authority = _native_authority(db, actor, scope.company_id)
    epoch = _project_epoch(db, scope, project_id)
    table = ProjectCommercial.__table__
    row = db.connection().execute(select(table.c.customer_id, table.c.seller_id, table.c.currency)
        .where(table.c.project_id == project_id)).first()
    _source(db, actor, project_id)
    if authority != _native_authority(db, actor, scope.company_id) or epoch != _project_epoch(db, scope, project_id):
        _deny('Native Construction billing authority changed', 403)
    if row is None:
        return None
    if row.seller_id != scope.company_id or row.currency != project.currency:
        _deny('Project commercial identity requires reconciliation', 409)
    return ProjectBillingSource(row.customer_id, row.seller_id, row.currency)


def _deny(message='Construction project is unavailable', status=404):
    raise HTTPException(status, message)


def _source(db, actor, project_id):
    from app.apps.project_management.models import PMSProject
    from app.branches.models import BranchOwnership
    from .models import PackRecordOwnership
    scope = db.info.get('business_pack_scope')
    branch = db.info.get('branch_context')
    state = inspect(actor, raiseerr=False)
    if (scope is None or scope.pack_key != 'construction' or type(project_id) is not int or project_id < 1
            or state is None or state.session is not db or not state.persistent
            or actor.id != scope.user_id or actor.organization_id != scope.company_id
            or getattr(branch, 'company_id', None) != scope.company_id
            or getattr(branch, 'branch_id', None) != scope.branch_id):
        _deny('Construction source authorization changed', 403)
    connection = db.connection()
    _current(scope, connection)
    project = PMSProject.__table__
    owner = PackRecordOwnership.__table__
    native = BranchOwnership.__table__
    row = connection.execute(select(project.c.id, project.c.workspace_id).where(
        project.c.id == project_id, project.c.organization_id == scope.company_id,
        project.c.branch_id == scope.branch_id, project.c.deleted_at.is_(None),
        exists().where(owner.c.resource_table == project.name, owner.c.resource_key == str(project_id),
            owner.c.company_id == scope.company_id, owner.c.branch_id == scope.branch_id,
            owner.c.context_id == scope.context_id),
        exists().where(native.c.resource_table == project.name, native.c.resource_key == str(project_id),
            native.c.company_id == scope.company_id, native.c.branch_id == scope.branch_id),
    )).first()
    if row is None:
        _deny()
    return scope, row.workspace_id


def project_for_action(db, actor, project_id, action='browse'):
    """Run the actual native action check over one explicitly owned project."""
    from app.access.models import AccessMembership, AccessPolicy, AccessRole
    from app.apps.project_management.access import get_project_for_action
    from app.apps.project_management.models import PMSProject, PMSProjectMember, PMSWorkspaceMember
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    from app.apps.srm.commercial_models import ProjectCommercial
    from app.models.company import Company
    from app.shared.models import ServicePolicy
    from app.shared.settings import effective

    if action not in {'browse', 'manage_tasks', 'approve', 'edit_project'}:
        _deny('Unreviewed Construction project action', 403)
    scope, workspace_id = _source(db, actor, project_id)
    authority = _native_authority(db, actor, scope.company_id)
    epoch = _project_epoch(db, scope, project_id)
    policy_table = AccessPolicy.__table__
    policy = db.connection().execute(select(policy_table.c.grants).where(
        policy_table.c.company_id == scope.company_id, policy_table.c.user_id == scope.user_id)).scalar_one_or_none()
    role_ids = frozenset(grant['roleId'] for grant in (policy or {}).values()
                         if isinstance(grant, dict) and type(grant.get('roleId')) is int)
    criteria = {
        PMSProject: and_(PMSProject.id == project_id, PMSProject.organization_id == scope.company_id,
                         PMSProject.branch_id == scope.branch_id),
        PMSProjectMember: and_(PMSProjectMember.project_id == project_id, PMSProjectMember.user_id == scope.user_id),
        PMSWorkspaceMember: and_(PMSWorkspaceMember.workspace_id == workspace_id, PMSWorkspaceMember.user_id == scope.user_id),
        WorkspaceArchive: WorkspaceArchive.workspace_id == workspace_id,
        AccessMembership: and_(AccessMembership.company_id == scope.company_id, AccessMembership.user_id == scope.user_id),
        AccessPolicy: and_(AccessPolicy.company_id == scope.company_id, AccessPolicy.user_id == scope.user_id),
        AccessRole: and_(AccessRole.company_id == scope.company_id, AccessRole.id.in_(role_ids)),
        ProjectCommercial: and_(ProjectCommercial.project_id == project_id, ProjectCommercial.seller_id == scope.company_id),
        Company: Company.id == scope.company_id,
        ServicePolicy: and_(ServicePolicy.kind == 'settings', ServicePolicy.scope_key.in_(
            ('platform', f'company:{scope.company_id}', f'company:{scope.company_id}:module:srm'))),
    }
    allowed = frozenset(criteria)

    def restrict(execution):
        if (not execution.is_select or not execution.is_orm_statement
                or execution.is_insert or execution.is_update or execution.is_delete):
            _deny('Construction authorization resource is read-only', 403)
        assert_mapped_sources(execution.statement, allowed)
        execution.statement = execution.statement.options(*(with_loader_criteria(model, criterion,
            include_aliases=True, propagate_to_loaders=True) for model, criterion in criteria.items()))

    def no_write(*args, **kwargs):
        _deny('Construction authorization resource is read-only', 403)

    connection = db.connection()
    # rollback_only prevents closing this private Session from rolling back or
    # committing the request's already-open transaction.
    native = Session(bind=connection, autoflush=False, expire_on_commit=False,
                     join_transaction_mode='rollback_only')
    native.info.update(shared_actor=(scope.user_id, scope.company_id),
                       branch_context=db.info.get('branch_context'),
                       security_write_request=bool(db.info.get('security_write_request')))
    event.listen(native, 'do_orm_execute', restrict)
    event.listen(native, 'before_flush', no_write)
    event.listen(native, 'before_commit', no_write)
    native.commit = no_write
    native.rollback = no_write
    native.flush = native.add = native.add_all = native.delete = no_write
    native.bulk_save_objects = native.bulk_insert_mappings = native.bulk_update_mappings = no_write
    try:
        project = get_project_for_action(native, project_id, actor, action)
        commercial = native.get(ProjectCommercial, project_id)
        # A mismatched legal seller is corrupt linkage, never a default-currency
        # fallback that could alter an already priced project.
        actual_seller = connection.scalar(select(ProjectCommercial.__table__.c.seller_id).where(
            ProjectCommercial.__table__.c.project_id == project_id))
        if actual_seller is not None and actual_seller != scope.company_id:
            _deny('Project seller requires reconciliation', 409)
        currency = commercial.currency if commercial else effective(native, scope.company_id, 'srm')['values']['currency']
        result = ProjectSource(project.id, project.name, currency)
        _source(db, actor, project_id)
        if _native_authority(db, actor, scope.company_id) != authority:
            _deny('Native Construction authority changed', 403)
        if epoch != _project_epoch(db, scope, project_id):
            _deny('Native Construction project authority changed', 403)
        _PROJECT_PROOFS.setdefault(db, {})[project_id] = _ProjectProof(scope, authority, epoch)
        return result
    finally:
        native.close()


def project_files(db, actor, project_id, *, file_ids=None, offset=0, limit=50):
    """Read minimal native file metadata for one freshly authorized owned site.

    Files remain canonical PMS assets. This resource grants no PMS ORM access,
    storage paths, download authority, or authority over another project.
    """
    from app.apps.project_management.models import PMSFileAsset
    from .operations import require
    require(db, actor, 'sites.view', 'diary.record')
    project_for_action(db, actor, project_id)
    scope, _ = _source(db, actor, project_id)
    authority = _native_authority(db, actor, scope.company_id)
    epoch = _project_epoch(db, scope, project_id)
    table = PMSFileAsset.__table__
    query = select(table.c.id, table.c.original_name, table.c.visibility,
        table.c.uploaded_by_user_id).where(table.c.project_id == project_id, table.c.deleted_at.is_(None))
    if file_ids is not None:
        query = query.where(table.c.id.in_(file_ids)).with_for_update()
    else:
        query = query.where((table.c.visibility != 'Work Evidence') |
            (table.c.uploaded_by_user_id == actor.id)).order_by(table.c.id.desc()).offset(offset).limit(limit)
    rows = db.connection().execute(query).all()
    if file_ids is not None:
        if {row.id for row in rows} != set(file_ids):
            _deny("Site photos must be uploaded to this project's Files first", 422)
        if any(row.visibility == 'Work Evidence' and row.uploaded_by_user_id != actor.id for row in rows):
            _deny('This project file is private to its uploader', 403)
    _source(db, actor, project_id)
    if authority != _native_authority(db, actor, scope.company_id) or epoch != _project_epoch(db, scope, project_id):
        _deny('Native Construction file authority changed', 403)
    return [{'id': row.id, 'original_name': row.original_name} for row in rows]


def subcontract_vendor_roles(db, actor, project_id, vendor):
    """Canonical roles of the already native-authorized, available CRM vendor."""
    from types import SimpleNamespace
    from app.shared.master_data import relationships
    from app.shared.master_data_models import BusinessRelationship
    from app.apps.srm.services.commercial import customer
    project_for_action(db, actor, project_id, 'edit_project')
    scope, _ = _source(db, actor, project_id)
    if customer(db, vendor.id, actor) is not vendor:
        _deny('Construction vendor identity changed', 403)
    table = BusinessRelationship.__table__
    roles = db.connection().execute(select(table.c.role).where(
        table.c.organization_id == scope.company_id, table.c.account_id == vendor.id)).scalars().all()
    return relationships(db, vendor, 'company', links=[SimpleNamespace(role=role) for role in roles])


def validate_industry_source(db, scope, item):
    """No private BOQ/project/parent link may cross its actual source boundary."""
    from .construction_materials import validate_item
    validate_item(db, scope, item)
    from app.apps.srm.industry_models import IndustryRecord
    from .models import PackRecordOwnership
    if type(item) is not IndustryRecord or scope.pack_key != 'construction':
        return
    kinds = {'boq', 'variation', 'measurement', 'site_diary', 'subcontract', 'material_issue'}
    if item.kind not in kinds:
        return
    from .construction_billing import validate_record
    validate_record(db, item)
    state = inspect(item)
    if state.persistent and any(state.attrs[name].history.has_changes()
                                for name in ('kind', 'project_id', 'parent_id')):
        _deny('Construction source identity is immutable', 403)
    # Source validation uses the actual request actor, never the row's author.
    from app.models.user import User
    actor = db.get(User, scope.user_id)
    _source(db, actor, item.project_id)
    if item.parent_id is not None:
        row, owner = IndustryRecord.__table__, PackRecordOwnership.__table__
        valid = db.connection().scalar(select(exists().where(
            row.c.id == item.parent_id, row.c.project_id == item.project_id,
            row.c.organization_id == scope.company_id, row.c.branch_id == scope.branch_id,
            row.c.kind.in_(('boq', 'variation')), row.c.status == 'approved',
            exists().where(owner.c.resource_table == row.name, owner.c.resource_key == str(item.parent_id),
                owner.c.company_id == scope.company_id, owner.c.branch_id == scope.branch_id,
                owner.c.context_id == scope.context_id))))
        if not valid:
            _deny('Construction parent is unavailable')
    if item.kind in {'variation', 'measurement'} and item.parent_id is None:
        _deny('Construction parent is required', 422)


def project_reference(db, scope, item, parent, pairs):
    """Certify only the actual canonical IndustryRecord.project_id foreign key."""
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.project_management.models import PMSProject
    if (scope.pack_key != 'construction' or type(item) is not IndustryRecord
            or parent is not PMSProject.__table__ or len(pairs) != 1
            or pairs[0][0] != 'project_id' or pairs[0][1] is not PMSProject.__table__.c.id):
        return False
    validate_industry_source(db, scope, item)
    return True


def authorize_record_project(db, actor, record_id):
    """Authorize the project of one actual context-owned record before ORM get."""
    from app.apps.srm.industry_models import IndustryRecord
    from .models import PackRecordOwnership
    scope = db.info.get('business_pack_scope')
    if scope is None or scope.pack_key != 'construction':
        return
    _current(scope, db.connection())
    row, owner = IndustryRecord.__table__, PackRecordOwnership.__table__
    actual = db.connection().execute(select(row.c.kind, row.c.project_id).where(row.c.id == record_id,
        row.c.organization_id == scope.company_id, row.c.branch_id == scope.branch_id,
        exists().where(owner.c.resource_table == row.name, owner.c.resource_key == str(record_id),
            owner.c.company_id == scope.company_id, owner.c.branch_id == scope.branch_id,
            owner.c.context_id == scope.context_id))).first()
    if actual is None:
        _deny('Industry record not found')
    if actual.kind not in {'boq', 'variation', 'measurement', 'site_diary', 'subcontract', 'material_issue'}:
        return
    if actual.project_id is None:
        _deny('Industry record not found')
    project_for_action(db, actor, actual.project_id)


def authorize_retry_project(db, actor, request_id):
    """Prove the stored retry source before its native parent-filtered ORM read."""
    from app.apps.srm.industry_models import IndustryRecord
    from .models import PackRecordOwnership
    scope = db.info.get('business_pack_scope')
    _current(scope, db.connection())
    row, owner = IndustryRecord.__table__, PackRecordOwnership.__table__
    ident = db.connection().scalar(select(row.c.id).where(row.c.request_id == str(request_id),
        row.c.organization_id == scope.company_id, row.c.branch_id == scope.branch_id,
        exists().where(owner.c.resource_table == row.name, owner.c.resource_key == row.c.id.cast(String),
            owner.c.company_id == scope.company_id, owner.c.branch_id == scope.branch_id,
            owner.c.context_id == scope.context_id)))
    if ident is not None:
        authorize_record_project(db, actor, ident)


def require_clean_billing_start(db, actor, project_id):
    """Blind duplicate-source reservation check after actual project proof."""
    from app.apps.srm.commercial_models import ProjectCommercial, InvoiceContext
    from app.apps.srm.models import SRMInvoice, SRMInvoiceDraft
    from sqlalchemy import or_, func
    scope, _ = _source(db, actor, project_id)
    commercial = ProjectCommercial.__table__
    ctx = db.connection().execute(select(commercial.c.seller_id, commercial.c.sales_order_id,
        commercial.c.engagement_id).where(commercial.c.project_id == project_id)).first()
    if ctx and ctx.seller_id != scope.company_id:
        _deny('Project seller requires reconciliation', 409)
    invoice, context, draft = SRMInvoice.__table__, InvoiceContext.__table__, SRMInvoiceDraft.__table__
    conditions = [context.c.project_id == project_id]
    if ctx and ctx.sales_order_id:
        conditions.append(invoice.c.sales_order_id == ctx.sales_order_id)
    if ctx and ctx.engagement_id:
        conditions.append(invoice.c.engagement_id == ctx.engagement_id)
    linked = invoice.outerjoin(context, context.c.invoice_id == invoice.c.id).outerjoin(
        draft, draft.c.id == invoice.c.invoice_draft_id)
    if db.connection().scalar(select(exists().select_from(linked).where(or_(*conditions),
            func.coalesce(invoice.c.status, '') != 'cancelled',
            func.coalesce(draft.c.source_type, '') != 'industry_measurement'))):
        _deny('This project already has other billing sources. Reconcile existing billing before approving BOQ measurement billing.', 409)


def project_options(db, actor, search='', offset=0):
    from app.apps.project_management.models import PMSProject, PMSProjectMember, PMSWorkspaceMember
    from app.apps.project_management.access import accessible_project_query
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    from app.branches.models import BranchOwnership
    from .models import PackRecordOwnership
    scope = db.info.get('business_pack_scope')
    branch = db.info.get('branch_context')
    if (scope is None or scope.pack_key != 'construction' or actor.id != scope.user_id
            or actor.organization_id != scope.company_id
            or getattr(branch, 'branch_id', None) != scope.branch_id):
        _deny('Construction source authorization changed', 403)
    _current(scope, db.connection())
    authority = _native_authority(db, actor, scope.company_id)
    project, owner, branch_owner = PMSProject.__table__, PackRecordOwnership.__table__, BranchOwnership.__table__
    ownership = and_(project.c.organization_id == scope.company_id, project.c.branch_id == scope.branch_id,
        exists().where(owner.c.resource_table == project.name, owner.c.resource_key == project.c.id.cast(String),
            owner.c.company_id == scope.company_id, owner.c.branch_id == scope.branch_id,
            owner.c.context_id == scope.context_id),
        exists().where(branch_owner.c.resource_table == project.name,
            branch_owner.c.resource_key == project.c.id.cast(String),
            branch_owner.c.company_id == scope.company_id, branch_owner.c.branch_id == scope.branch_id))
    owned_ids = select(project.c.id).where(ownership)
    workspace_ids = select(project.c.workspace_id).where(ownership)
    criteria = {
        PMSProject: PMSProject.id.in_(owned_ids),
        PMSProjectMember: and_(PMSProjectMember.project_id.in_(owned_ids), PMSProjectMember.user_id == scope.user_id),
        PMSWorkspaceMember: and_(PMSWorkspaceMember.workspace_id.in_(workspace_ids), PMSWorkspaceMember.user_id == scope.user_id),
        WorkspaceArchive: WorkspaceArchive.workspace_id.in_(workspace_ids),
    }

    def restrict(execution):
        if not execution.is_select or not execution.is_orm_statement:
            _deny('Construction project picker is read-only', 403)
        assert_mapped_sources(execution.statement, frozenset(criteria))
        execution.statement = execution.statement.options(*(with_loader_criteria(model, criterion,
            include_aliases=True, propagate_to_loaders=True) for model, criterion in criteria.items()))

    def no_write(*args, **kwargs):
        _deny('Construction project picker is read-only', 403)

    native = Session(bind=db.connection(), autoflush=False, expire_on_commit=False,
                     join_transaction_mode='rollback_only')
    native.info.update(shared_actor=(scope.user_id, scope.company_id), branch_context=branch,
                       security_write_request=False)
    event.listen(native, 'do_orm_execute', restrict)
    event.listen(native, 'before_flush', no_write)
    event.listen(native, 'before_commit', no_write)
    native.commit = native.rollback = no_write
    native.flush = native.add = native.add_all = native.delete = no_write
    native.bulk_save_objects = native.bulk_insert_mappings = native.bulk_update_mappings = no_write
    try:
        # Exact existing native picker predicate, intersected with explicit
        # context ownership BEFORE SQL pagination. No per-row ORM graph loads.
        q = accessible_project_query(native, actor).filter(PMSProject.is_task_collection.is_(False),
            PMSProject.is_archived.is_(False))
        if search.strip():
            q = q.filter(PMSProject.name.ilike('%' + search.strip().replace('%', r'\%').replace('_', r'\_') + '%', escape='\\'))
        rows = q.with_entities(PMSProject.id, PMSProject.name).order_by(PMSProject.name, PMSProject.id).offset(offset).limit(51).all()
        _current(scope, db.connection())
        if _native_authority(db, actor, scope.company_id) != authority:
            _deny('Native Construction authority changed', 403)
        return {'items': [{'id': row.id, 'name': row.name} for row in rows[:50]], 'has_more': len(rows) > 50}
    finally:
        native.close()
