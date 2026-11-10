from datetime import date, timedelta
from uuid import uuid4
from io import BytesIO
import pytest
from tests.rich_text_test_utils import organization_context
from app.models.asset import Asset, AssetAssignment
from app.models.employee import Employee
from app.models.exit import ExitRecord, ExitChecklistItem
from app.models.notification import Notification
from app.models.audit import AuditLog
B='/api/v1/assets'; TODAY=date.today()

def person(db,code='ASSET-E'):
    e=Employee(employee_id=code,first_name='Asset',last_name=code,status='Active',date_of_joining=TODAY-timedelta(days=500));db.add(e);db.commit();return e

def create(c,h,**v):
    r=c.post(B+'/',headers=h,json={'name':'Work laptop','asset_tag':uuid4().hex[:20],**v});assert r.status_code==201,r.text;return r.json()

def batch(c,h,e,ids,**v):return c.post(B+'/assignments/batch',headers=h,json={'employee_id':e.id,'asset_ids':ids,'assigned_date':str(TODAY),'request_key':uuid4().hex,**v})
def assigned(c,h,db):
    e=person(db);a=create(c,h);r=batch(c,h,e,[a['id']]);assert r.status_code==201,r.text;return e,a,r.json()['assignment_ids'][0]
def receive(c,h,i,condition='Good',**v):return c.post(B+f'/assignments/{i}/receive',headers=h,json={'return_date':str(TODAY),'condition':condition,**v})
def inspect(c,h,i,**v):return c.post(B+f'/assignments/{i}/inspection',headers=h,json={'comments':'Physical inspection complete','disposition':'Available','condition':'Good',**v})
def decide(c,h,i,d='approve'):return c.post(B+f'/approvals/{i}/decision',headers=h,json={'decision':d,'reason':'Verified against company policy'})

@pytest.mark.parametrize('category',['Laptop','Phone','Bike','Car','Furniture','Network switch','Industrial tool'])
def test_any_category(client,db,superuser_headers,category):
    r=client.post(B+'/categories',headers=superuser_headers,json={'name':category});assert r.status_code==201,r.text
    a=create(client,superuser_headers,name=category,category_id=r.json()['id'],details={'supplier':'Supplier','engine_number':'ENG','custom_fields':{'color':'blue'}},location='HQ',purchase_cost='1500.50')
    assert client.get(B+f"/{a['id']}",headers=superuser_headers).json()['details']['custom_fields']['color']=='blue'

@pytest.mark.parametrize('field,value',[('name',''),('name',' '),('asset_tag',''),('asset_tag',' '),('purchase_cost',-1),('status','Assigned'),('status','Bogus'),('condition','Broken'),('details',{'insurance_expiry':'bad'}),('category_id',99999)])
def test_invalid_asset(client,superuser_headers,field,value):
    assert client.post(B+'/',headers=superuser_headers,json={'name':'Asset','asset_tag':uuid4().hex,field:value}).status_code==422

@pytest.mark.parametrize('field',['asset_tag','serial_number'])
def test_duplicates(client,superuser_headers,field):
    value=uuid4().hex;create(client,superuser_headers,**{field:value})
    assert client.post(B+'/',headers=superuser_headers,json={'name':'Duplicate','asset_tag':uuid4().hex,field:value}).status_code==409

@pytest.mark.parametrize('change',[{'asset_ids':[]},{'asset_ids':[1,1]},{'asset_ids':[-1]},{'assigned_date':str(TODAY+timedelta(days=1))},{'expected_return_date':str(TODAY-timedelta(days=1))},{'condition_at_assignment':'Damaged'}])
def test_invalid_handover(client,db,superuser_headers,change):
    e=person(db);a=create(client,superuser_headers)
    assert batch(client,superuser_headers,e,change.get('asset_ids',[a['id']]),**{k:v for k,v in change.items() if k!='asset_ids'}).status_code==422


def test_atomic_batch_and_idempotency(client,db,superuser_headers):
    e=person(db);a=create(client,superuser_headers);b=create(client,superuser_headers);key=uuid4().hex
    first=batch(client,superuser_headers,e,[a['id']],request_key=key);assert first.status_code==201,first.text
    assert batch(client,superuser_headers,e,[a['id']],request_key=key).json()==first.json()
    assert batch(client,superuser_headers,e,[b['id'],a['id']]).status_code==409
    assert db.get(Asset,b['id']).status=='Available' and db.query(AssetAssignment).count()==1
    assert batch(client,superuser_headers,e,[a['id']],request_key=key,remarks='Changed').status_code==409

@pytest.mark.parametrize('condition,disposition,physical',[('New','Available','New'),('Good','Available','Good'),('Fair','Available','Fair'),('Poor','Under Repair','Poor'),('Damaged','Under Repair','Damaged'),('Under Repair','Under Repair','Poor'),('Under Inspection','Available','Good'),('Missing Accessories','Under Repair','Fair')])
def test_inspection_lifecycle(client,db,superuser_headers,condition,disposition,physical):
    e,a,i=assigned(client,superuser_headers,db)
    r=receive(client,superuser_headers,i,condition);assert r.status_code==200,r.text
    assert db.get(Asset,a['id']).status=='Pending Inspection'
    assert batch(client,superuser_headers,e,[a['id']]).status_code==409
    assert receive(client,superuser_headers,i).status_code==409
    r=inspect(client,superuser_headers,i,disposition=disposition,condition=physical);assert r.status_code==200,r.text
    result=decide(client,superuser_headers,r.json()['id']);assert result.status_code==200,result.text
    assert db.get(Asset,a['id']).status==disposition and db.get(AssetAssignment,i).inspection_status=='Approved'
    assert decide(client,superuser_headers,r.json()['id']).status_code in {400,409}

@pytest.mark.parametrize('change',[{'return_date':'2000-01-01'},{'return_date':str(TODAY+timedelta(days=1))},{'condition':'Invalid'},{'photo_document_ids':[99999]},{'accessories_returned':['Key'],'missing_accessories':['Key']},{'condition':'Lost','damage_description':''}])
def test_invalid_returns(client,db,superuser_headers,change):
    _,_,i=assigned(client,superuser_headers,db)
    assert receive(client,superuser_headers,i,**change).status_code==422
    assert db.get(AssetAssignment,i).is_active


def test_missing_accessories_reject_and_resubmit(client,db,superuser_headers):
    e=person(db);a=create(client,superuser_headers);i=batch(client,superuser_headers,e,[a['id']],accessories=['Charger','Bag']).json()['assignment_ids'][0]
    assert receive(client,superuser_headers,i,accessories_returned=['Bag']).status_code==200
    assert db.get(AssetAssignment,i).return_details['missing_accessories']==['Charger']
    assert inspect(client,superuser_headers,i).status_code==422
    r=inspect(client,superuser_headers,i,missing_resolved=True);assert r.status_code==200,r.text
    assert decide(client,superuser_headers,r.json()['id'],'reject').status_code==200
    assert db.get(Asset,a['id']).status=='Pending Inspection'
    assert inspect(client,superuser_headers,i,missing_resolved=True).status_code==200


def test_recovery_policy_approval_settlement(client,db,superuser_headers):
    _,_,i=assigned(client,superuser_headers,db);receive(client,superuser_headers,i,'Damaged')
    payload={'amount':'125.00','reason':'Screen damage assessed','policy_reference':'HR policy 42'};url=B+f'/assignments/{i}/recovery'
    assert client.post(url,headers=superuser_headers,json=payload).status_code==409
    r=client.post(B+'/policy',headers=superuser_headers,json={'recovery_enabled':True,'recovery_limit':'500'});assert r.status_code==200,r.text
    r=client.post(url,headers=superuser_headers,json=payload);assert r.status_code==200,r.text
    assert client.post(url,headers=superuser_headers,json=payload).status_code==409
    settle=B+f'/assignments/{i}/settle-recovery'
    assert client.post(settle,headers=superuser_headers,json={'reference':'BANK-12'}).status_code==409
    assert decide(client,superuser_headers,r.json()['id']).status_code==200
    r=client.post(settle,headers=superuser_headers,json={'reference':'BANK-12'});assert r.status_code==200,r.text
    assert r.json()['payroll_deduction_created'] is False

@pytest.mark.parametrize('payload',[{'amount':-1,'reason':'Bad','policy_reference':'P'},{'amount':0,'reason':'Bad','policy_reference':'P'},{'amount':1,'reason':'','policy_reference':'Policy'},{'amount':1,'reason':'Damage proposal','policy_reference':''},{'amount':1001,'reason':'Damage proposal','policy_reference':'Policy'}])
def test_invalid_recovery(client,db,superuser_headers,payload):
    _,_,i=assigned(client,superuser_headers,db);receive(client,superuser_headers,i)
    client.post(B+'/policy',headers=superuser_headers,json={'recovery_enabled':True,'recovery_limit':'1000'})
    assert client.post(B+f'/assignments/{i}/recovery',headers=superuser_headers,json=payload).status_code==422


def test_transfer_audit_and_new_ack(client,db,superuser_headers):
    _,a,i=assigned(client,superuser_headers,db);other=person(db,'OTHER')
    r=client.post(B+f'/assignments/{i}/transfer',headers=superuser_headers,json={'employee_id':other.id,'reason':'Team reassignment','assigned_date':str(TODAY)})
    assert r.status_code==201,r.text
    new=db.get(AssetAssignment,r.json()['assignment_id']);assert new.is_active and not new.acknowledgement_signed and new.employee_id==other.id
    assert not db.get(AssetAssignment,i).is_active and db.get(Asset,a['id']).status=='Assigned'
    assert db.query(AuditLog).filter_by(entity_type='asset',entity_id=a['id'],action='reassignment').count()==1


def test_extension_and_reminder_dedup(client,db,superuser_headers):
    _,_,i=assigned(client,superuser_headers,db);url=B+f'/assignments/{i}/extend'
    assert client.post(url,headers=superuser_headers,json={'expected_return_date':str(TODAY+timedelta(days=3)),'reason':'Project extended'}).status_code==200
    assert client.post(url,headers=superuser_headers,json={'expected_return_date':str(TODAY),'reason':'Backdate'}).status_code==422
    client.post(B+'/policy',headers=superuser_headers,json={})
    first=client.post(B+'/reminders/run',headers=superuser_headers);assert first.status_code==200,first.text
    assert first.json()['queued']>=1
    assert client.post(B+'/reminders/run',headers=superuser_headers).json()['queued']==0


def test_exit_inspection_gate_and_certificate(client,db,superuser_headers):
    e,a,i=assigned(client,superuser_headers,db)
    r=client.post('/api/v1/exit/records',headers=superuser_headers,json={'employee_id':e.id,'exit_type':'Resignation','last_working_date':str(TODAY)});assert r.status_code==201,r.text
    identity=r.json()['id'];url=B+f'/exit-clearance/{identity}/complete-assets'
    assert client.post(url,headers=superuser_headers).status_code==409
    receive(client,superuser_headers,i);assert client.post(url,headers=superuser_headers).status_code==409
    r=inspect(client,superuser_headers,i);decide(client,superuser_headers,r.json()['id'])
    r=client.post(url,headers=superuser_headers);assert r.status_code==200,r.text
    assert not r.json()['company_exit_completed'] and db.get(ExitRecord,identity).status=='Initiated'
    assert all(t.is_completed==('asset' in t.task_name.lower()) for t in db.query(ExitChecklistItem).filter_by(exit_record_id=identity))
    r=client.get(B+f'/exit-clearance/{identity}/certificate',headers=superuser_headers);assert r.status_code==200 and r.content.startswith(b'%PDF-'),r.text[:100]


def test_upload_shared_evidence_and_pdf_receipt(client,db,superuser_headers,tmp_path,monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,'UPLOAD_DIR',str(tmp_path))
    _,a,i=assigned(client,superuser_headers,db)
    r=client.post('/api/v1/access/services/documents',headers=superuser_headers,data={'companyId':'1','module':'hrms','entity':'asset','entityId':str(a['id'])},files={'file':('evidence.pdf',BytesIO(b'%PDF-1.4 asset evidence'),'application/pdf')})
    assert r.status_code==201,r.text;doc=r.json();assert 'storage_path' not in doc
    assert client.get(f"/api/v1/access/services/documents/{doc['id']}/download",headers=superuser_headers).content==b'%PDF-1.4 asset evidence'
    assert receive(client,superuser_headers,i,photo_document_ids=[doc['id']]).status_code==200
    r=client.get(B+f'/assignments/{i}/receipt',headers=superuser_headers);assert r.status_code==200 and r.content.startswith(b'%PDF-')


def test_large_register_counts_and_paging(client,db,superuser_headers):
    for i in range(33):create(client,superuser_headers,name=f'Equipment {i:02}')
    assert client.get(B+'/summary',headers=superuser_headers).json()['total']==33
    r=client.get(B+'/',headers=superuser_headers,params={'limit':10,'offset':10,'sort':'name','descending':False});assert len(r.json())==10 and r.json()[0]['name']=='Equipment 10'
    assert client.get(B+'/',headers=superuser_headers,params={'sort':'DROP TABLE assets'}).status_code==422
