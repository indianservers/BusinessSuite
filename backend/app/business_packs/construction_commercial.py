"""Finite native PMS commercial identity setup before any site scope is priced."""
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, event, exists, inspect, select
from sqlalchemy.orm import Session, with_loader_criteria

from app.core.deps import get_db, get_current_user
from app.apps.srm.commercial_models import ProjectCommercial, SellerGrant, InvoiceContext
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMAuditLog, SRMInvoice
from app.apps.srm.services.commercial import customer, seller
from .construction import _source, _project_epoch, project_for_action
from .common_core import _native_authority
from .common_queries import assert_mapped_sources
from .construction_documents import _Writer, _AuthorityReads, _key
from .operations import require

router = APIRouter(tags=['Construction canonical commercial identity'])
_COMMANDS = WeakKeyDictionary()
_ADVANCED = ('contact_id', 'team_id', 'opportunity_id', 'sales_order_id', 'engagement_id')


class CommercialInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    customer_id: int = Field(gt=0)
    currency: str = Field(pattern=r'^[A-Z]{3}$')


def fail(message, status=409):
    raise HTTPException(status, message)


def _current(db, project_id):
    return db.connection().execute(select(ProjectCommercial.__table__).where(ProjectCommercial.__table__.c.project_id == project_id)).first()


def _priced(db, project_id):
    row, ctx, invoice = IndustryRecord.__table__, InvoiceContext.__table__, SRMInvoice.__table__
    return bool(db.connection().scalar(select(exists().where(row.c.project_id == project_id,
        row.c.kind.in_(('boq', 'variation', 'measurement'))))) or db.connection().scalar(select(exists().select_from(
            ctx.join(invoice, ctx.c.invoice_id == invoice.c.id)).where(ctx.c.project_id == project_id))))


def _payload(row, project_id, *, locked=False):
    return {'project_id': project_id, 'customer_id': row.customer_id if row else None,
        'seller_id': row.seller_id if row else None, 'currency': row.currency if row else None,
        'identity_locked': locked, 'has_advanced_links': bool(row and any(getattr(row, key) is not None for key in _ADVANCED))}


def _access(db, actor, project_id, *, write=False):
    from app.access.service import check_background_access
    from app.apps.srm.services.commercial import lock_tenant
    scope, _ = _source(db, actor, project_id)
    require(db, actor, *('billing.prepare',) if write else ('billing.view', 'billing.prepare'))
    before = _native_authority(db, actor, scope.company_id)
    if write:
        if not scope.writable:
            fail('A writable Construction commercial context is required', 403)
        lock_tenant(db, actor)
    check_background_access(db, actor, 'srm', 'create' if write else 'view', administrative_read=False, stamp=False)
    check_background_access(db, actor, 'project_management', 'edit' if write else 'view', administrative_read=False, stamp=False)
    project_for_action(db, actor, project_id, 'edit_project' if write else 'browse')
    if before != _native_authority(db, actor, scope.company_id):
        fail('Native commercial identity authority changed while waiting', 403)
    return scope


class _CommercialReads(_AuthorityReads):
    def __init__(self, connection, company, customer_id):
        super().__init__(connection, company)
        from app.apps.srm.anonymous_cash import _CONTROL
        schema = inspect(connection)
        self.columns[_CONTROL.name] = [c['name'] for c in schema.get_columns(_CONTROL.name)] if schema.has_table(_CONTROL.name) else None
        if self.columns[_CONTROL.name] is not None:
            query = select(_CONTROL).where(_CONTROL.c.customer_id == customer_id)
            self.rows[_key(query)] = connection.execute(query).freeze()
        self.info = MappingProxyType({})
        from hashlib import sha256
        self.fingerprint = sha256(repr([(key, value.data) for key, value in self.rows.items()]).encode()).hexdigest()


@dataclass
class _Link:
    db: object
    actor: object
    scope: object
    project_id: int
    data: CommercialInput
    original: object
    root: object = None
    record: object = None
    minted: list = field(default_factory=list)

    def __post_init__(self):
        self.authority = _native_authority(self.db, self.actor, self.scope.company_id)
        self.epoch = _project_epoch(self.db, self.scope, self.project_id)

    def current(self):
        if (_access(self.db, self.actor, self.project_id, write=True) is not self.scope
                or self.authority != _native_authority(self.db, self.actor, self.scope.company_id)
                or self.epoch != _project_epoch(self.db, self.scope, self.project_id)):
            fail('Native commercial identity authority changed', 403)
        customer(self.db, self.data.customer_id, self.actor)
        seller(self.db, self.scope.company_id, self.actor)
        if _priced(self.db, self.project_id):
            fail('Project scope is already priced; commercial identity requires reconciliation')

    def validate(self, session, *args):
        self.current()
        from app.apps.srm.commercial_api import LinkInput
        expected = LinkInput(customer_id=self.data.customer_id, seller_id=self.scope.company_id, currency=self.data.currency).model_dump()
        if session.deleted:
            fail('Commercial linking cannot delete records', 403)
        for row in [*session.new, *session.dirty]:
            if type(row) is ProjectCommercial:
                if self.root is not None and self.root is not row:
                    fail('Only one canonical ProjectCommercial row may be linked', 403)
                if (row.project_id != self.project_id or row.customer_id != self.data.customer_id
                        or row.seller_id != self.scope.company_id or row.currency != self.data.currency
                        or row.updated_by != self.actor.id or any(getattr(row, key) is not None for key in _ADVANCED)):
                    fail('Native commercial identity differs from its exact command', 403)
                self.root = row
            elif type(row) is SRMAuditLog:
                if (row not in session.new or row.id is not None or row.organization_id != self.scope.company_id
                        or row.entity_type != 'project' or row.entity_id != self.project_id
                        or row.action != 'commercial_linked' or row.actor_user_id != self.actor.id
                        or row.before_json is not None or row.after_json != expected or row.ip_address is not None):
                    fail('Native commercial audit differs from its canonical project command', 403)
            else:
                fail('Commercial linking cannot alter other native records', 403)
            if row not in self.minted:
                self.minted.append(row)


def _native(command):
    from app.apps.project_management.models import PMSProject, PMSProjectMember, PMSWorkspaceMember
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    from app.access.models import AccessMembership, AccessPolicy, AccessRole
    from app.apps.crm.models import CRMCompany
    from app.models.company import Company
    from app.apps.srm.commercial_api import LinkInput, link_project_service
    db, actor, scope = command.db, command.actor, command.scope
    connection = db.connection()
    _, workspace = _source(db, actor, command.project_id)
    grants = connection.scalar(select(AccessPolicy.__table__.c.grants).where(
        AccessPolicy.__table__.c.company_id == scope.company_id, AccessPolicy.__table__.c.user_id == actor.id)) or {}
    roles = {value['roleId'] for value in grants.values() if isinstance(value, dict) and type(value.get('roleId')) is int}
    criteria = {
        PMSProject: and_(PMSProject.id == command.project_id, PMSProject.organization_id == scope.company_id, PMSProject.branch_id == scope.branch_id),
        PMSProjectMember: and_(PMSProjectMember.project_id == command.project_id, PMSProjectMember.user_id == actor.id),
        PMSWorkspaceMember: and_(PMSWorkspaceMember.workspace_id == workspace, PMSWorkspaceMember.user_id == actor.id),
        WorkspaceArchive: WorkspaceArchive.workspace_id == workspace,
        AccessMembership: and_(AccessMembership.company_id == scope.company_id, AccessMembership.user_id == actor.id),
        AccessPolicy: and_(AccessPolicy.company_id == scope.company_id, AccessPolicy.user_id == actor.id),
        AccessRole: and_(AccessRole.company_id == scope.company_id, AccessRole.id.in_(roles)),
        CRMCompany: and_(CRMCompany.id == command.data.customer_id, CRMCompany.organization_id == scope.company_id, CRMCompany.deleted_at.is_(None)),
        ProjectCommercial: ProjectCommercial.project_id == command.project_id,
        Company: Company.id == scope.company_id,
        SellerGrant: and_(SellerGrant.organization_id == scope.company_id, SellerGrant.seller_id == scope.company_id),
    }
    reads = _CommercialReads(connection, scope.company_id, command.data.customer_id)
    native = _Writer(bind=connection, autoflush=False, expire_on_commit=False, join_transaction_mode='create_savepoint')
    native._authority_reads = reads
    native.info.update(shared_actor=(actor.id, scope.company_id), branch_context=db.info.get('branch_context'),
        security_write_request=True, suite_access_schema_ready=True)
    def restrict(execution):
        if not execution.is_select or not execution.is_orm_statement:
            fail('Commercial source allows reviewed native ORM reads only', 403)
        assert_mapped_sources(execution.statement, frozenset(criteria))
        execution.statement = execution.statement.options(*(with_loader_criteria(model, clause, include_aliases=True,
            propagate_to_loaders=True) for model, clause in criteria.items()))
    def deny_commit(*args):
        fail('Native commercial resource cannot commit its parent transaction', 403)
    event.listen(native, 'do_orm_execute', restrict)
    event.listen(native, 'before_flush', command.validate)
    event.listen(native, 'before_commit', deny_commit)
    try:
        link_project_service(command.project_id, LinkInput(customer_id=command.data.customer_id,
            seller_id=scope.company_id, currency=command.data.currency), native, actor, commit=False)
        if (command.root is None or len([row for row in command.minted if type(row) is ProjectCommercial]) != 1
                or len([row for row in command.minted if type(row) is SRMAuditLog]) != 1):
            fail('Native linking must produce one actual canonical link and one audit', 403)
        for row in command.minted:
            if type(row) is SRMAuditLog:
                from app.branches.models import BranchOwnership
                from .models import PackRecordOwnership
                for table, extra in ((BranchOwnership.__table__, {}), (PackRecordOwnership.__table__, {'context_id': scope.context_id, 'revision': 1})):
                    connection.execute(table.insert().values(resource_table=row.__tablename__, resource_key=str(row.id),
                        company_id=scope.company_id, branch_id=scope.branch_id, source='construction-commercial-native', **extra))
        command.current()
        if reads.fingerprint != _CommercialReads(connection, scope.company_id, command.data.customer_id).fingerprint:
            fail('Native commercial authority source changed', 403)
        event.remove(native, 'before_commit', deny_commit)
        Session.commit(native)
        return _payload(command.root, command.project_id)
    finally:
        native.close()


def validate_record(db, scope, row):
    if type(row) is not IndustryRecord or row.kind != 'commercial_link':
        return
    command = _COMMANDS.get(db)
    if inspect(row).persistent:
        stored = db.connection().execute(select(IndustryRecord.__table__).where(IndustryRecord.__table__.c.id == row.id)).first()
        if (row.data != stored.data or row.status != stored.status or row.revision != stored.revision
                or any(getattr(row, name) != getattr(stored, name) for name in ('kind', 'project_id', 'parent_id', 'invoice_id', 'title', 'created_by', 'request_id'))):
            fail('Commercial identity provenance is immutable', 403)
        return
    if (type(command) is not _Link or command.record is not row or command.scope is not scope
            or row.project_id != command.project_id or row.kind != 'commercial_link' or row.status != 'linked'
            or row.created_by != command.actor.id or row.parent_id is not None or row.invoice_id is not None
            or row.data != command.expected_record):
        fail('A genuine native commercial link command is required', 403)
    command.current()


@router.get('/projects/{project_id}/commercial-source')
def commercial_source(project_id: int, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    scope = _access(db, actor, project_id)
    row = _current(db, project_id)
    if row:
        if row.seller_id != scope.company_id:
            fail('Reconcile the project seller before using Construction billing')
        customer(db, row.customer_id, actor)
        seller(db, scope.company_id, actor)
    return _payload(row, project_id, locked=_priced(db, project_id))


@router.post('/projects/{project_id}/commercial-source')
def link_commercial(project_id: int, data: CommercialInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    from app.apps.srm.industry_api import digest, query
    scope = _access(db, actor, project_id, write=True)
    customer(db, data.customer_id, actor)
    seller(db, scope.company_id, actor)
    from .construction import authorize_retry_project
    authorize_retry_project(db, actor, data.request_id)
    old = query(db, actor, scope.branch_id).filter_by(request_id=str(data.request_id)).first()
    if old:
        if old.kind != 'commercial_link' or old.project_id != project_id or old.data['_request_digest'] != digest(data):
            fail('Commercial request was already used with different details')
        return old.data['native_result']
    current = _current(db, project_id)
    if current and (current.customer_id, current.seller_id, current.currency) == (data.customer_id, scope.company_id, data.currency):
        return _payload(current, project_id, locked=_priced(db, project_id))
    if _priced(db, project_id):
        fail('Configure the commercial identity before preparing any project BOQ or measurement')
    if current and any(getattr(current, key) is not None for key in _ADVANCED):
        fail('Preserve advanced native commercial links; use their reviewed native reconciliation workflow')
    command = _Link(db, actor, scope, project_id, data, current)
    try:
        with db.begin_nested():
            result = _native(command)
            row = IndustryRecord(organization_id=scope.company_id, branch_id=scope.branch_id, project_id=project_id,
                kind='commercial_link', title='Canonical PMS commercial identity', status='linked', revision=1,
                request_id=str(data.request_id), created_by=actor.id,
                data={'_request_digest': digest(data), 'native_result': result})
            command.record, command.expected_record = row, row.data.copy()
            _COMMANDS[db] = command
            db.add(row); db.flush()
            command.current()
        command.current()
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        _COMMANDS.pop(db, None)
