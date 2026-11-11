import json,os,time
from pathlib import Path
from uuid import uuid4
from datetime import date
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from app.ai_operator.action_benchmark import cases,manifest
from app.models.employee import Employee
from app.apps.crm.models import CRMTask
from app.models.helpdesk import HelpdeskTicket

ROOT='/api/v1/ai-operator/suite'


@pytest.mark.parametrize('case',cases(),ids=lambda c:c['id'])
def test_workplace_conversation(case,client,db):
    started=time.monotonic();h,user,project,_=setup_suite(client,db)
    if case['family']=='ten-actions':
        from app.shared.models import ServicePolicy
        db.add(ServicePolicy(scope_key='company:1:ai_security',organization_id=1,kind='ai_security',values_json={'max_calls':12},updated_by=user.id));db.commit()
    db.add(Employee(employee_id='BENCH-'+str(user.id),user_id=user.id,first_name='Workplace',last_name='QA',date_of_joining=date.today()));db.commit()
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':case['id']}).json()['id']
    turns=[];run=None
    try:
        for message in case['messages']:
            message=message.replace('{project_id}',str(project))
            r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':case['module'],'conversation_id':chat,'text':message})
            assert r.status_code==200,(case['id'],r.text)
            run=r.json();turns.append({'status':run['status'],'tools':[s['tool'] for s in (run.get('plan') or {}).get('steps',[])]})
            assert run['status'] not in ('failed','queued','executing','succeeded'),(case['id'],run)
            assert db.query(CRMTask).count()==db.query(HelpdeskTicket).count()==0
        if case['cancelled']:
            assert run['status']=='cancelled',run
            assert not run['plan']['steps']
        else:
            assert run['status']=='awaiting_approval',run
            assert [s['tool'] for s in run['plan']['steps']]==case['expected_tools'],run
            for step in run['workflow_steps']:assert all(n<step['step'] for n in step['depends_on'])
            approve(client,h,run);tick(client,db)
            done=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
            assert done['status']=='succeeded',done
            assert len(done['receipts'])==len(case['expected_tools'])
            before=(db.query(CRMTask).count(),db.query(HelpdeskTicket).count())
            tick(client,db);assert before==(db.query(CRMTask).count(),db.query(HelpdeskTicket).count())
            response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':case['module'],'conversation_id':chat,'text':case['receipt_question']})
            assert response.status_code==200,response.text
            assert not response.json()['plan']['steps'] and before==(db.query(CRMTask).count(),db.query(HelpdeskTicket).count())
        outcome='passed'
    except BaseException:
        outcome='failed';raise
    finally:
        folder=os.environ.get('ACTION_BENCHMARK_RESULTS')
        if folder:
            path=Path(folder);path.mkdir(parents=True,exist_ok=True)
            (path/(case['id']+'.json')).write_text(json.dumps({'case_id':case['id'],'family':case['family'],'outcome':outcome,
                'turns':len(turns)+bool(case['receipt_question']),'duration_ms':round((time.monotonic()-started)*1000),
                'observations':turns,'native_receipts_verified':outcome=='passed' and not case['cancelled']}),encoding='utf-8')
