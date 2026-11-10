"""Reviewable revisions and result cards for the existing server action engine."""
from copy import deepcopy
from typing import Any,Literal
from pydantic import Field
from fastapi import HTTPException
from app.ai_operator.suite_tools import Strict

class DraftChange(Strict):
    step: int = Field(ge=1,le=12)
    field: Literal['title','name','subject','description','priority','due_date','start_date','owner_user_id','assignee_user_id','assignee_user_ids','reason','from_date','to_date','body']
    value: Any

class DraftRevision(Strict):
    request_key: str = Field(min_length=8,max_length=100)
    plan_hash: str = Field(min_length=64,max_length=64)
    changes: list[DraftChange] = Field(min_length=1,max_length=40)

EDITABLE={'crm.create_task','crm.update_task','pms.create_task','pms.create_project','pms.create_milestone','hrms.create_ticket','hrms.request_leave'}

def revised_plan(run,data):
    from app.ai_operator.suite import Plan
    from app.ai_operator.service import digest
    if run.status!='awaiting_approval' or run.plan_hash!=data.plan_hash or digest(run.plan)!=data.plan_hash:
        raise HTTPException(409,'Only the unchanged, unapproved draft can be edited. Reload the latest reply.')
    plan=deepcopy(run.plan);seen=set()
    for edit in data.changes:
        if (edit.step,edit.field) in seen:raise HTTPException(422,'Edit each field once per revision')
        seen.add((edit.step,edit.field))
        if edit.step>len(plan['steps']):raise HTTPException(422,'Select an existing draft step')
        step=plan['steps'][edit.step-1]
        if step['tool'] not in EDITABLE:raise HTTPException(422,'Use the native reviewed form to edit this action')
        step['payload'][edit.field]=edit.value
    plan['summary']='Review the edited actions. This is a new draft; the previous approval cannot execute it.'
    plan['source_ids']=[]
    return Plan.model_validate(plan)

def result_cards(run):
    if not run.plan:return []
    request=(run.result or {}).get('request',{})
    if not run.plan.get('steps') and run.status=='answered':
        return [{'id':f'answer-{run.id}','kind':'answer','title':'Answer','body':run.plan['summary'],'status':'answered'}]
    receipts={r['step']:r for r in run.receipts or []};cards=[]
    for index,step in enumerate(run.plan.get('steps',[]),1):
        receipt=receipts.get(index);payload=step.get('payload',{});tool=step['tool'];record=(receipt or {}).get('record_id');href=None
        if receipt and receipt.get('status')=='succeeded':
            if tool in {'crm.create_task','crm.update_task'}:href='/crm/tasks'
            elif tool=='hrms.create_ticket':href='/helpdesk'
            elif tool=='hrms.request_leave':href='/leave'
            elif tool=='pms.create_project' and record:href=f'/pms/projects/{record}'
            elif tool.startswith('pms.'):
                project=step.get('record_id') or request.get('project_id')
                if isinstance(project,dict):project=(receipts.get(project.get('$step')) or {}).get('record_id')
                if type(project) is int:href=f'/pms/projects/{project}'
        cards.append({'id':f'{run.id}-{index}','step':index,'kind':'record' if receipt else 'draft',
            'title':str(payload.get('title') or payload.get('subject') or payload.get('name') or tool.replace('.',' '))[:220],
            'tool':tool,'status':receipt.get('status','succeeded') if receipt else run.status,'record_id':record,'href':href})
    return cards
