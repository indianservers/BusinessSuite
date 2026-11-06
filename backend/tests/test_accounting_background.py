"""Mock providers drive scheduling, CRM links, invoice views and daily reports."""
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from app.models.user import User
from app.apps.crm.models import CRMCompany
from app.shared.import_models import ImportConnection
from app.shared.import_connectors import seal
from app.shared.accounting_sync import service, jobs
from app.shared.accounting_sync.models import SyncConnection, SyncRecord, SyncRun, SyncCustomerLink
from app.shared.accounting_sync.providers import ProviderError
from tests.test_import_workspace import import_headers
from test_identity_utils import own_workflow_records

BASE="/api/v1/accounting-sync"

def provider_snapshot():
    return {"customers":[{"external_id":"c1","name":"Acme","currency":"INR"},{"external_id":"c2","name":"Acme","currency":"INR"}],
      "invoices":[
        {"external_id":"i1","customer_external_id":"c1","number":"INV-1","currency":"INR","amount":"1000.10","outstanding":"600.10","date":"2026-11-07","due_date":"2026-11-08","status":"open"},
        {"external_id":"i2","customer_external_id":"c1","number":"INV-2","currency":"USD","amount":"20","outstanding":"10","date":"2026-11-06T20:00:00Z","status":"open"},
        {"external_id":"draft","customer_external_id":"c1","number":"DRAFT","currency":"INR","amount":"99","outstanding":"99","date":"2026-11-07","status":"draft"},
        {"external_id":"other","customer_external_id":"c2","number":"OTHER","currency":"INR","amount":"50","outstanding":"50","date":"2026-11-06","status":"open"}],
      "payments":[{"external_id":"p1","customer_external_id":"c1","reference":"RCPT-1","currency":"INR","amount":"400","date":"2026-11-07"},
                  {"external_id":"p2","customer_external_id":"c1","reference":"RCPT-2","currency":"USD","amount":"10","date":"2026-11-06T20:00:00Z"}]}

@pytest.fixture
def setup(client,db,import_headers):
    actor=db.query(User).filter_by(email="testadmin@test.com").one()
    source=ImportConnection(id=str(uuid4()),organization_id=1,branch_id=int(import_headers['X-Suite-Branch']),created_by=actor.id,provider="zoho",account_id="123",region="in",secret=seal({"access_token":"mock","expires_at":9999999999}))
    company=CRMCompany(organization_id=1,name="Acme",created_by_user_id=actor.id)
    unrelated=CRMCompany(organization_id=1,name="Acme",created_by_user_id=actor.id)
    db.add_all([source,company,unrelated]);db.flush();own_workflow_records(db,source,company,unrelated);db.commit()
    response=client.post(BASE+'/connections',headers=import_headers,json={"provider":"zoho","source_connection_id":source.id,"interval_minutes":5})
    assert response.status_code==201,response.text
    return response.json(),company.id,unrelated.id,actor.id,sessionmaker(bind=db.get_bind(),autoflush=False,join_transaction_mode="create_savepoint")

def force_due(db,identity):
    db.expire_all();row=db.get(SyncConnection,identity);row.next_sync_at=service.now()-timedelta(seconds=1);db.commit()

def test_background_sync_populates_customer_invoice_and_daily_views(client,db,import_headers,setup,monkeypatch):
    connection,company,other,actor,factory=setup
    calls=[]
    def pull(*args):calls.append(1);return deepcopy(provider_snapshot())
    monkeypatch.setattr(service,'pull',pull)
    result=jobs.process_due(factory)
    assert result['completed']==1,result
    db.expire_all();row=db.get(SyncConnection,connection['id']);assert row.last_success_at and row.next_sync_at and row.consecutive_failures==0
    assert jobs.process_due(factory)['completed']==0
    assert len(calls)==1
    mapped=client.put(f"{BASE}/connections/{row.id}/customer-links",headers=import_headers,json={"external_id":"c1","crm_company_id":company})
    assert mapped.status_code==200,mapped.text
    view=client.get(f"{BASE}/customer-360/company/{company}",headers=import_headers)
    assert view.status_code==200,view.text
    assert 'no-store' in view.headers['cache-control']
    data=view.json();assert data['invoice_count']==3 and data['payment_count']==2
    assert {(b['currency'],b['outstanding']) for b in data['balances']}=={('INR','600.10'),('USD','10')}
    assert client.get(f"{BASE}/customer-360/company/{other}",headers=import_headers).json()['links']==[]
    invoices=client.get(BASE+'/invoices',headers=import_headers,params={"crm_company_id":company,"page_size":1}).json()
    assert invoices['total']==3 and len(invoices['items'])==1 and invoices['items'][0]['provider']=='zoho'
    assert client.get(BASE+'/invoices',headers=import_headers,params={"q":"INV-1"}).json()['total']==1
    assert client.get(BASE+'/invoices',headers=import_headers,params={"q":"%"}).json()['total']==0
    report=client.get(BASE+'/daily-sales',headers=import_headers,params={"start_date":"2026-11-07","end_date":"2026-11-07"})
    assert report.status_code==200,report.text
    rows={r['currency']:r for r in report.json()['items']}
    assert rows['INR']['invoiced']=='1000.10' and rows['INR']['receipts']=='400'
    assert rows['USD']['invoiced']=='20' and rows['USD']['receipts']=='10'
    assert report.json()['timezone']=='Asia/Kolkata'
    assert report.json()['sources'][0]['as_of']
    assert client.get(BASE+'/daily-sales',headers=import_headers,params={"start_date":"2026-11-08","end_date":"2026-11-07"}).status_code==422
    # Settlement is reflected everywhere without creating native invoices or receipts.
    changed=provider_snapshot();changed['invoices'][0]['outstanding']='0';changed['invoices'][0]['status']='paid'
    monkeypatch.setattr(service,'pull',lambda *a:deepcopy(changed));force_due(db,row.id)
    assert jobs.process_due(factory)['completed']==1
    assert ('INR','0') in {(b['currency'],b['outstanding']) for b in client.get(f"{BASE}/customer-360/company/{company}",headers=import_headers).json()['balances']}
    from app.apps.srm.models import SRMInvoice,SRMReceipt
    assert db.query(SRMInvoice).count()==0 and db.query(SRMReceipt).count()==0
    # Removing a mapping removes the relationship, not provider history.
    link=mapped.json()
    assert client.delete(f"{BASE}/connections/{row.id}/customer-links/{link['id']}",headers=import_headers).status_code==204
    assert client.get(f"{BASE}/customer-360/company/{company}",headers=import_headers).json()['invoice_count']==0

def test_schedule_backoff_pause_and_permission_revocation(client,db,import_headers,setup,monkeypatch):
    connection,company,other,actor,factory=setup;identity=connection['id']
    monkeypatch.setattr(service,'pull',lambda *a:deepcopy(provider_snapshot()))
    assert jobs.process_due(factory)['completed']==1
    def fail(*a):raise ProviderError('Mock provider outage')
    monkeypatch.setattr(service,'pull',fail);force_due(db,identity)
    assert jobs.process_due(factory)['failed']==1
    db.expire_all();row=db.get(SyncConnection,identity)
    assert row.consecutive_failures==1 and row.schedule_error=='Mock provider outage'
    first=row.next_sync_at
    assert db.query(SyncRecord).filter_by(connection_id=identity,present=True).count()==8
    force_due(db,identity);assert jobs.process_due(factory)['failed']==1
    db.expire_all();assert db.get(SyncConnection,identity).next_sync_at>first
    client.patch(f"{BASE}/connections/{identity}",headers=import_headers,json={"enabled":False});force_due(db,identity)
    assert jobs.process_due(factory)['failed']==0
    client.patch(f"{BASE}/connections/{identity}",headers=import_headers,json={"enabled":True})
    assert client.put(f"{BASE}/connections/{identity}/schedule",headers=import_headers,json={"auto_sync":True,"interval_minutes":1}).status_code==422
    # Revoked owners cannot reuse saved provider credentials in the background.
    user=db.get(User,actor);user.is_active=False;db.commit();force_due(db,identity)
    result=jobs.process_due(factory);assert result['blocked']==1,result
    db.expire_all();assert 'blocked' in db.get(SyncConnection,identity).schedule_error

def test_scheduled_claim_is_atomic_and_disabled_schedule_not_claimed(client,db,import_headers,setup):
    connection,*_=setup;row=db.get(SyncConnection,connection['id'])
    token=service.acquire(db,row,scheduled=True)
    with pytest.raises(HTTPException):service.acquire(db,row,scheduled=True)
    service.apply_snapshot(db,row,token,provider_snapshot())
    response=client.put(f"{BASE}/connections/{row.id}/schedule",headers=import_headers,json={"auto_sync":False,"interval_minutes":30})
    assert response.status_code==200 and response.json()['next_sync_at'] is None
    with pytest.raises(HTTPException):service.acquire(db,row,scheduled=True)

def test_cross_company_links_and_consumers_are_hidden(client,db,import_headers,setup,monkeypatch):
    connection,company,other,actor,factory=setup
    monkeypatch.setattr(service,'pull',lambda *a:deepcopy(provider_snapshot()))
    assert jobs.process_due(factory)['completed']==1
    assert client.put(f"{BASE}/connections/{connection['id']}/customer-links",headers=import_headers,json={"external_id":"not-a-customer","crm_company_id":company}).status_code==404
    row=db.get(CRMCompany,other);row.organization_id=9999;db.commit()
    assert client.put(f"{BASE}/connections/{connection['id']}/customer-links",headers=import_headers,json={"external_id":"c1","crm_company_id":other}).status_code==404
    assert client.get(f"{BASE}/customer-360/company/{other}",headers=import_headers).status_code==404
    row=db.get(SyncConnection,connection['id']);row.organization_id=9999;db.commit()
    assert client.get(BASE+'/invoices',headers=import_headers).json()['total']==0
    assert client.get(BASE+'/daily-sales',headers=import_headers).json()['sources']==[]

def test_tally_agent_renews_session_without_reposting_successful_upload(monkeypatch):
    import importlib.util
    from pathlib import Path
    import httpx
    spec=importlib.util.spec_from_file_location('accounting_agent',Path(__file__).parents[1]/'scripts/accounting_sync_agent.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    session=module.AgentSession('https://suite.example','expired','refresh','bridge',1)
    calls=[]
    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith('/refresh'):return httpx.Response(200,json={"access_token":"renewed","refresh_token":"next"})
        if request.headers['Authorization']=='Bearer expired':return httpx.Response(401)
        return httpx.Response(200,json={"status":"completed"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert session.upload(client,'connection',provider_snapshot())['status']=='completed'
    assert len(calls)==3 and session.refresh=='next'


def test_active_owner_without_finance_grants_is_blocked(client,db,import_headers,setup,monkeypatch):
    connection,company,other,actor,factory=setup
    user=db.get(User,actor);user.is_superuser=False;db.commit()
    calls=[]
    monkeypatch.setattr(service,'pull',lambda *a:calls.append(1))
    result=jobs.process_due(factory)
    assert result['blocked']==1,result
    assert calls==[]


def test_scheduler_capability_rejects_missing_or_wrong_secret(client,db,monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,'CRON_SECRET','mock-scheduler-secret-only')
    calls=[]
    monkeypatch.setattr(jobs,'dispatch_due',lambda **kwargs:calls.append(kwargs) or {"completed":1})
    path='/api/v1/internal/accounting-sync'
    assert client.get(path).status_code==401
    assert client.get(path,headers={"Authorization":"Bearer wrong"}).status_code==401
    assert calls==[]
    response=client.get(path,headers={"Authorization":"Bearer mock-scheduler-secret-only"})
    assert response.status_code==200,response.text
    assert response.json()=={"completed":1} and calls==[{"limit":2}]


def test_shared_reader_sees_only_explicit_customer_links(client,db,import_headers,setup,monkeypatch):
    connection,company,other,actor,factory=setup
    monkeypatch.setattr(service,'pull',lambda *a:deepcopy(provider_snapshot()))
    assert jobs.process_due(factory)['completed']==1
    assert client.put(f"{BASE}/connections/{connection['id']}/customer-links",headers=import_headers,json={"external_id":"c1","crm_company_id":company}).status_code==200
    from tests.test_pms_workspaces import account
    viewer,headers=account(db,'accounting-finance-viewer@test.com',True)
    headers['X-Suite-Branch']=import_headers['X-Suite-Branch']
    # A different reader can see linked business data but not the owner's unlinked customer.
    data=client.get(BASE+'/invoices',headers=headers)
    assert data.status_code==200,data.text
    assert data.json()['total']==3
    assert all(r['customer_external_id']=='c1' for r in data.json()['items'])
    # Owner-only connection administration remains private.
    assert client.get(BASE+'/connections',headers=headers).json()['items']==[]
    assert client.get(f"{BASE}/connections/{connection['id']}/records?entity=customers",headers=headers).status_code==404
