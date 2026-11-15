"""Explicit anonymous counter control accounts and private financial source permit.

No names, JSON flags or public request fields confer authority. SQLAlchemy ORM,
bulk and structured Core mutations share a source-specific engine barrier.
Trusted exec_driver_sql is a server/migration escape hatch, not a public API.
"""
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass
import re
from fastapi import HTTPException
from sqlalchemy import event,inspect,select,and_,or_,Table,MetaData,Column,Integer,String,Boolean,DateTime
from sqlalchemy.engine import Engine
from sqlalchemy.sql.dml import Insert,Update,Delete
from sqlalchemy.sql.elements import TextClause
from app.db.base_class import Base
# Guard imports must not register an undeployed optional ORM model in Base.
_CONTROL=Table('srm_anonymous_cash_accounts',MetaData(),
    Column('id',Integer),Column('organization_id',Integer),Column('branch_id',Integer),Column('pack_context_id',Integer),
    Column('customer_id',Integer),Column('kind',String),Column('jurisdiction_country',String),Column('account_label',String),
    Column('active',Boolean),Column('revision',Integer),Column('created_by',Integer),
    Column('created_at',DateTime(timezone=True)),Column('updated_at',DateTime(timezone=True)))


def fail(message,code=403):raise HTTPException(code,message)

def installed(connection):
    inspector=inspect(connection);name=_CONTROL.name
    if not inspector.has_table(name):return False
    if not set(_CONTROL.c.keys())<={c['name'] for c in inspector.get_columns(name)}:
        fail('Anonymous counter account installation is incomplete',503)
    return True

def account_for_customer(connection,customer_id):
    if customer_id is None or not installed(connection):return None
    return connection.execute(select(_CONTROL).where(_CONTROL.c.customer_id==customer_id)).mappings().first()

@dataclass
class _Permit:
    account_id:int
    company:int
    branch:int
    context_id:int|None
    customer_id:int
    actor_id:int
    actor_role_id:int|None
    pack_scope:object
    financial_ready:bool=False

_TOKEN=object()
_KEY='anonymous_counter_private_permit'

@contextmanager
def checkout_permit(db,actor,account,scope):
    connection=db.connection()
    permit=_Permit(account['id'],account['organization_id'],account['branch_id'],account['pack_context_id'],account['customer_id'],actor.id,actor.role_id,scope)
    connection_info=connection.info
    previous=connection_info.get(_KEY)
    if previous is not None:fail('Anonymous counter transaction scopes cannot be nested')
    connection_info[_KEY]=(_TOKEN,permit)
    try:yield permit
    finally:
        if previous is None:connection_info.pop(_KEY,None)
        else:connection_info[_KEY]=previous


def _authorized(connection,account,*,financial=False):
    entry=connection.info.get(_KEY)
    if not isinstance(entry,tuple) or len(entry)!=2 or entry[0] is not _TOKEN:return False
    permit=entry[1]
    if (not isinstance(permit,_Permit) or (financial and not permit.financial_ready) or not account['active']
        or (permit.account_id,permit.company,permit.branch,permit.context_id,permit.customer_id)!=(account['id'],account['organization_id'],account['branch_id'],account['pack_context_id'],account['customer_id'])):return False
    from app.models.user import User
    from app.models.company import Branch
    actor=connection.execute(select(User.id).where(User.id==permit.actor_id,User.is_active.is_(True),User.role_id==permit.actor_role_id)).first()
    branch=connection.execute(select(Branch.id).where(Branch.id==permit.branch,Branch.company_id==permit.company,Branch.is_active.is_(True))).first()
    if not actor or not branch:return False
    if permit.pack_scope is not None:
        from app.business_packs.boundary import _current
        _current(permit.pack_scope,connection)
    return True


def guard_customer(db,customer_id,*,financial=False):
    account=account_for_customer(db.connection(),customer_id)
    if account and not _authorized(db.connection(),account,financial=financial):
        fail('Anonymous counter control accounts require a fully paid authorized counter checkout')

_ROOTS={'srm_sales_orders','srm_invoice_drafts','srm_invoices','srm_receipts','srm_engagements','srm_contracts','srm_pos_returns','srm_collection_reminders','srm_pos_service_checkouts'}
_LINKS={
    'srm_pos_checkout_lines':(('checkout_id','srm_pos_service_checkouts'),),
    'srm_pos_checkout_payments':(('checkout_id','srm_pos_service_checkouts'),('receipt_id','srm_receipts')),
    'srm_pos_service_occurrences':(('checkout_id','srm_pos_service_checkouts'),),
    'srm_sales_order_lines':(('sales_order_id','srm_sales_orders'),),
    'srm_invoice_lines':(('invoice_id','srm_invoices'),),
    'srm_receipt_allocations':(('receipt_id','srm_receipts'),('invoice_id','srm_invoices')),
    'srm_billing_plans':(('engagement_id','srm_engagements'),),
    'srm_billing_milestones':(('billing_plan_id','srm_billing_plans'),),
    'srm_pos_return_lines':(('return_id','srm_pos_returns'),),
    'srm_revenue_events':(('invoice_id','srm_invoices'),('engagement_id','srm_engagements')),
}
_MASTERS={'crm_companies','crm_contacts','suite_company_master_details','suite_contact_identity_links','suite_contact_channels','suite_company_contact_links','suite_business_relationships','suite_contact_birthdays'}
_ALLOWED={'srm_pos_service_checkouts','srm_pos_checkout_lines','srm_pos_checkout_payments','srm_sales_orders','srm_sales_order_lines','srm_invoice_drafts','srm_invoices','srm_invoice_lines','srm_receipts','srm_receipt_allocations','srm_revenue_events'}


def _table_name(table):
    while getattr(table,'original',None) is not None:table=table.original
    return table.name


def _customers(connection,table,rows):
    name=_table_name(table)
    result=set()
    if name=='crm_companies':result.update(row.get('id') for row in rows if row.get('id') is not None)
    if name in _MASTERS-{'crm_companies'}:
        for row in rows:
            for key in ('account_id','company_id'):
                if row.get(key) is not None:result.add(row[key])
            contact_id=row.get('contact_id') or (row.get('id') if name=='crm_contacts' else None)
            links=Base.metadata.tables.get('suite_contact_identity_links')
            if contact_id and links is not None:
                result.update(value for value in connection.execute(select(links.c.account_id).where(links.c.contact_id==contact_id)).scalars() if value is not None)
    if name in _ROOTS:
        result.update(row.get('customer_id') for row in rows if row.get('customer_id') is not None)
        if name=='srm_sales_orders':result.update(row.get('crm_company_id') for row in rows if row.get('crm_company_id') is not None)
    if name in _ROOTS:
        for row in rows:
            ids={row.get(key) for key in ('customer_id','crm_company_id') if row.get(key) is not None}
            if not ids:continue
            accounts=connection.execute(select(_CONTROL).where(_CONTROL.c.customer_id.in_(ids))).mappings().all()
            for account in accounts:
                if 'organization_id' in row and (row['organization_id'] or 1)!=account['organization_id']:fail('Anonymous financial source company differs')
                if row.get('branch_id') is not None and row['branch_id']!=account['branch_id']:fail('Anonymous financial source branch differs')
    for column,parent_name in _LINKS.get(_table_name(table),()):
        ids={row.get(column) for row in rows if row.get(column) is not None}
        parent=Base.metadata.tables.get(parent_name)
        if ids and parent is not None:
            values=connection.execute(select(parent).where(parent.c.id.in_(ids))).mappings().all()
            result.update(_customers(connection,parent,values))
    return result


def _params(clause,multiparams,params):
    rows=[dict(value) for value in multiparams] if multiparams else [dict(params or {})]
    for row in rows:
        for column,value in (getattr(clause,'_values',None) or {}).items():
            key=getattr(column,'key',column)
            if key not in row:
                if hasattr(value,'value'):row[key]=value.value
                elif isinstance(value,(str,int,type(None))):row[key]=value
    return rows


@event.listens_for(Engine,'before_execute')
def guard_financial_sources(connection,clause,multiparams,params,execution_options):
    if isinstance(clause,TextClause):
        return _guard_text(connection,clause,params,multiparams)
    if not isinstance(clause,(Insert,Update,Delete)):return
    table=clause.table
    if _table_name(table) not in _ROOTS|set(_LINKS)|_MASTERS:return
    if not installed(connection):return
    if not connection.execute(select(_CONTROL.c.id).limit(1)).first():return
    new_rows=_params(clause,multiparams,params)
    if isinstance(clause,Insert) and getattr(clause,'select',None) is not None:
        names=clause._select_names
        new_rows=[dict(zip(names,row)) for row in connection.execute(clause.select,params or {}).all()]
    customers=_customers(connection,table,new_rows)
    if isinstance(clause,Insert):
        for values in new_rows:
            if all(values.get(key.name) is not None for key in table.primary_key):
                existing=connection.execute(select(table).where(*(key==values[key.name] for key in table.primary_key))).mappings().all()
                customers.update(_customers(connection,table,existing))
        if getattr(clause,'_post_values_clause',None) is not None:fail('Use a native financial operation instead of an unclassified financial upsert')
    if isinstance(clause,(Update,Delete)):
        statement=select(table).where(*clause._where_criteria)
        for values in new_rows:
            try:old_rows=connection.execute(statement,values).mappings().all()
            except Exception:fail('Financial source ownership cannot be established')
            customers.update(_customers(connection,table,old_rows))
    accounts=connection.execute(select(_CONTROL).where(_CONTROL.c.customer_id.in_(customers))).mappings().all() if customers else []
    for account in accounts:
        if _table_name(table) not in _ALLOWED or not _authorized(connection,account,financial=True):
            fail('Anonymous counter financial sources can only change in their authorized checkout transaction')


def _guard_text(connection,clause,params,multiparams):
    sql=clause.text.strip()
    previous=None
    while previous!=sql:
        previous=sql
        sql=re.sub(r'(?s)^\s*(?:/\*.*?\*/|--[^\n]*(?:\n|$))','',sql).strip()
    matcher=re.search if sql.upper().startswith('WITH ') else re.match
    match=matcher(r'(?is)\b(insert\s+into|update|delete\s+from)\s+(?:(?:public|"public")\.)?["`]?([a-z_][a-z0-9_]*)["`]?',sql)
    if not match or match.group(2) not in _ROOTS|set(_LINKS)|_MASTERS:return
    if not installed(connection):return
    if not connection.execute(select(_CONTROL.c.id).limit(1)).first():return
    table=Base.metadata.tables.get(match.group(2))
    if table is None:fail('Financial source model is unavailable')
    valuesets=multiparams or [params or {}]
    customers=set()
    for values in valuesets:
        row={}
        if match.group(1).lower().startswith('insert'):
            insert=re.search(r'(?is)\(([^)]+)\)\s*values\s*\(([^)]+)\)',sql)
            if not insert:fail('Use a typed native financial insert with explicit source identity')
            for column,value in zip(insert.group(1).split(','),insert.group(2).split(',')):
                column=column.strip().strip('"`');value=value.strip()
                if value.startswith(':'):row[column]=values.get(value[1:])
                elif value.isdigit():row[column]=int(value)
                elif value.upper()!='NULL':fail('Use explicit financial source values')
        else:
            where=re.search(r'(?is)\bwhere\s+(?:[a-z_]+\.)?["`]?([a-z_]+)["`]?\s*=\s*(:[a-z_][a-z0-9_]*|[0-9]+)\s*;?$',sql)
            if not where or where.group(1) not in table.c:fail('Use a typed native financial mutation with exact source identity')
            raw=where.group(2);ident=values.get(raw[1:]) if raw.startswith(':') else int(raw)
            old=connection.execute(select(table).where(table.c[where.group(1)]==ident)).mappings().all()
            customers.update(_customers(connection,table,old))
            for column in ['customer_id','crm_company_id',*[link[0] for link in _LINKS.get(_table_name(table),())]]:
                value=re.search(r'(?is)\b'+re.escape(column)+r'\s*=\s*(:[a-z_][a-z0-9_]*|[0-9]+)',sql)
                if value:
                    raw=value.group(1);row[column]=values.get(raw[1:]) if raw.startswith(':') else int(raw)
        customers.update(_customers(connection,table,[row]))
    accounts=connection.execute(select(_CONTROL).where(_CONTROL.c.customer_id.in_(customers))).mappings().all() if customers else []
    for account in accounts:
        if _table_name(table) not in _ALLOWED or not _authorized(connection,account,financial=True):fail('Anonymous counter financial mutations require their private checkout transaction')


def _scope_query(db,company,branch,scope):
    from .anonymous_cash_models import AnonymousCashAccount
    return db.query(AnonymousCashAccount).filter_by(organization_id=company,branch_id=branch,pack_context_id=scope.context_id if scope else None)


def _validate_party(db,party,country,label,*,account=None,birth_actor=None):
    from app.shared.master_data_models import CompanyMasterDetails
    from app.apps.crm.models import CRMContact
    if party.name!=label or party.status!='Active' or party.deleted_at is not None or party.account_type!='Customer':fail('Select a dedicated active customer ledger control account',422)
    if any(getattr(party,key) for key in ('email','phone','phone_country_code','address','city','state','website')):fail('Anonymous control accounts cannot contain personal contact or address data',422)
    from app.core.input_validation import CONTRACT
    actual=next((c['iso'] for c in CONTRACT['countries'] if party.country in {c['iso'],c['country']}),None)
    if actual!=country:fail('The control account jurisdiction must match the explicit setup country',422)
    details=db.get(CompanyMasterDetails,party.id)
    if details and (details.addresses or details.tax_registrations or details.legal_name or details.trade_name or details.business_type=='Individual'):
        fail('Anonymous control accounts cannot impersonate a person or tax-registered customer',422)
    from app.apps.crm.contact_identity import ContactIdentityLink
    if db.info.get('business_pack_policy') is not None:
        # Fixed validation projection for this typed control account only. No
        # contact identities, names or bodies are returned to the caller.
        scope=db.info.get('business_pack_scope')
        from .service_checkout import _source_scope
        from .anonymous_cash_models import AnonymousCashAccount
        if account is None:
            from app.business_packs.anonymous_birth import assert_born_account
            if birth_actor is None or assert_born_account(db,birth_actor,party) is not scope:
                fail('Counter control source is outside this context')
        else:
            if (scope is None or inspect(account).session is not db
                    or not inspect(account).persistent or account.kind!='anonymous_cash'
                    or (account.organization_id,account.branch_id,account.pack_context_id,account.customer_id)
                        !=(scope.company_id,scope.branch_id,scope.context_id,party.id)
                    or party.organization_id!=scope.company_id):fail('Counter control source is outside this context')
            _source_scope(db,scope,scope.company_id,scope.branch_id,AnonymousCashAccount,account.id)
        contacts=CRMContact.__table__;links=ContactIdentityLink.__table__
        has_link=select(links.c.id).where(links.c.contact_id==contacts.c.id).exists()
        invalid_link=select(links.c.id).where(links.c.contact_id==contacts.c.id,or_(
            links.c.organization_id!=scope.company_id,links.c.account_id.is_(None),links.c.account_id!=party.id,
            links.c.person_id.is_not(None),links.c.employee_id.is_not(None),links.c.lead_id.is_not(None))).exists()
        invalid=select(contacts.c.id).where(contacts.c.company_id==party.id,or_(
            contacts.c.organization_id.is_(None),contacts.c.organization_id!=scope.company_id,
            contacts.c.full_name!=party.name,contacts.c.email.is_not(None)&(contacts.c.email!=''),
            contacts.c.phone.is_not(None)&(contacts.c.phone!=''),
            contacts.c.phone_country_code.is_not(None)&(contacts.c.phone_country_code!=''),~has_link,invalid_link)).exists()
        if db.connection().scalar(select(invalid)):
            fail('Anonymous control accounts cannot have personal contacts',422)
    else:
        for contact in db.query(CRMContact).filter_by(company_id=party.id):
            links=db.query(ContactIdentityLink).filter_by(contact_id=contact.id).all()
            if (not links or any(link.account_id!=party.id or link.person_id is not None or link.employee_id is not None or link.lead_id is not None for link in links)
                    or contact.full_name!=party.name or contact.email or contact.phone or contact.phone_country_code):
                fail('Anonymous control accounts cannot have personal contacts',422)


def resolve_account(db,user,company,branch,scope):
    from app.apps.crm.models import CRMCompany
    from .service_checkout import _source_scope
    if not installed(db.connection()):fail('Configure the anonymous counter account after installing its schema',503)
    from .anonymous_cash_models import AnonymousCashAccount
    row=_scope_query(db,company,branch,scope).populate_existing().first()
    if not row or not row.active:fail('An administrator must enable the anonymous counter control account first',409)
    _source_scope(db,scope,company,branch,AnonymousCashAccount,row.id)
    party=db.query(CRMCompany).filter_by(id=row.customer_id,organization_id=company).first()
    if not party:fail('Counter control party is outside this company',403)
    from app.branches.models import BranchOwnership
    proof=db.connection().execute(select(BranchOwnership.__table__).where(BranchOwnership.resource_table=='crm_companies',BranchOwnership.resource_key==str(party.id))).mappings().first()
    if not proof or (proof['company_id'],proof['branch_id'])!=(company,branch):fail('Counter control account is outside this branch')
    _validate_party(db,party,row.jurisdiction_country,row.account_label,account=row)
    return {column.name:getattr(row,column.name) for column in row.__table__.c}


def configure(data,db,user,*,commit=True):
    from .service_checkout import _authority,_stamp_new
    from app.access.settings_hub import context,can_edit_company
    from app.apps.srm.services.commercial import lock_tenant
    from app.shared.master_data import CompanyInput,write_company
    from app.apps.crm.models import CRMCompany
    from app.apps.srm.models import SRMSalesOrder,SRMInvoice,SRMReceipt
    company,branch,scope=_authority(db,user,configuration=True)
    control=context(db,user)
    if not control['admin'] or not can_edit_company(control):fail('Actual company administrator authority is required')
    if not installed(db.connection()):fail('Anonymous counter account installation is required',503)
    from .anonymous_cash_models import AnonymousCashAccount
    with db.begin_nested(), ExitStack() as birth_stack:
        lock_tenant(db,user)
        current=_scope_query(db,company,branch,scope).with_for_update().populate_existing().first()
        if current:
            if (data.action in {'create','select'} and data.expected_revision==0 and data.label==current.account_label
                    and data.jurisdiction_country==current.jurisdiction_country and data.active==current.active
                    and data.customer_id in (None,current.customer_id)):
                return {'id':current.id,'revision':current.revision,'active':current.active,'customer_id':current.customer_id}
            if data.expected_revision!=current.revision:fail('Counter account revision changed',409)
            if data.action!='status':fail('Counter account source identity cannot be replaced',409)
            current.active=data.active;db.flush()
            result={'id':current.id,'revision':current.revision,'active':current.active,'customer_id':current.customer_id}
        else:
            if data.expected_revision or data.action=='status':fail('Counter account does not exist',409)
            if data.action=='create':
                payload=CompanyInput(name=data.label,country=data.jurisdiction_country,roles=['Customer'],notes='Anonymous counter cash control ledger account. No named customer, personal address, contact or tax identity is asserted.')
                if scope is None:
                    party=write_company(db,user,'srm',payload)
                else:
                    from app.business_packs.anonymous_birth import canonical_account_birth
                    birth_stack.enter_context(canonical_account_birth(db,user,payload))
                    party=write_company(db,user,'srm',payload)
            else:
                party=db.query(CRMCompany).filter_by(id=data.customer_id,organization_id=company).first()
                if not party:fail('Selected customer account is outside this company',404)
                if any(db.query(model.id).filter_by(customer_id=party.id).first() for model in (SRMSalesOrder,SRMInvoice,SRMReceipt)):
                    fail('An existing transaction customer cannot be reclassified as anonymous cash',409)
            from app.apps.crm.contact_identity import link_source
            link_source(db,party,'account');db.flush()
            if scope is not None and data.action=='create':
                from app.business_packs.anonymous_birth import enroll_born_account
                enroll_born_account(db,user,party)
            _validate_party(db,party,data.jurisdiction_country,data.label,birth_actor=user if data.action=='create' else None)
            current=AnonymousCashAccount(organization_id=company,branch_id=branch,pack_context_id=scope.context_id if scope else None,
                customer_id=party.id,jurisdiction_country=data.jurisdiction_country,account_label=data.label,active=data.active,created_by=user.id)
            db.add(current);db.flush();_stamp_new(db,scope,company,branch,[current])
            _validate_party(db,party,data.jurisdiction_country,data.label,account=current)
            result={'id':current.id,'revision':current.revision,'active':current.active,'customer_id':current.customer_id}
        from app.apps.srm.api.router import _audit
        _audit(db,user,'anonymous_cash_account',current.id,'configured',after={**result,'reason':data.reason})
        db.flush()
    if commit:db.commit()
    return result
