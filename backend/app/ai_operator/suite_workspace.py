"""Reviewable revisions and result cards for the existing server action engine."""
from copy import deepcopy
import re
from typing import Any,Literal
from pydantic import Field
from fastapi import HTTPException
from app.ai_operator.suite_tools import Strict

class DraftChange(Strict):
    step: int = Field(ge=1,le=12)
    field: Literal['duration_minutes','log_date','start_at','end_at','timezone','meeting_url','kind','title','name','subject','description','priority','due_date','start_date','owner_user_id','assignee_user_id','assignee_user_ids','reason','from_date','to_date','body','content','slides','chart','panels','prompt','submit_label','success_message','accent','fields','workflow','settings']
    value: Any

class DraftRevision(Strict):
    request_key: str = Field(min_length=8,max_length=100)
    plan_hash: str = Field(min_length=64,max_length=64)
    changes: list[DraftChange] = Field(min_length=1,max_length=40)

EDITABLE={'crm.create_task','crm.update_task','pms.create_task','pms.create_project','pms.create_milestone','hrms.create_ticket','hrms.request_leave'}
EDITABLE.update(m+'.'+action+'_form' for m in ('crm','pms','hrms') for action in ('create','edit'))
EDITABLE.update({'pms.create_saved_view','pms.update_saved_view'})
EDITABLE.add('pms.start_timer')
EDITABLE.update({'pms.create_time_log','pms.edit_time_log'})
EDITABLE.update({'pms.create_calendar_event','pms.edit_calendar_event'})
EDITABLE.add('crm.create_saved_view')
EDITABLE.add('hrms.create_saved_view')
EDITABLE.update({'crm.update_saved_view','hrms.update_saved_view'})
EDITABLE.update(f'{m}.{a}_artifact' for m in ('crm','pms','hrms') for a in ('create','edit'))
EDITABLE.update(f'{m}.transcribe_audio' for m in ('crm','pms','hrms'))
EDITABLE.update(f'{m}.{action}_image' for m in ('crm','pms','hrms') for action in ('generate','edit'))


def draft_workflow(plan):
    """Recover conversational state from a canonically validated create draft.

    Keep its complete payload; natural follow-ups may change supported fields
    but must not discard assignees, descriptions or existing parent IDs. Complex
    references outside the local composer remain in the native review editor.
    """
    tools={'crm.create_task':('CRM','tasks.create','title'),
        'pms.create_task':('PMS','tasks.create','title'),
        'pms.create_milestone':('PMS','milestone.create','name'),
        'hrms.create_ticket':('HRMS','ticket.create','subject')}
    def refs(value):
        if isinstance(value,dict):return '$step' in value or any(refs(v) for v in value.values())
        return isinstance(value,list) and any(refs(v) for v in value)
    if not plan.steps or len(plan.steps)>12 or plan.question:return None
    state={'intents':[],'composer':'validated-server-draft-v1','project_id':None}
    projects=set()
    for index,step in enumerate(plan.steps,1):
        payload=deepcopy(step.payload)
        if step.tool=='pms.create_project':
            if index!=1 or refs(payload):return None
            state['new_project']=payload
            continue
        if step.tool not in tools:return None
        module,intent,title_field=tools[step.tool]
        remaining={k:v for k,v in payload.items() if k!='parent_task_id'}
        if refs(remaining):return None
        slots={'action_verb':'create','title':payload[title_field],'_draft_payload':payload}
        for field in ('priority','due_date'):
            if field in payload and payload[field] is not None:slots[field]=payload[field]
        if intent=='ticket.create':slots['body']=payload.get('description') or payload[title_field]
        parent=payload.get('parent_task_id')
        if isinstance(parent,dict):
            if set(parent)!={'$step','field'} or parent.get('field')!='id' or not isinstance(parent.get('$step'),int):return None
            slots['_parent_step']=parent['$step']
        if module=='PMS':
            if isinstance(step.record_id,dict):
                if not state.get('new_project') or step.record_id!={'$step':1,'field':'id'}:return None
            elif type(step.record_id) is int:projects.add(step.record_id);slots['_record_id']=step.record_id
            else:return None
        state['intents'].append({'module':module,'intent':intent,'slots':slots,'question':None})
    if not state['intents'] and not state.get('new_project'):return None
    if len(projects)==1:state['project_id']=next(iter(projects))
    return state

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
            if tool in {m+'.'+action+'_form' for m in ('crm','pms','hrms') for action in ('create','edit','publish','close')} and type(record) is int:href=receipt.get('form_url') or f'/{tool.split(".")[0]}/forms/{record}/edit'
            elif tool in {'pms.start_timer','pms.stop_timer','pms.discard_timer'}:href=f'/pms/time-tracking?projectId={step.get("record_id")}'
            elif tool in {'pms.create_time_log','pms.edit_time_log','pms.remove_time_log'}:href=f'/pms/time-tracking?projectId={step.get("record_id")}'
            elif tool in {'pms.create_calendar_event','pms.edit_calendar_event','pms.remove_calendar_event'}:href=receipt.get('calendar_url') or '/pms/calendar'
            elif tool in {'crm.create_task','crm.update_task'}:href='/crm/tasks'
            elif tool in {'crm.remove_saved_view','hrms.remove_saved_view'}:href='/crm/tasks' if tool.startswith('crm.') else '/hrms/helpdesk'
            elif tool in {'hrms.create_saved_view','hrms.update_saved_view'} and isinstance(record,str) and re.fullmatch(r'[a-f0-9]{32}',record):href=f'/hrms/helpdesk?view={record}'
            elif tool in {'crm.create_saved_view','crm.update_saved_view'} and isinstance(record,str) and re.fullmatch(r'[a-f0-9]{32}',record):href=f'/crm/tasks?view={record}'
            elif tool in {'crm.create_lead','crm.update_lead','crm.qualify_lead','crm.convert_lead'}:href='/crm/leads'
            elif tool in {'hrms.status_ticket','hrms.assign_ticket','hrms.escalate_ticket','hrms.reply_ticket'}:href='/hrms/helpdesk'
            elif tool=='hrms.update_employee' and record:href=f'/hrms/employees/{record}'
            elif tool=='hrms.create_ticket':href='/helpdesk'
            elif tool=='hrms.request_leave':href='/leave'
            elif tool=='pms.update_milestone' and type(receipt.get('project_id')) is int:href=f"/pms/projects/{receipt['project_id']}/milestones"
            elif tool=='pms.create_project' and record:href=f'/pms/projects/{record}'
            elif tool=='pms.remove_saved_view':href='/pms/tasks/advanced'
            elif tool in {'pms.create_saved_view','pms.update_saved_view'} and record:href=f'/pms/tasks/advanced?view={record}'
            elif tool.startswith('pms.'):
                project=step.get('record_id') or request.get('project_id')
                if isinstance(project,dict):project=(receipts.get(project.get('$step')) or {}).get('record_id')
                if type(project) is int:href=f'/pms/projects/{project}'
        timer_body=None
        if receipt and receipt.get('status')=='succeeded':
            if tool=='pms.stop_timer' and type(receipt.get('duration_minutes')) is int:timer_body=f"Recorded {receipt['duration_minutes']} minute(s) as Pending time."
            elif tool=='pms.start_timer':timer_body='Timer started; time is not recorded until it is stopped.'
            elif tool=='pms.discard_timer':timer_body='Timer discarded without recording time.'
        cards.append({'id':f'{run.id}-{index}','step':index,'kind':'record' if receipt else 'draft',
            'title':str(payload.get('title') or payload.get('subject') or payload.get('name') or tool.replace('.',' '))[:220],
            'body':timer_body,'tool':tool,'status':receipt.get('status','succeeded') if receipt else run.status,'record_id':record,'href':href,
            'artifact_id':receipt.get('artifact_id') if receipt else None,'artifact_revision':receipt.get('artifact_revision') if receipt else None})
    return cards
