"""Native offering regressions using real API, catalog and customer records."""
from datetime import date
from decimal import Decimal
import pytest
from app.shared.offering_contracts import Duration, Plan
from app.shared.plan_engine import end_date
from app.shared.plan_models import CustomerPlan
from app.apps.crm.models import CRMCompany
from app.apps.srm.models import SRMProduct
from tests.test_shared_catalog import headers, create, item, ROOT
from tests.test_service_checkout import scenario
from tests.test_business_suite_pos_integrity import catalog
from tests.test_contact_directory import directory_identity


def config(**extra):
    return {"duration":{"unit":"month","count":6},"beneficiary_type":"family","beneficiary_limit":3,
        "benefits":[{"key":"swim","label":"Swimming sessions","type":"sessions","allowance":20}],**extra}


@pytest.mark.parametrize("kind",["membership","subscription"])
def test_native_plan_catalog_round_trip(client,db,headers,kind):
    offering=create(client,headers,item(kind,plan=config()))
    assert not db.get(SRMProduct,offering['id']).track_inventory
    for source in ['pms','crm','srm']:
        response=client.get(ROOT+'/items',params={'source':source,'kind':kind},headers=headers)
        assert response.status_code==200,response.text
        assert response.json()['items'][0]['kind']==kind
        assert response.json()['items'][0]['plan']['benefits'][0]['allowance']=='20'
        products=client.get(ROOT+'/items',params={'source':source,'kind':'product'},headers=headers)
        assert not products.json()['items']
    edited={k:v for k,v in offering.items() if k!='id'}
    edited['name']='Updated plan'
    response=client.put(f"{ROOT}/items/{kind}/{offering['id']}?source=pms",json=edited,headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['version']==2


def test_bundle_rejects_cycles_and_foreign_components(client,db,headers):
    product=create(client,headers)
    first=create(client,headers,item('bundle',code='B1',bundle={'components':[{'offering_id':product['id']}]}))
    second=create(client,headers,item('bundle',code='B2',bundle={'components':[{'offering_id':first['id']}]}))
    edited={k:v for k,v in first.items() if k!='id'}
    edited['bundle']['components']=[{'offering_id':second['id']}]
    response=client.put(f"{ROOT}/items/bundle/{first['id']}?source=pms",json=edited,headers=headers)
    assert response.status_code==422,response.text
    foreign=SRMProduct(organization_id=99,sku='FOREIGN',item_name='Foreign',product_type='stock',active=True)
    db.add(foreign);db.commit()
    response=client.post(ROOT+'/items?source=pms',headers=headers,json=item('bundle',code='B3',bundle={'components':[{'offering_id':foreign.id}]}))
    assert response.status_code==404,response.text


@pytest.mark.parametrize('payload',[
    item('membership'),item('subscription'),item('bundle'),
    item('membership',plan=config(),track_inventory=True),
    item('product',plan=config()),
    item('membership',plan=config(benefits=[{'key':'d','label':'Discount','type':'discount_percent','value':101}])),
    item('subscription',plan=config(billing={'automation':True})),
])
def test_invalid_offerings_rejected(client,headers,payload):
    response=client.post(ROOT+'/items?source=pms',headers=headers,json=payload)
    assert response.status_code==422,response.text


def purchased(client,db,headers,activation='purchase'):
    offering=create(client,headers,item('membership',plan=config(activation=activation)))
    buyer=CRMCompany(name='Plan customer',organization_id=1)
    db.add(buyer)
    from test_identity_utils import own_workflow_records
    own_workflow_records(db,buyer);db.commit()
    payload={'offering_id':offering['id'],'kind':'membership','customer_id':buyer.id,'request_key':'purchase-0001'}
    response=client.post('/api/v1/customer-plans?source=pms',headers=headers,json=payload)
    assert response.status_code==201,response.text
    return response.json(),payload


def test_issue_usage_retries_reversal_and_pause(client,db,headers):
    plan,payload=purchased(client,db,headers)
    listing=client.get('/api/v1/customer-plans',params={'source':'pms','customer_id':payload['customer_id']},headers=headers)
    assert listing.status_code==200,listing.text
    assert listing.json()['total']==1
    assert client.post('/api/v1/customer-plans?source=pms',headers=headers,json=payload).json()['id']==plan['id']
    assert db.query(CustomerPlan).count()==1
    path=f"/api/v1/customer-plans/{plan['id']}?source=pms"
    detail=client.get(path,headers=headers).json()
    benefit=detail['benefits'][0]
    consume=f"/api/v1/customer-plans/entitlements/{benefit['id']}/consume?source=pms"
    usage={'quantity':3,'request_key':'usage-000001','reference':'appointment-1'}
    result=client.post(consume,headers=headers,json=usage)
    assert result.status_code==200,result.text
    assert client.post(consume,headers=headers,json=usage).json()['id']==result.json()['id']
    assert Decimal(str(client.get(path,headers=headers).json()['benefits'][0]['remaining']))==17
    assert client.post(consume,headers=headers,json={**usage,'quantity':4}).status_code==409
    assert client.post(consume,headers=headers,json={**usage,'quantity':18,'request_key':'usage-000002'}).status_code==409
    reversal=client.post(f"/api/v1/customer-plans/usage/{result.json()['id']}/reverse?source=pms",headers=headers,json={'request_key':'reverse-0001'})
    assert reversal.status_code==200,reversal.text
    assert Decimal(str(client.get(path,headers=headers).json()['benefits'][0]['remaining']))==20
    assert client.post(f"/api/v1/customer-plans/usage/{result.json()['id']}/reverse?source=pms",headers=headers,json={'request_key':'reverse-0002'}).status_code==409
    pause=client.post(f"/api/v1/customer-plans/{plan['id']}/lifecycle?source=pms",headers=headers,json={'action':'pause','revision':1,'request_key':'pause-000001'})
    assert pause.status_code==200,pause.text
    assert client.post(consume,headers=headers,json={**usage,'request_key':'usage-paused'}).status_code==422


def test_approval_does_not_grant_access_and_tenant_isolation(client,db,headers):
    plan,_=purchased(client,db,headers,'approval')
    detail=client.get(f"/api/v1/customer-plans/{plan['id']}?source=pms",headers=headers).json()
    assert detail['status']=='pending'
    response=client.post(f"/api/v1/customer-plans/entitlements/{detail['benefits'][0]['id']}/consume?source=pms",headers=headers,json={'quantity':1,'request_key':'pending-usage','reference':'booking'})
    assert response.status_code==422,response.text
    row=db.get(CustomerPlan,plan['id']);row.organization_id=99;db.commit()
    assert client.get(f"/api/v1/customer-plans/{plan['id']}?source=pms",headers=headers).status_code==404


def test_calendar_duration_and_independent_billing():
    assert end_date(date(2028,1,31),Duration(unit='month',count=1))==date(2028,2,29)
    assert end_date(date(2028,2,29),Duration(unit='year',count=1))==date(2029,2,28)
    assert end_date(date.today(),Duration(unit='lifetime')) is None
    plan=Plan.model_validate(config(billing={'interval_unit':'month','interval_count':1}))
    assert plan.duration.count==6 and plan.billing.interval_count==1


def test_paid_pos_checkout_issues_plan_once_and_preserves_approval(db,scenario):
    from tests.test_srm_native_transaction_operations import native_writer
    from app.shared.catalog import save_item, ItemInput
    from app.apps.srm.service_checkout import checkout
    from app.apps.srm.service_checkout_schemas import CheckoutInput
    from uuid import uuid4
    user,branch,_,basket=scenario
    with native_writer(db,user,branch):
        offering=save_item(db,user,'srm',ItemInput(kind='membership',code='POS-PLAN',name='Six month access',price=100,tax=18,plan=config(activation='approval')))
        db.commit()
        original=basket(False).model_dump(mode='json')
        original['lines']=[{'client_line_key':str(uuid4()),'line_kind':'product','product_id':offering['id'],'quantity':'1'}]
        original['payments']=[{'payment_key':str(uuid4()),'method':'cash','amount':'118'}]
        data=CheckoutInput.model_validate(original)
        result=checkout(data,db,user)
        assert checkout(data,db,user)==result
        plans=db.query(CustomerPlan).filter_by(offering_id=offering['id']).all()
        assert len(plans)==1 and plans[0].status=='pending'
        assert plans[0].price_snapshot['price']=='100.00'


@pytest.mark.parametrize('filename',['alembic/versions/20261119_088_customer_plans.py','alembic_postgresql/versions/pg_20261119_127_customer_plans.py'])
def test_additive_migration_and_safe_empty_downgrade(filename):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    spec=importlib.util.spec_from_file_location('plan_migration',Path(__file__).parents[1]/filename)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with create_engine('sqlite://').begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert 'catalog_usage_ledger' in inspect(connection).get_table_names()
            migration.downgrade()
            assert 'catalog_usage_ledger' not in inspect(connection).get_table_names()


def test_postgres_migration_compiles_history_triggers_without_live_database():
    import importlib.util
    from pathlib import Path
    from io import StringIO
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path=Path(__file__).parents[1]/'alembic_postgresql/versions/pg_20261119_127_customer_plans.py'
    spec=importlib.util.spec_from_file_location('plan_pg_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    output=StringIO()
    with Operations.context(MigrationContext.configure(dialect_name='postgresql',opts={'as_sql':True,'output_buffer':output})):
        migration.upgrade()
    assert 'CREATE FUNCTION catalog_reject_history_mutation()' in output.getvalue()
    assert 'BEFORE UPDATE OR DELETE ON catalog_usage_ledger' in output.getvalue()


def test_customer_plan_views_filter_states_and_effective_dates_before_pagination(client,db,headers):
    from datetime import timedelta
    plan,payload=purchased(client,db,headers)
    params={'customer_id':payload['customer_id'],'source':'pms','view':'active','per_page':1}
    assert client.get('/api/v1/customer-plans',params=params,headers=headers).json()['total']==1
    paused=client.post(f"/api/v1/customer-plans/{plan['id']}/lifecycle?source=pms",headers=headers,json={'action':'pause','revision':1,'request_key':'view-pause-001'})
    assert paused.status_code==200,paused.text
    assert client.get('/api/v1/customer-plans',params=params,headers=headers).json()['total']==0
    assert client.get('/api/v1/customer-plans',params={**params,'view':'all'},headers=headers).json()['total']==1
    assert client.get('/api/v1/customer-plans',params={**params,'view':'renewals'},headers=headers).json()['total']==1
    row=db.get(CustomerPlan,plan['id']);row.status='active';row.start_date=date.today()-timedelta(days=90);row.end_date=date.today()-timedelta(days=1);db.commit()
    assert client.get('/api/v1/customer-plans',params=params,headers=headers).json()['total']==0
    assert client.get('/api/v1/customer-plans',params={**params,'view':'all'},headers=headers).json()['total']==1
    row.status='cancelled';db.commit()
    assert client.get('/api/v1/customer-plans',params={**params,'view':'renewals'},headers=headers).json()['total']==0
