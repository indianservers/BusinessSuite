"""Explicit selected-POS projections. No general catalogue or CRM authority."""
from decimal import Decimal
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from sqlalchemy import select,func,or_,exists,cast,String
from app.apps.srm.models import SRMProduct,SRMWarehouse,SRMInventoryBalance
from app.apps.crm.models import CRMCompany
from app.apps.srm.services.commercial import require,tenant,lock_tenant
from app.core.input_validation import EmailAddress,NationalPhone,CallingCode,normalize_phone,clean_text,CONTRACT
from app.business_packs.models import PackMasterAvailability,PackRecordOwnership
from app.branches.models import BranchOwnership

READ=('checkout.view','checkout.create','billing.prepare')


def fail(message,code=403):raise HTTPException(code,message)


def authority(db,actor,selected=None,*,create=False):
    from app.access.service import check_background_access
    from app.branches.service import context
    from app.business_packs.access import resolve_context
    require(actor,*('srm_manage','srm_admin') if create else ('srm_view','srm_manage','srm_admin'))
    check_background_access(db,actor,'srm','create' if create else 'view')
    branch=getattr(db.info.get('branch_context'),'branch_id',None)
    if not branch:fail('Select one native POS branch',409)
    company=tenant(actor);fresh=context(db,actor,company,str(branch))
    scope=resolve_context(db,actor,fresh,requested_context_id=selected)
    if scope is None:fail('Select a Business Pack for this POS surface',409)
    if db.info.get('business_pack_scope')!=scope:fail('POS scope differs from the verified request')
    actions=('patients.register','customers.register') if create else READ
    if not any(scope.pack_key+'.'+action in scope.capabilities for action in actions):fail('Assigned Business Pack role cannot perform this POS operation')
    if create and branch not in fresh.writable:fail('The native POS branch is read only')
    return company,branch,scope


def features(db,actor,scope):
    from app.access.service import check_background_access
    can_create=scope.writable and any(scope.pack_key+'.'+key in scope.capabilities for key in ('customers.register','patients.register'))
    if can_create:
        try:
            require(actor,'srm_manage','srm_admin');check_background_access(db,actor,'srm','create')
        except HTTPException:can_create=False
    from .pos_customer_fields import snapshot,UNAVAILABLE
    required_setup=can_create and not snapshot(db,actor,scope.company_id,scope).available
    if required_setup:can_create=False
    can_schedule=scope.writable and any(scope.pack_key+'.'+key in scope.capabilities for key in ('appointments.schedule','reservations.schedule'))
    if can_schedule:
        try:
            from app.apps.srm.service_checkout_options import _authority as scheduling_authority
            check_background_access(db,actor,'srm','create')
            scheduling_authority(db,actor,str(scope.context_id))
        except HTTPException as error:
            if error.status_code!=403:raise
            can_schedule=False
    can_return=scope.writable and scope.pack_key=='retail' and all('retail.'+name in scope.capabilities for name in ('returns.approve','payments.record'))
    if can_return:
        try:
            from app.apps.fam.access import FAM_SRM_POSTING_MANAGE_PERMISSIONS
            from app.business_packs.retail.returns import _ready
            require(actor,'srm_manage','srm_admin');require(actor,'srm_collection_create','srm_admin')
            require(actor,*FAM_SRM_POSTING_MANAGE_PERMISSIONS)
            check_background_access(db,actor,'srm','create')
            check_background_access(db,actor,'fam','view');check_background_access(db,actor,'fam','create');check_background_access(db,actor,'fam','approve')
            _ready(db)
        except HTTPException:can_return=False
    return {'appointments_schedule':can_schedule,'retail_returns':can_return,'customers_register':can_create,'registration_unavailable_reason':(UNAVAILABLE if required_setup else None),'held_bills':False,'follow_ups':False,'advanced_customer':False,
            'countries':[{'code':row['iso'],'name':row['country']} for row in CONTRACT['countries']]}


def capacity(db,product,company,branch,scope):
    """Fixed capacity projection. Never returns a balance or warehouse body."""
    from app.apps.srm.service_checkout import _source_scope
    warehouse=db.query(SRMWarehouse).filter_by(id=product.default_warehouse_id,organization_id=company,active=True).first() if product.default_warehouse_id else None
    if warehouse is None:return None
    _source_scope(db,scope,company,branch,SRMWarehouse,warehouse.id,master=True)
    native=BranchOwnership.__table__
    owner=db.connection().execute(select(native.c.company_id,native.c.branch_id).where(native.c.resource_table==warehouse.__tablename__,native.c.resource_key==str(warehouse.id))).first()
    if owner is None or tuple(owner)!=(company,branch):return None
    balance=SRMInventoryBalance.__table__;anchor=PackRecordOwnership.__table__
    query=select(balance.c.quantity).where(balance.c.organization_id==company,balance.c.product_id==product.id,balance.c.warehouse_id==warehouse.id,
        ~exists(select(anchor.c.id).where(anchor.c.resource_table==balance.name,anchor.c.resource_key==cast(balance.c.id,String))))
    quantity=db.connection().scalar(query)
    from app.business_packs.pharma.fefo import supported
    if supported(scope,product):
        from sqlalchemy import inspect
        from app.business_packs.pharma.models import MODELS
        if not all(inspect(db.connection()).has_table(m.__tablename__) for m in MODELS):return None
        from app.business_packs.pharma.reads import eligible_quantity
        quantity=min(Decimal(quantity or 0),eligible_quantity(db,scope,product.id,warehouse.id))
    return {'warehouse_id':warehouse.id,'available_quantity':str(Decimal(quantity or 0))}


def catalog(db,actor,selected=None,*,after=0,limit=200,search=''):
    from app.business_packs.catalog_predicate import _pos_projection,_workspace_predicate
    from app.shared.catalog_branches import availability_clause
    company,branch,scope=authority(db,actor,selected)
    query=db.query(SRMProduct).filter(SRMProduct.organization_id==company,SRMProduct.id>after,SRMProduct.active.is_(True),SRMProduct.deleted_at.is_(None),availability_clause(SRMProduct,branch))
    if search:
        query=query.filter(or_(*(column.contains(search,autoescape=True) for column in (SRMProduct.item_name,SRMProduct.sku,SRMProduct.barcode))))
    with _pos_projection(db,actor,scope):
        rows=query.filter(~_workspace_predicate(db,scope)).order_by(SRMProduct.id).limit(limit+1).all()
    items=[]
    feature_values=features(db,actor,scope)
    from app.apps.srm.service_checkout_models import ServiceBookingPolicy
    policies={row.service_product_id:row for row in db.query(ServiceBookingPolicy).filter_by(organization_id=company,branch_id=branch,pack_context_id=scope.context_id).filter(ServiceBookingPolicy.service_product_id.in_([row.id for row in rows[:limit]])).all()}
    for row in rows[:limit]:
        service=(row.product_type or '').lower() in {'service','services','membership','subscription','bundle'}
        physical=bool(row.track_inventory and not service)
        stock=capacity(db,row,company,branch,scope) if physical else None
        required=bool((row.metadata_json or {}).get('follow_up',{}).get('required')) if isinstance((row.metadata_json or {}).get('follow_up'),dict) else False
        tracked=not service and any((row.batch_tracking,row.serial_tracking,row.expiry_tracking))
        from app.business_packs.pharma.fefo import MAX_ALLOCATIONS, pos_batches, supported
        pharma_lot=supported(scope,row)
        policy=policies.get(row.id) if service else None
        reason=('Scheduling is inactive for this service' if policy and not policy.active else 'Appointment scheduling permission is required for this service' if policy and policy.booking_required and not feature_values['appointments_schedule'] else 'Required follow-up workflow is not integrated in this POS' if required else 'Tracked stock requires an allocation workflow' if tracked and not pharma_lot else 'No eligible stock warehouse is available' if physical and stock is None else None)
        lots = pos_batches(db, scope, row, stock['warehouse_id']) if pharma_lot and stock is not None else []
        if len(lots) > MAX_ALLOCATIONS:
            reason = 'Too many eligible batches. Reconcile stock before checkout.'
        items.append({key:getattr(row,key) for key in ('id','item_name','sku','barcode','category_name','product_type','sales_rate','mrp','gst_rate','unit_code')}|{
            'images':[value for value in (row.metadata_json or {}).get('images', []) if isinstance(value, str)][:10] if isinstance((row.metadata_json or {}).get('images'), list) else [],
            'duration_minutes':policy.default_duration_minutes if policy else None,
            'active':True,'track_inventory':physical,'batch_tracking':bool(row.batch_tracking and not service),'serial_tracking':bool(row.serial_tracking and not service),
            'expiry_tracking':bool(row.expiry_tracking and not service),'stock':stock,'booking_policy':({'required':policy.booking_required,'active':policy.active,'revision':policy.revision} if policy else None),'checkout_supported':reason is None,'unsupported_reason':reason,
            **({'lot_allocation':'fefo','lots':lots[:MAX_ALLOCATIONS]} if pharma_lot and stock is not None else {})})
    return {'items':items,'next':rows[limit-1].id if len(rows)>limit else None,'has_more':len(rows)>limit,'features':feature_values}


CUSTOMER_FIELDS=('id','name','phone','phone_country_code','email','address','city','state','country')
def customer_output(row):return {name:getattr(row,name) for name in CUSTOMER_FIELDS}


def customer_query(db,company):
    # Role metadata is a fixed parent-reference predicate, never a public role
    # directory or grant to read its rows. Visible account rows still pass the
    # native company/branch and exact PackMasterAvailability ORM boundaries.
    from app.shared.master_data_models import BusinessRelationship
    role=BusinessRelationship.__table__
    ids=select(role.c.account_id).where(role.c.organization_id==company,role.c.role=='Customer',role.c.status=='Active')
    # Connection projection deliberately reveals no relationships or private body.
    role_ids=list(db.connection().scalars(ids))
    query=db.query(CRMCompany).filter(CRMCompany.organization_id==company,CRMCompany.deleted_at.is_(None),CRMCompany.status=='Active',or_(CRMCompany.account_type=='Customer',CRMCompany.id.in_(role_ids)))
    from app.apps.srm.anonymous_cash import installed
    if installed(db.connection()):
        from app.apps.srm.anonymous_cash_models import AnonymousCashAccount
        table=AnonymousCashAccount.__table__
        controls=list(db.connection().scalars(select(table.c.customer_id).where(table.c.organization_id==company)))
        query=query.filter(~CRMCompany.id.in_(controls))
    return query


def customers(db,actor,selected=None,*,after=0,limit=50,search=''):
    company,branch,scope=authority(db,actor,selected)
    query=customer_query(db,company).filter(CRMCompany.id>after)
    if search:query=query.filter(or_(CRMCompany.name.contains(search,autoescape=True),CRMCompany.phone.contains(search,autoescape=True)))
    rows=query.order_by(CRMCompany.id).limit(limit+1).all()
    return {'items':[customer_output(row) for row in rows[:limit]],'next':rows[limit-1].id if len(rows)>limit else None,'features':features(db,actor,scope)}


def customer_detail(db,actor,ident,selected=None):
    company,branch,scope=authority(db,actor,selected)
    row=customer_query(db,company).filter(CRMCompany.id==ident).first()
    if row is None:fail('POS customer not found',404)
    return customer_output(row)


from .pos_customer_fields import CustomValueInput


class CustomerInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    custom_fields:list[CustomValueInput]=Field(default_factory=list,max_length=200)
    schema_fingerprint:str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$')
    name:str=Field(min_length=1,max_length=180)
    email:EmailAddress|None=Field(default=None,max_length=150)
    phone:NationalPhone|None=None
    phone_country_code:CallingCode|None=None
    address:str=Field(min_length=1,max_length=2000)
    city:str=Field(default='',max_length=100)
    state:str=Field(min_length=1,max_length=100)
    country:str=Field(min_length=2,max_length=100)
    @field_validator('name','city','state')
    @classmethod
    def plain(cls,value):return clean_text(value,180,required=bool(value))
    @field_validator('address')
    @classmethod
    def address_plain(cls,value):return clean_text(value,2000,multiline=True)
    @field_validator('country')
    @classmethod
    def country_code(cls,value):
        match=next((row['iso'] for row in CONTRACT['countries'] if value.casefold() in {row['iso'].casefold(),row['country'].casefold()}),None)
        if match is None:raise ValueError('Select a supported billing country')
        return match
    @model_validator(mode='after')
    def phone_pair(self):
        if bool(self.phone)!=bool(self.phone_country_code):raise ValueError('Provide both phone number and calling code')
        if self.phone:normalize_phone(self.phone,self.phone_country_code)
        return self


def create_customer(data,db,actor,selected=None):
    # Implemented only by the closed native account birth command below.
    company,branch,scope=authority(db,actor,selected,create=True)
    lock_tenant(db,actor)
    if authority(db,actor,selected,create=True)!=(company,branch,scope):fail('POS customer authority changed')
    from .pos_customer_fields import validate
    normalized,fingerprint=validate(db,actor,company,scope,data.custom_fields,data.schema_fingerprint)
    return _create_customer(data,db,actor,company,branch,scope,normalized,fingerprint)

def _create_customer(data,db,actor,company,branch,scope,custom_values,field_fingerprint):
    """Closed birth command: no update/adoption and no general SQL permission.

    Canonical identity hooks cannot query their broader directories under the
    operational boundary. These fixed statements create their same intrinsic
    account identity/channel projections only for the freshly inserted account.
    """
    from app.apps.crm.models import CRMContact
    from app.apps.crm.contact_identity import ContactIdentityLink
    from app.shared.master_data_models import ContactChannel,CompanyMasterDetails,BusinessRelationship
    from app.apps.srm.service_checkout import _source_scope
    with db.begin_nested():
        c=CRMCompany.__table__;contact=CRMContact.__table__;channels=ContactChannel.__table__
        phone,normalized=normalize_phone(data.phone,data.phone_country_code) if data.phone else (None,None)
        email=str(data.email).casefold() if data.email else None
        matches=[func.lower(func.trim(c.c.name))==data.name.casefold()]
        if email:matches.append(func.lower(c.c.email)==email)
        if phone:matches.append((c.c.phone==phone)&(c.c.phone_country_code==data.phone_country_code))
        connection=db.connection()
        duplicate=connection.scalar(select(c.c.id).where(func.coalesce(c.c.organization_id,1)==company,c.c.deleted_at.is_(None),or_(*matches)).limit(1))
        for kind,value in [('email',email),('phone',normalized)]:
            if not value:continue
            if connection.scalar(select(channels.c.id).where(channels.c.organization_id==company,channels.c.kind==kind,func.lower(channels.c.normalized_value)==value.casefold()).limit(1)):
                duplicate=True
            predicate=func.lower(contact.c.email)==email if kind=='email' else (contact.c.phone==phone)&(contact.c.phone_country_code==data.phone_country_code)
            if connection.scalar(select(contact.c.id).where(func.coalesce(contact.c.organization_id,1)==company,contact.c.deleted_at.is_(None),predicate).limit(1)):duplicate=True
        if duplicate:fail('A matching business identity already exists. Ask an authorized administrator to review the existing record.',409)
        values={'organization_id':company,'branch_id':branch,'name':data.name,'email':email,'phone':phone,'phone_country_code':data.phone_country_code if phone else None,
            'address':data.address,'city':data.city,'state':data.state,'country':data.country,'account_type':'Customer','status':'Active','owner_user_id':actor.id,'created_by_user_id':actor.id,'updated_by_user_id':actor.id}
        ident=connection.execute(c.insert().values(**values).returning(c.c.id)).scalar_one()
        owned=[(c.name,ident)]
        contact_id=connection.execute(contact.insert().values(organization_id=company,branch_id=branch,company_id=ident,full_name=data.name,first_name=data.name.split(' ',1)[0][:100],
            email=email,phone=phone,phone_country_code=data.phone_country_code if phone else None,owner_user_id=actor.id,created_by_user_id=actor.id,
            country=None,status='Active',lifecycle_stage='Customer',tags_text='Customer').returning(contact.c.id)).scalar_one()
        owned.append((contact.name,contact_id))
        link=ContactIdentityLink.__table__
        link_id=connection.execute(link.insert().values(organization_id=company,contact_id=contact_id,account_id=ident).returning(link.c.id)).scalar_one()
        owned.append((link.name,link_id))
        details=CompanyMasterDetails.__table__
        connection.execute(details.insert().values(account_id=ident,organization_id=company,business_type='Individual',addresses=[{'type':'Billing','line1':data.address,'city':data.city,'state':data.state,'country':data.country}],tax_registrations=[],version=1))
        owned.append((details.name,ident))
        roles=BusinessRelationship.__table__
        role_id=connection.execute(roles.insert().values(organization_id=company,account_id=ident,role='Customer',status='Active').returning(roles.c.id)).scalar_one()
        owned.append((roles.name,role_id))
        for kind,value,normalized_value,code in [('email',email,email,None),('phone',phone,normalized,data.phone_country_code)]:
            if not value:continue
            for field,owner_id in [('account_id',ident),('contact_id',contact_id)]:
                channel_id=connection.execute(channels.insert().values(organization_id=company,**{field:owner_id},kind=kind,value=value,normalized_value=normalized_value,country_code=code,
                    label='Primary',is_primary=True,whatsapp=False,verification_status='unverified').returning(channels.c.id)).scalar_one()
                owned.append((channels.name,channel_id))
        # Only identities returned by INSERT above can enter this lifecycle.
        # No existing source, context, owner or enrollment is accepted in input.
        owner=BranchOwnership.__table__
        for table,key in owned:
            connection.execute(owner.insert().values(company_id=company,branch_id=branch,resource_table=table,resource_key=str(key),source='pos_customer_birth'))
        availability=PackMasterAvailability.__table__
        connection.execute(availability.insert().values(company_id=company,branch_id=branch,context_id=scope.context_id,resource_table=c.name,resource_key=str(ident),active=True,revision=1))
        from .pos_customer_fields import _insert_values,assert_current
        _insert_values(db,actor,company,branch,ident,custom_values)
        assert_current(db,actor,company,scope,field_fingerprint)
        if authority(db,actor,str(scope.context_id),create=True)!=(company,branch,scope):fail('POS customer authority changed')
        row=db.query(CRMCompany).filter_by(id=ident,organization_id=company).one()
        _source_scope(db,scope,company,branch,CRMCompany,ident,master=True)
        result=customer_output(row)
        from app.apps.srm.api.router import _audit
        _audit(db,actor,'customer',ident,'quick_added',after=result)
        db.flush()
    db.commit()
    return result


def customer_schema(db,actor,selected=None):
    company,branch,scope=authority(db,actor,selected,create=True)
    from .pos_customer_fields import snapshot, _policy
    return snapshot(db,actor,company,scope).output()


def customer_identity(db, actor, ident, selected=None):
    """Only configured, FLS-visible operational identifiers for an authorized buyer."""
    company, branch, scope = authority(db, actor, selected)
    if customer_query(db, company).filter(CRMCompany.id == ident).first() is None:
        fail('POS customer not found', 404)
    from .pos_customer_fields import snapshot, _policy
    from app.apps.crm.models import CRMCustomFieldValue
    keys = {'patient_id','patient_number','medical_record_number','mrn','prescription_id',
            'prescription_reference','prescription_status','vehicle_registration','vehicle_number',
            'vehicle_model','vehicle_make','registration_number'}
    definitions = snapshot(db, actor, company, scope).definitions
    _, rules = _policy(db, actor)
    fields = {}
    for row in definitions:
        identifiers = {row['field_key'], 'cf_'+row['field_key'], row['field_name']}
        visible = row['is_visible'] is True and all(rule['can_view'] and not rule['mask_value'] for rule in rules if rule['field_name'] in identifiers)
        if visible and row['field_key'].lower().removeprefix('cf_') in keys:
            fields[row['id']] = row
    values = CRMCustomFieldValue.__table__
    rows = db.connection().execute(select(values).where(values.c.organization_id == company,
        values.c.entity == 'companies', values.c.record_id == ident, values.c.custom_field_id.in_(fields),
        values.c.deleted_at.is_(None))).mappings() if fields else []
    result = []
    for row in rows:
        value = next((row[key] for key in ('value_text','value_number','value_date','value_datetime','value_boolean','value_json') if row[key] is not None), None)
        if value is None or isinstance(value, dict):
            continue
        result.append({'label':fields[row['custom_field_id']]['label'], 'value':', '.join(map(str,value)) if isinstance(value,list) else str(value)})
    return {'customer_id':ident,'fields':result}
