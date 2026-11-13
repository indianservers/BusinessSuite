"""Stopping new work must preserve authorized observation and cancellation."""
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,prepare,tick,ROOT
from tests.test_suite_conversations import create
from ai_test_utils import auth_headers
from app.ai_agents.models import AiSecuritySetting,AiUsageLimit,AiUsageEvent
from app.apps.crm.models import CRMTask
from uuid import uuid4
import pytest

@pytest.mark.parametrize('stop',['emergency','quota'])
@pytest.mark.parametrize('legacy',[False,True])
@pytest.mark.parametrize('stage',['draft','queued'])
def test_stopped_owner_can_inspect_and_cancel_but_cannot_approve_or_start(client,db,stop,legacy,stage):
    h,user,_,_=setup_suite(client,db)
    chat=create(client,h)
    run=prepare(client,h,[{'tool':'crm.create_task','payload':{'title':'Must remain unexecuted'}}],conversation_id=chat)
    if stage=='queued':
        response=client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
        assert response.status_code==200,response.text
    if legacy:
        from app.ai_agents.security import signature
        from app.ai_operator.suite_models import SuiteRun
        from app.ai_operator.assistant_models import AssistantConversation
        for row in (db.get(SuiteRun,run['id']),db.get(AssistantConversation,chat)):
            context={key:value for key,value in row.security_context.items() if key not in {'signature','control_fingerprint'}}
            row.security_context={**context,'signature':signature(context)}
        db.commit()
    if stop=='emergency':db.add(AiSecuritySetting(company_id=1,ai_enabled=False))
    else:
        db.add(AiUsageLimit(company_id=1,limit_type='per_company',period='daily',max_requests=1,is_active=True))
        db.add(AiUsageEvent(company_id=1,user_id=user.id,event_type='synthetic_limit',module='CROSS'))
    db.commit()
    response=client.get(ROOT+'/runs',headers=h)
    assert response.status_code==200,response.text
    response=client.get(ROOT+f'/runs/{run["id"]}',headers=h)
    assert response.status_code==200,response.text
    response=client.get(ROOT+'/conversations',headers=h)
    assert response.status_code==200,response.text
    response=client.get(ROOT+f'/conversations/{chat}',headers=h)
    assert response.status_code==200,response.text
    blocked=403 if stop=='emergency' else 429
    response=client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
    assert response.status_code==blocked,response.text
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'text':'Create new task','local_plan':{'summary':'New work','steps':[]}})
    assert response.status_code==blocked,response.text
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_manage'])
    response=client.get(ROOT+f'/runs/{run["id"]}',headers=other)
    assert response.status_code==404,response.text
    response=client.post(ROOT+f'/runs/{run["id"]}/cancel',headers=other)
    assert response.status_code==404,response.text
    cancelled=client.post(ROOT+f'/runs/{run["id"]}/cancel',headers=h)
    assert cancelled.status_code==200,cancelled.text
    assert cancelled.json()['status']=='cancelled'
    assert tick(client,db)==0
    assert db.query(CRMTask).count()==0


def test_emergency_controls_do_not_bypass_revoked_ai_grants(client,db):
    from tests.test_suite_module_scope import managed
    from app.access.models import AccessPolicy
    _,_,headers,user=managed(client,db)
    response=client.post(ROOT+'/commands',headers=headers,json={'request_key':str(uuid4()),'text':'Prepare a private draft','module':'HRMS','local_plan':{'summary':'Waiting for a record','question':'Which record?','steps':[]}})
    assert response.status_code==200,response.text
    run=response.json();assert run['status']=='needs_clarification'
    db.add(AiSecuritySetting(company_id=1,ai_enabled=False));db.commit()
    response=client.get(ROOT+f'/runs/{run["id"]}',headers=headers)
    assert response.status_code==200,response.text
    policy=db.query(AccessPolicy).filter_by(user_id=user.id,company_id=1).one()
    policy.grants={**policy.grants,'ai':{**policy.grants['ai'],'enabled':False}};db.commit()
    response=client.get(ROOT+f'/runs/{run["id"]}',headers=headers)
    assert response.status_code==403,response.text
    response=client.post(ROOT+f'/runs/{run["id"]}/cancel',headers=headers)
    assert response.status_code==403,response.text


@pytest.mark.parametrize('kind',['confirmation','payload','execution'])
def test_control_proof_cannot_authorize_business_execution(client,db,kind):
    from app.ai_agents.security import seal,verify
    from fastapi import HTTPException
    _,user,_,_=setup_suite(client,db)
    context=seal(db,user,payload={'step':'synthetic'})
    options={'control':True,'history':True}
    if kind=='confirmation':options['confirmation']=True
    elif kind=='payload':options['payload']={'step':'synthetic'}
    else:options['history']=False
    with pytest.raises(HTTPException) as denied:verify(db,user,context,**options)
    assert denied.value.status_code==403


def test_legacy_all_enabled_context_remains_stoppable_without_resigning(client,db):
    from app.ai_agents.security import seal,signature,verify
    from fastapi import HTTPException
    _,user,_,_=setup_suite(client,db)
    context=seal(db,user);context.pop('control_fingerprint');context.pop('signature');context['signature']=signature(context)
    verify(db,user,context,history=True,control=True)
    db.add(AiSecuritySetting(company_id=1,ai_enabled=False));db.commit()
    verify(db,user,context,history=True,control=True)


def test_control_fingerprint_tampering_is_rejected(client,db):
    from app.ai_agents.security import seal,verify
    from fastapi import HTTPException
    _,user,_,_=setup_suite(client,db)
    context=seal(db,user);context['control_fingerprint']='0'*64
    with pytest.raises(HTTPException) as denied:verify(db,user,context,history=True,control=True)
    assert denied.value.status_code==409


def test_legacy_nondefault_control_baseline_is_not_guessed(client,db):
    from app.ai_agents.security import seal,signature,verify
    from fastapi import HTTPException
    _,user,_,_=setup_suite(client,db)
    setting=AiSecuritySetting(company_id=1,pms_ai_enabled=False);db.add(setting);db.commit()
    context=seal(db,user);context.pop('control_fingerprint');context.pop('signature');context['signature']=signature(context)
    verify(db,user,context,history=True,control=True)
    setting.ai_enabled=False;db.commit()
    with pytest.raises(HTTPException) as denied:verify(db,user,context,history=True,control=True)
    assert denied.value.status_code==403
