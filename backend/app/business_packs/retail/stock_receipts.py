"""Fixed Retail receipt command over native GRNs and canonical warehouse stock."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from uuid import UUID
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, inspect

from app.apps.srm.models import SRMGoodsReceipt, SRMGoodsReceiptLine, SRMInventoryMovement, SRMInventoryBalance
from app.apps.srm.service_checkout import _authority, _source_scope
from app.apps.srm.stock_resource import _product, _native_branch, _write_quantity_cache
from app.business_packs.models import PackRecordOwnership

_ACTIVE = WeakKeyDictionary()


class ReceiptInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: UUID
    product_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    unit_cost: Decimal = Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    currency: str = Field(default='INR', pattern=r'^[A-Z]{3}$')
    received_date: date
    reference_number: str = Field(default='', max_length=120)
    notes: str = Field(default='', max_length=4000)


def fail(message, status=403):
    raise HTTPException(status, message)


def authority(db, actor, action, *, write=False):
    from app.apps.srm.services.commercial import require
    require(actor, *('srm_manage', 'srm_admin') if write else ('srm_view', 'srm_manage', 'srm_admin'))
    company, branch, scope = _authority(db, actor, order=write, write=write)
    if scope is None or scope.pack_key != 'retail' or 'retail.' + action not in scope.capabilities:
        fail('Select an authorized Retail context for this operation')
    installed = db.info.get('business_pack_scope')
    if installed != scope:
        fail('Verified Retail request scope changed')
    from app.business_packs.native_policy import native_srm_policy
    if db.info.get('business_pack_policy') != native_srm_policy('retail').policy:
        fail('Audited Retail isolation adapter is not installed', 503)
    return company, branch, installed


def _values(item):
    return {column.name: deepcopy(getattr(item, column.name)) for column in inspect(item).mapper.columns
            if column.name not in {'id', 'created_at'}}


def validate_item(db, scope, item):
    """Boundary hook: only exact command instances may create native Retail GRNs."""
    state = inspect(item)
    is_receipt = type(item) in (SRMGoodsReceipt, SRMGoodsReceiptLine)
    is_movement = type(item) is SRMInventoryMovement and (
        item.movement_type == 'retail_receipt' or type(getattr(item, '_suite_source_record', None)) is SRMGoodsReceiptLine)
    if not is_receipt and not is_movement:
        return
    command = _ACTIVE.get(db)
    planned = command[1].get(item) if command and command[0] is scope else None
    if item in db.deleted or planned is None or _values(item) != planned:
        if item in db.new or item in db.deleted or any(attr.history.has_changes() for attr in state.attrs):
            fail('Native Retail receipt sources require the fixed immutable stock command')
    if is_movement and item in db.new:
        source = getattr(item, '_suite_source_record', None)
        if command is None or source not in command[1] or not inspect(source).persistent:
            fail('Retail receipt movement requires its actual persisted GRN line')


def result(db, scope, row):
    _source_scope(db, scope, scope.company_id, scope.branch_id, SRMGoodsReceipt, row.id)
    lines = db.query(SRMGoodsReceiptLine).filter_by(goods_receipt_id=row.id).all()
    if row.status != 'posted' or len(lines) != 1:
        fail('Native Retail receipt requires reconciliation', 409)
    line = lines[0]
    _source_scope(db, scope, scope.company_id, scope.branch_id, SRMGoodsReceiptLine, line.id)
    movement = db.query(SRMInventoryMovement).filter_by(organization_id=scope.company_id,
        reference_number='RETAIL-GRN-LINE-' + str(line.id), movement_type='retail_receipt').one_or_none()
    if movement is None or (movement.product_id, movement.warehouse_id, movement.quantity_in,
            movement.quantity_out, movement.rate, movement.value, movement.created_by, movement.movement_date) != (
            line.product_id, line.warehouse_id, line.accepted_quantity, 0, line.unit_price,
            line.line_total, row.created_by, row.receipt_date):
        fail('Native Retail receipt stock provenance differs', 409)
    _source_scope(db, scope, scope.company_id, scope.branch_id, SRMInventoryMovement, movement.id)
    return {'id': row.id, 'number': row.grn_number, 'movement_id': movement.id, 'state': 'committed',
            'product_id': line.product_id, 'warehouse_id': line.warehouse_id,
            'quantity': format(line.accepted_quantity, '.3f'), 'unit_cost': format(line.unit_price, '.2f')}


def create(data, db, actor):
    if db in _ACTIVE or db.in_nested_transaction():
        fail('Retail stock receipts cannot nest inside another command', 409)
    data = ReceiptInput.model_validate(data.model_dump())
    from app.apps.srm.services.commercial import lock_tenant
    from app.apps.srm.models import SRMWarehouse
    company, branch, scope = authority(db, actor, 'stock.receive', write=True)
    lock_tenant(db, actor)
    if authority(db, actor, 'stock.receive', write=True) != (company, branch, scope):
        fail('Retail receipt authorization changed while waiting')
    payload = data.model_dump(mode='json', exclude={'reference_number', 'notes'})
    # Keep pre-wiring request hashes stable when these optional native fields are absent.
    payload.update({key: getattr(data, key) for key in ('reference_number', 'notes') if getattr(data, key)})
    fingerprint = sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    number = 'RGRN-' + str(data.request_key)
    prior = db.query(SRMGoodsReceipt).filter_by(organization_id=company, grn_number=number).one_or_none()
    if prior is not None:
        if prior.created_by != actor.id or (prior.metadata_json or {}).get('request_sha256') != fingerprint:
            fail('Receipt request key was already used for another command', 409)
        return result(db, scope, prior)
    # Global native number uniqueness must never adopt a foreign pack's GRN.
    if db.connection().scalar(select(SRMGoodsReceipt.id).where(SRMGoodsReceipt.organization_id == company, SRMGoodsReceipt.grn_number == number)):
        fail('Receipt request key is unavailable', 409)
    with db.begin_nested():
        if data.received_date > date.today():
            fail('Stock receipt date cannot be in the future', 422)
        product, physical = _product(db, data.product_id, company, branch, scope, data.currency)
        if not physical:
            fail('Retail receipts require an eligible quantity-only physical product', 409)
        from app.business_packs.pharma.reads import workspace_bound
        if db.connection().scalar(select(workspace_bound(db, company, data.product_id))):
            fail('Workspace offerings are unavailable for Retail stock receipts', 409)
        warehouse = db.query(SRMWarehouse).filter_by(id=data.warehouse_id, organization_id=company, active=True).one_or_none()
        if warehouse is None:
            fail('Eligible warehouse is unavailable', 404)
        _source_scope(db, scope, company, branch, SRMWarehouse, warehouse.id, master=True)
        _native_branch(db, SRMWarehouse.__tablename__, warehouse.id, company, branch)
        balance = SRMInventoryBalance.__table__
        current = db.connection().execute(select(balance).where(balance.c.organization_id == company,
            balance.c.product_id == data.product_id, balance.c.warehouse_id == data.warehouse_id).with_for_update()).mappings().first()
        if current and db.connection().scalar(select(PackRecordOwnership.id).where(
                PackRecordOwnership.resource_table == balance.name, PackRecordOwnership.resource_key == str(current['id']))):
            fail('Canonical stock cannot adopt a privately owned balance')
        old = Decimal(current['quantity'] or 0) if current else Decimal(0)
        new = old + data.quantity
        if old < 0 or new >= Decimal('100000000000') or data.quantity * data.unit_cost >= Decimal('1000000000000'):
            fail('Receipt exceeds native stock capacity or requires reconciliation', 409)
        row = SRMGoodsReceipt(organization_id=company, grn_number=number, status='posted', receipt_date=data.received_date,
            subtotal=data.quantity * data.unit_cost, tax_amount=0, total_amount=data.quantity * data.unit_cost,
            metadata_json={'request_sha256': fingerprint, 'currency': data.currency}, created_by=actor.id,
            reference_number=data.reference_number or None, notes=data.notes or None)
        planned = {}
        _ACTIVE[db] = (scope, planned)
        try:
            planned[row] = _values(row)
            db.add(row); db.flush()
            line = SRMGoodsReceiptLine(goods_receipt_id=row.id, product_id=data.product_id, warehouse_id=data.warehouse_id,
                quantity=data.quantity, accepted_quantity=data.quantity, rejected_quantity=0, unit_price=data.unit_cost,
                tax_amount=0, line_total=data.quantity * data.unit_cost)
            planned[line] = _values(line)
            db.add(line); db.flush()
            average = (old * Decimal(current['average_cost'] or 0) + data.quantity * data.unit_cost) / new if current else data.unit_cost
            if current:
                changed = db.connection().execute(balance.update().where(balance.c.id == current['id'], balance.c.quantity == current['quantity']).values(quantity=new, average_cost=average))
                if changed.rowcount != 1:
                    fail('Stock changed; retry receipt', 409)
            else:
                db.connection().execute(balance.insert().values(organization_id=company, product_id=data.product_id,
                    warehouse_id=data.warehouse_id, quantity=new, average_cost=average))
            from app.apps.srm.services.commercial_numbering import reserve_number
            movement = SRMInventoryMovement(organization_id=company,
                movement_number=reserve_number(db, SRMInventoryMovement, 'INV', 'movement_number', company, actor=actor),
                movement_type='retail_receipt', movement_date=data.received_date, product_id=data.product_id,
                warehouse_id=data.warehouse_id, quantity_in=data.quantity, quantity_out=0, rate=data.unit_cost,
                value=data.quantity * data.unit_cost, reference_number='RETAIL-GRN-LINE-' + str(line.id),
                notes='Native Retail goods receipt', created_by=actor.id)
            movement._suite_source_record = line
            planned[movement] = _values(movement)
            db.add(movement); db.flush()
            _write_quantity_cache(db, data.product_id, company)
            response = result(db, scope, row)
        finally:
            _ACTIVE.pop(db, None)
    db.commit()
    return response


def list_receipts(db, actor, *, after=0, limit=100):
    company, branch, scope = authority(db, actor, 'stock.view')
    rows = db.query(SRMGoodsReceipt).filter(SRMGoodsReceipt.organization_id == company,
        SRMGoodsReceipt.id > after).order_by(SRMGoodsReceipt.id).limit(limit + 1).all()
    items = [{**result(db, scope, row), 'receipt_date': row.receipt_date.isoformat(),
              'currency': (row.metadata_json or {}).get('currency'), 'reference_number': row.reference_number} for row in rows[:limit]]
    return {'items': items, 'next_after': rows[limit - 1].id if len(rows) > limit else None}
