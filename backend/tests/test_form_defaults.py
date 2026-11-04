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
    assert len(body['fields'])==39
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
    assert client.get(URL,params={'branch_id':branch.id},headers=admin).status_code==403
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


def test_new_quotes_use_defaults_and_freeze_document_settings(client,db,superuser_headers):
    from app.shared.form_defaults import document_defaults
    headers=superuser_headers
    settings=client.get(URL,headers=headers).json()
    result=client.put(URL,headers=headers,json={'version':settings['version'],'values':{'currency':'EUR','quote_validity_days':21,'payment_terms_days':15,'quote_template':'compact','date_format':'DD/MM/YYYY'}})
    assert result.status_code==200,result.text
    created=client.post('/api/v1/crm/quotes',headers=headers,json={'quoteNumber':'DEFAULT-SNAPSHOT-1','issueDate':'2026-11-05'})
    assert created.status_code==201,created.text
    quote=created.json()
    assert quote['currency']=='EUR'
    assert '15' in quote['terms']
    snapshot=document_defaults(db,1,'crm','quotation',quote['id'])
    assert snapshot['quote_template']=='compact'
    assert snapshot['date_format']=='DD/MM/YYYY'
    result=client.put(URL,headers=headers,json={'version':result.json()['version'],'values':{'currency':'USD','quote_template':'detailed','date_format':'YYYY-MM-DD'}})
    assert result.status_code==200,result.text
    assert document_defaults(db,1,'crm','quotation',quote['id'])['quote_template']=='compact'
    pdf=client.get(f"/api/v1/crm/quotes/{quote['id']}/pdf",headers=headers)
    assert pdf.status_code==200,pdf.text
    assert pdf.content.startswith(b'%PDF')
    explicit=client.post('/api/v1/crm/quotes',headers=headers,json={'quoteNumber':'DEFAULT-EXPLICIT','issueDate':'2026-11-05','expiryDate':'2026-12-31','currency':'GBP','terms':'Custom terms'})
    assert explicit.status_code==201,explicit.text
    assert explicit.json()['currency']=='GBP'
    assert explicit.json()['terms']=='Custom terms'


def test_effective_defaults_respect_requested_branch_header(client,db):
    headers,user=actor(db,superuser=True)
    from test_identity_utils import attach_workflow_branch
    attach_workflow_branch(db,user);db.commit()
    branch=Branch(name='Second defaults branch',company_id=1);db.add(branch);db.commit()
    saved=client.put(URL,params={'branch_id':branch.id},headers=headers,json={'version':0,'values':{'currency':'AED'}})
    assert saved.status_code==200,saved.text
    result=client.get(BASE+'/defaults/effective',headers={**headers,'X-Suite-Branch':str(branch.id)})
    assert result.status_code==200,result.text
    assert result.json()['branchId']==branch.id
    assert result.json()['values']['currency']=='AED'
    assert result.json()['modules']['crm']['currency']=='AED'

def test_new_planner_inherits_week_and_timezone_but_saved_preferences_win(client,db,superuser_headers):
    settings=client.get(URL,headers=superuser_headers).json()
    saved=client.put(URL,headers=superuser_headers,params={'module':'project_management'},json={'version':0,'values':{'week_start':6,'working_days':[0,1,2,3,4],'timezone':'Asia/Dubai'}})
    assert saved.status_code==200,saved.text
    prefs=client.get('/api/v1/project-management/planner/preferences',headers=superuser_headers)
    assert prefs.status_code==200,prefs.text
    value=prefs.json()['preferences']
    assert value['week_start']==6
    assert value['timezone']=='Asia/Dubai'
    assert {day['day'] for day in value['workdays'] if day['enabled']}=={6,0,1,2,3}
    value['timezone']='UTC'
    existing=client.put('/api/v1/project-management/planner/preferences',headers=superuser_headers,json={'revision':0,'preferences':value})
    assert existing.status_code==200,existing.text
    assert client.get('/api/v1/project-management/planner/preferences',headers=superuser_headers).json()['preferences']['timezone']=='UTC'


def test_default_price_list_changes_picker_prices_only_when_requested(client,db,superuser_headers):
    from tests.test_shared_catalog import item
    headers=superuser_headers
    product=client.post('/api/v1/catalog/items',params={'source':'crm'},headers=headers,json=item(code='DEFAULT-LIST-PRODUCT'))
    assert product.status_code==201,product.text
    book=client.post('/api/v1/crm/price-books',headers=headers,json={'name':'Default price list','currency':'INR'})
    assert book.status_code==201,book.text
    entry=client.post('/api/v1/crm/price-book-items',headers=headers,json={'price_book_id':book.json()['id'],'item_type':'product','product_id':product.json()['id'],'unit_price':99,'tax_rate':5})
    assert entry.status_code==201,entry.text
    regular=client.get('/api/v1/catalog/items',params={'source':'crm'},headers=headers)
    selected=client.get('/api/v1/catalog/items',params={'source':'crm','price_book_id':book.json()['id']},headers=headers)
    assert selected.status_code==200,selected.text
    assert regular.json()['items'][0]['price']==125.5
    assert selected.json()['items'][0]['price']==99
    assert selected.json()['items'][0]['tax']==5
    assert client.get('/api/v1/catalog/items',params={'source':'crm','price_book_id':999999},headers=headers).status_code==422


@pytest.mark.parametrize('version',[-1,True,'0',0.5])
def test_defaults_version_is_a_strict_nonnegative_integer(client,db,version):
    headers,_=actor(db,superuser=True)
    assert client.put(URL,headers=headers,json={'version':version,'values':{}}).status_code==422
