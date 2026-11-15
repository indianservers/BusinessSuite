"""An unchanged historical assignee FK for one exact tab header update.

No User ORM visibility or assignment mutation is granted. Only four native
derived totals may change, alongside the tab's optimistic revision.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from weakref import WeakKeyDictionary
from sqlalchemy import and_, event, exists, inspect, or_, select
from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine
from app.models.user import User
from app.business_packs.native_checkout_authority import capture
from .models import RestaurantServiceOrder

_leases = WeakKeyDictionary()
_MONEY = ('subtotal', 'discount_amount', 'tax_amount', 'total_amount')


def _deny():
    from fastapi import HTTPException
    raise HTTPException(403, 'Restaurant derived order header certificate changed')


@dataclass(frozen=True)
class _Header:
    scope: object
    actor: object
    epoch: str
    native: object
    order: object
    original: dict
    source: dict
    expected: tuple
    customer_id: int | None = None


def _assignee(db, plan):
    from app.access.models import AccessMembership
    from app.common.models import CommonPerson
    from app.models.employee import Employee
    from app.models.company import Branch
    ident = plan.original['assigned_user_id']
    if type(ident) is not int or ident < 1 or ident != plan.original['created_by'] or ident != plan.source['created_by']:
        return False
    user, member, person, employee, branch = (model.__table__ for model in (User, AccessMembership, CommonPerson, Employee, Branch))
    belongs = or_(exists(select(member.c.id).where(member.c.user_id == ident, member.c.company_id == plan.scope.company_id, member.c.active.is_(True))),
        exists(select(person.c.id).where(person.c.user_id == ident, person.c.organization_id == plan.scope.company_id)),
        exists(select(employee.c.id).select_from(employee.join(branch, employee.c.branch_id == branch.c.id)).where(
            employee.c.user_id == ident, branch.c.company_id == plan.scope.company_id)))
    revoked = exists(select(member.c.id).where(member.c.user_id == ident, member.c.company_id == plan.scope.company_id, member.c.active.is_(False)))
    return bool(db.connection().scalar(select(exists(select(user.c.id).where(user.c.id == ident, belongs, ~revoked)))))


def _verify(db, plan, *, flushing):
    if (db.info.get('business_pack_scope') is not plan.scope or _leases.get(db) is not plan
            or plan.scope.pack_key != 'restaurant' or plan.scope.user_id != plan.actor.id
            or inspect(plan.actor).session is not db or not inspect(plan.actor).persistent):
        _deny()
    for row, model in ((plan.native, SRMSalesOrder), (plan.order, RestaurantServiceOrder)):
        state = inspect(row)
        if type(row) is not model or state.session is not db or not state.persistent or state.identity != (row.id,) or row in db.deleted:
            _deny()
    if capture(db, plan.actor, plan.scope, order=True, billing=False, payments=False, write=True) != plan.epoch:
        _deny()
    if not _assignee(db, plan):
        _deny()
    from .sources import private
    private(db, plan.scope, SRMSalesOrder, plan.native.id)
    private(db, plan.scope, RestaurantServiceOrder, plan.order.id)
    for row, values in ((plan.native, plan.original), (plan.order, plan.source)):
        state = inspect(row)
        for name, original in values.items():
            if row is plan.native and name == 'customer_id' and plan.customer_id is not None:
                expected = plan.customer_id if flushing else original
            elif row is plan.native and name in _MONEY and plan.customer_id is None:
                expected = plan.expected[_MONEY.index(name)] if flushing else original
            elif row is plan.order and name == 'revision':
                expected = original+1 if flushing else original
            else:
                expected = original
                if state.attrs[name].history.has_changes():
                    _deny()
            if getattr(row, name) != expected:
                _deny()
    for model, values in ((SRMSalesOrder, plan.original), (RestaurantServiceOrder, plan.source)):
        table = model.__table__
        current = db.connection().execute(select(table).where(table.c.id == values['id']).with_for_update()).mappings().one_or_none()
        if current is None or dict(current) != values:
            _deny()
    for row in set(db.new) | set(db.dirty) | set(db.deleted):
        if type(row) is SRMSalesOrderLine or type(row) is SRMSalesOrder and row is not plan.native:
            _deny()
        if plan.customer_id is not None and row is not plan.native and row is not plan.order:
            _deny()


@contextmanager
def header_update(db, actor, scope, epoch, native, order, totals):
    if db in _leases or len(totals) != 4:
        _deny()
    originals = []
    for row, model in ((native, SRMSalesOrder), (order, RestaurantServiceOrder)):
        state = inspect(row)
        if type(row) is not model or state.session is not db or not state.persistent or row in db.deleted:
            _deny()
        originals.append(deepcopy(dict(db.connection().execute(select(model.__table__).where(model.id == row.id).with_for_update()).mappings().one())))
    if (originals[0]['organization_id'] != scope.company_id or originals[1]['source_kind'] != 'unpaid_tab'
            or (originals[1]['organization_id'], originals[1]['branch_id'], originals[1]['pack_context_id'], originals[1]['sales_order_id']) !=
               (scope.company_id, scope.branch_id, scope.context_id, native.id)):
        _deny()
    plan = _Header(scope, actor, epoch, native, order, originals[0], originals[1], tuple(totals))
    _leases[db] = plan
    def check(session, *args):
        _verify(session, plan, flushing=True)
    try:
        _verify(db, plan, flushing=False)
        event.listen(db, 'before_flush', check)
        try:
            yield
        finally:
            event.remove(db, 'before_flush', check)
    finally:
        _leases.pop(db, None)


def reference(db, scope, row, parent, pairs):
    if parent is not User.__table__ or tuple((name, key.name) for name, key in pairs) != (('assigned_user_id', 'id'),):
        return False
    plan = _leases.get(db)
    if plan is None or plan.scope is not scope or plan.native is not row:
        return False
    _verify(db, plan, flushing=True)
    return True


@contextmanager
def customer_update(db, actor, scope, epoch, native, order, selected):
    """One NULL-to-named customer binding, never a reassignment or money edit."""
    from app.apps.crm.models import CRMCompany
    from app.apps.srm.models import SRMInvoice
    from app.apps.srm.service_checkout_models import POSServiceCheckout
    from app.apps.srm.services.commercial import customer
    from .models import RestaurantCommand
    from .sources import private
    if (db in _leases or type(selected) is not CRMCompany or inspect(selected).session is not db
            or not inspect(selected).persistent or db.is_modified(selected, include_collections=True)):
        _deny()
    if selected.organization_id != scope.company_id or customer(db, selected.id, actor) is not selected:
        _deny()
    from app.apps.srm.service_checkout import _source_scope
    _source_scope(db, scope, scope.company_id, scope.branch_id, CRMCompany, selected.id, master=True)
    originals = []
    for row, model in ((native, SRMSalesOrder), (order, RestaurantServiceOrder)):
        state = inspect(row)
        if type(row) is not model or state.session is not db or not state.persistent or row in db.deleted:
            _deny()
        originals.append(deepcopy(dict(db.connection().execute(select(model.__table__).where(model.id == row.id).with_for_update()).mappings().one())))
    if (originals[0]['organization_id'] != scope.company_id or originals[0]['customer_id'] is not None
            or originals[0]['status'] != 'draft' or originals[1]['source_kind'] != 'unpaid_tab' or originals[1]['state'] != 'open'
            or (originals[1]['organization_id'], originals[1]['branch_id'], originals[1]['pack_context_id'], originals[1]['sales_order_id']) !=
               (scope.company_id, scope.branch_id, scope.context_id, native.id)):
        _deny()
    if (db.connection().scalar(select(SRMInvoice.id).where(SRMInvoice.sales_order_id == native.id).limit(1))
            or db.connection().scalar(select(POSServiceCheckout.id).where(POSServiceCheckout.sales_order_id == native.id).limit(1))
            or db.connection().scalar(select(RestaurantCommand.id).where(RestaurantCommand.service_order_id == order.id,
                RestaurantCommand.action.in_(('tab.assign_customer','tab.assign_anonymous'))).limit(1))):
        _deny()
    plan = _Header(scope, actor, epoch, native, order, originals[0], originals[1],
        tuple(originals[0][key] for key in _MONEY), selected.id)
    _leases[db] = plan
    def check(session, *args):
        _verify(session, plan, flushing=True)
    try:
        _verify(db, plan, flushing=False)
        event.listen(db, 'before_flush', check)
        try:
            yield
        finally:
            event.remove(db, 'before_flush', check)
    finally:
        _leases.pop(db, None)
