"""Central usage observes AI scope without exposing business conversations."""
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,ROOT
from tests.test_suite_provider_admin import admin
from tests.test_suite_module_scope import managed
from app.ai_operator.models import OperatorApiLog
from app.ai_operator.suite_models import SuiteRun
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from uuid import uuid4


def log(db,user,scope='company:1',**values):
    row=OperatorApiLog(scope_key=scope,user_id=user.id,module='CROSS',provider='gemini',model='test-model',purpose='suite_plan',status='success',duration_ms=20,input_tokens=10,output_tokens=5,**values)
    db.add(row);return row


def test_ai_admin_usage_respects_own_scope_and_excludes_private_content(client,db):
    _,owner,_,_=setup_suite(client,db)
    headers,user=admin(client,db)
    own=log(db,user,estimated_cost=Decimal('0.000015'))
    log(db,owner,estimated_cost=Decimal('100'))
    db.add(SuiteRun(user_id=user.id,scope_key='company:1',request_key=str(uuid4()),request_hash='0'*64,command='PRIVATE CONVERSATION MUST NOT LEAK',plan={'summary':'Private server review','steps':[]},status='answered',result={'intelligence':{'engine':'server'}}));db.commit()
    response=client.get(ROOT+'/analytics',headers=headers)
    assert response.status_code==200,response.text
    data=response.json();assert data['scope_key']=='company:1'
    assert data['visibility']['record_scope']=='own'
    assert [row['id'] for row in data['logs']]==[own.id]
    assert data['groups'][0]['requests']==1
    assert data['server_plans']==1
    assert 'PRIVATE CONVERSATION' not in response.text and 'encrypted_key' not in response.text and 'query_text' not in response.text
    response=client.get('/api/v1/project-management/projects',headers=headers)
    assert response.status_code==403,response.text


def test_organization_usage_aggregates_authorized_users_and_marks_partial_pricing(client,db):
    _,owner,_,_=setup_suite(client,db)
    headers,user=admin(client,db)
    from app.access.models import AccessPolicy
    policy=db.query(AccessPolicy).filter_by(user_id=user.id).one()
    policy.grants={'ai':{**policy.grants['ai'],'scope':'organization'}};db.commit()
    log(db,user,estimated_cost=Decimal('0.001'));log(db,owner)
    log(db,user,created_at=datetime.now(timezone.utc)-timedelta(days=40));db.commit()
    response=client.get(ROOT+'/analytics',headers=headers,params={'days':30})
    assert response.status_code==200,response.text
    data=response.json();assert len(data['logs'])==2
    group=data['groups'][0];assert group['requests']==2 and group['priced_requests']==1
    assert Decimal(str(group['estimated_cost']))==Decimal('0.001')
    assert group['input_tokens']==20 and group['output_tokens']==10
    assert data['visibility']['record_scope']=='organization'


def test_usage_does_not_cross_company_or_open_admin_data_to_viewers(client,db):
    _,_,viewer,_=managed(client,db)
    headers,user=admin(client,db,company=2)
    log(db,user,scope='company:2');db.commit()
    response=client.get(ROOT+'/analytics',headers=headers)
    assert response.status_code==200,response.text
    assert len(response.json()['logs'])==1
    response=client.get(ROOT+'/analytics',headers=viewer)
    assert response.status_code==403,response.text
    response=client.get(ROOT+'/analytics',headers=headers,params={'days':366})
    assert response.status_code==422,response.text


def test_usage_remains_available_for_admin_during_operational_stop(client,db):
    setup_suite(client,db)
    headers,user=admin(client,db)
    from app.ai_agents.models import AiSecuritySetting
    db.add(AiSecuritySetting(company_id=1,ai_enabled=False));log(db,user);db.commit()
    response=client.get(ROOT+'/analytics',headers=headers)
    assert response.status_code==200,response.text
    assert len(response.json()['logs'])==1


def test_unknown_cost_is_not_zero_and_nonplans_are_not_server_plans(client,db):
    setup_suite(client,db)
    headers,user=admin(client,db)
    log(db,user)
    for engine,plan in [('server',None),('provider',{'summary':'Cloud-generated plan','steps':[]})]:
        db.add(SuiteRun(user_id=user.id,scope_key='company:1',request_key=str(uuid4()),request_hash='0'*64,command='Private request',status='failed' if plan is None else 'answered',plan=plan,result={'intelligence':{'engine':engine}}))
    db.commit()
    response=client.get(ROOT+'/analytics',headers=headers)
    assert response.status_code==200,response.text
    data=response.json();assert data['server_plans']==0
    assert data['groups'][0]['estimated_cost'] is None
    assert data['groups'][0]['priced_requests']==0
    assert data['logs'][0]['estimated_cost'] is None
    assert 'priced requests only' in data['cost_note']
