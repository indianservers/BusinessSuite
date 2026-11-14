"""Server-owned conversational drafts for native personal timers."""
import re
from uuid import uuid4
from fastapi import HTTPException
from app.ai_operator.timer_actions import ACTIONS,Start,Stop,anchor,row_for,state
from app.ai_operator.service import digest


def prepare(db,user,data,parent):
    from app.ai_operator.suite import Plan,Step,authorize
    text=re.sub(r'(?i)^\s*PMS\s*:\s*','',data.text).strip()
    if data.module not in (None,'PMS') and not re.match(r'(?i)^\s*PMS\s*:',data.text):return None,None
    match=re.fullmatch(r'(?is)(start|begin|stop|discard|show|check|review)\s+(?:(?:a|my|the)\s+)?timer(?:\s+(?:on|for)\s+task\s+#?([1-9][0-9]{0,17}))?(?:\s*:\s*(.*))?[?!. ]*',text)
    question=re.fullmatch(r"(?i)(?:is my timer running|what(?:'s| is) my timer status)[?!. ]*",text)
    prior=(parent.result or {}).get('timer_draft') if parent else None
    if parent and parent.status=='awaiting_approval':
        steps=(parent.plan or {}).get('steps',[])
        if len(steps)==1 and steps[0]['tool'] in ACTIONS:
            prior={**steps[0]['payload'],'action':steps[0]['tool'].split('.')[1].removesuffix('_timer'),'project_id':steps[0]['record_id']}
    billing=re.fullmatch(r'(?i)make it (billable|nonbillable|non-billable)[.! ]*',text) if prior and prior.get('action')=='start' else None
    follow=bool(prior and (billing or re.match(r'(?i)^(?:project|task|description|timezone|billable)=',text)))
    if not match and not question and not follow:return None,None
    if follow and (parent.status not in {'needs_clarification','awaiting_approval','answered'} or parent.receipts):
        raise HTTPException(409,'The timer request was already processed; make a fresh explicit request')
    if follow and parent.status=='answered' and prior.get('action')!='status':raise HTTPException(409,'Read the timer before preparing another action')
    if parent and parent.status=='awaiting_approval' and not follow:raise HTTPException(409,'Finish or revise the pending action before another timer request')
    data.module='PMS';authorize(db,user,data.workspace_id,'PMS')
    action=prior['action'] if follow else 'status' if question or match[1].lower() in {'show','check','review'} else 'start' if match[1].lower() in {'start','begin'} else match[1].lower()
    inherited=(parent.result or {}).get('request',{}) if parent else {}
    pid=data.project_id or (inherited.get('project_id') if inherited.get('module')=='PMS' else None)
    draft=dict(prior) if follow else {'action':action,'project_id':pid}
    if action=='start' and not follow:
        draft.update(session_key=str(uuid4()),timezone=data.timezone,description='',is_billable=False,
            task_id=data.task_ids[0] if len(data.task_ids)==1 else None)
    def ask(message):return Plan(summary='Clarify your personal timer request.',question=message,steps=[]),draft
    if match and match[2]:
        if action!='start':return ask('Only timer starts accept a task. Stop/discard use your current active session.')
        draft['task_id']=int(match[2])
    if billing:draft['is_billable']=billing[1].lower()=='billable'
    values=match[3] if match else text if follow and not billing else ''
    for part in (values or '').split(';'):
        if not part.strip():continue
        key,sep,value=part.strip().partition('=');key=key.lower();value=value.strip()
        if not sep or key not in {'project','task','description','timezone','billable'}:return ask('Use project=ID; task=ID or none; description=work; timezone=Asia/Kolkata; billable=true/false.')
        if action!='start' and key!='project':return ask('Status, stop and discard use only the selected project and the current server timer.')
        if key in {'project','task'}:
            if key=='task' and value.lower()=='none':draft['task_id']=None;continue
            if not re.fullmatch(r'[1-9][0-9]{0,17}',value):return ask('Choose a positive numeric project/task ID.')
            draft['project_id' if key=='project' else 'task_id']=int(value)
        elif key=='billable':
            if value.lower() not in {'true','false'}:return ask('Choose billable=true or billable=false.')
            draft['is_billable']=value.lower()=='true'
        else:draft[key]=value
    row=row_for(db,user)
    if action=='start' and draft.get('task_id') and not draft.get('project_id'):
        from app.apps.project_management.access import get_task_project_for_action
        task,_=get_task_project_for_action(db,draft['task_id'],user,'log_time');draft['project_id']=task.project_id
    if action in {'stop','discard','status'} and row and row.active and not draft.get('project_id'):draft['project_id']=row.project_id
    if not draft.get('project_id'):return ask('Which project should this timer request cover? Reply project=123.')
    project=anchor(db,user,draft['project_id'],write=action!='status')
    if project.workspace_id!=data.workspace_id:raise HTTPException(403,'Open the timer project in its selected workspace before continuing')
    if row and row.active and row.project_id!=project.id:raise HTTPException(409,'Your active timer belongs to another project; select its authorized project')
    current=digest(state(row))
    if action!='status' and draft.get('source_sha256') and draft['source_sha256']!=current:raise HTTPException(409,'Timer changed; start a fresh review from current state')
    draft['source_sha256']=current;data.project_id=project.id
    if action=='status':
        data.context=[*data.context,Step(tool='pms.timer',record_id=project.id,payload={})]
        if data.provider=='auto':data.provider='local'
        return (Plan(summary='Read your authorized timer status.',steps=[]) if data.provider=='local' else None),draft
    if action in {'stop','discard'}:
        if not row or not row.active:return ask('There is no active timer in this project. Start a new timer or check its status.')
        draft['session_key']=row.session_key
        payload={'source_sha256':current,'session_key':row.session_key}
    else:
        payload={key:draft[key] for key in Start.model_fields}
        try:payload=Start.model_validate(payload).model_dump(mode='json')
        except ValueError:return ask('Choose valid timer details and a description of at most 4000 characters.')
    return Plan(summary=f'Review {action} of your native timer. Stop records actual server elapsed minutes; discard loses unrecorded time.',
        steps=[Step(tool=f'pms.{action}_timer',record_id=project.id,payload=payload)]),draft


def read_followup(parent,packet,data):
    if not packet or packet.get('action')!='status' or (parent.result or {}).get('timer_draft',{}).get('action')!='status':return False
    if parent.status not in {'needs_clarification','answered'} or parent.receipts or parent.approval_id or (parent.plan or {}).get('steps'):return False
    prior=(parent.result or {}).get('request',{})
    if any(prior.get(key) for key in ('workflow_id','commitment_id','candidate_id')):return False
    if prior.get('project_id') not in (None,packet.get('project_id')):return False
    return bool(data.context) and all(step.tool=='pms.timer' and step.record_id==packet.get('project_id') for step in data.context)


def local_answer(context,sources):
    lines=[]
    for packet in context:
        if packet['tool']!='pms.timer':continue
        value=packet['records']
        if not isinstance(value,dict) or value.get('truncated'):continue
        if value['active']:lines.append(f"Your timer is running in project {value['project_id']} since {value['started_at']} (stored timezone {value['timezone']}). Running time is not yet a recorded time entry.")
        else:lines.append(f"You have no active timer in selected project {value['project_id']}.")
    if not lines:return {'summary':'Timer status could not fit the source disclosure budget.','question':'Open native time tracking or narrow the source selection.','steps':[],'source_ids':[]}
    return {'summary':'\n'.join(lines)[:2000],'steps':[],'source_ids':[source['id'] for source in sources if source['tool']=='pms.timer']}
