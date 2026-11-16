"""Client certificates and handover evidence; native invoices remain the money source."""
import csv
import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app.apps.srm.industry_models import IndustryRecord
from .access import PackScope
from .boundary import _current
from .common_core import _native_authority
from .construction import _source, project_for_action
from .operations import require

KINDS = frozenset({'payment_certificate', 'handover'})
_COMMANDS = WeakKeyDictionary()
router = APIRouter(tags=['Construction delivery documents'])


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CertificateInput(Strict):
    request_id: UUID
    title: str = Field(min_length=1, max_length=220)
    measurement_id: int = Field(gt=0)


class ChecklistItem(Strict):
    label: str = Field(min_length=1, max_length=500)
    complete: bool


class HandoverInput(Strict):
    request_id: UUID
    title: str = Field(min_length=1, max_length=220)
    project_id: int = Field(gt=0)
    checklist: list[ChecklistItem] = Field(min_length=1, max_length=100)
    file_ids: list[int] = Field(min_length=1, max_length=100)
    task_ids: list[int] = Field(default_factory=list, max_length=500)
    blockers: str = Field(default='', max_length=4000)


class ReviewInput(Strict):
    expected_revision: int = Field(ge=1)
    status: Literal['approved', 'rejected']
    reason: str = Field(default='', max_length=2000)


class HandoverUpdate(Strict):
    expected_revision: int = Field(ge=1)
    checklist: list[ChecklistItem] = Field(min_length=1, max_length=100)
    file_ids: list[int] = Field(min_length=1, max_length=100)
    task_ids: list[int] = Field(default_factory=list, max_length=500)
    blockers: str = Field(default='', max_length=4000)


def fail(message, status=409):
    raise HTTPException(status, message)


def _access(db, actor, *, write=False, financial=False, approval=False):
    from app.apps.srm.industry_api import context
    scope = db.info.get('business_pack_scope')
    if not isinstance(scope, PackScope) or scope.pack_key != 'construction' or scope.user_id != actor.id:
        fail('A selected Construction delivery context is required', 403)
    require(db, actor, *(['billing.prepare', 'boq.approve'] if approval else
        ['billing.prepare'] if financial and write else ['reports.view', 'billing.view', 'billing.prepare']
        if financial else ['diary.record'] if write else ['sites.view']))
    _current(scope, db.connection())
    authority = _native_authority(db, actor, scope.company_id)
    context(db, actor, write=write, finance=financial and write)
    if authority != _native_authority(db, actor, scope.company_id):
        fail('Native Construction delivery authority changed while waiting', 403)
    if financial:
        from app.apps.srm.services.commercial import require as native_require
        native_require(actor, 'srm_invoice_view', 'srm_invoice_create', 'srm_invoice_approve',
                       'srm_collection_view', 'srm_collection_create', 'srm_admin')
    _current(scope, db.connection())
    return scope


def _measurement_snapshot(db, actor, measurement_id):
    from app.apps.srm.industry_api import get
    from app.apps.srm.services.commercial import invoice_for, money
    from .construction_billing import assert_invoice_source
    scope = db.info['business_pack_scope']
    measurement = get(db, actor, scope.branch_id, measurement_id, 'measurement')
    if measurement.status != 'approved' or measurement.invoice_id is None:
        fail('A payment certificate requires an approved measurement and issued native invoice')
    invoice = invoice_for(db, measurement.invoice_id, actor, lock=True)
    if invoice.approved_at is None or invoice.status in {'draft', 'pending_approval', 'cancelled'}:
        fail('Issue the certified measurement invoice before preparing its payment certificate')
    if not assert_invoice_source(db, invoice):
        fail('The payment certificate requires its original certified native invoice', 403)
    data = measurement.data
    quantity, rate, tax = (Decimal(data[key]) for key in ('quantity', 'unit_rate', 'tax_rate'))
    retention = money(Decimal(data.get('retention_amount', '0')))
    return measurement, invoice, {
        'measurement_id': measurement.id, 'measurement_revision': measurement.revision,
        'boq_id': measurement.parent_id, 'boq_code': data.get('boq_code', ''),
        'measured_on': data['measured_on'], 'unit': data['unit'], 'quantity': str(quantity),
        'unit_rate': str(rate), 'tax_rate': str(tax), 'currency': data['currency'],
        'invoice_id': invoice.id, 'invoice_number': invoice.invoice_number,
        'invoice_subtotal': str(money(invoice.subtotal)), 'invoice_tax': str(money(invoice.tax_amount)),
        'invoice_total': str(money(invoice.total_amount)), 'retention_percent': str(data.get('retention_percent', '0')),
        'retention_amount': str(retention), 'certified_net_payable': str(money(invoice.total_amount - retention)),
    }


def _same_financial_source(measurement, current, original):
    if current == original:
        return True
    marker = measurement.data.get('_work_package_attribution')
    if not isinstance(marker, dict):
        return False
    before, after = original.get('measurement_revision'), current.get('measurement_revision')
    return (type(before) is int and type(after) is int and after == before + 1
        and marker.get('from_revision') == before and marker.get('to_revision') == after == measurement.revision
        and marker.get('work_package_id') == measurement.data.get('work_package_id')
        and marker.get('task_id') == measurement.data.get('work_package_task_id')
        and marker.get('actor_id') != measurement.created_by and bool(str(marker.get('reason', '')).strip())
        and {key: value for key, value in current.items() if key != 'measurement_revision'}
            == {key: value for key, value in original.items() if key != 'measurement_revision'})


def _files(db, actor, project_id, file_ids):
    from .construction_documents import _owned_file
    result = []
    if len(set(file_ids)) != len(file_ids) or any(type(value) is not int or value <= 0 for value in file_ids):
        fail('Choose distinct canonical PMS project documents', 422)
    project_for_action(db, actor, project_id)
    for ident in file_ids:
        source = _owned_file(db, actor, ident)
        if source.project_id != project_id:
            fail('Handover documents must belong to this site', 404)
        if source.visibility == 'Work Evidence' and source.uploaded_by_user_id != actor.id:
            fail('Handover cannot expose another uploader\'s private evidence', 403)
        result.append({'id': source.id, 'name': source.original_name, 'size_bytes': source.size_bytes,
                       'version_number': source.version_number})
    return result


def _tasks(db, actor, project_id, task_ids):
    from .construction_planning import task_sources
    if len(set(task_ids)) != len(task_ids) or any(type(value) is not int or value <= 0 for value in task_ids):
        fail('Choose distinct canonical PMS task references', 422)
    tasks = task_sources(db, actor, project_id)
    if not set(task_ids).issubset({item['id'] for item in tasks}):
        fail('Handover tasks must be current owned tasks of this site', 404)
    return tasks


def _handover_sources(db, actor, row, *, ready):
    data = row.data
    files = _files(db, actor, row.project_id, data['file_ids'])
    tasks = _tasks(db, actor, row.project_id, data['task_ids'])
    if ready:
        from app.apps.project_management.api.router import DONE_STATUSES
        if data['blockers'].strip() or any(not item['complete'] for item in data['checklist']):
            fail('Resolve handover blockers and complete every checklist item before approval')
        if any(not item.get('completed_at') or item['status'] not in DONE_STATUSES
               for item in tasks):
            fail('Complete every current native project task before approving handover')
        if not files:
            fail('A handover requires its supporting canonical PMS documents')
    return json.loads(json.dumps({'files': files, 'tasks': tasks}, default=str))


def validate_record(db, scope, row):
    """Typed births/reviews only; approved evidence and source identity are immutable."""
    if type(row) is not IndustryRecord or row.kind not in KINDS:
        return
    if scope is None or scope.pack_key != 'construction':
        fail('Construction delivery records require their original selected context', 403)
    state = inspect(row)
    command = _COMMANDS.get(db)
    current = command is not None and command['row'] is row
    if current:
        _current(scope, db.connection())
        if command['authority'] != _native_authority(db, command['actor'], scope.company_id):
            fail('Construction delivery authority changed during its command', 403)
    if not state.persistent:
        if not current or command['action'] != 'create' or row.status != 'draft' or row.approved_by is not None:
            fail('Construction delivery records require a genuine native source command', 403)
        if row.kind == 'payment_certificate':
            measurement, invoice, snapshot = _measurement_snapshot(db, command['actor'], row.data['measurement_id'])
            if measurement.project_id != row.project_id or invoice.id != row.invoice_id or not _same_financial_source(measurement, snapshot, row.data['source_snapshot']):
                fail('Payment certificate differs from its canonical certified source', 403)
        else:
            _handover_sources(db, command['actor'], row, ready=False)
        return
    table = IndustryRecord.__table__
    stored = db.connection().execute(select(table).where(table.c.id == row.id)).mappings().one()
    if any(getattr(row, key) != stored[key] for key in
           ('kind', 'project_id', 'parent_id', 'invoice_id', 'created_by', 'request_id', 'title')):
        fail('Construction delivery source identity is immutable', 403)
    if row.data != stored['data'] or row.status != stored['status'] or row.revision != stored['revision'] or row.approved_by != stored['approved_by']:
        if not current or command['action'] not in {'approved', 'rejected', 'revise'}:
            fail('Only independent native delivery review may change this record', 403)
        if command['action'] == 'revise':
            if (row.kind != 'handover' or stored['status'] != 'draft' or row.status != 'draft'
                    or row.approved_by is not None or row.revision != stored['revision'] + 1
                    or row.data != command['next_data']):
                fail('Only a native draft handover revision is permitted', 403)
            _handover_sources(db, command['actor'], row, ready=False)
            return
        old_data = dict(stored['data'])
        next_data = {**old_data, 'transition_reason': command['reason']}
        if command['action'] == 'approved':
            next_data.update(command['approval_data'])
        if (stored['status'] != 'draft' or row.created_by == command['actor'].id
                or row.status != command['action'] or row.revision != stored['revision'] + 1
                or row.approved_by != command['actor'].id or row.data != next_data):
            fail('Delivery review differs from the independent native command', 403)


@event.listens_for(IndustryRecord, 'before_insert')
def _mint_delivery(mapper, connection, row):
    if row.kind in KINDS:
        db = inspect(row).session
        scope = db.info.get('business_pack_scope')
        validate_record(db, scope, row)


def _create(db, actor, scope, kind, data, *, project_id, invoice_id=None, extra):
    from app.apps.srm.industry_api import existing, out
    old = existing(db, actor, scope.branch_id, data, kind)
    if old is not None:
        return out(old)
    if db in _COMMANDS:
        fail('Construction delivery commands cannot nest', 403)
    # The canonical helper flushes immediately: mint the instance first so the
    # source validator can certify this exact object rather than a caller flag.
    from app.apps.srm.industry_api import digest, audit
    row = IndustryRecord(organization_id=scope.company_id, branch_id=scope.branch_id, kind=kind,
        title=data.title, request_id=str(data.request_id), project_id=project_id, invoice_id=invoice_id,
        status='draft', revision=1, created_by=actor.id,
        data={**data.model_dump(mode='json', exclude={'request_id', 'title'}), '_request_digest': digest(data), **extra})
    _COMMANDS[db] = {'row': row, 'actor': actor, 'action': 'create',
                     'authority': _native_authority(db, actor, scope.company_id)}
    try:
        db.add(row); db.flush()
        audit(db, actor, row, kind + '_prepared')
        validate_record(db, scope, row)
        db.commit()
        return out(row)
    finally:
        _COMMANDS.pop(db, None)


def certificate(data: CertificateInput, db, actor):
    from app.apps.srm.industry_api import existing, out, query
    scope = _access(db, actor, write=True, financial=True)
    old = existing(db, actor, scope.branch_id, data, 'payment_certificate')
    if old is not None:
        return out(old)
    measurement, invoice, snapshot = _measurement_snapshot(db, actor, data.measurement_id)
    project_for_action(db, actor, measurement.project_id, 'browse')
    if any(row.data.get('measurement_id') == measurement.id for row in
           query(db, actor, scope.branch_id).filter_by(project_id=measurement.project_id, kind='payment_certificate').all()):
        fail('This certified measurement already has its distinct payment certificate')
    return _create(db, actor, scope, 'payment_certificate', data, project_id=measurement.project_id,
                   invoice_id=invoice.id, extra={'source_snapshot': snapshot, 'document_type': 'Construction payment certificate'})


def handover(data: HandoverInput, db, actor):
    scope = _access(db, actor, write=True)
    project_for_action(db, actor, data.project_id, 'manage_tasks')
    _files(db, actor, data.project_id, data.file_ids)
    _tasks(db, actor, data.project_id, data.task_ids)
    return _create(db, actor, scope, 'handover', data, project_id=data.project_id,
                   extra={'document_type': 'Construction project handover'})


def update_handover(ident, data: HandoverUpdate, db, actor):
    from app.apps.srm.industry_api import get, revision, save
    scope = _access(db, actor, write=True)
    row = get(db, actor, scope.branch_id, ident, 'handover')
    project_for_action(db, actor, row.project_id, 'manage_tasks')
    revision(row, data.expected_revision)
    if row.status != 'draft':
        fail('Approved or rejected handovers retain their historical evidence')
    next_data = {**row.data, **data.model_dump(mode='json', exclude={'expected_revision'})}
    if db in _COMMANDS:
        fail('Construction delivery commands cannot nest', 403)
    _COMMANDS[db] = {'row': row, 'actor': actor, 'action': 'revise', 'next_data': next_data,
                     'authority': _native_authority(db, actor, scope.company_id)}
    try:
        row.data = next_data
        return save(db, actor, row, 'handover_revised')
    finally:
        _COMMANDS.pop(db, None)


def transition(ident, data: ReviewInput, db, actor):
    from app.apps.srm.industry_api import get, revision, save
    scope = _access(db, actor, write=True, approval=True)
    row = get(db, actor, scope.branch_id, ident)
    if row.kind not in KINDS:
        fail('Choose a Construction certificate or handover', 404)
    project_for_action(db, actor, row.project_id, 'approve')
    revision(row, data.expected_revision)
    if row.status != 'draft':
        fail('Only draft delivery records can be independently approved or rejected')
    if row.created_by == actor.id:
        fail('A different native project approver must review this delivery record', 403)
    if data.status == 'rejected' and not data.reason.strip():
        fail('Enter the independent reviewer\'s rejection reason', 422)
    approval_data = {}
    if data.status == 'approved':
        if row.kind == 'payment_certificate':
            _access(db, actor, financial=True)
            measurement, invoice, snapshot = _measurement_snapshot(db, actor, row.data['measurement_id'])
            if measurement.project_id != row.project_id or invoice.id != row.invoice_id or not _same_financial_source(measurement, snapshot, row.data['source_snapshot']):
                fail('Reconcile the certified invoice source before approving the certificate')
        else:
            approval_data['approved_sources'] = _handover_sources(db, actor, row, ready=True)
        approval_data['approved_at'] = datetime.now(timezone.utc).isoformat()
    if db in _COMMANDS:
        fail('Construction delivery commands cannot nest', 403)
    _COMMANDS[db] = {'row': row, 'actor': actor, 'action': data.status,
                     'reason': data.reason, 'approval_data': approval_data,
                     'authority': _native_authority(db, actor, scope.company_id)}
    try:
        row.status, row.approved_by = data.status, actor.id
        row.data = {**row.data, 'transition_reason': data.reason, **approval_data}
        return save(db, actor, row, 'delivery_' + data.status)
    finally:
        _COMMANDS.pop(db, None)


def client_report(db, actor, project_id, metrics=None):
    from app.apps.srm.industry_api import query, out, summary
    from app.apps.srm.services.commercial import invoice_for, money
    scope = _access(db, actor, financial=True)
    project = project_for_action(db, actor, project_id)
    rows = query(db, actor, scope.branch_id).filter_by(project_id=project_id).order_by(IndustryRecord.id).all()
    invoices = []
    for row in rows:
        if row.kind != 'measurement' or row.invoice_id is None:
            continue
        invoice = invoice_for(db, row.invoice_id, actor)
        invoices.append({'measurement_id': row.id, 'invoice_id': invoice.id, 'invoice_number': invoice.invoice_number,
            'currency': invoice.currency, 'invoice_total': str(money(invoice.total_amount)),
            'collected': str(money(invoice.paid_amount)), 'outstanding': str(money(invoice.balance_amount))})
    return {'document_type': 'Construction client progress report', 'project_id': project_id, 'project_name': project.name,
        'generated_at': datetime.now(timezone.utc).isoformat(), 'commercial': summary(project_id, db, actor),
        'planning': metrics, 'native_invoices': invoices,
        'payment_certificates': [out(row) for row in rows if row.kind == 'payment_certificate'],
        'handovers': [out(row) for row in rows if row.kind == 'handover']}


def export_record(db, actor, ident, format='json'):
    from app.apps.srm.industry_api import get, out
    scope = _access(db, actor)
    row = get(db, actor, scope.branch_id, ident)
    if row.kind not in KINDS:
        fail('Delivery export is not available for this record', 404)
    if row.status != 'approved':
        fail('Approve the distinct certificate or handover before downloading its final document')
    if row.kind == 'payment_certificate':
        _access(db, actor, financial=True)
    return export_data(out(row), f'construction-{row.kind}-{row.id}', format)


def export_data(data, name, format='json'):
    if format == 'json':
        return json.dumps(data, indent=2, default=str).encode(), 'application/json', name + '.json'
    if format != 'csv':
        fail('Choose JSON or CSV export', 422)
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['field', 'value'])
    def safe(value):
        value = str(value)
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value
    def emit(value, prefix=''):
        if isinstance(value, dict):
            for key, item in value.items():
                emit(item, f'{prefix}.{key}' if prefix else key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                emit(item, f'{prefix}[{index}]')
        else:
            writer.writerow([safe(prefix), safe(value)])
    emit(data)
    return output.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8', name + '.csv'


from app.core.deps import get_db, get_current_user


@router.post('/payment-certificates', status_code=201)
def prepare_certificate(data: CertificateInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    return certificate(data, db, actor)


@router.post('/handovers', status_code=201)
def prepare_handover(data: HandoverInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    return handover(data, db, actor)


@router.put('/handovers/{ident}')
def revise_handover(ident: int, data: HandoverUpdate, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    return update_handover(ident, data, db, actor)


@router.post('/delivery/{ident}/review')
def review_delivery(ident: int, data: ReviewInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    return transition(ident, data, db, actor)


@router.get('/delivery/{ident}/export')
def download_delivery(ident: int, format: Literal['json', 'csv'] = 'json',
        db: Session = Depends(get_db), actor=Depends(get_current_user)):
    content, media_type, filename = export_record(db, actor, ident, format)
    return Response(content, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="{filename}"'})
