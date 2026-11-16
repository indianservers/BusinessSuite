"""Isolated additive checkout persistence contracts; no runtime activation."""
import os
from pathlib import Path
import runpy
from types import SimpleNamespace
import app.apps.srm.service_checkout_models as checkout_models
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy import Column, Integer, String, JSON, Numeric, MetaData, Table, UniqueConstraint, create_engine, event, select, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.db.base_class import Base
from app.apps.srm.service_checkout_models import *

MIGRATION = Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261114_103_service_checkout.py'
COLLECTION_MIGRATION = Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261114_104_collection_session.py'

@pytest.fixture(params=['models', 'migration'])
def db(request, monkeypatch):
    native = {
        'companies': {}, 'branches': {'company_id': Integer}, 'users': {},
        'crm_companies': {'organization_id': Integer}, 'employees': {'branch_id': Integer},
        'srm_products': {'organization_id': Integer, 'product_type': String},
        'srm_industry_records': {'organization_id': Integer, 'branch_id': Integer, 'kind': String, 'data': JSON, 'customer_id': Integer},
        'srm_pos_sessions': {'organization_id': Integer, 'branch_id': Integer},
        'suite_branch_ownership': {'company_id': Integer, 'branch_id': Integer, 'resource_table': String, 'resource_key': String},
        'srm_sales_orders': {'organization_id': Integer, 'customer_id': Integer, 'currency': String},
        'srm_sales_order_lines': {'sales_order_id':Integer,'product_id':Integer,**{k:Numeric(24,10) for k in ('quantity','unit_price','discount_amount','tax_amount','line_total')}},
        'srm_invoices': {'organization_id':Integer,'customer_id':Integer,'currency':String,'sales_order_id':Integer},
        'srm_invoice_lines': {'invoice_id':Integer,'source_type':String,'source_id':Integer,**{k:Numeric(24,10) for k in ('quantity','unit_price','discount_amount','tax_amount','line_total')}},
        'srm_receipts': {'organization_id':Integer,'customer_id':Integer,'currency':String},
        'business_pack_contexts': {'company_id': Integer, 'branch_id': Integer},
    }
    metadata = MetaData()
    for name, fields in native.items():
        args = [Column('id', Integer, primary_key=True)] + [Column(k, v) for k,v in fields.items()]
        if name == 'business_pack_contexts': args.append(UniqueConstraint('id','company_id','branch_id'))
        table = Table(name, metadata, *args)
        if name not in Base.metadata.tables: table.to_metadata(Base.metadata)
    for model in MODELS: model.__table__.to_metadata(metadata)
    monkeypatch.setattr(checkout_models, "Base", SimpleNamespace(metadata=metadata))
    url = os.environ.get('SERVICE_CHECKOUT_TEST_DATABASE_URL', 'sqlite://')
    parsed = make_url(url)
    if parsed.get_backend_name() != 'sqlite':
        assert parsed.host in {'localhost','127.0.0.1','::1'}
        assert parsed.database.startswith('business_suite_service_models_') and parsed.database.endswith('_test')
    engine = create_engine(url)
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def fk(c, r): c.execute('PRAGMA foreign_keys=ON')
    metadata.drop_all(engine)
    if request.param == 'models': metadata.create_all(engine)
    else:
        metadata.create_all(engine, tables=[metadata.tables[n] for n in native])
        migration = runpy.run_path(str(MIGRATION))
        with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
            migration['upgrade'](); migration['upgrade'](); migration['downgrade']()
            collection_migration = runpy.run_path(str(COLLECTION_MIGRATION))
            collection_migration['upgrade'](); collection_migration['upgrade']()
            category_migration = runpy.run_path(str(Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261116_122_employee_categories.py'))
            category_migration['upgrade'](); category_migration['upgrade']()
    with engine.begin() as conn:
        seeds = {'companies':[{'id':1},{'id':2}], 'branches':[{'id':11,'company_id':1},{'id':22,'company_id':2}],
            'users':[{'id':1}], 'crm_companies':[{'id':201,'organization_id':1}],
            'srm_pos_sessions':[{'id':601,'organization_id':1,'branch_id':11}],
            'suite_branch_ownership':[{'id':1,'company_id':1,'branch_id':11,'resource_table':'srm_pos_sessions','resource_key':'601'}],
            'employees':[{'id':101,'branch_id':11}],
            'srm_sales_orders':[{'id':1001,'organization_id':1,'customer_id':201,'currency':'INR'}],
            'srm_sales_order_lines':[{'id':1101,'sales_order_id':1001,'product_id':401,'quantity':1,'unit_price':100,'discount_amount':0,'tax_amount':18,'line_total':118}],
            'srm_invoices':[{'id':1201,'organization_id':1,'customer_id':201,'currency':'INR','sales_order_id':1001}],
            'srm_invoice_lines':[{'id':1301,'invoice_id':1201,'source_type':'sales_order_line','source_id':1101,'quantity':1,'unit_price':100,'discount_amount':0,'tax_amount':18,'line_total':118}],
            'srm_receipts':[{'id':1401,'organization_id':1,'customer_id':201,'currency':'INR'}],
            'srm_products':[{'id':401,'organization_id':1,'product_type':'service'},{'id':402,'organization_id':1,'product_type':'goods'}],
            'business_pack_contexts':[{'id':1,'company_id':1,'branch_id':11},{'id':2,'company_id':1,'branch_id':11},{'id':3,'company_id':2,'branch_id':22}],
            'srm_industry_records':[{'id':301,'organization_id':1,'branch_id':11,'kind':'resource','data':{'employee_id':101},'customer_id':None},{'id':303,'organization_id':1,'branch_id':11,'kind':'appointment','data':{},'customer_id':201}]}
        for name, rows in seeds.items(): conn.execute(metadata.tables[name].insert(), rows)
    with Session(engine) as session: yield session
    metadata.drop_all(engine); engine.dispose()

def policy(context=None, **kw):
    return ServiceBookingPolicy(organization_id=1,branch_id=11,pack_context_id=context,service_product_id=401,
        default_duration_minutes=30,min_duration_minutes=5,max_duration_minutes=120,**kw)

def checkout(context=None, key=None, **kw):
    return POSServiceCheckout(organization_id=1,branch_id=11,pack_context_id=context,request_id=key or str(uuid4()),
        request_sha256='a'*64,created_by=1,customer_id=201,currency='INR',pos_session_id=601,billing_mode='invoice_at_checkout',**kw)

def test_six_tables_and_no_shadow_ledger(db):
    assert len(MODELS)==6
    assert 'amount' not in POSCheckoutPayment.__table__.c
    assert POSCheckoutPayment.__table__.c.collection_session_id.nullable
    assert POSServiceCheckout.__mapper__.version_id_col is POSServiceCheckout.__table__.c.revision
    assert {'uq_service_checkout_request_legacy','uq_service_checkout_request_pack'} <= {i['name'] for i in inspect(db.bind).get_indexes(POSServiceCheckout.__tablename__)}


def test_collection_register_can_bind_once_and_later_payment_uses_new_register(db):
    root = checkout(); db.add(root); db.flush()
    payment = POSCheckoutPayment(checkout_id=root.id, payment_key=str(uuid4()), receipt_id=1401, request_sha256='b'*64)
    db.add(payment); db.commit()
    assert payment.collection_session_id is None
    payment.collection_session_id = 601; db.commit()
    metadata = checkout_models.Base.metadata
    db.connection().execute(metadata.tables['srm_pos_sessions'].insert().values(id=602, organization_id=1, branch_id=11))
    db.connection().execute(metadata.tables['suite_branch_ownership'].insert().values(id=2, company_id=1, branch_id=11, resource_table='srm_pos_sessions', resource_key='602'))
    db.connection().execute(metadata.tables['srm_receipts'].insert().values(id=1402, organization_id=1, customer_id=201, currency='INR'))
    later = POSCheckoutPayment(checkout_id=root.id, payment_key=str(uuid4()), receipt_id=1402, request_sha256='c'*64, collection_session_id=602)
    db.add(later); db.commit()
    assert root.pos_session_id == 601 and later.collection_session_id == 602
    payment.collection_session_id = 602
    with pytest.raises(ServiceCheckoutIdentityError): db.commit()
    db.rollback()
    payment.collection_session_id = None
    with pytest.raises(ServiceCheckoutIdentityError): db.commit()


@pytest.mark.parametrize('company,branch', [(2, 22), (1, 22)])
def test_collection_register_rejects_foreign_company_or_branch(db, company, branch):
    root = checkout(); db.add(root); db.flush()
    db.connection().execute(checkout_models.Base.metadata.tables['srm_pos_sessions'].insert().values(id=602, organization_id=company, branch_id=branch))
    db.connection().execute(checkout_models.Base.metadata.tables['suite_branch_ownership'].insert().values(id=2, company_id=company, branch_id=branch, resource_table='srm_pos_sessions', resource_key='602'))
    db.add(POSCheckoutPayment(checkout_id=root.id, payment_key=str(uuid4()), receipt_id=1401,
        request_sha256='b'*64, collection_session_id=602))
    with pytest.raises(ServiceCheckoutIdentityError): db.commit()


def test_collection_register_requires_explicit_sidecar_even_if_branch_column_matches(db):
    root = checkout(); db.add(root); db.flush()
    db.connection().execute(checkout_models.Base.metadata.tables['srm_pos_sessions'].insert().values(id=602, organization_id=1, branch_id=11))
    db.add(POSCheckoutPayment(checkout_id=root.id, payment_key=str(uuid4()), receipt_id=1401,
        request_sha256='b'*64, collection_session_id=602))
    with pytest.raises(ServiceCheckoutIdentityError): db.commit()

@pytest.mark.parametrize('context',[None,1])
def test_request_retry_unique_but_other_context_independent(db,context):
    key=str(uuid4()); first=checkout(context,key); db.add(first); db.commit()
    db.add(checkout(context,key))
    with pytest.raises(IntegrityError): db.commit()
    db.rollback(); db.add(checkout(2,key)); db.commit()

@pytest.mark.parametrize('context',[None,1])
def test_policy_nullsafe_unique(db,context):
    db.add(policy(context)); db.commit(); db.add(policy(context))
    with pytest.raises(IntegrityError): db.commit()
    db.rollback(); db.add(policy(2)); db.commit()

def test_context_company_branch_cannot_be_spoofed(db):
    db.add(policy(3))
    with pytest.raises(IntegrityError): db.commit()

def test_policy_cannot_target_stock_or_foreign_branch(db):
    p=policy(); p.service_product_id=402; db.add(p)
    with pytest.raises(ServiceCheckoutIdentityError): db.commit()
    db.rollback(); p=policy();p.branch_id=22;db.add(p)
    with pytest.raises(ServiceCheckoutIdentityError): db.commit()

def test_generated_scope_key_cannot_be_supplied(db):
    p=policy(1);p.scope_context_key=2;db.add(p)
    with pytest.raises(Exception): db.commit()

def test_eligibility_exact_nullsafe_policy_source(db):
    p=policy();db.add(p);db.commit()
    db.add(ServiceSpecialistEligibility(organization_id=1,branch_id=11,pack_context_id=1,
        booking_policy_id=p.id,service_product_id=401,provider_resource_id=301))
    with pytest.raises(IntegrityError):db.commit()

def test_eligibility_nullsafe_uniqueness(db):
    p=policy();db.add(p);db.flush()
    def e(): return ServiceSpecialistEligibility(organization_id=1,branch_id=11,booking_policy_id=p.id,service_product_id=401,provider_resource_id=301)
    db.add(e());db.commit();db.add(e())
    with pytest.raises(IntegrityError):db.commit()

@pytest.mark.parametrize('field,value',[('state','approved'),('billing_mode','free'),('currency','inr'),('revision',0)])
def test_database_checks(db,field,value):
    values=dict(organization_id=1,branch_id=11,request_id=str(uuid4()),request_sha256='a'*64,created_by=1,
        customer_id=201,currency='INR',pos_session_id=601,billing_mode='invoice_at_checkout')
    values[field]=value
    with pytest.raises(IntegrityError): db.execute(POSServiceCheckout.__table__.insert().values(**values));db.commit()

def test_immutable_expired_identity_and_revision(db):
    p=policy();db.add(p);db.commit();db.expire(p);p.service_product_id=402
    with pytest.raises(ServiceCheckoutIdentityError):db.commit()
    db.rollback();p=db.get(ServiceBookingPolicy,p.id);p.revision=9
    with pytest.raises(ServiceCheckoutRevisionError):db.commit()

def test_optimistic_revision_updates_and_no_delete(db):
    p=policy();db.add(p);db.commit();assert p.revision==1
    p.active=False;db.commit();assert p.revision==2
    db.delete(p)
    with pytest.raises(ServiceCheckoutIdentityError):db.commit()

@pytest.mark.parametrize('field,value',[('request_id','invalid'),('request_sha256','x'*64),('revision',True)])
def test_malformed_typed_assignments(field,value):
    with pytest.raises(ValueError): checkout(**{field:value}) if field not in {'request_id','request_sha256'} else setattr(checkout(),field,value)

def test_reschedule_marker_cleanup(db):
    with pytest.raises(RuntimeError):
        with occurrence_reschedule_scope(db,7):
            assert db.info['service_checkout_reschedule']=={7}
            raise RuntimeError()
    assert 'service_checkout_reschedule' not in db.info
    with pytest.raises(ServiceCheckoutIdentityError):
        with occurrence_reschedule_scope(db,True): pass


def chain(db,context=None,start=None):
    p=policy(context);db.add(p);db.flush()
    eligibility=ServiceSpecialistEligibility(organization_id=1,branch_id=11,pack_context_id=context,
        booking_policy_id=p.id,service_product_id=401,provider_resource_id=301)
    db.add(eligibility);db.flush()
    root=checkout(context,sales_order_id=1001,invoice_id=1201);db.add(root);db.flush()
    line=POSCheckoutLine(checkout_id=root.id,client_line_key=str(uuid4()),line_kind='booked_service',product_id=401,
        sales_order_line_id=1101,invoice_line_id=1301,quantity=1,unit_price=100,discount_amount=0,tax_amount=18,line_total=118)
    db.add(line);db.flush()
    start=start or datetime.now(timezone.utc).replace(microsecond=0)+timedelta(days=1)
    occurrence=POSServiceOccurrence(checkout_id=root.id,checkout_line_id=line.id,occurrence_key=str(uuid4()),
        appointment_id=303,service_product_id=401,provider_resource_id=301,employee_id=101,
        starts_at=start,ends_at=start+timedelta(minutes=30),duration_minutes=30,
        booking_policy_id=p.id,policy_revision=p.revision,eligibility_id=eligibility.id,eligibility_revision=eligibility.revision)
    db.add(occurrence);db.flush()
    payment=POSCheckoutPayment(checkout_id=root.id,payment_key=str(uuid4()),receipt_id=1401,request_sha256='b'*64)
    db.add(payment);db.flush()
    return root,line,occurrence,payment

@pytest.mark.parametrize('context',[None,1])
def test_native_chain_inherits_exact_scope_and_preserves_ledger(db,context):
    root,line,occurrence,payment=chain(db,context);db.commit()
    assert all(x.scope_context_key==(context or 0) for x in (root,line,occurrence,payment))
    assert line.line_total==Decimal('118')
    assert 'actual_hours' not in occurrence.__table__.c

@pytest.mark.parametrize('kind',['price','appointment','payment','scope'])
def test_native_chain_identity_changes_denied(db,kind):
    root,line,occurrence,payment=chain(db);db.commit()
    if kind=='price':line.unit_price=99
    elif kind=='appointment':occurrence.appointment_id=301
    elif kind=='payment':payment.receipt_id=999
    else:line.scope_context_key=1
    with pytest.raises(ServiceCheckoutIdentityError):db.commit()

def test_occurrence_schedule_requires_marker_and_exact_duration(db):
    root,line,occurrence,payment=chain(db);db.commit()
    occurrence.ends_at=occurrence.ends_at.replace(tzinfo=timezone.utc)+timedelta(minutes=5)
    with pytest.raises(ServiceCheckoutIdentityError):db.commit()
    db.rollback()
    with occurrence_reschedule_scope(db,occurrence.id):
        occurrence.starts_at=occurrence.starts_at.replace(tzinfo=timezone.utc)+timedelta(hours=1)
        occurrence.ends_at=occurrence.ends_at.replace(tzinfo=timezone.utc)+timedelta(hours=1)
        db.commit()
    assert occurrence.revision==2
    with occurrence_reschedule_scope(db,occurrence.id):
        occurrence.duration_minutes=45
        with pytest.raises(ServiceCheckoutIdentityError):db.commit()

def test_native_charge_difference_denied_at_creation(db):
    root=checkout(sales_order_id=1001);db.add(root);db.flush()
    db.add(POSCheckoutLine(checkout_id=root.id,client_line_key=str(uuid4()),line_kind='booked_service',product_id=401,
        sales_order_line_id=1101,quantity=1,unit_price=99,discount_amount=0,tax_amount=18,line_total=117))
    with pytest.raises(ServiceCheckoutIdentityError):db.commit()

def test_stale_parallel_policy_revision_denied(db):
    p=policy();db.add(p);db.commit()
    with Session(db.bind) as other:
        stale=other.get(ServiceBookingPolicy,p.id)
        p.active=False;db.commit()
        stale.default_duration_minutes=45
        with pytest.raises(StaleDataError):other.commit()


def test_past_occurrence_cannot_reschedule_even_with_marker(db):
    root,line,occurrence,payment=chain(db,start=datetime.now(timezone.utc)-timedelta(days=1))
    db.commit()
    with occurrence_reschedule_scope(db,occurrence.id):
        occurrence.starts_at=datetime.now(timezone.utc)+timedelta(days=1)
        occurrence.ends_at=occurrence.starts_at+timedelta(minutes=30)
        with pytest.raises(ServiceCheckoutIdentityError):db.commit()


def test_policy_revision_snapshot_cannot_be_invented(db):
    root,line,occurrence,payment=chain(db);db.commit()
    with occurrence_reschedule_scope(db,occurrence.id):
        occurrence.policy_revision=500
        with pytest.raises(ServiceCheckoutIdentityError):db.commit()
