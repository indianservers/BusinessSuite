import pytest
from app.models.company import Company, Branch
from app.apps.crm.models import CRMPipeline, CRMPipelineStage
from app.shared.form_defaults import FIELDS, effective
from tests.test_settings_hub import actor, BASE
URL=BASE+'/defaults/configuration'

def test_defaults_catalog_and_all_values_round_trip(client,db):
    headers,_=actor(db,superuser=True)
    response=client.get(URL,headers=headers)
    assert response.status_code==200,response.text
    body=response.json()
    assert len(body['fields'])==38
    values={f['key']:f['default'] for f in FIELDS}
    values.update(currency='USD',country='US',phone_country_code='+1',timezone='America/New_York',task_priority='High',pay_frequency='Weekly',working_days=[0,1,2,3,4])
    saved=client.put(URL,headers=headers,json={'version':body['version'],'values':values})
    assert saved.status_code==200,saved.text
    assert client.get(URL,headers=headers).json()['overrides']==values
    assert db.get(Company,1).default_currency=='USD'
    history=client.get(BASE+'/history/business-defaults',headers=headers).json()['items']
    assert history and 'currency' in history[0]['fields']
    assert 'USD' not in str(history)

def test_scope_precedence_and_reset(client,db):
    headers,_=actor(db,superuser=True)
    branch=Branch(name='Defaults branch',company_id=1,is_active=True);db.add(branch);db.commit()
    for params,priority in [({},'Low'),({'module':'crm'},'High'),({'branch_id':branch.id},'Urgent'),({'module':'crm','branch_id':branch.id},'Medium')]:
        r=client.put(URL,params=params,headers=headers,json={'version':0,'values':{'task_priority':priority}})
        assert r.status_code==200,r.text
    assert effective(db,1,'crm',branch.id)['values']['task_priority']=='Medium'
    assert effective(db,1,'srm',branch.id)['values']['task_priority']=='Urgent'
    assert effective(db,1,'crm')['values']['task_priority']=='High'
    r=client.put(URL,params={'module':'crm','branch_id':branch.id},headers=headers,json={'version':1,'values':{}})
    assert r.status_code==200,r.text
    assert effective(db,1,'crm',branch.id)['values']['task_priority']=='Urgent'

@pytest.mark.parametrize('values',[{'currency':'BAD'},{'country':'XX'},{'phone_country_code':'+999'},{'timezone':'Invalid/Zone'},{'working_days':[]},{'working_days':[1,1]},{'quote_validity_days':0},{'tax_rate':101},{'week_start':True},{'owner_mode':'specific_user'},{'not_a_default':1},{'currency':None},{'branch_id':True},{'quote_validity_days':1.5}])
def test_invalid_defaults_do_not_save(client,db,values):
    headers,_=actor(db,superuser=True)
    r=client.put(URL,headers=headers,json={'version':0,'values':values})
    assert r.status_code==422,r.text
    assert client.get(URL,headers=headers).json()['version']==0

def test_permissions_and_tenant_isolation(client,db):
    admin,_=actor(db,superuser=True)
    assert client.put(URL,headers=admin,json={'version':0,'values':{'currency':'EUR'}}).status_code==200
    employee,_=actor(db,"defaults-reader")
    assert client.get(URL,headers=employee).status_code==403
    assert client.put(URL,headers=employee,json={'version':1,'values':{'currency':'USD'}}).status_code==403
    r=client.get(BASE+'/defaults/effective',headers=employee)
    assert r.status_code==200,r.text
    assert r.json()['values']['currency']=='EUR'
    other=Company(name='Other tenant',default_currency='GBP');db.add(other);db.flush()
    branch=Branch(name='Foreign branch',company_id=other.id);db.add(branch);db.commit()
    assert client.get(URL,params={'branch_id':branch.id},headers=admin).status_code==422
    assert client.put(URL,headers=admin,json={'version':1,'values':{'branch_id':branch.id}}).status_code==422
    assert effective(db,other.id)['values']['currency']=='GBP'

def test_stage_pipeline_and_stale_save(client,db):
    headers,user=actor(db,superuser=True)
    from test_identity_utils import attach_workflow_branch
    attach_workflow_branch(db,user);db.commit()
    a=client.post('/api/v1/crm/pipelines',headers=headers,json={'name':'A'})
    b=client.post('/api/v1/crm/pipelines',headers=headers,json={'name':'B'})
    assert a.status_code==201,a.text
    assert b.status_code==201,b.text
    aid=a.json()['id'];bid=b.json()['id']
    stage=client.post('/api/v1/crm/pipeline-stages',headers=headers,json={'name':'Open','pipeline_id':bid,'stage_type':'open'})
    assert stage.status_code==201,stage.text
    sid=stage.json()['id']
    assert client.put(URL,headers=headers,json={'version':0,'values':{'pipeline_id':aid,'stage_id':sid}}).status_code==422
    result=client.put(URL,headers=headers,json={'version':0,'values':{'pipeline_id':bid,'stage_id':sid}})
    assert result.status_code==200,result.text
    assert client.put(URL,headers=headers,json={'version':0,'values':{}}).status_code==409
