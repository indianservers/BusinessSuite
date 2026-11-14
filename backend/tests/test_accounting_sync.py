from datetime import timedelta
import pytest
from fastapi import HTTPException
from app.shared.accounting_sync import service, providers
from app.shared.accounting_sync.models import SyncConnection, SyncRecord, SyncRun
from app.shared.import_models import ImportConnection
from app.shared.import_connectors import seal
from app.models.user import User
from tests.test_import_workspace import import_headers

BASE="/api/v1/accounting-sync/connections"


def test_shared_accounting_and_imports_use_real_module_entitlements(client, db, import_headers):
    from app.apps.business_os.models import BOSEnabledModule
    def enabled(module, value):
        row=db.query(BOSEnabledModule).filter_by(company_id=1,module_key=module).first()
        if row is None:
            row=BOSEnabledModule(company_id=1,module_key=module,display_name=module)
            db.add(row)
        row.enabled=value
        db.commit()
    enabled("api",False)
    enabled("import_api",False)
    assert client.get(BASE,headers=import_headers).status_code==200
    assert client.get('/api/v1/imports/crm/catalog',headers=import_headers).status_code==200
    enabled("fam",False)
    assert client.get(BASE,headers=import_headers).status_code==403
    assert client.get('/api/v1/imports/fam/catalog',headers=import_headers).status_code==403
    enabled("crm",False)
    assert client.get('/api/v1/imports/crm/catalog',headers=import_headers).status_code==403
    assert client.get('/api/v1/accounting-sync/customer-360/lead/999',headers=import_headers).status_code==403

def snapshot():
    return {"customers":[{"external_id":"c1","name":"Acme","currency":"INR"}],"invoices":[{"external_id":"i1","customer_external_id":"c1","currency":"INR","amount":"1000.10","outstanding":"600.10","status":"open"}],"payments":[{"external_id":"p1","customer_external_id":"c1","currency":"INR","amount":"400"}]}

def tally(client,headers,account="company-guid"):
    r=client.post(BASE,headers=headers,json={"provider":"tally","account_id":account})
    assert r.status_code==201,r.text
    return r.json()

def push(client,headers,connection,data):
    return client.post(f"{BASE}/{connection['id']}/snapshot",headers={**headers,"X-Accounting-Bridge-Token":connection['bridge_token']},json={"account_id":connection['account_id'],**data})

def test_snapshot_upsert_settlement_currency_and_removal(client,db,import_headers):
    c=tally(client,import_headers)
    first=push(client,import_headers,c,snapshot());assert first.status_code==200,first.text
    assert first.json()["counts"]["created"]==3
    again=push(client,import_headers,c,snapshot());assert again.json()["counts"]["unchanged"]==3
    balance=client.get(f"{BASE}/{c['id']}/balances",headers=import_headers).json()
    assert balance["items"]==[{"customer_external_id":"c1","currency":"INR","outstanding":"600.10"}]
    data=snapshot();data["invoices"][0]["outstanding"]="0";data["invoices"].append({"external_id":"i2","customer_external_id":"c1","currency":"USD","amount":"3","outstanding":"3"});data["payments"]=[]
    result=push(client,import_headers,c,data).json();assert result["counts"]["updated"]==1 and result["counts"]["missing"]==1
    rows=client.get(f"{BASE}/{c['id']}/records?entity=payments",headers=import_headers).json();assert rows["total"]==0
    assert db.query(SyncRecord).filter_by(connection_id=c['id']).count()==4
    assert len(client.get(f"{BASE}/{c['id']}/balances",headers=import_headers).json()["items"])==2
    assert len(client.get(f"{BASE}/{c['id']}/runs",headers=import_headers).json()["items"])==3

def test_failures_preserve_snapshot_and_log_run(client,db,import_headers):
    c=tally(client,import_headers);push(client,import_headers,c,snapshot())
    bad=snapshot();bad["invoices"][0]["amount"]="NaN"
    result=push(client,import_headers,c,bad).json();assert result["status"]=="failed"
    assert db.query(SyncRecord).filter_by(connection_id=c['id'],entity="invoices").one().data["amount"]=="1000.10"
    bad=snapshot();bad["customers"]*=2
    assert push(client,import_headers,c,bad).json()["status"]=="failed"
    assert push(client,import_headers,c,snapshot()).json()["status"]=="completed"

def test_bridge_authorization_pause_rotation_and_scope(client,db,import_headers):
    c=tally(client,import_headers)
    assert 'bridge_token' not in client.get(BASE,headers=import_headers).text
    no_token=client.post(f"{BASE}/{c['id']}/snapshot",headers=import_headers,json={"account_id":c['account_id'],**snapshot()});assert no_token.status_code==403
    assert push(client,import_headers,{**c,"account_id":"other"},snapshot()).status_code==409
    client.patch(f"{BASE}/{c['id']}",headers=import_headers,json={"enabled":False})
    assert push(client,import_headers,c,snapshot()).status_code==409
    client.patch(f"{BASE}/{c['id']}",headers=import_headers,json={"enabled":True})
    token=client.post(f"{BASE}/{c['id']}/rotate-bridge-token",headers=import_headers).json()["bridge_token"]
    assert push(client,import_headers,c,snapshot()).status_code==403
    c['bridge_token']=token;assert push(client,import_headers,c,snapshot()).json()["status"]=="completed"
    row=db.get(SyncConnection,c['id']);row.organization_id=99999;db.commit()
    assert client.get(f"{BASE}/{c['id']}/balances",headers=import_headers).status_code==404
    assert client.post(f"{BASE}/{c['id']}/sync",headers=import_headers).status_code==404

def test_run_lease_and_expiry(client,db,import_headers):
    c=tally(client,import_headers);row=db.get(SyncConnection,c['id'])
    old=service.acquire(db,row)
    with pytest.raises(HTTPException) as e:service.acquire(db,row)
    assert e.value.status_code==409
    row.lease_until=service.now()-timedelta(seconds=1);db.commit()
    new=service.acquire(db,row)
    assert db.get(SyncRun,old).status=="interrupted"
    with pytest.raises(providers.ProviderError):service.apply_snapshot(db,row,old,snapshot())
    service.apply_snapshot(db,row,new,snapshot())

@pytest.mark.parametrize("provider",["zoho","quickbooks"])
def test_cloud_oauth_binding_pull_and_no_native_posting(client,db,import_headers,monkeypatch,provider):
    actor=db.query(User).filter_by(email="testadmin@test.com").one()
    branch=int(import_headers["X-Suite-Branch"])
    # Use the authorized company resolved by the same request boundary.
    from app.apps.srm.services.commercial import tenant
    source=ImportConnection(id="cloud-source",organization_id=tenant(actor),branch_id=branch,created_by=actor.id,provider=provider,account_id="123",region="in",secret=seal({"access_token":"secret","expires_at":9999999999}))
    db.add(source);db.flush()
    from test_identity_utils import own_workflow_records
    own_workflow_records(db,source);db.commit()
    connected=client.post(BASE,headers=import_headers,json={"provider":provider,"source_connection_id":source.id,"sandbox":True});assert connected.status_code==201,connected.text
    calls=[]
    def get(url,headers,params):
        calls.append(url)
        if provider=="quickbooks":
            assert url.startswith("https://sandbox-quickbooks.api.intuit.com/")
            kind=params['query'].split()[3]
            rows={"Customer":[{"Id":"c1","DisplayName":"Acme","CurrencyRef":{"value":"INR"}}],"Invoice":[{"Id":"i1","CustomerRef":{"value":"c1"},"CurrencyRef":{"value":"INR"},"TotalAmt":"1000.10","Balance":"600.10"}],"Payment":[{"Id":"p1","CustomerRef":{"value":"c1"},"TotalAmt":400,"CurrencyRef":{"value":"INR"}}]}
            return {"QueryResponse":{kind:rows[kind]}}
        kind=url.rsplit('/',1)[1]
        rows={"contacts":[{"contact_id":"c1","contact_name":"Acme","currency_code":"INR"}],"invoices":[{"invoice_id":"i1","customer_id":"c1","currency_code":"INR","total":"1000.10","balance":"600.10"}],"customerpayments":[{"payment_id":"p1","customer_id":"c1","currency_code":"INR","amount":400}]}
        return {kind:rows[kind],"page_context":{"has_more_page":False}}
    monkeypatch.setattr(providers,"get_json",get)
    ident=connected.json()['id'];result=client.post(f"{BASE}/{ident}/sync",headers=import_headers)
    assert result.json()['status']=="completed",result.text
    assert len(calls)==3
    assert client.get(f"{BASE}/{ident}/balances",headers=import_headers).json()['items'][0]['outstanding']=="600.10"
    replacement=ImportConnection(id="replacement-source",organization_id=source.organization_id,branch_id=source.branch_id,created_by=source.created_by,provider=provider,account_id="123",region="in",secret=source.secret)
    db.add(replacement);db.flush();own_workflow_records(db,replacement);db.commit()
    reconnected=client.post(f"{BASE}/{ident}/reconnect",headers=import_headers,json={"source_connection_id":replacement.id,"sandbox":True})
    assert reconnected.status_code==200,reconnected.text
    assert client.post(f"{BASE}/{ident}/sync",headers=import_headers).json()['counts']['unchanged']==3
    if provider=="quickbooks":
        assert client.post(f"{BASE}/{ident}/reconnect",headers=import_headers,json={"source_connection_id":replacement.id,"sandbox":False}).status_code==409
    def fail(*a,**kw):raise providers.ProviderError("Provider unavailable")
    monkeypatch.setattr(providers,"get_json",fail)
    assert client.post(f"{BASE}/{ident}/sync",headers=import_headers).json()['status']=="failed"
    assert client.get(f"{BASE}/{ident}/records?entity=invoices",headers=import_headers).json()['total']==1

def test_tally_xml_safety_and_export_only():
    from app.shared.accounting_sync.tally import xml_root,export_request
    with pytest.raises(providers.ProviderError):xml_root(b'<!DOCTYPE foo [<!ENTITY x "boom">]><ENVELOPE/>')
    with pytest.raises(providers.ProviderError):xml_root(b'<ENVELOPE><LINEERROR>bad</LINEERROR></ENVELOPE>')
    xml=export_request('Acme & Co','Ledger')
    assert '<TALLYREQUEST>Export</TALLYREQUEST>' in xml and 'Acme &amp; Co' in xml
    assert 'Import' not in xml

def test_transport_retries_only_reads(monkeypatch):
    import httpx
    attempts=[]
    def handler(request):
        assert request.method=='GET';attempts.append(request)
        return httpx.Response(429,headers={'Retry-After':'0'}) if len(attempts)<3 else httpx.Response(200,json={'code':0})
    real=httpx.Client
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    monkeypatch.setattr(providers.time,'sleep',lambda _:None)
    assert providers.get_json('https://example.invalid',{}, {})=={'code':0}
    assert len(attempts)==3


def test_pagination_and_incomplete_response_fail_closed(monkeypatch):
    from types import SimpleNamespace
    source=SimpleNamespace(provider="zoho",account_id="123",region="in")
    conn=SimpleNamespace(provider="zoho",account_id="123",sandbox=False)
    monkeypatch.setattr(providers.oauth,"access_token",lambda *a:"private")
    pages=[]
    def get(url,headers,params):
        pages.append((url,params["page"]))
        kind=url.rsplit("/",1)[1]
        if kind=="contacts":
            return {"contacts":[{"contact_id":str(params["page"]),"contact_name":"Customer"}],"page_context":{"has_more_page":params["page"]==1}}
        return {kind:[],"page_context":{"has_more_page":False}}
    monkeypatch.setattr(providers,"get_json",get)
    data=providers.pull(None,conn,source)
    assert [r["external_id"] for r in data["customers"]]==["1","2"]
    assert len(pages)==4
    monkeypatch.setattr(providers,"get_json",lambda *a:{"contacts":[]})
    with pytest.raises(providers.ProviderError):providers.pull(None,conn,source)

def test_database_publish_failure_rolls_back_every_entity(client,db,import_headers,monkeypatch):
    c=tally(client,import_headers);push(client,import_headers,c,snapshot())
    original=db.commit;calls=[]
    def fail_publish():
        calls.append(1)
        if len(calls)==2: raise RuntimeError("private database detail")
        return original()
    monkeypatch.setattr(db,"commit",fail_publish)
    row=db.get(SyncConnection,c['id']);data=snapshot();data['customers'][0]['name']='Changed';data['invoices'][0]['outstanding']='0'
    run=service.execute(db,row,data)
    assert run.status=='failed' and 'private' not in run.error
    assert db.query(SyncRecord).filter_by(connection_id=c['id'],entity='customers').one().data['name']=='Acme'
    assert service.balances(db,c['id'])[0]['outstanding']=='600.10'

def test_tally_fixture_company_bill_and_receipt_reconciliation(monkeypatch):
    from app.shared.accounting_sync.tally import TallyReader,xml_root
    reader=TallyReader('Acme','company-guid','INR')
    fixtures={
      'Company':'<COMPANY NAME="Acme"><GUID>company-guid</GUID></COMPANY>',
      'Ledger':'<LEDGER NAME="Buyer"><GUID>customer-guid</GUID><ISBILLWISEON>Yes</ISBILLWISEON></LEDGER>',
      'Bills':'<BILL NAME="INV-1"><CLOSINGBALANCE>-600.10</CLOSINGBALANCE></BILL>',
      'Voucher':"""<VOUCHER><GUID>invoice-guid</GUID><VOUCHERTYPENAME>Sales</VOUCHERTYPENAME><PARTYLEDGERNAME>Buyer</PARTYLEDGERNAME><DATE>20261106</DATE><VOUCHERNUMBER>INV-1</VOUCHERNUMBER><ALLLEDGERENTRIES.LIST><LEDGERNAME>Buyer</LEDGERNAME><AMOUNT>-1000.10</AMOUNT><BILLALLOCATIONS.LIST><NAME>INV-1</NAME><BILLTYPE>New Ref</BILLTYPE></BILLALLOCATIONS.LIST></ALLLEDGERENTRIES.LIST></VOUCHER><VOUCHER><GUID>receipt-guid</GUID><VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME><DATE>20261106</DATE><ALLLEDGERENTRIES.LIST><LEDGERNAME>Buyer</LEDGERNAME><AMOUNT>400</AMOUNT></ALLLEDGERENTRIES.LIST></VOUCHER>"""}
    monkeypatch.setattr(reader,'collection',lambda kind,child=None:xml_root(('<ENVELOPE><COLLECTION>'+fixtures[kind]+'</COLLECTION></ENVELOPE>').encode()))
    data=reader.snapshot();assert data['account_id']=='company-guid'
    assert data['invoices'][0]['outstanding']=='600.10'
    assert data['payments'][0]['amount']=='400'
    fixtures['Bills']+='<BILL NAME="OPENING"><CLOSINGBALANCE>-20</CLOSINGBALANCE></BILL>'
    with pytest.raises(providers.ProviderError):reader.snapshot()

def test_frozen_migration_schema_matches_models():
    import sqlalchemy as sa
    from alembic.operations import Operations
    from alembic.migration import MigrationContext
    from app.shared.accounting_sync import schema
    engine=sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(sa.text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        conn.execute(sa.text('CREATE TABLE crm_companies (id INTEGER PRIMARY KEY)'))
        op=Operations(MigrationContext.configure(conn));schema.upgrade(op)
        from app.shared.accounting_sync import background_schema
        background_schema.upgrade(op)
        inspector=sa.inspect(conn)
        for model in (SyncConnection,SyncRecord,SyncRun):
            assert {c['name'] for c in inspector.get_columns(model.__tablename__)}==set(model.__table__.columns.keys())
        background_schema.downgrade(op)
        schema.downgrade(op)
        assert set(sa.inspect(conn).get_table_names())=={'users','crm_companies'}
    engine.dispose()
