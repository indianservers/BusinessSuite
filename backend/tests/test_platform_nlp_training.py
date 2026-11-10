from io import BytesIO
from uuid import uuid4
import json
from tests.test_public_signup import platform_store,platform_headers,PASSWORD
from app.platform_owner.models import PlatformAdmin,PlatformRecord
from app.core.security import get_password_hash
from app.platform_owner.nlp_training import process

ROOT='/api/v1/platform/nlp-training'


def trainer(client,store):
    actor=PlatformAdmin(email='trainer@indianservers.com',name='saisatish',role='model_trainer',permissions=['nlp.train'],hashed_password=get_password_hash(PASSWORD))
    store.add(actor);store.commit()
    response=client.post('/api/v1/auth/platform/login',json={'email':'trainer@indianservers.com','password':PASSWORD})
    assert response.status_code==200,response.text
    assert response.json()['permissions']==['nlp.train']
    return {'Authorization':'Bearer '+response.json()['access_token']}


def uploaded(client,h):
    from openpyxl import Workbook
    book=Workbook();sheet=book.active;sheet.title='Commands'
    sheet.append(['module','query','intent','split']);sheet.append(['CRM','CRM: fetch prospect roster','leads.list','train'])
    stream=BytesIO();book.save(stream)
    response=client.post(ROOT+'/datasets',headers=h,files={'file':('commands.xlsx',stream.getvalue())})
    assert response.status_code==200,response.text
    return response.json()['id']


def test_customer_superadmin_and_anonymous_cannot_train(client,db,superuser_headers,platform_headers):
    for path in [ROOT,ROOT+'/template']:
        assert client.get(path).status_code==401
        assert client.get(path,headers=superuser_headers).status_code==401
    assert client.get('/api/v1/ai-operator/suite/training/template',headers=superuser_headers).status_code==403
    assert client.get('/api/v1/ai-operator/suite/nlp-queries',headers=superuser_headers).status_code==403


def test_email_login_only_training_access_and_review_gate(client,db,platform_store,monkeypatch):
    monkeypatch.setattr('app.platform_owner.nlp_training.run_background',lambda ident:None)
    h=trainer(client,platform_store)
    for path in ['/settings','/customers','/staff','/records/tasks','/reports']:
        assert client.get('/api/v1/platform'+path,headers=h).status_code==403,path
    assert client.patch('/api/v1/platform/profile',headers=h,json={'action':'preferences','reason':'Denied edit','values':{}}).status_code==403
    assert client.get('/api/v1/platform/me',headers=h).json()['role']=='model_trainer'
    assert client.get(ROOT+'/template',headers=h).status_code==200
    ident=uploaded(client,h)
    job={'dataset_id':ident,'request_key':str(uuid4()),'epochs':220}
    assert client.post(ROOT+'/jobs',headers=h,json=job).status_code==422
    assert client.post(f'{ROOT}/datasets/{ident}/approve',headers=h,json={}).status_code==422
    assert client.post(f'{ROOT}/datasets/{ident}/approve',headers=h,json={'privacy_reviewed':True}).status_code==200
    first=client.post(ROOT+'/jobs',headers=h,json=job)
    assert first.status_code==200,first.text
    assert client.post(ROOT+'/jobs',headers=h,json=job).json()['id']==first.json()['id']
    assert client.post(ROOT+'/jobs',headers=h,json={**job,'epochs':100}).status_code==409
    assert client.post(f'{ROOT}/jobs/{first.json()["id"]}/activate',headers=h).status_code==409


def test_platform_server_training_activation_and_scope(client,db,platform_store,monkeypatch,tmp_path):
    monkeypatch.setattr('app.platform_owner.nlp_training.run_background',lambda ident:None)
    monkeypatch.setenv('LOCAL_NLP_TRAINING_DIR',str(tmp_path))
    h=trainer(client,platform_store);ident=uploaded(client,h)
    client.post(f'{ROOT}/datasets/{ident}/approve',headers=h,json={'privacy_reviewed':True})
    queued=client.post(ROOT+'/jobs',headers=h,json={'dataset_id':ident,'request_key':str(uuid4())})
    assert queued.status_code==200,queued.text
    job_id=queued.json()['id'];process(platform_store,job_id)
    job=platform_store.get(PlatformRecord,job_id)
    assert job.state=='succeeded',job.data
    assert all(job.data['metrics']['modules'][module]['training_commands']>=1200 for module in ('PMS','CRM','HRMS'))
    assert (tmp_path/f'platform/runs/{job_id}/model/CRM.keras').is_file()
    response=client.post(f'{ROOT}/jobs/{job_id}/activate',headers=h)
    assert response.status_code==200,response.text
    from app.ai_operator.local_tensorflow import artifact_path,load,scope_matches
    bundle=load()
    assert bundle['training_scope']=={'platform':True}
    assert scope_matches(bundle,{'company_id':123,'branch_id':1,'workspace_id':None})
    assert str(tmp_path) in str(artifact_path())
    listing=client.get(ROOT,headers=h).json()
    assert listing['active_job_id']==job_id
    assert 'w1' not in json.dumps(listing)
    assert client.post(ROOT+'/reset',headers=h).status_code==200
    assert client.delete(f'{ROOT}/datasets/{ident}',headers=h).status_code==200
    assert client.post(f'{ROOT}/jobs/{job_id}/activate',headers=h).status_code==409


def test_platform_email_required_and_owner_has_full_access(client,db,platform_headers):
    assert client.post('/api/v1/auth/platform/login',json={'email':'owner','password':PASSWORD}).status_code==422
    signed=client.post('/api/v1/auth/platform/login',json={'email':'owner@Indianservers.com','password':PASSWORD})
    assert signed.status_code==200,signed.text
    assert signed.json()['role']=='owner'
    from app.platform_owner.service import ALL_PERMISSIONS
    assert set(signed.json()['permissions'])==ALL_PERMISSIONS
    headers={'Authorization':'Bearer '+signed.json()['access_token']}
    for path in ['/settings','/staff','/customers', '/nlp-training']:
        response=client.get('/api/v1/platform'+path,headers=headers)
        assert response.status_code==200,response.text
