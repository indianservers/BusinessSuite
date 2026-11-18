"""Atomic native service checkout; never commits a partial basket.

commit=False owns a savepoint inside the caller's transaction. The caller must
commit that transaction once, or roll it back. commit=True is for a dedicated
request unit of work and commits only after every native operation succeeds.
No API is registered by importing this module.
"""
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from hashlib import sha256
import json
from uuid import uuid5, NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import event, inspect, select
from app.apps.srm.service_checkout_models import (
    MODELS, ServiceBookingPolicy, ServiceSpecialistEligibility, POSServiceCheckout,
    POSCheckoutLine, POSServiceOccurrence, POSCheckoutPayment,
)
from app.apps.srm.service_checkout_schemas import CheckoutInput, PolicyInput, EligibilityInput
from app.apps.srm.services.commercial import tenant, require, record, customer, lock_tenant


def fail(message,code=422): raise HTTPException(code,message)


def _track_quantity_rollback(db, product_ids):
    """Expire Core-maintained stock caches when a checkout savepoint unwinds.

    Native stock writes use set_committed_value, so SQLAlchemy does not mark
    these product attributes dirty or expire them on a nested rollback. Keep
    the hook for the request session, including a caller's later savepoint.
    The canonical SQL balances and stock command remain unchanged.
    """
    from app.apps.srm.models import SRMProduct
    key = 'service_checkout_quantity_cache_ids'
    if key not in db.info:
        tracked = db.info[key] = set()

        def expire_quantities(session, transaction):
            for ident in tracked:
                cached = session.identity_map.get((SRMProduct, (ident,), None))
                if cached is not None and inspect(cached).persistent:
                    session.expire(cached, ['current_quantity'])

        event.listen(db, 'after_soft_rollback', expire_quantities)
    db.info[key].update(product_ids)

def installation_ready(db):
    from app.db.schema_columns import table_columns
    required={m.__tablename__:set(m.__table__.c.keys()) for m in MODELS}
    for model in MODELS:
        for foreign_key in model.__table__.foreign_keys:
            table,column=foreign_key.target_fullname.rsplit('.',1)
            required.setdefault(table,set()).add(column)
    actual=table_columns(db.connection(),required)
    return all(table in actual and columns<=actual[table] for table,columns in required.items())


def _authority(db,user,*,billing=False,payments=False,bookings=False,configuration=False,order=True,write=True,pure_probe=False):
    from app.access.service import check_background_access
    from app.branches.service import context as branch_context
    from app.business_packs.access import resolve_context
    from app.apps.srm.industry_api import context
    if not user.is_active or (write and db.info.get('security_write_request') is False):
        fail('An active actor and writable operation are required',403)
    if order:require(user,'srm_manage','srm_admin')
    if pure_probe:
        check_background_access(db,user,'srm','create' if write else 'view',administrative_read=False,stamp=False)
    else:
        check_background_access(db,user,'srm','create' if write else 'view')
    if billing:
        require(user,'srm_invoice_create','srm_admin');require(user,'srm_invoice_approve','srm_admin')
        check_background_access(db,user,'srm','approve')
    if payments: require(user,'srm_collection_create','srm_admin')
    if not installation_ready(db):fail('Service checkout installation is incomplete',503)
    supplied=db.info.get('branch_context')
    selected=getattr(supplied,'branch_id',None)
    if not selected:fail('Select one writable branch',409)
    fresh=branch_context(db,user,tenant(user),str(selected))
    if write and selected not in fresh.writable:fail('A writable branch is required',403)
    scope=resolve_context(db,user,fresh,requested_context_id=getattr(db.info.get('business_pack_scope'),'context_id',None))
    installed=db.info.get('business_pack_scope')
    if scope is not None:
        needed=set()
        if billing and not any(scope.pack_key+'.'+key in scope.capabilities for key in ('billing.prepare','checkout.create')):
            fail('Assigned Business Pack role cannot prepare checkout billing',403)
        if payments:needed.add('payments.record')
        if bookings:needed.add('appointments.schedule')
        if configuration and not any(scope.pack_key+'.'+key in scope.capabilities for key in ('settings.manage','providers.manage')):
            fail('Assigned Business Pack role cannot configure service eligibility',403)
        if any(scope.pack_key+'.'+name not in scope.capabilities for name in needed):
            fail('Assigned Business Pack role cannot perform this operation',403)
    if installed is not None and installed!=scope:fail('Business Pack authorization changed',403)
    native_fingerprint=None
    if scope is not None:
        from app.business_packs.native_checkout_authority import capture
        native_fingerprint=capture(db,user,scope,order=order,billing=billing,payments=payments,write=write)
    if order:
        actual=context(db,user,write,appointments=True)
        if actual!=selected:fail('Verified branch context changed',403)
    if scope is not None:
        if capture(db,user,scope,order=order,billing=billing,payments=payments,write=write)!=native_fingerprint:
            fail('Native checkout authorization changed while waiting; reload before continuing',403)
    return tenant(user),selected,scope


def checkout_capabilities(db, user):
    """Read-only recovery probe; use the checkout authority checks without writing."""
    from app.access.service import check_background_access
    from app.branches.service import context as branch_context
    result = {'checkout_create': False, 'checkout_collect': False}
    for name, payments in (('checkout_create', False), ('checkout_collect', True)):
        try:
            company, branch, _ = _authority(db, user, billing=True, payments=payments, write=False)
            check_background_access(db, user, 'srm', 'create')
            if branch not in branch_context(db, user, company, str(branch)).writable:
                continue
            result[name] = True
        except HTTPException as error:
            if error.status_code not in (403, 409, 503):
                raise
    return result


def _scope(query,model,company,branch,scope):
    return query.filter(model.organization_id==company,model.branch_id==branch,
        model.pack_context_id==(scope.context_id if scope else None))


def _source_scope(db,scope,company,branch,model,ident,*,master=False):
    from app.business_packs.models import PackRecordOwnership,PackMasterAvailability
    owned=PackRecordOwnership.__table__;available=PackMasterAvailability.__table__
    batch=db.info.get('checkout_report_read_batch')
    batch=batch if batch and batch['scope']==scope else None
    if batch is None and not inspect(db.connection()).has_table(owned.name):
        if scope is None:return
        fail('Business Pack ownership installation is incomplete',503)
    key=str(ident)
    proof=batch['pack'].get((model.__tablename__,key)) if batch is not None else db.connection().execute(select(owned).where(owned.c.resource_table==model.__tablename__,owned.c.resource_key==key)).mappings().first()
    if proof and (scope is None or proof['company_id']!=company or proof['branch_id']!=branch or proof['context_id']!=scope.context_id):
        fail('Source is outside the selected Business Pack context',403)
    if scope is not None and not proof:
        allowed=master and ((model.__tablename__,key) in batch['available'] if batch is not None else db.connection().execute(select(available.c.id).where(available.c.resource_table==model.__tablename__,
            available.c.resource_key==key,available.c.company_id==company,available.c.branch_id==branch,
            available.c.context_id==scope.context_id,available.c.active.is_(True))).first())
        if not allowed:fail('Source has no explicit availability in this Business Pack context',403)


def _stamp_new(db,scope,company,branch,objects):
    """Private creation-only adapter. Sources passed here were just flushed here.

    Exact native branch stamps are mandatory. This cannot adopt a standalone
    source or retag existing ownership; there is no route accepting source IDs.
    """
    if scope is None:return
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackRecordOwnership
    from app.branches.catalog import resource_key
    owner=PackRecordOwnership.__table__;native=BranchOwnership.__table__
    for obj in objects:
        table=obj.__table__;key=resource_key(table,{c.name:getattr(obj,c.name) for c in table.primary_key})
        branch_proof=db.connection().execute(select(native).where(native.c.resource_table==table.name,native.c.resource_key==key)).mappings().first()
        if not branch_proof or branch_proof['company_id']!=company or branch_proof['branch_id']!=branch:
            fail('New checkout source lacks exact native branch ownership',403)
        proof=db.connection().execute(select(owner).where(owner.c.resource_table==table.name,owner.c.resource_key==key)).mappings().first()
        if proof:
            if (proof['company_id'],proof['branch_id'],proof['context_id'])!=(company,branch,scope.context_id):
                fail('Checkout source ownership cannot be retagged',403)
        else:
            db.connection().execute(owner.insert().values(company_id=company,branch_id=branch,context_id=scope.context_id,
                resource_table=table.name,resource_key=key,source='service-checkout-created'))


def _provider(db,user,branch,ident,employee_id):
    from app.apps.srm.industry_api import get,provider_employee,PROVIDER_TYPES
    provider=get(db,user,branch,ident,'resource')
    provider_employee(db,user,branch,employee_id)
    if (provider.status!='active' or provider.data.get('employee_id')!=employee_id
            or provider.data.get('resource_type') not in PROVIDER_TYPES):
        fail('Choose the active HRMS-linked provider for this employee')
    return provider


def save_policy(data:PolicyInput,db,user,*,commit=True):
    company,branch,scope=_authority(db,user,configuration=True)
    from app.apps.srm.models import SRMProduct
    from app.shared.catalog_branches import assert_available
    with db.begin_nested():
        lock_tenant(db,user)
        product=record(db,SRMProduct,data.service_product_id,user);assert_available(product,user)
        _source_scope(db,scope,company,branch,SRMProduct,product.id,master=True)
        if not product.active or product.product_type.lower() not in {'service','services'}:fail('Choose an active service')
        row=_scope(db.query(ServiceBookingPolicy),ServiceBookingPolicy,company,branch,scope).filter_by(service_product_id=product.id).with_for_update().first()
        new=row is None
        if row is not None:_source_scope(db,scope,company,branch,type(row),row.id)
        if row is None:
            if data.expected_revision is not None:fail('Service policy no longer exists',409)
            row=ServiceBookingPolicy(organization_id=company,branch_id=branch,pack_context_id=scope.context_id if scope else None,service_product_id=product.id)
            db.add(row)
        elif data.expected_revision!=row.revision:fail('Service policy revision changed',409)
        previous_revision = row.revision
        for key,value in data.model_dump(exclude={'expected_revision','service_product_id','required_resource_types'}).items():setattr(row,key,value)
        db.flush()
        if data.required_resource_types is not None:
            from app.apps.srm.service_resource_requirements import required_types
            previous = required_types(product, row.id)
            requested = set(data.required_resource_types)
            if previous != requested:
                product.metadata_json = {**(product.metadata_json or {}), 'service_resource_requirements': {
                    **(product.metadata_json or {}).get('service_resource_requirements', {}), str(row.id): sorted(requested)}}
                if not new:
                    row.revision = previous_revision + 1
                db.flush()
        if new:_stamp_new(db,scope,company,branch,[row])
        result={'id':row.id,'revision':row.revision,'service_product_id':row.service_product_id}
    if commit:db.commit()
    return result


def _assert_employee_category(db, employee_id, policy):
    if not policy.employee_categories:
        return
    from app.models.employee import Employee
    from sqlalchemy import select
    from app.models.company import Branch
    # A policy's company and branch bound this validation-only category read.
    employee = db.connection().execute(select(Employee.work_categories).join(Branch,
        Employee.branch_id == Branch.id).where(Employee.id == employee_id,
        Employee.branch_id == policy.branch_id, Branch.company_id == policy.organization_id,
        Branch.is_active.is_(True), Employee.deleted_at.is_(None),
        Employee.status.in_(('Active', 'Probation', 'On Leave')))).first()
    from app.shared.employee_categories import matches_categories
    if employee is None or not matches_categories(employee.work_categories, policy.employee_categories):
        fail('Employee no longer belongs to a category allowed for this service', 409)


def save_eligibility(data:EligibilityInput,db,user,*,commit=True):
    company,branch,scope=_authority(db,user,configuration=True)
    with db.begin_nested():
        lock_tenant(db,user)
        policy=_scope(db.query(ServiceBookingPolicy),ServiceBookingPolicy,company,branch,scope).filter_by(id=data.policy_id,active=True).with_for_update().first()
        if not policy:fail('Service policy not found',404)
        if policy.revision!=data.expected_policy_revision:fail('Service policy revision changed',409)
        _assert_employee_category(db,data.employee_id,policy)
        provider=_provider(db,user,branch,data.provider_resource_id,data.employee_id)
        _source_scope(db,scope,company,branch,type(provider),provider.id,master=True)
        _source_scope(db,scope,company,branch,ServiceBookingPolicy,policy.id)
        row=_scope(db.query(ServiceSpecialistEligibility),ServiceSpecialistEligibility,company,branch,scope).filter_by(service_product_id=policy.service_product_id,provider_resource_id=data.provider_resource_id).with_for_update().first()
        new=row is None
        if row is not None:_source_scope(db,scope,company,branch,type(row),row.id)
        if row is None:
            if data.expected_revision is not None:fail('Specialist eligibility no longer exists',409)
            row=ServiceSpecialistEligibility(organization_id=company,branch_id=branch,pack_context_id=scope.context_id if scope else None,
                booking_policy_id=policy.id,service_product_id=policy.service_product_id,provider_resource_id=data.provider_resource_id)
            db.add(row)
        elif data.expected_revision!=row.revision:fail('Specialist eligibility revision changed',409)
        if row.booking_policy_id!=policy.id:fail('Specialist policy identity cannot change',409)
        row.active=data.active;db.flush()
        if new:_stamp_new(db,scope,company,branch,[row])
        result={'id':row.id,'revision':row.revision,'policy_id':policy.id}
    if commit:db.commit()
    return result


def _digest(data):
    return sha256(json.dumps(data.model_dump(mode='json'),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _cross_pack_busy(db,company,branch,booking):
    """Privacy-safe busy proof across aliases/packs; never returns booking data."""
    from app.business_packs.availability import appointment_conflict
    if appointment_conflict(db, company, booking.starts_at, booking.starts_at+timedelta(minutes=booking.duration_minutes),
            resource_ids=[booking.provider_resource_id, *booking.additional_resource_ids], employee_ids=[booking.employee_id]):
        fail('Provider or resource is unavailable at that time',409)


def _collection_register(db,user,company,branch,scope,selected=None,*,cash=False,currency=None):
    """An actual current register, never the closed register of an old basket."""
    from app.apps.srm.models import SRMPOSSession
    from app.branches.models import BranchOwnership
    def verify(row):
        if not row or (row.organization_id or 1)!=company:fail('Collection register not found',404)
        if row.status!='open' or row.deleted_at is not None:fail('Collection register must be open',409)
        if row.cashier_user_id not in (None,user.id):fail('Collection register belongs to another cashier',403)
        proof=db.connection().execute(select(BranchOwnership.__table__).where(BranchOwnership.resource_table=='srm_pos_sessions',BranchOwnership.resource_key==str(row.id))).mappings().first()
        if not proof or (proof['company_id'],proof['branch_id'])!=(company,branch):fail('Collection register is outside the selected branch',403)
        _source_scope(db,scope,company,branch,SRMPOSSession,row.id,master=True)
        return row
    def chosen(row):
        if cash:
            from .register_currency import require_cash_currency
            require_cash_currency(db,row,currency)
        return row
    if selected is not None:return chosen(verify(db.query(SRMPOSSession).filter_by(id=selected).first()))
    rows=db.query(SRMPOSSession).filter(SRMPOSSession.organization_id==company,SRMPOSSession.status=='open',
        SRMPOSSession.deleted_at.is_(None),(SRMPOSSession.cashier_user_id==user.id)|(SRMPOSSession.cashier_user_id.is_(None))).order_by(SRMPOSSession.id).all()
    eligible=[]
    for row in rows:
        try:eligible.append(verify(row))
        except HTTPException as error:
            if error.status_code not in {403,404,409}:raise
    if len(eligible)>1:fail('Select the register receiving this payment',409)
    if eligible:return chosen(eligible[0])
    if cash:fail('Open and select a register before receiving cash',409)
    return None


def _payment_digest(payment,selected_session=None):
    payload=payment.model_dump(mode='json')
    if selected_session is not None:payload={'payment':payload,'pos_session_id':selected_session}
    return sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def checkout(data:CheckoutInput,db,user,*,commit=True):
    data=CheckoutInput.model_validate(data.model_dump())
    from .anonymous_cash import account_for_customer,resolve_account,checkout_permit
    if data.buyer_mode=='registered':
        if account_for_customer(db.connection(),data.customer_id):fail('Select anonymous_cash buyer mode for the configured counter control account',403)
        return _checkout_operation(data,db,user,commit=commit)
    if any(line.booking or line.line_kind=='booked_service' for line in data.lines):fail('Appointments require a named customer')
    if not data.payments:fail('Anonymous counter sales require full payment at checkout')
    company,branch,scope=_authority(db,user,billing=True,payments=True)
    account=resolve_account(db,user,company,branch,scope)
    with checkout_permit(db,user,account,scope):
        result=_checkout_operation(data,db,user,commit=False,resolved_customer_id=account['customer_id'])
    if commit:db.commit()
    return result


def _checkout_operation(data:CheckoutInput,db,user,*,commit=True,resolved_customer_id=None):
    data=CheckoutInput.model_validate(data.model_dump())
    buyer_id=resolved_customer_id or data.customer_id
    company,branch,scope=_authority(db,user,billing=True,payments=bool(data.payments),bookings=any(x.booking for x in data.lines))
    _track_quantity_rollback(db, (line.product_id for line in data.lines))
    from app.apps.srm.api import router as native
    from app.apps.srm.models import SRMProduct,SRMSalesOrder,SRMSalesOrderLine,SRMInvoiceLine
    from app.apps.srm.schemas import SRMSalesOrderCreate,SRMReceiptCreate,SRMReceiptAllocationRequest
    from app.apps.srm.industry_api import AppointmentInput,appointment_operation,available
    from app.shared.catalog_branches import assert_available
    fingerprint=_digest(data)
    with db.begin_nested():
        lock_tenant(db,user)
        previous=_scope(db.query(POSServiceCheckout),POSServiceCheckout,company,branch,scope).filter_by(request_id=str(data.request_id)).with_for_update().first()
        if previous:
            _source_scope(db,scope,company,branch,POSServiceCheckout,previous.id)
            if previous.created_by!=user.id or previous.request_sha256!=fingerprint:fail('Checkout request key already used with different details',409)
            if previous.state!='committed':fail('Checkout request is not committed',409)
            return checkout_result(previous,db,scope=scope)
        customer(db,buyer_id,user)
        register=_collection_register(db,user,company,branch,scope,data.pos_session_id,cash=any(payment.method=='cash' for payment in data.payments),currency=data.currency)
        if scope and data.bill_discount_amount>0 and scope.pack_key+'.discounts.approve' not in scope.capabilities:
            fail('Assigned Business Pack role cannot approve discounts',403)
        prepared=[];selected=[];slots=[]
        for line in data.lines:
            product=record(db,SRMProduct,line.product_id,user);assert_available(product,user)
            _source_scope(db,scope,company,branch,SRMProduct,product.id,master=True)
            if scope:
                from app.business_packs.catalog_predicate import _assert_pos_product
                _assert_pos_product(db,user,scope,product)
            from app.business_packs.pharma.quantity import validate as validate_sale_quantity
            validate_sale_quantity(db, product.id, line.quantity)
            service=product.product_type.lower() in {'service','services'}
            if not service and (product.batch_tracking or product.serial_tracking):
                from app.business_packs.pharma.fefo import supported
                if not supported(scope,product):fail('This item requires a checkout with batch or serial allocation',409)
            if data.buyer_mode=='anonymous_cash' and (line.follow_up is not None or ((product.metadata_json or {}).get('follow_up') or {}).get('required')):
                fail('Choose a named customer for follow-up commitments')
            if not product.active or product.currency!=data.currency:fail('Choose active catalog items in the checkout currency')
            if service != (line.line_kind!='product'):fail('Cart line kind differs from the catalog product type')
            policy=None;eligibility=None
            if service:
                policy=_scope(db.query(ServiceBookingPolicy),ServiceBookingPolicy,company,branch,scope).filter_by(service_product_id=product.id).with_for_update().first()
                if policy and not policy.active:fail('Service booking policy is inactive',409)
                if policy and policy.booking_required and not line.booking:fail('This service requires an appointment')
            if line.booking:
                b=line.booking
                if b.starts_at<=datetime.now(timezone.utc):fail('Book a future service occurrence')
                if not policy or policy.id!=b.policy_id or policy.revision!=b.expected_policy_revision:fail('Service policy revision changed',409)
                eligibility=_scope(db.query(ServiceSpecialistEligibility),ServiceSpecialistEligibility,company,branch,scope).filter_by(
                    id=b.eligibility_id,booking_policy_id=policy.id,service_product_id=product.id,provider_resource_id=b.provider_resource_id,active=True).with_for_update().first()
                if not eligibility or eligibility.revision!=b.expected_eligibility_revision:fail('Specialist eligibility revision changed',409)
                _assert_employee_category(db,b.employee_id,policy)
                provider=_provider(db,user,branch,b.provider_resource_id,b.employee_id)
                _source_scope(db,scope,company,branch,type(provider),provider.id,master=True)
                _source_scope(db,scope,company,branch,ServiceBookingPolicy,policy.id)
                _source_scope(db,scope,company,branch,ServiceSpecialistEligibility,eligibility.id)
                if not policy.min_duration_minutes<=b.duration_minutes<=policy.max_duration_minutes or (not policy.allow_duration_override and b.duration_minutes!=policy.default_duration_minutes):fail('Choose a duration permitted by the service policy')
                start=b.starts_at;end=start+timedelta(minutes=b.duration_minutes)
                for old in slots:
                    if (old.employee_id==b.employee_id or old.provider_resource_id==b.provider_resource_id) and start<old.starts_at+timedelta(minutes=old.duration_minutes) and old.starts_at<end:fail('Provider has overlapping occurrences in this basket',409)
                slots.append(b)
                _cross_pack_busy(db,company,branch,b)
                resources=[b.provider_resource_id,*b.additional_resource_ids]
                from app.apps.srm.industry_api import get
                for ident in b.additional_resource_ids:
                    additional=get(db,user,branch,ident,'resource')
                    _source_scope(db,scope,company,branch,type(additional),additional.id,master=True)
                from app.apps.srm.service_resource_requirements import assert_required_resources
                assert_required_resources(product, policy.id, [get(db,user,branch,ident,'resource') for ident in b.additional_resource_ids])
                available(db,user,branch,start,b.duration_minutes,resources, draft_bookings=[{
                    'id':None,'branch_id':branch,'starts_at':old.starts_at,
                    'ends_at':old.starts_at+timedelta(minutes=old.duration_minutes),
                    'resource_ids':[old.provider_resource_id,*old.additional_resource_ids]} for old in slots[:-1]])
                for bound,is_lower in ((eligibility.effective_from,True),(eligibility.effective_until,False)):
                    if bound:
                        bound=bound.replace(tzinfo=timezone.utc) if bound.tzinfo is None else bound
                        if (is_lower and start<bound) or (not is_lower and end>bound):fail('Specialist is unavailable for this interval',409)
            rate=line.unit_price if line.unit_price is not None else (product.sales_rate or Decimal(0))
            if scope and (Decimal(rate)!=Decimal(product.sales_rate or 0) or line.discount_amount>0) and scope.pack_key+'.discounts.approve' not in scope.capabilities:
                fail('Assigned Business Pack role cannot override prices or approve discounts',403)
            prepared.append({'product_id':product.id,'quantity':line.quantity,'unit_price':rate,'discount_amount':line.discount_amount,
                'description':product.item_name,'metadata_json':{'checkout_line_key':str(line.client_line_key),'note':line.note,
                    **({'follow_up':line.follow_up.model_dump(mode='json')} if line.follow_up is not None else {}),
                    **({'warehouse_id':line.warehouse_id} if line.warehouse_id else {})}})
            selected.append((line,product,policy,eligibility))
        order_input=SRMSalesOrderCreate(title='Service checkout',customer_id=buyer_id,currency=data.currency,terms=data.note,
            metadata_json={'source':'pos','pos_sale_id':str(data.request_id),'pos_session_id':data.pos_session_id},
            discount_amount=sum((line.discount_amount for line in data.lines),Decimal(0))+data.bill_discount_amount,lines=prepared)
        normalized=native._normalize_pos_order(db,order_input,company)
        native._validate_pos_stock_available(db,normalized,company,actor=user)
        expected=sum((line.line_total for line in normalized.lines),Decimal(0))
        if data.expected_total is not None and data.expected_total!=expected:fail('Checkout total changed; review the current prices and tax',409)
        if sum((p.amount for p in data.payments),Decimal(0))>expected:fail('Payments exceed the native invoice total')
        if data.buyer_mode=='anonymous_cash':
            if expected<=0 or not data.payments or sum((p.amount for p in data.payments),Decimal(0))!=expected:
                fail('Anonymous counter sales require full payment at checkout; use a named customer for credit')
            from .anonymous_cash import _KEY
            entry=db.connection().info.get(_KEY)
            if not entry:fail('Anonymous counter checkout authorization is missing',403)
            entry[1].financial_ready=True
        root=POSServiceCheckout(organization_id=company,branch_id=branch,pack_context_id=scope.context_id if scope else None,
            request_id=str(data.request_id),request_sha256=fingerprint,created_by=user.id,customer_id=buyer_id,
            currency=data.currency,pos_session_id=data.pos_session_id,billing_mode=data.billing_mode)
        db.add(root);db.flush();_stamp_new(db,scope,company,branch,[root])
        if scope:
            from app.business_packs.catalog_predicate import _pos_projection
            with _pos_projection(db,user,scope):
                order_data=native.create_sales_order_operation(order_input,db,user,commit=False)
        else:
            order_data=native.create_sales_order_operation(order_input,db,user,commit=False)
        order=db.get(SRMSalesOrder,order_data['id']);root.sales_order_id=order.id;db.flush()
        _stamp_new(db,scope,company,branch,[order,*order.lines])
        order_lines=db.query(SRMSalesOrderLine).filter_by(sales_order_id=order.id).order_by(SRMSalesOrderLine.id).all()
        invoice=native._create_invoice_from_lines(db,user,'sales_order',order.id,None,order,[{
            'source_type':'sales_order_line','source_id':line.id,'description':line.description,'quantity':line.quantity,
            'unit_price':line.unit_price,'discount_amount':line.discount_amount,'tax_amount':line.tax_amount,'line_total':line.line_total}
            for line in order_lines],data.currency)
        db.flush();native.approve_invoice_operation(invoice.id,db,user,commit=False);root.invoice_id=invoice.id;db.flush()
        _stamp_new(db,scope,company,branch,[invoice])
        billed={line.source_id:line for line in db.query(SRMInvoiceLine).filter_by(invoice_id=invoice.id).all()}
        _stamp_new(db,scope,company,branch,list(billed.values()))
        source_by_key={(line.metadata_json or {}).get('checkout_line_key'):line for line in order_lines}
        for line,product,policy,eligibility in selected:
            source=source_by_key[str(line.client_line_key)];charge=billed[source.id]
            mapped=POSCheckoutLine(checkout_id=root.id,client_line_key=str(line.client_line_key),line_kind=line.line_kind,
                product_id=product.id,sales_order_line_id=source.id,invoice_line_id=charge.id,quantity=source.quantity,
                unit_price=source.unit_price,discount_amount=source.discount_amount,tax_amount=source.tax_amount,
                line_total=source.line_total,catalog_tax_snapshot=(source.metadata_json or {}).get('tax_snapshot',{}))
            db.add(mapped);db.flush();_stamp_new(db,scope,company,branch,[mapped])
            if line.booking:
                b=line.booking
                occurrence_key=uuid5(NAMESPACE_URL,f'checkout:{company}:{branch}:{root.pack_context_id}:{data.request_id}:{line.client_line_key}')
                from app.apps.srm.industry_models import IndustryRecord
                if db.connection().execute(select(IndustryRecord.id).where(IndustryRecord.organization_id==company,IndustryRecord.branch_id==branch,IndustryRecord.request_id==str(occurrence_key))).first():
                    fail('Appointment source key is already reserved',409)
                appointment=appointment_operation(AppointmentInput(request_id=occurrence_key,title=product.item_name,
                    customer_id=buyer_id,service_id=product.id,resource_ids=[b.provider_resource_id,*b.additional_resource_ids],
                    starts_at=b.starts_at,duration_minutes=b.duration_minutes),db,user,commit=False)
                _stamp_new(db,scope,company,branch,[db.get(IndustryRecord,appointment['id'])])
                occurrence=POSServiceOccurrence(checkout_id=root.id,checkout_line_id=mapped.id,occurrence_key=str(occurrence_key),
                    appointment_id=appointment['id'],service_product_id=product.id,provider_resource_id=b.provider_resource_id,
                    employee_id=b.employee_id,starts_at=b.starts_at,ends_at=b.starts_at+timedelta(minutes=b.duration_minutes),
                    duration_minutes=b.duration_minutes,booking_policy_id=policy.id,policy_revision=policy.revision,
                    eligibility_id=eligibility.id,eligibility_revision=eligibility.revision)
                db.add(occurrence);db.flush();_stamp_new(db,scope,company,branch,[occurrence])
                native_appointment=db.get(IndustryRecord,appointment['id'])
                native_appointment.data={**native_appointment.data,'pos_checkout_id':root.id,'pos_occurrence_id':occurrence.id}
                db.flush()
        for payment in data.payments:
            receipt=native.create_receipt_operation(SRMReceiptCreate(customer_id=buyer_id,receipt_date=date.today(),
                payment_method=payment.method,reference_number=payment.reference,currency=data.currency,amount=payment.amount),db,user,commit=False)
            native.confirm_receipt_operation(receipt['id'],db,user,commit=False)
            native.allocate_receipt_operation(receipt['id'],SRMReceiptAllocationRequest(invoice_id=invoice.id,amount=payment.amount,request_id=payment.payment_key),db,user,commit=False)
            from app.apps.srm.models import SRMReceipt
            _stamp_new(db,scope,company,branch,[db.get(SRMReceipt,receipt['id'])])
            mapped_payment=POSCheckoutPayment(checkout_id=root.id,payment_key=str(payment.payment_key),receipt_id=receipt['id'],collection_session_id=register.id,
                request_sha256=_payment_digest(payment))
            db.add(mapped_payment);db.flush();_stamp_new(db,scope,company,branch,[mapped_payment])
        root.state='committed';root.committed_at=datetime.now(timezone.utc);db.flush()
        result=checkout_result(root,db,scope=scope)
    if commit:db.commit()
    return result


def _validate_group_sources(root,db,scope):
    """Fail closed on corrupted pointers as well as ordinary API writes."""
    from app.apps.srm.models import SRMSalesOrder,SRMSalesOrderLine,SRMInvoice,SRMInvoiceLine,SRMReceipt,SRMReceiptAllocation,SRMPOSSession
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm.commercial_models import InvoiceContext,ReceiptContext
    from app.branches.models import BranchOwnership
    company,branch=root.organization_id,root.branch_id
    batch=db.info.get('checkout_report_read_batch')
    batch=batch if batch and batch['scope']==scope else None
    def get(model,ident):
        return batch['objects'].get((model,ident)) if batch is not None else db.get(model,ident)
    def rows(model,field,ident):
        return batch['children'].get((model,field,ident),[]) if batch is not None else db.query(model).filter(getattr(model,field)==ident).all()
    def native(model,ident,*,master=False):
        item=get(model,ident)
        if item is None:fail('Checkout native source unavailable',409)
        org=getattr(item,'organization_id',company) or 1
        if org!=company:fail('Checkout native company identity differs',409)
        owner=batch['branch'].get((model.__tablename__,str(ident))) if batch is not None else db.connection().execute(select(BranchOwnership.__table__).where(
            BranchOwnership.resource_table==model.__tablename__,BranchOwnership.resource_key==str(ident))).mappings().first()
        if not owner or (owner['company_id'],owner['branch_id'])!=(company,branch):fail('Checkout native branch identity differs',403)
        _source_scope(db,scope,company,branch,model,ident,master=master)
        return item
    order=native(SRMSalesOrder,root.sales_order_id)
    invoice=native(SRMInvoice,root.invoice_id)
    if (order.customer_id!=root.customer_id or order.currency!=root.currency or invoice.customer_id!=root.customer_id
            or invoice.currency!=root.currency or invoice.sales_order_id!=order.id):fail('Checkout native order/invoice identity differs',409)
    def amount(value):
        try:result=Decimal(value)
        except (TypeError,ValueError,ArithmeticError):fail('Checkout native financial value is invalid',409)
        if not result.is_finite():fail('Checkout native financial value is invalid',409)
        return result
    for value in (invoice.total_amount,invoice.paid_amount,invoice.balance_amount):amount(value)
    fields=('quantity','unit_price','discount_amount','tax_amount','line_total')
    mapped_lines=rows(POSCheckoutLine,'checkout_id',root.id)
    native_line_ids={x.id for x in rows(SRMInvoiceLine,'invoice_id',invoice.id)}
    if native_line_ids!={x.invoice_line_id for x in mapped_lines} or sum((Decimal(x.line_total) for x in mapped_lines),Decimal(0))!=amount(invoice.total_amount):
        fail('Checkout group charge mapping differs from native invoice',409)
    for line in mapped_lines:
        source=native(SRMSalesOrderLine,line.sales_order_line_id)
        billed=native(SRMInvoiceLine,line.invoice_line_id)
        if (source.sales_order_id!=order.id or source.product_id!=line.product_id or billed.invoice_id!=invoice.id
                or billed.source_type!='sales_order_line' or billed.source_id!=source.id
                or any(amount(getattr(line,key))!=amount(getattr(source,key)) or amount(getattr(line,key))!=amount(getattr(billed,key)) for key in fields)):
            fail('Checkout native line charge identity differs',409)
    for occurrence in rows(POSServiceOccurrence,'checkout_id',root.id):
        appointment=native(IndustryRecord,occurrence.appointment_id)
        _schedule_matches(appointment,occurrence)
        provider=native(IndustryRecord,occurrence.provider_resource_id,master=True)
        if not isinstance(provider.data,dict) or provider.data.get('employee_id')!=occurrence.employee_id:fail('Grouped employee/provider schedule identity differs',409)
        if (appointment.kind!='appointment' or appointment.branch_id!=branch or appointment.customer_id!=root.customer_id or appointment.invoice_id is not None
                or not isinstance(appointment.data,dict) or appointment.data.get('service_id')!=occurrence.service_product_id
                or occurrence.provider_resource_id not in appointment.data.get('resource_ids',[])):
            fail('Checkout native appointment identity differs',409)
    invoice_context=get(InvoiceContext,invoice.id)
    seller=invoice_context.seller_id if invoice_context else company
    for mapped in rows(POSCheckoutPayment,'checkout_id',root.id):
        receipt=native(SRMReceipt,mapped.receipt_id)
        if mapped.collection_session_id is not None:native(SRMPOSSession,mapped.collection_session_id,master=True)
        amount(receipt.amount);amount(receipt.unallocated_amount)
        receipt_context=get(ReceiptContext,receipt.id)
        receipt_seller=receipt_context.seller_id if receipt_context else company
        if receipt.customer_id!=root.customer_id or receipt.currency!=root.currency or seller!=receipt_seller:
            fail('Checkout native receipt identity differs',409)
        allocations=rows(SRMReceiptAllocation,'receipt_id',receipt.id)
        if not allocations or any(a.invoice_id!=invoice.id for a in allocations) or not any(a.request_id==mapped.payment_key for a in allocations):
            fail('Checkout receipt allocation differs from group invoice',409)


def checkout_result(root,db,*,scope=None):
    from app.apps.srm.models import SRMInvoice,SRMReceipt
    _validate_group_sources(root,db,scope)
    invoice=db.get(SRMInvoice,root.invoice_id)
    if not invoice:fail('Checkout native invoice is unavailable',409)
    lines=db.query(POSCheckoutLine).filter_by(checkout_id=root.id).order_by(POSCheckoutLine.id).all()
    occurrences={x.checkout_line_id:x for x in db.query(POSServiceOccurrence).filter_by(checkout_id=root.id)}
    payments=db.query(POSCheckoutPayment).filter_by(checkout_id=root.id).order_by(POSCheckoutPayment.id).all()
    batches=None
    if scope is not None and scope.pack_key=='pharma':
        from app.business_packs.pharma.fefo import sale_allocations
        batches=sale_allocations(db,scope,root,lines)
    return {'id':root.id,'state':root.state,'revision':root.revision,'sales_order_id':root.sales_order_id,
        'invoice':{'id':invoice.id,'number':invoice.invoice_number,'status':invoice.status,'currency':invoice.currency,
            'total':str(invoice.total_amount),'paid':str(invoice.paid_amount),'balance':str(invoice.balance_amount)},
        'lines':[{'id':line.id,'client_line_key':line.client_line_key,'kind':line.line_kind,'product_id':line.product_id,
            'invoice_line_id':line.invoice_line_id,'quantity':format(Decimal(line.quantity).normalize(),'f'),'unit_price':format(Decimal(line.unit_price),'.2f'),
            'discount':format(Decimal(line.discount_amount),'.2f'),'tax':format(Decimal(line.tax_amount),'.2f'),'total':format(Decimal(line.line_total),'.2f'),
            'appointment_id':occurrences[line.id].appointment_id if line.id in occurrences else None,
            **({'batch_allocations':batches[line.id]} if batches is not None else {})} for line in lines],
        'receipts':[_receipt_result(db,p) for p in payments]}

def servicecheckout_state(db,actor,branch_ctx,checkout_id,pack_scope=None):
    """Read group-native balances; line charges never pretend to be allocations."""
    from app.access.service import check_background_access
    from app.branches.service import context as branch_context
    from app.business_packs.access import resolve_context
    from app.apps.srm.services.commercial import invoice_for
    if not actor.is_active:fail('Active actor required',403)
    require(actor,'srm_invoice_view','srm_invoice_create','srm_collection_view','srm_collection_create','srm_admin')
    check_background_access(db,actor,'srm','view')
    if type(checkout_id) is not int or checkout_id<1:fail('Checkout not found',404)
    if not installation_ready(db):fail('Service checkout installation is incomplete',503)
    branch=getattr(branch_ctx,'branch_id',None)
    if not branch:fail('Select one branch',409)
    company=tenant(actor)
    fresh=branch_context(db,actor,company,str(branch))
    supplied=pack_scope or db.info.get('business_pack_scope')
    scope=resolve_context(db,actor,fresh,requested_context_id=getattr(supplied,'context_id',None))
    if supplied is not None and scope!=supplied:fail('Business Pack authorization changed',403)
    row=_scope(db.query(POSServiceCheckout),POSServiceCheckout,company,branch,scope).filter_by(id=checkout_id).first()
    if not row:fail('Checkout not found',404)
    if scope and not (any(scope.pack_key+'.'+name in scope.capabilities for name in ('billing.view','checkout.view','billing.prepare')) or (scope.pack_key+'.checkout.create' in scope.capabilities and row.created_by==actor.id)):
        fail('Assigned Business Pack role cannot inspect billing',403)
    _source_scope(db,scope,company,branch,POSServiceCheckout,row.id)
    if row.state!='committed':fail('Checkout is not committed',409)
    invoice=invoice_for(db,row.invoice_id,actor)
    _source_scope(db,scope,company,branch,type(invoice),invoice.id)
    return checkout_result(row,db,scope=scope)


def _receipt_result(db,mapped):
    from app.apps.srm.models import SRMReceipt
    receipt=db.get(SRMReceipt,mapped.receipt_id)
    if not receipt:fail('Checkout receipt unavailable',409)
    return {'id':receipt.id,'payment_key':mapped.payment_key,'number':receipt.receipt_number,
        'status':receipt.status,'method':receipt.payment_method,'reference':receipt.reference_number,
        'amount':format(Decimal(receipt.amount),'.2f'),'unallocated':format(Decimal(receipt.unallocated_amount),'.2f'),
        'collection_session_id':mapped.collection_session_id}


def append_payment(checkout_id,data,db,user,*,commit=True):
    """Collect on one native group invoice; exact key replays never charge twice."""
    from app.apps.srm.service_checkout_schemas import AppendPaymentInput
    from app.apps.srm.schemas import SRMReceiptCreate,SRMReceiptAllocationRequest
    from app.apps.srm.api import router as native
    from app.apps.srm.models import SRMReceipt,SRMInvoice
    data=AppendPaymentInput.model_validate(data.model_dump())
    company,branch,scope=_authority(db,user,payments=True,order=False)
    native_fingerprint=None
    if scope is not None:
        from app.business_packs.native_checkout_authority import capture
        native_fingerprint=capture(db,user,scope,order=False,billing=False,payments=True,write=True)
    fingerprint=_payment_digest(data.payment,data.pos_session_id)
    with db.begin_nested():
        lock_tenant(db,user)
        if scope is not None and capture(db,user,scope,order=False,billing=False,payments=True,write=True)!=native_fingerprint:
            fail('Native payment authorization changed while waiting; reload before continuing',403)
        root=_scope(db.query(POSServiceCheckout),POSServiceCheckout,company,branch,scope).filter_by(id=checkout_id).with_for_update().populate_existing().first()
        if not root:fail('Checkout not found',404)
        _source_scope(db,scope,company,branch,POSServiceCheckout,root.id)
        if root.state!='committed':fail('Only a committed checkout can receive payments',409)
        previous=db.query(POSCheckoutPayment).filter_by(checkout_id=root.id,payment_key=str(data.payment.payment_key)).first()
        if previous:
            prior_receipt=db.get(SRMReceipt,previous.receipt_id)
            if not prior_receipt or prior_receipt.created_by!=user.id or previous.request_sha256!=fingerprint:fail('Payment key already used with different details',409)
        else:
            if data.expected_revision!=root.revision:fail('Checkout revision changed',409)
            invoice=native.invoice_for(db,root.invoice_id,user,lock=True)
            _source_scope(db,scope,company,branch,type(invoice),invoice.id)
            if invoice.status in {'draft','pending_approval','cancelled'}:fail('Checkout invoice must be issued',409)
            if data.payment.amount>Decimal(invoice.balance_amount):fail('Payment exceeds invoice balance')
            payment=data.payment
            register=_collection_register(db,user,company,branch,scope,data.pos_session_id,cash=payment.method=='cash',currency=root.currency)
            receipt=native.create_receipt_operation(SRMReceiptCreate(customer_id=root.customer_id,receipt_date=date.today(),
                payment_method=payment.method,reference_number=payment.reference,currency=root.currency,amount=payment.amount),db,user,commit=False)
            native.confirm_receipt_operation(receipt['id'],db,user,commit=False)
            native.allocate_receipt_operation(receipt['id'],SRMReceiptAllocationRequest(invoice_id=invoice.id,amount=payment.amount,request_id=payment.payment_key),db,user,commit=False)
            mapped=POSCheckoutPayment(checkout_id=root.id,payment_key=str(payment.payment_key),receipt_id=receipt['id'],
                collection_session_id=register.id if register else None,request_sha256=fingerprint)
            db.add(mapped);db.flush();_stamp_new(db,scope,company,branch,[db.get(SRMReceipt,receipt['id']),mapped])
            root.updated_at=datetime.now(timezone.utc)
        db.flush()
        if scope is not None and scope.pack_key=='restaurant':
            from app.business_packs.restaurant.settlement import after_native_payment
            after_native_payment(db,user,scope,root,native_fingerprint)
        result=checkout_result(root,db,scope=scope)
    if commit:db.commit()
    return result

def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _schedule_matches(appointment,occurrence):
    data=appointment.data
    try:
        valid=(isinstance(data,dict) and appointment.starts_at is not None and appointment.ends_at is not None
            and _utc(appointment.starts_at)==_utc(occurrence.starts_at) and _utc(appointment.ends_at)==_utc(occurrence.ends_at)
            and _utc(datetime.fromisoformat(data['starts_at']))==_utc(occurrence.starts_at)
            and data.get('duration_minutes')==occurrence.duration_minutes
            and data.get('service_id')==occurrence.service_product_id
            and occurrence.provider_resource_id in data.get('resource_ids',[]))
    except (ValueError,TypeError,KeyError,AttributeError):valid=False
    if not valid:fail('Grouped appointment schedule changed outside the validated scheduling workflow',409)


def _schedule_rows(appointment_id,db,user,company,branch,scope,*,lock=False):
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm.models import SRMSalesOrderLine,SRMInvoiceLine,SRMSalesOrder,SRMInvoice
    if type(appointment_id) is not int or appointment_id<1:fail('Grouped appointment not found',404)
    query=db.query(IndustryRecord).filter_by(id=appointment_id,organization_id=company,branch_id=branch,kind='appointment')
    appointment=(query.with_for_update() if lock else query).populate_existing().first()
    if not appointment:fail('Grouped appointment not found',404)
    query=db.query(POSServiceOccurrence).filter_by(appointment_id=appointment.id,organization_id=company,branch_id=branch)
    occurrence=(query.with_for_update() if lock else query).populate_existing().first()
    if not occurrence:fail('Grouped appointment not found',404)
    query=_scope(db.query(POSServiceCheckout),POSServiceCheckout,company,branch,scope).filter_by(id=occurrence.checkout_id)
    root=(query.with_for_update() if lock else query).populate_existing().first()
    if not root:fail('Grouped appointment not found',404)
    if root.state!='committed':fail('Grouped appointment checkout is not committed',409)
    if appointment.customer_id!=root.customer_id or appointment.invoice_id is not None:
        fail('Grouped appointment customer or invoice identity differs',409)
    for row in (appointment,occurrence,root):_source_scope(db,scope,company,branch,type(row),row.id)
    line=db.query(POSCheckoutLine).filter_by(id=occurrence.checkout_line_id,checkout_id=root.id,
        organization_id=company,branch_id=branch,scope_context_key=root.scope_context_key).first()
    if not line or line.line_kind!='booked_service' or line.product_id!=occurrence.service_product_id:
        fail('Grouped service source identity differs',409)
    _source_scope(db,scope,company,branch,POSCheckoutLine,line.id)
    # Trusted source proof only: never expose monetary/customer fields in
    # scheduling DTOs and never mutate issued financial line snapshots.
    order_line=db.get(SRMSalesOrderLine,line.sales_order_line_id)
    billed=db.get(SRMInvoiceLine,line.invoice_line_id)
    if not order_line or not billed:fail('Grouped service charge source unavailable',409)
    from app.branches.models import BranchOwnership
    order=db.get(SRMSalesOrder,root.sales_order_id);invoice=db.get(SRMInvoice,root.invoice_id)
    if (not order or not invoice or (order.organization_id or 1)!=company or (invoice.organization_id or 1)!=company
            or order.customer_id!=root.customer_id or invoice.customer_id!=root.customer_id
            or order.currency!=root.currency or invoice.currency!=root.currency or invoice.sales_order_id!=order.id):
        fail('Grouped native source identity differs',409)
    for row in (order_line,billed,order,invoice):
        _source_scope(db,scope,company,branch,type(row),row.id)
        proof=db.connection().execute(select(BranchOwnership.__table__).where(BranchOwnership.resource_table==row.__tablename__,BranchOwnership.resource_key==str(row.id))).mappings().first()
        if not proof or (proof['company_id'],proof['branch_id'])!=(company,branch):fail('Grouped native source is outside this branch',403)
    if (order_line.sales_order_id!=root.sales_order_id or order_line.product_id!=line.product_id
            or billed.invoice_id!=root.invoice_id or billed.source_type!='sales_order_line' or billed.source_id!=order_line.id):
        fail('Grouped service charge source differs',409)
    try:
        amounts_match=all(Decimal(getattr(line,key))==Decimal(getattr(order_line,key))==Decimal(getattr(billed,key))
            for key in ('quantity','unit_price','discount_amount','tax_amount','line_total'))
    except (ValueError,TypeError,ArithmeticError):amounts_match=False
    if not amounts_match:fail('Grouped service charge snapshot differs',409)
    _schedule_matches(appointment,occurrence)
    from app.apps.srm.industry_api import get
    provider=get(db,user,branch,occurrence.provider_resource_id,'resource',lock=False)
    if provider.data.get('employee_id')!=occurrence.employee_id:fail('Grouped employee/provider schedule identity differs',409)
    _source_scope(db,scope,company,branch,type(provider),provider.id,master=True)
    return appointment,occurrence,root,provider


def _schedule_result(appointment,occurrence,provider):
    from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
    zone=provider.data.get('timezone')
    try:ZoneInfo(zone)
    except (TypeError,ValueError,ZoneInfoNotFoundError):fail('Provider timezone is unavailable',503)
    return {'appointment_id':appointment.id,'service_id':occurrence.service_product_id,'provider_timezone':zone,'appointment_revision':appointment.revision,
        'occurrence_id':occurrence.id,'occurrence_revision':occurrence.revision,
        'booking':{'policy_id':occurrence.booking_policy_id,'expected_policy_revision':occurrence.policy_revision,
            'eligibility_id':occurrence.eligibility_id,'expected_eligibility_revision':occurrence.eligibility_revision,
            'provider_resource_id':occurrence.provider_resource_id,'employee_id':occurrence.employee_id,
            'starts_at':_utc(occurrence.starts_at).isoformat(),'duration_minutes':occurrence.duration_minutes},
        'additional_resource_ids':[ident for ident in appointment.data['resource_ids'] if ident!=occurrence.provider_resource_id]}


def grouped_schedule(appointment_id,db,user):
    company,branch,scope=_authority(db,user,bookings=True,write=False)
    appointment,occurrence,root,provider=_schedule_rows(appointment_id,db,user,company,branch,scope)
    return _schedule_result(appointment,occurrence,provider)


def reschedule_grouped(appointment_id,data,db,user,*,commit=True):
    from app.apps.srm.service_checkout_schemas import GroupedRescheduleInput
    from app.apps.srm.service_checkout_models import occurrence_reschedule_scope
    from app.apps.srm.industry_api import available,get,audit
    data=GroupedRescheduleInput.model_validate(data.model_dump())
    company,branch,scope=_authority(db,user,bookings=True)
    with db.begin_nested():
        lock_tenant(db,user)
        appointment,occurrence,root,old_provider=_schedule_rows(appointment_id,db,user,company,branch,scope,lock=True)
        if appointment.revision!=data.expected_appointment_revision or occurrence.revision!=data.expected_occurrence_revision:
            fail('Appointment or service occurrence revision changed; reload the schedule',409)
        b=data.booking
        if appointment.status!='booked' or _utc(occurrence.starts_at)<=datetime.now(timezone.utc) or b.starts_at<=datetime.now(timezone.utc):
            fail('Only future booked service occurrences can be rescheduled',409)
        policy=_scope(db.query(ServiceBookingPolicy),ServiceBookingPolicy,company,branch,scope).filter_by(
            id=b.policy_id,service_product_id=occurrence.service_product_id,active=True).with_for_update().populate_existing().first()
        if not policy or policy.revision!=b.expected_policy_revision:fail('Service policy revision changed; review current options',409)
        eligibility=_scope(db.query(ServiceSpecialistEligibility),ServiceSpecialistEligibility,company,branch,scope).filter_by(
            id=b.eligibility_id,booking_policy_id=policy.id,service_product_id=occurrence.service_product_id,
            provider_resource_id=b.provider_resource_id,active=True).with_for_update().populate_existing().first()
        if not eligibility or eligibility.revision!=b.expected_eligibility_revision:fail('Specialist eligibility revision changed; review current options',409)
        for row in (policy,eligibility):_source_scope(db,scope,company,branch,type(row),row.id)
        _assert_employee_category(db,b.employee_id,policy)
        provider=_provider(db,user,branch,b.provider_resource_id,b.employee_id)
        _source_scope(db,scope,company,branch,type(provider),provider.id,master=True)
        resources=[b.provider_resource_id,*data.additional_resource_ids]
        for ident in data.additional_resource_ids:
            additional=get(db,user,branch,ident,'resource');_source_scope(db,scope,company,branch,type(additional),additional.id,master=True)
        if not policy.min_duration_minutes<=b.duration_minutes<=policy.max_duration_minutes or (not policy.allow_duration_override and b.duration_minutes!=policy.default_duration_minutes):
            fail('Choose a duration permitted by the service policy')
        end=b.starts_at+timedelta(minutes=b.duration_minutes)
        for bound,lower in ((eligibility.effective_from,True),(eligibility.effective_until,False)):
            if bound and ((lower and b.starts_at<_utc(bound)) or (not lower and end>_utc(bound))):fail('Specialist is unavailable for this interval',409)
        from app.apps.srm.service_resource_requirements import assert_current_service_requirements
        from app.apps.srm.models import SRMProduct
        product = record(db,SRMProduct,occurrence.service_product_id,user)
        assert_current_service_requirements(db,user,branch,product,resources)
        available(db,user,branch,b.starts_at,b.duration_minutes,resources,ignore=appointment.id)
        with occurrence_reschedule_scope(db,occurrence.id):
            appointment.starts_at=b.starts_at;appointment.ends_at=end
            appointment.data={**appointment.data,'starts_at':b.starts_at.isoformat(),'duration_minutes':b.duration_minutes,'resource_ids':resources}
            appointment.revision+=1
            for key,value in {'provider_resource_id':b.provider_resource_id,'employee_id':b.employee_id,'starts_at':b.starts_at,'ends_at':end,
                'duration_minutes':b.duration_minutes,'booking_policy_id':policy.id,'policy_revision':policy.revision,
                'eligibility_id':eligibility.id,'eligibility_revision':eligibility.revision}.items():setattr(occurrence,key,value)
            db.flush();audit(db,user,appointment,'group_rescheduled');db.flush()
        result=_schedule_result(appointment,occurrence,provider)
    if commit:db.commit()
    return result
