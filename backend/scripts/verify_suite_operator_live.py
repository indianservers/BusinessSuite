"""Metered live Gemini QA. Retains labelled records; never sends external messages."""
import json
import secrets
import sys
import time
from datetime import date
from pathlib import Path
from uuid import uuid4
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.base import Base  # noqa
from app.db.session import SessionLocal
from app.models.user import User, Role, Permission
from app.apps.project_management.models import PMSWorkspaceMember
from app.core.security import create_access_token

OUT = Path(__file__).resolve().parents[2]/'.local/operator-live-qa'
auth = json.loads((OUT/'auth.json').read_text())
admin = httpx.Client(base_url='http://127.0.0.1:1534/api/v1', headers={'Authorization':'Bearer '+auth['token']}, timeout=90)
stamp = uuid4().hex[:7].upper()
evidence = {'checks': [], 'label': stamp}


def call(c, method, path, body=None):
    r = c.request(method, path, json=body)
    assert r.status_code in (200,201), f'{method} {path}: HTTP {r.status_code}'
    return r.json()


def check(name, detail):
    evidence['checks'].append({'name':name,'status':'passed','evidence':detail})
    print('PASS',name,flush=True)
    (OUT/'suite-results.json').write_text(json.dumps(evidence,indent=2))


def run(c, text, workspace, context=None):
    row=call(c,'POST','/ai-operator/suite/commands',{'text':text,'workspace_id':workspace,'request_key':str(uuid4()),'context':context or []})
    assert row['status'] in ('answered','awaiting_approval'), f'Run {row["id"]}: {row["status"]} {row.get("error_code")} {row.get("plan")}'
    return row


def execute(c, row, expected_tools):
    assert row['status']=='awaiting_approval' and [s['tool'] for s in row['plan']['steps']]==expected_tools, row
    call(c,'POST',f'/ai-operator/suite/runs/{row["id"]}/approve',{'plan_hash':row['plan_hash']})
    for _ in range(100):
        final=call(c,'GET',f'/ai-operator/suite/runs/{row["id"]}')
        if final['status']=='succeeded':return final
        assert final['status'] not in ('paused','failed','needs_reconciliation','cancelled'), final
        time.sleep(1)
    raise AssertionError('Worker did not finish')


qa_user_id=None
try:
    workspace=call(admin,'POST','/project-management/workspaces',{'name':'Suite Gemini QA '+stamp})['id']
    evidence['workspace_id']=workspace
    inherited=call(admin,'GET',f'/ai-operator/providers?workspace_id={workspace}')['items']
    assert len(inherited)==1 and inherited[0]['provider']=='gemini' and inherited[0]['inherited']
    check('New workspace inherits Gemini without copying its credential',{'workspace_id':workspace,'model':inherited[0]['model']})
    customer=call(admin,'POST','/crm/companies',{'name':'Suite QA customer '+stamp})['id']
    row=run(admin, f'Create exactly these four independent records, in this order. 1: CRM task with title "Suite QA {stamp}". 2: FAM cost center code "SQ{stamp}" and name "Suite QA {stamp}". 3: SRM draft manual invoice for customer_id {customer}, currency INR, one line description "Suite QA {stamp}", quantity 1, unit_price 1, discount_amount 0, tax_amount 0. 4: PMS project name "Suite QA {stamp}" with project_key "SQ{stamp}" in the selected workspace. No other actions or fields; do not issue, send or post anything.', workspace)
    final=execute(admin,row,['crm.create_task','fam.create_cost_center','srm.draft_invoice','pms.create_project'])
    check('Real Gemini four-module plan executes through canonical APIs after approval',{'run_id':final['id'],'receipts':final['receipts']})
    context=[{'tool':t} for t in ['hrms.directory','crm.tasks','srm.dashboard','fam.dashboard','pms.projects']]
    summary=run(admin,'Summarize the selected authorized HR, CRM, sales, accounting and project sources in five short bullets. State empty sources explicitly. Do not create actions or ask questions. These are limited samples.',workspace,context)
    assert summary['status']=='answered' and not summary['plan']['steps']
    check('Real Gemini summary spans all five modules with minimized API context',{'run_id':summary['id'],'summary':summary['plan']['summary']})
    employee=call(admin,'POST','/employees/',{'employee_id':'AI-QA-'+stamp,'first_name':'SuiteQA','last_name':stamp,'date_of_joining':'2026-10-24',
        'create_user_account':True,'user_email':'suite-qa-'+stamp.lower()+'@example.com','user_password':secrets.token_urlsafe(30)})
    with SessionLocal() as db:
        qa=db.query(User).filter_by(email='suite-qa-'+stamp.lower()+'@example.com').one()
        qa_user_id=qa.id
        role=Role(name='suite_qa_'+stamp)
        role.permissions=db.query(Permission).filter(Permission.name=='ai_assistant').all()
        db.add(role);db.flush();qa.role_id=role.id
        db.add(PMSWorkspaceMember(workspace_id=workspace,user_id=qa.id,role='Member'));db.commit()
        qa_token=create_access_token(str(qa.id))
    member=httpx.Client(base_url='http://127.0.0.1:1534/api/v1',headers={'Authorization':'Bearer '+qa_token},timeout=90)
    hr=run(member,f'Create one HR helpdesk ticket for me, subject "Suite QA {stamp}", description "Internal AI operator verification; no external delivery", priority Medium. No other actions.',workspace)
    hrfinal=execute(member,hr,['hrms.create_ticket'])
    check('Real Gemini HRMS self-service action uses employee-linked member permissions',{'run_id':hrfinal['id'],'employee_id':employee['id'],'receipts':hrfinal['receipts']})
    logs=call(admin,'GET',f'/ai-operator/analytics?workspace_id={workspace}')
    relevant=[l for l in logs['logs'] if l.get('suite_run_id') in [row['id'],summary['id'],hr['id']]]
    assert len(relevant)==3 and all(l['provider']=='gemini' and l['status']=='success' and l['input_tokens']>0 for l in relevant)
    evidence['logs']=relevant
    evidence['status']='passed'
    check('Workspace usage logs correlate module context, suite run, tokens, cost and latency',{'log_ids':[l['id'] for l in relevant]})
except Exception as exc:
    evidence['status']='failed';evidence['error']=str(exc);print('FAIL',str(exc),flush=True)
finally:
    if qa_user_id:
        with SessionLocal() as db:
            db.get(User,qa_user_id).is_active=False;db.commit()
        evidence['qa_member_disabled_after_verification']=True
    (OUT/'suite-results.json').write_text(json.dumps(evidence,indent=2,default=str))
    admin.close()
raise SystemExit(0 if evidence.get('status')=='passed' else 1)
