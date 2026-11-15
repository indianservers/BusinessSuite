from datetime import date
from fastapi import APIRouter, Depends, Query
from app.core.deps import get_db, get_current_user
from app.apps.srm.service_checkout_api import pack_selection
from .schemas import TableCreate, TableUpdate, PaidOrderOpen, KitchenSubmit, TicketTransition, TabCreate, TabAdd, TabBill, TabPayment, TabAssignCustomer, TabAnonymousSettle, TableTransfer
from .schemas import TabRemove, ReservationCreate, ReservationReschedule, ReservationTransition
from . import service

router = APIRouter(prefix='/srm/restaurant', tags=['Restaurant fulfillment'])

from .split_schemas import SplitBill, SplitPayment


@router.get('/tabs/{order_id}/bills')
def split_bills(order_id: int, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .split_bills import listing
    return listing(order_id, db, actor)


@router.post('/tabs/{order_id}/bills', status_code=201)
def split_bill(order_id: int, data: SplitBill, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .split_bills import issue
    return issue(order_id, data, db, actor)


@router.get('/tabs/{order_id}/bills/{bill_id}')
def split_bill_detail(order_id: int, bill_id: int, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .split_bills import listing
    result = listing(order_id, db, actor)
    bill = next((row for row in result['bills'] if row['bill_id'] == bill_id), None)
    if bill is None:
        service.fail('Restaurant split bill is unavailable', 404)
    return {**result, 'bills': [bill]}


@router.post('/tabs/{order_id}/bills/{bill_id}/payments', status_code=201)
def split_payment(order_id: int, bill_id: int, data: SplitPayment, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .split_bills import pay
    return pay(order_id, bill_id, data, db, actor)


@router.get('/capabilities')
def capabilities(db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    return service.capabilities(db, actor)


@router.get('/tables')
def tables(after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    return service.table_list(db, actor, after=after, limit=limit)


@router.get('/registers')
def registers(after: int = Query(0, ge=0), db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .settlement import registers
    return registers(db, actor, after=after)


@router.post('/tables', status_code=201)
def create_table(data: TableCreate, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    return service.table_write(data, db, actor)


@router.put('/tables/{table_id}')
def update_table(table_id: int, data: TableUpdate, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    return service.table_write(data, db, actor, ident=table_id)


@router.post('/paid-orders', status_code=201)
def open_paid(data: PaidOrderOpen, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    return service.open_paid_order(data, db, actor)


@router.get('/paid-orders/{checkout_id}/source')
def paid_source(checkout_id: int, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    return service.paid_order_source(checkout_id, db, actor)


@router.get('/menu')
def menu(search: str = Query('', max_length=100), after: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100),
         currency: str = Query('INR', pattern=r'^[A-Z]{3}$'), db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .tabs import menu
    return menu(db, actor, search=search, after=after, limit=limit, currency=currency)


@router.get('/customers')
def customers(search: str = Query('', max_length=100), after: int = Query(0, ge=0),
              db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    scope = service.authority(db, actor, 'orders.create')
    from app.apps.srm.commercial_api import DIRECTORY
    from app.apps.srm.pos_surface import customer_query
    from app.apps.srm.services.commercial import require
    from app.access.catalog import permission_objects
    from app.apps.crm.models import CRMCompany
    require(actor, *DIRECTORY)
    query = customer_query(db, scope.company_id).filter(CRMCompany.id > after)
    names = {permission.name for permission in permission_objects(actor)}
    if not actor.is_superuser and not names.intersection(set(DIRECTORY[3:])):
        from app.apps.crm.api.router import _apply_record_visibility, _get_resource
        query = _apply_record_visibility(query, _get_resource('companies'), actor, db)
    if search:
        query = query.filter(CRMCompany.name.contains(search, autoescape=True))
    rows = query.order_by(CRMCompany.id).limit(51).all()
    return {'items': [{'id': item.id, 'name': item.name} for item in rows[:50]], 'next': rows[49].id if len(rows) > 50 else None}


@router.post('/tabs', status_code=201)
def create_tab(data: TabCreate, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .tabs import create
    return create(data, db, actor)


@router.get('/tabs')
def active_tabs(after: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100), db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .tabs import active
    return active(db, actor, after=after, limit=limit)


@router.post('/tabs/{order_id}/items', status_code=201)
def add_tab_items(order_id: int, data: TabAdd, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .tabs import add
    return add(order_id, data, db, actor)


@router.get('/orders/{order_id}')
def order(order_id: int, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    return service.get_order(order_id, db, actor)


@router.post('/tabs/{order_id}/bill', status_code=201)
def bill_tab(order_id: int, data: TabBill, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .settlement import bill
    return bill(order_id, data, db, actor)


@router.post('/tabs/{order_id}/anonymous-settlement', status_code=201)
def anonymous_settlement(order_id: int, data: TabAnonymousSettle, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .anonymous import settle
    return settle(order_id, data, db, actor)


@router.post('/tabs/{order_id}/customer')
def assign_tab_customer(order_id: int, data: TabAssignCustomer, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .customers import assign
    return assign(order_id, data, db, actor)


@router.get('/tabs/{order_id}/billing')
def tab_billing(order_id: int, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .settlement import state
    return state(order_id, db, actor)


@router.post('/tabs/{order_id}/payments', status_code=201)
def tab_payment(order_id: int, data: TabPayment, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .settlement import payment
    return payment(order_id, data, db, actor)


@router.post('/orders/{order_id}/tickets', status_code=201)
def submit(order_id: int, data: KitchenSubmit, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    if order_id != data.service_order_id:
        service.fail('Order path and source must agree', 422)
    return service.submit(data, db, actor)


@router.get('/kitchen')
def kitchen(after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), include_served: bool = False, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    return service.kitchen(db, actor, after=after, limit=limit, include_served=include_served)


@router.post('/tickets/{ticket_id}/prepare')
def prepare(ticket_id: int, data: TicketTransition, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    return service.transition(ticket_id, 'prepare', data, db, actor)


@router.post('/tickets/{ticket_id}/ready')
def ready(ticket_id: int, data: TicketTransition, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    return service.transition(ticket_id, 'ready', data, db, actor)


@router.post('/tickets/{ticket_id}/serve')
def serve(ticket_id: int, data: TicketTransition, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    return service.transition(ticket_id, 'serve', data, db, actor)


@router.post('/tabs/{order_id}/transfer')
def transfer_tab(order_id: int, data: TableTransfer, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .transfers import transfer
    return transfer(order_id, data, db, actor)


@router.get('/daily-summary')
def daily_summary(day: date, timezone_name: str = Query('Asia/Kolkata', max_length=100), db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .reports import daily
    return daily(day, timezone_name, db, actor)


@router.post('/tabs/{order_id}/remove-items')
def remove_tab_items(order_id: int, data: TabRemove, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .removals import remove
    return remove(order_id, data, db, actor)


@router.get('/reservations')
def reservations(after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .reservations import listing
    return listing(db, actor, after=after, limit=limit)


@router.post('/reservations', status_code=201)
def create_reservation(data: ReservationCreate, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .reservations import save
    return save(data, db, actor)


@router.put('/reservations/{ident}')
def reschedule_reservation(ident: int, data: ReservationReschedule, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .reservations import save
    return save(data, db, actor, ident=ident)


@router.post('/reservations/{ident}/transition')
def transition_reservation(ident: int, data: ReservationTransition, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .reservations import transition
    return transition(ident, data, db, actor)
