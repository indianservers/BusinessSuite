"""One explicit named-customer binding for an originally anonymous draft tab."""
from sqlalchemy import select
from app.apps.crm.models import CRMCompany
from .models import RestaurantServiceOrder as Order, RestaurantCommand as Command
from .service import fail, record, prior, save_command, digest
from .schemas import TabAssignCustomer
from .sources import private


def valid_birth(db, scope, order, native):
    """Preserve the original hash; an immutable command proves the only transition."""
    from .tabs import _birth
    table = Order.__table__
    original = db.connection().execute(select(table).where(table.c.id == order.id,
        table.c.sales_order_id == native['id'], table.c.organization_id == scope.company_id,
        table.c.branch_id == scope.branch_id, table.c.pack_context_id == scope.context_id,
        table.c.source_kind == 'unpaid_tab')).mappings().one_or_none()
    if original is None:
        return False
    command = Command.__table__
    commands = db.connection().execute(select(command).where(command.c.service_order_id == order.id,
        command.c.action.in_(('tab.assign_customer','tab.assign_anonymous')), command.c.organization_id == scope.company_id,
        command.c.branch_id == scope.branch_id, command.c.pack_context_id == scope.context_id)).mappings().all()
    if not commands:
        return original['source_sha256'] == _birth(scope, native)
    if len(commands) != 1:
        return False
    applied = commands[0]
    result = applied['result']
    private(db, scope, Command, applied['id'])
    if not isinstance(result, dict):
        return False
    if (type(result.get('customer_id')) is not int or result['customer_id'] < 1
            or result.get('previous_customer_id', 1) is not None or native['customer_id'] != result['customer_id']
            or result.get('id') != order.id or result.get('sales_order_id') != native['id']
            or result.get('original_source_sha256') != original['source_sha256']
            or original['source_sha256'] != _birth(scope, {**native, 'customer_id': None})
            or type(result.get('previous_revision')) is not int or result['previous_revision'] < 1
            or result.get('revision') != result['previous_revision']+1 or result['revision'] > original['revision']):
        return False
    try:
        payload = TabAssignCustomer(request_key=applied['request_key'], expected_revision=result['previous_revision'], customer_id=result['customer_id'])
    except ValueError:
        return False
    if digest(applied['action'], order.id, payload) != applied['request_sha256']:
        return False
    if applied['action'] == 'tab.assign_anonymous':
        from .anonymous import authorized_birth
        if not authorized_birth(db, scope, order, native, applied):
            return False
    customer = CRMCompany.__table__
    return db.connection().scalar(select(customer.c.id).where(customer.c.id == result['customer_id'], customer.c.organization_id == scope.company_id)) is not None


def assign(ident, data, db, actor, *, commit=True):
    from .tabs import writer, source
    from app.apps.srm.pos_surface import customer_query
    from app.apps.srm.access import get_sales_order_for_user
    from .references import customer_update
    scope, epoch = writer(db, actor)
    order = record(db, Order, scope, ident)
    source(db, actor, scope, order)
    replay = prior(db, actor, scope, 'tab.assign_customer', ident, data)
    if replay is not None:
        return replay
    if order.source_kind != 'unpaid_tab' or order.state != 'open' or order.revision != data.expected_revision:
        fail('Only the current unbilled walk-in tab can receive its first customer', 409)
    native = get_sales_order_for_user(db, order.sales_order_id, actor)
    if native.customer_id is not None:
        fail('A tab customer cannot be reassigned', 409)
    selected = customer_query(db, scope.company_id).filter(CRMCompany.id == data.customer_id).first()
    if selected is None:
        fail('Choose an available named customer in this Restaurant context', 404)
    with db.begin_nested():
        with customer_update(db, actor, scope, epoch, native, order, selected):
            native.customer_id = selected.id
            order.revision += 1
            db.flush()
        answer = save_command(db, actor, scope, 'tab.assign_customer', ident, data,
            {'id': order.id, 'sales_order_id': native.id, 'previous_customer_id': None, 'customer_id': selected.id,
             'previous_revision': data.expected_revision, 'revision': order.revision, 'original_source_sha256': order.source_sha256}, order=order)
        from app.apps.srm.api.router import _audit
        _audit(db, actor, 'sales_order', native.id, 'restaurant_customer_assigned')
        source(db, actor, scope, order)
    if commit:
        db.commit()
    return answer
