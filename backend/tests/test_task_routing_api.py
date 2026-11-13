"""Comparable task evidence and final-model attribution on native suite APIs."""
from uuid import uuid4
from decimal import Decimal
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider
from tests.test_ai_operations import setup
from app.ai_operator.models import OperatorProvider,OperatorApiLog
from app.ai_operator.routing import measurements
from app.apps.crm.models import CRMTask
ROOT='/api/v1/ai-operator/suite'


def command(client,h,workspace,project,text,provider='gemini',**extra):
    return client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'text':text,
        'provider':provider,'module':'CRM','workspace_id':workspace,'project_id':project,**extra})


def rate(client,h,run):
    response=client.post(ROOT+'/operations/reviews',headers=h,json={'suite_run_id':run['id'],'supported':True,'correct':True})
    assert response.status_code==200,response.text


def test_task_matching_separates_answers_actions_artifacts_and_output_schema(client,db,monkeypatch):
    h,user,project,task,workspace=setup(client,db)
    plan={'summary':'Visible work summary','steps':[]}
    calls=mock_provider(monkeypatch,plan)
    for text in ('Show visible leads','List visible leads','Summarize visible leads'):
        r=command(client,h,workspace,project,text);assert r.status_code==200,r.text
        assert r.json()['status']=='answered';rate(client,h,r.json())
    r=command(client,h,workspace,project,'Show current leads',provider='auto');assert r.status_code==200,r.text
    decision=r.json()['result']['routing']
    assert decision['measurement']['reviews']==3 and decision['task_profile']['operation']=='answer'
    before=len(calls)
    for text,extra in [('Create a CRM task',{}),('Create a document proposal',{}),('Show visible leads',{'mode':'summary'}),('Show HR employees',{'module':'HRMS'})]:
        denied=command(client,h,workspace,project,text,provider='auto',**extra)
        assert denied.status_code==409,denied.text
        assert 'matching this task profile' in denied.json()['detail']
    assert len(calls)==before
    plan.update({'summary':'Review one task','steps':[{'tool':'crm.create_task','payload':{'title':'Confirm delivery'}}]})
    before_tasks=db.query(CRMTask).count()
    for text in ('Create a CRM task','Create a follow-up task','Create a task to confirm delivery'):
        r=command(client,h,workspace,project,text);assert r.status_code==200,r.text
        assert r.json()['status']=='awaiting_approval';rate(client,h,r.json())
    r=command(client,h,workspace,project,'Create a CRM follow-up task',provider='auto');assert r.status_code==200,r.text
    assert r.json()['status']=='awaiting_approval' and not r.json()['receipts']
    assert r.json()['result']['routing']['measurement']['reviews']==3
    assert r.json()['result']['routing']['task_profile']['operation']=='actions'
    assert db.query(CRMTask).count()==before_tasks


def test_same_task_uses_measured_cost_and_only_final_provider_gets_review_credit(client,db,monkeypatch):
    h,user,project,task,workspace=setup(client,db)
    primary=db.query(OperatorProvider).filter_by(provider='gemini').one()
    primary.input_price=primary.output_price=Decimal('5')
    alternate=OperatorProvider(scope_key=primary.scope_key,provider='openai',model='synthetic-task-model',
        encrypted_key=primary.encrypted_key,enabled=True,data_sharing_allowed=True,updated_by=user.id,
        input_price=Decimal('1'),output_price=Decimal('1'))
    db.add(alternate);db.commit()
    mock_provider(monkeypatch,{'summary':'Visible lead summary','steps':[]})
    for provider in ('gemini','openai'):
        for _ in range(3):
            r=command(client,h,workspace,project,'Show leads',provider);assert r.status_code==200,r.text
            run=r.json();rate(client,h,run)
            if provider=='openai':
                # A successful intermediate round must not inherit the final model's rating.
                db.add(OperatorApiLog(scope_key=primary.scope_key,module='CRM',user_id=user.id,suite_run_id=run['id'],
                    provider='gemini',model=primary.model,purpose='suite_plan',status='success',duration_ms=5,
                    input_tokens=100,output_tokens=50,estimated_cost=Decimal('0.00075')))
                db.commit()
    rows={r['provider']:r for r in measurements(db,user,workspace,project)}
    assert rows['gemini']['reviews']==3 and rows['openai']['reviews']==3
    r=command(client,h,workspace,project,'List leads',provider='auto');assert r.status_code==200,r.text
    assert r.json()['result']['routing']['selected_provider']=='openai'
    alternate.data_sharing_allowed=False;db.commit()
    r=command(client,h,workspace,project,'List leads',provider='auto');assert r.status_code==200,r.text
    assert r.json()['result']['routing']['selected_provider']=='gemini'
