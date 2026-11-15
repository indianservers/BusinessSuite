"""One fixed project-consumption command over canonical native stock.

An issued IndustryRecord is the durable source. No balance mapper, general
stock mutation, shared-master write or cross-pack history is granted.
"""
from dataclasses import dataclass
from copy import deepcopy
from decimal import Decimal
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import inspect, select

from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMInventoryBalance, SRMInventoryMovement, SRMProduct, SRMWarehouse

_ACTIVE = WeakKeyDictionary()
_FIELDS = ('organization_id','branch_id','kind','title','status','revision','request_id',
           'created_by','project_id','customer_id','parent_id','invoice_id','stock_movement_id','data')
_NUMBERS = frozenset({'quantity_in','quantity_out','rate','value'})
_MOVEMENT_FIELDS = frozenset({'organization_id','movement_number','movement_type','movement_date',
    'product_id','warehouse_id','quantity_in','quantity_out','rate','value','reference_number','notes','created_by'})


def fail(message, status=403):
    raise HTTPException(status, message)


@dataclass
class _Command:
    scope: object
    actor: object
    expected: dict
    root: object = None
    movement: object = None
    movement_values: dict = None


def _authority(db, actor, project_id):
    from app.apps.srm.industry_api import context, require_pack_operation
    from app.access.service import check_background_access
    from .boundary import _current
    from .common_core import _native_authority
    from .construction import project_for_action, _project_epoch
    # The finite command must retain the native write ceiling even when called
    # by another server operation rather than the foreground HTTP dependency.
    check_background_access(db, actor, 'srm', 'create', stamp=False)
    branch = context(db, actor, True)
    check_background_access(db, actor, 'srm', 'create', stamp=False)
    require_pack_operation(db, actor, 'materials.request')
    scope = db.info.get('business_pack_scope')
    if scope is None or scope.pack_key != 'construction' or branch != scope.branch_id:
        fail('An authorized Construction material context is required')
    _current(scope, db.connection())
    project_for_action(db, actor, project_id, 'manage_tasks')
    return scope, (_native_authority(db, actor, scope.company_id), _project_epoch(db, scope, project_id))


def _same_movement(row, expected):
    if not isinstance(expected, dict) or set(expected) != _MOVEMENT_FIELDS:
        return False
    for name, value in expected.items():
        actual = row[name] if hasattr(row, 'keys') else getattr(row, name)
        if name in _NUMBERS:
            if actual is None or Decimal(str(actual)) != Decimal(str(value)):
                return False
        elif name == 'movement_date':
            if actual.isoformat() != value:
                return False
        elif actual != value:
            return False
    return True


def validate_item(db, scope, item):
    """A finite source/instance certificate, never a caller-supplied purpose."""
    state = inspect(item)
    command = _ACTIVE.get(db)
    old_material = False
    if type(item) is IndustryRecord and state.persistent and state.attrs.kind.history.has_changes():
        old_material = db.connection().scalar(select(IndustryRecord.__table__.c.kind).where(
            IndustryRecord.__table__.c.id == state.identity[0])) == 'material_issue'
    if type(item) is IndustryRecord and (item.kind == 'material_issue' or old_material):
        if command is not None and command.scope is scope:
            if command.root is None and item in db.new:
                command.root = item
            if command.root is item:
                if item in db.deleted or any(getattr(item, name) != value for name, value in command.expected.items()):
                    fail('Construction material source differs from its native command')
                return
        if item in db.new or item in db.deleted or any(attr.history.has_changes() for attr in state.attrs):
            fail('Issued Construction material sources are immutable')
    if type(item) is SRMInventoryMovement:
        from_industry = type(getattr(item, '_suite_source_record', None)) is IndustryRecord
        old_kind = None
        if state.persistent and state.identity:
            table = SRMInventoryMovement.__table__
            old_kind = db.connection().scalar(select(table.c.movement_type).where(table.c.id == state.identity[0]))
        if from_industry or item.movement_type == 'project_consumption' or old_kind == 'project_consumption':
            if command is not None and command.scope is scope and command.movement is item:
                if item in db.deleted or not _same_movement(item, command.movement_values):
                    fail('Project consumption differs from its certified material source')
                if getattr(item, '_suite_source_record', None) is not command.root:
                    fail('Project consumption requires the actual persisted material source')
                return
            if item in db.new or item in db.deleted or any(attr.history.has_changes() for attr in state.attrs):
                fail('Project consumption requires its fixed Construction command')


def _verify(db, scope, row):
    from app.apps.srm.service_checkout import _source_scope
    from app.apps.srm.industry_api import MaterialInput, digest
    state = inspect(row)
    if type(row) is not IndustryRecord or state.session is not db or not state.persistent or state.identity != (row.id,):
        fail('Material issue requires its actual persisted native source')
    _source_scope(db, scope, scope.company_id, scope.branch_id, IndustryRecord, row.id)
    table = IndustryRecord.__table__
    actual = db.connection().execute(select(*(table.c[name] for name in _FIELDS)).where(table.c.id == row.id)).mappings().one()
    if any(getattr(row, name) != actual[name] for name in _FIELDS):
        fail('Material issue differs from its persisted source')
    source = row.data.get('_material_source')
    if row.kind != 'material_issue' or row.status != 'issued' or not isinstance(source,dict) or type(source.get('version')) is not int or source['version'] != 1 or not row.stock_movement_id:
        fail('Material issue requires native source reconciliation', 409)
    try:
        payload = MaterialInput.model_validate({'request_id':row.request_id,'title':row.title,
            **{key:row.data[key] for key in MaterialInput.model_fields if key not in {'request_id','title'}}})
    except (ValueError, KeyError, TypeError):
        fail('Material source input requires reconciliation', 409)
    if digest(payload) != row.data.get('_request_digest') or payload.project_id != row.project_id:
        fail('Material source input changed', 409)
    expected=source.get('movement')
    if not isinstance(expected,dict) or set(expected)!=_MOVEMENT_FIELDS:
        fail('Material stock provenance requires reconciliation',409)
    if (expected['organization_id'],expected['created_by'],expected['product_id'],expected['warehouse_id'],
        expected['movement_type'],expected['movement_date'],expected['reference_number'],expected['notes']) != (
        scope.company_id,row.created_by,payload.product_id,payload.warehouse_id,
        'project_consumption',payload.issue_date.isoformat(),f'PMS-{row.project_id}',payload.notes):
        fail('Material stock provenance differs from its input',409)
    try:
        if (Decimal(expected['quantity_out'])!=payload.quantity or Decimal(expected['quantity_in'])!=0
                or Decimal(expected['rate'])<=0 or Decimal(source['quantity_before'])<payload.quantity):
            fail('Material stock quantity requires reconciliation',409)
    except (ValueError,TypeError,KeyError,ArithmeticError):
        fail('Material stock quantity requires reconciliation',409)
    _source_scope(db, scope, scope.company_id, scope.branch_id, SRMInventoryMovement, row.stock_movement_id)
    movement = SRMInventoryMovement.__table__
    native = db.connection().execute(select(movement).where(movement.c.id == row.stock_movement_id)).mappings().one()
    if not _same_movement(native, source['movement']):
        fail('Material stock history requires reconciliation', 409)


def issue(data, db, actor):
    try:
        return _issue(data, db, actor)
    except BaseException:
        db.rollback()
        raise
    finally:
        _ACTIVE.pop(db, None)


def _issue(data, db, actor):
    from app.apps.srm import industry_api as native
    from app.apps.srm.service_checkout import _source_scope
    from app.apps.srm.stock_resource import _product, _native_branch, _write_quantity_cache
    from app.apps.srm.services.commercial import money
    from app.apps.srm.services.commercial_numbering import reserve_number
    from app.shared.settings import effective
    from .models import PackRecordOwnership
    scope, epoch = _authority(db, actor, data.project_id)
    previous = native.existing(db, actor, scope.branch_id, data, 'material_issue')
    if previous is not None:
        if previous.created_by != actor.id:
            fail('This material request belongs to another actor', 409)
        _verify(db, scope, previous)
        return native.out(previous)
    currency = effective(db, scope.company_id, 'srm')['values']['currency']
    product, physical = _product(db, data.product_id, scope.company_id, scope.branch_id, scope, currency)
    if not physical:
        fail('Choose an active quantity-only stock item for project consumption', 422)
    _source_scope(db, scope, scope.company_id, scope.branch_id, SRMWarehouse, data.warehouse_id, master=True)
    _native_branch(db, SRMWarehouse.__tablename__, data.warehouse_id, scope.company_id, scope.branch_id)
    warehouse = SRMWarehouse.__table__
    warehouse_row = db.connection().execute(select(warehouse.c.warehouse_name).where(
        warehouse.c.id == data.warehouse_id, warehouse.c.organization_id == scope.company_id,
        warehouse.c.active.is_(True)).with_for_update()).first()
    if warehouse_row is None:
        fail('Eligible project warehouse is unavailable', 404)
    balance = SRMInventoryBalance.__table__
    stored = db.connection().execute(select(balance.c.id, balance.c.quantity, balance.c.average_cost).where(
        balance.c.organization_id == scope.company_id, balance.c.product_id == data.product_id,
        balance.c.warehouse_id == data.warehouse_id).with_for_update()).first()
    if stored is None or stored.quantity is None or stored.quantity < data.quantity:
        fail('Insufficient eligible stock for project materials', 409)
    owner = PackRecordOwnership.__table__
    if db.connection().scalar(select(owner.c.id).where(owner.c.resource_table == balance.name, owner.c.resource_key == str(stored.id))):
        fail('A canonical stock balance cannot adopt private ownership')
    master = SRMProduct.__table__
    details = db.connection().execute(select(master.c.item_name, master.c.average_cost).where(
        master.c.id == data.product_id, master.c.organization_id == scope.company_id)).one()
    rate = Decimal(stored.average_cost or details.average_cost or 0)
    if rate <= 0:
        fail('Record a valued native receipt before issuing project materials', 409)
    if _authority(db, actor, data.project_id) != (scope, epoch):
        fail('Project material authority changed while waiting')
    values = data.model_dump(mode='json', exclude={'request_id','title'})
    command = _Command(scope, actor, dict(organization_id=scope.company_id, branch_id=scope.branch_id,
        kind='material_issue',title=data.title,status='draft',revision=1,request_id=str(data.request_id),
        created_by=actor.id,project_id=data.project_id,customer_id=None,parent_id=None,invoice_id=None,
        stock_movement_id=None,data={**values,'_request_digest':native.digest(data)}))
    _ACTIVE[db] = command
    row = native.create(db, actor, scope.branch_id, 'material_issue', data, project_id=data.project_id)
    movement_values = dict(organization_id=scope.company_id,
        movement_number=reserve_number(db, SRMInventoryMovement, 'INV', 'movement_number', scope.company_id, actor=actor),
        movement_type='project_consumption',movement_date=data.issue_date.isoformat(),product_id=data.product_id,
        warehouse_id=data.warehouse_id,quantity_in='0.000',quantity_out=str(data.quantity),rate=str(rate),
        value=str(money(data.quantity*rate)),reference_number=f'PMS-{data.project_id}',notes=data.notes,created_by=actor.id)
    source={'version':1,'balance_id':stored.id,'quantity_before':str(stored.quantity),'movement':movement_values}
    new_data={**row.data,'product_name':details.item_name,'warehouse_name':warehouse_row.warehouse_name,
              'movement_number':movement_values['movement_number'],'_material_source':source}
    # Keep input provenance separate from server-derived display snapshots.
    command.expected['data']=deepcopy(new_data);row.data=new_data;db.flush()
    changed=db.connection().execute(balance.update().where(balance.c.id==stored.id,
        balance.c.organization_id==scope.company_id,balance.c.product_id==data.product_id,
        balance.c.warehouse_id==data.warehouse_id,balance.c.quantity==stored.quantity).values(quantity=stored.quantity-data.quantity))
    if changed.rowcount != 1:
        fail('Project stock changed; retry the original material request', 409)
    movement=SRMInventoryMovement(**{**movement_values,'movement_date':data.issue_date,
        **{name:Decimal(movement_values[name]) for name in _NUMBERS}})
    movement._suite_source_record=row;command.movement=movement;command.movement_values=deepcopy(movement_values)
    db.add(movement);db.flush()
    command.expected.update(status='issued',stock_movement_id=movement.id)
    row.status='issued';row.stock_movement_id=movement.id;db.flush()
    _write_quantity_cache(db,data.product_id,scope.company_id)
    native.audit(db,actor,row,'stock_issued')
    if _authority(db,actor,data.project_id)!=(scope,epoch):
        fail('Project material authority changed before completion')
    _verify(db,scope,row)
    output=native.out(row);db.commit()
    return output
