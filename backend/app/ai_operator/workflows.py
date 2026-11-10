"""Server-owned dependency checks, checkpoints and bounded local workflow planning."""
import re
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException


def dependencies(plan):
    graph={}
    def refs(value):
        if isinstance(value,dict):
            if '$step' in value:return {value['$step']}
            return set().union(*(refs(v) for v in value.values())) if value else set()
        if isinstance(value,list):return set().union(*(refs(v) for v in value)) if value else set()
        return set()
    for index,step in enumerate(plan.steps,1):
        values=set(step.depends_on)|refs(step.payload)|refs(step.record_id)
        if any(type(v) is not int or not 1<=v<index for v in values):
            raise HTTPException(422,'Dependencies must refer to earlier steps; cycles and forward references are not allowed')
        if len(set(step.depends_on))!=len(step.depends_on):raise HTTPException(422,'Duplicate step dependencies')
        graph[index]=sorted(values)
    return graph


def validate_reference_types(plan):
    """A new CRM task ID cannot stand in for a PMS project or an HR identity."""
    kinds={'crm.create_task':'crm.task','crm.update_task':'crm.task','pms.create_project':'pms.project',
        'pms.kickoff':'pms.project','pms.create_task':'pms.task','pms.create_milestone':'pms.milestone',
        'hrms.create_ticket':'hrms.ticket','hrms.request_leave':'hrms.leave','hrms.approve_leave':'hrms.leave',
        'fam.create_cost_center':'fam.cost_center','srm.draft_invoice':'srm.invoice'}
    from app.ai_operator.suite_tools import TOOLS
    def check(value,expected):
        if isinstance(value,dict) and '$step' in value and expected:
            source=plan.steps[value['$step']-1].tool
            if kinds.get(source)!=expected:raise HTTPException(422,'A step reference must produce the required record type')
    for step in plan.steps:
        tool=TOOLS.get(step.tool)
        record_kind='pms.project' if tool and tool.module=='PMS' else 'crm.task' if step.tool=='crm.update_task' else 'hrms.leave' if step.tool=='hrms.approve_leave' else None
        check(step.record_id,record_kind)
        fields={'owner_user_id':'user','assignee_user_id':'user','handover_employee_id':'employee'}
        if step.tool=='pms.create_task':fields.update(parent_task_id='pms.task',milestone_id='pms.milestone')
        if step.tool=='fam.create_cost_center':fields['parent_id']='fam.cost_center'
        for field,expected in fields.items():check(step.payload.get(field),expected)


def progress(run):
    from app.ai_operator.suite import Plan
    if not run.plan:return []
    plan=Plan.model_validate(run.plan);graph=dependencies(plan)
    receipts={r['step']:r for r in run.receipts or []}
    done={n for n,r in receipts.items() if r.get('status')=='succeeded'}
    checkpoint=(run.result or {}).get('checkpoint') or {}
    return [{'step':i,'tool':s.tool,'depends_on':graph[i],
        'status':receipts[i].get('status','succeeded') if i in receipts else
            'executing' if run.active_step==i and run.status in {'executing','waiting_pms'} else
            'needs_reconciliation' if run.active_step==i and run.status=='needs_reconciliation' else
            'cancelled' if run.status in {'cancelled','superseded'} else
            'blocked' if not set(graph[i])<=done else
            'paused' if run.status=='paused' and i==len(receipts)+1 else 'pending',
        'attempts':(checkpoint.get('attempts') or {}).get(str(i),0)} for i,s in enumerate(plan.steps,1)]


def checkpoint(run,**values):
    state={**((run.result or {}).get('checkpoint') or {}),**values}
    run.result={**(run.result or {}),'checkpoint':state}
    return state


def begin_attempt(run,index):
    counts={**((run.result or {}).get('checkpoint') or {}).get('attempts',{})}
    counts[str(index)]=counts.get(str(index),0)+1
    checkpoint(run,attempts=counts,retry_at=None,retry_safe=False)
    return counts[str(index)]


def failure(run,exc,started):
    state=(run.result or {}).get('checkpoint') or {}
    count=(state.get('attempts') or {}).get(str(len(run.receipts)+1),1)
    # Only a read/pre-dispatch failure can be retried automatically. A returned
    # 5xx or timeout after invoking a write does not prove the write rolled back.
    import httpx
    transient=isinstance(exc,(httpx.TransportError,TimeoutError)) or isinstance(exc,HTTPException) and exc.status_code in {429,502,503,504}
    automatic=not started and transient and count<3 and run.status!='cancelling'
    checkpoint(run,retry_safe=not started,retry_at=(datetime.now(timezone.utc)+timedelta(seconds=2**count)).isoformat() if automatic else None)
    return 'needs_reconciliation' if started else 'queued' if automatic else 'paused'


def local_plan(data,parent,model_scope):
    """Compose supported local actions, retaining missing fields on the server.

    Quoted payloads are never split. No arbitrary endpoints or model-generated
    code are executed. All output still goes through canonical suite preflight.
    """
    from types import SimpleNamespace
    from app.ai_operator.local_nlp import parse,Interpretation
    from app.ai_operator.local_dialogue import continue_action
    from app.ai_operator.local_runtime import task_plan
    prior=(parent.result or {}).get('workflow') if parent and parent.status=='needs_clarification' else None
    if prior:
        state={**prior,'intents':[dict(v) for v in prior['intents']]}
        pos=state['pending'];old=state['intents'][pos]
        current=parse(data.text,old['module'],timezone=data.timezone,model_scope=model_scope)
        answer=continue_action(current,old,data.text,data.timezone,model_scope=model_scope)
        if answer.intent=='cancelled':return {'summary':'Workflow draft cancelled. No actions were executed.','steps':[]},{'cancelled':True}
        if answer.intent!=old['intent'] or answer.module!=old['module']:
            return {'summary':'The collected workflow is unchanged. No actions have run.',
                'question':f"Step {pos+1}: Please provide the requested {old['slots'].get('_awaiting','details').replace('_',' ')}, or cancel this draft and start a new workflow.",'steps':[]},state
        state['intents'][pos]={'module':answer.module,'intent':answer.intent,'slots':dict(answer.slots),'question':answer.question}
    else:
        # Split only separators outside quoted strings.
        parts=re.split(r'(?:\s+(?:and\s+then|then)\s+|;\s*)(?=(?:[^"“”]*["“][^"“”]*["”])*[^"“”]*$)',data.text,flags=re.I)
        if len(parts)<2:return None,None
        if len(parts)>8:raise HTTPException(422,'Prepare at most eight local workflow actions in one review')
        state={'intents':[],'project_id':data.project_id}
        for part in parts:
            if not re.match(r'^\s*(?:CRM|PMS|HRMS|HR)\s*:',part,re.I):
                return {'summary':'No workflow actions have been prepared.','question':'Prefix each local step with CRM:, PMS: or HRMS: so its module is explicit. Finance and other actions require an enabled connected provider.','steps':[]},None
            intent=parse(part.strip(),data.module,timezone=data.timezone,model_scope=model_scope)
            if intent.intent not in {'tasks.create','ticket.create','milestone.create'}:
                return {'summary':'This local workflow needs a supported action for each step.','question':'Use CRM/PMS task creation, PMS milestone creation or HRMS ticket creation with explicit module names. Connected providers can plan other supported tools.','steps':[]},None
            state['intents'].append({'module':intent.module,'intent':intent.intent,'slots':dict(intent.slots),'question':intent.question})
    steps=[]
    for pos,item in enumerate(state['intents']):
        intent=Interpretation(item['module'],item['intent'],1,dict(item['slots']),item.get('question'))
        if intent.slots.get('project_id'):state['project_id']=intent.slots['project_id']
        context=SimpleNamespace(project_id=state.get('project_id'),timezone=data.timezone,request_key=f'{data.request_key}-{pos}')
        result=task_plan(intent,context,[],[])
        if result is None:raise HTTPException(422,'This workflow step is not supported by the local action catalog')
        state['intents'][pos]={**item,'slots':dict(intent.slots)}
        if result.get('question'):
            state['pending']=pos
            return {'summary':f'Preparing a {len(state["intents"])}-step workflow. No actions have run.',
                'question':f'Step {pos+1}: '+result['question'],'steps':[]},state
        for step in result.get('steps',[]):
            step['depends_on']=[len(steps)] if steps else []
            steps.append(step)
    state.pop('pending',None)
    data.project_id=state.get('project_id')
    return {'summary':f'Review these {len(steps)} dependent actions across the selected modules. They execute in order; completed actions are retained if a later step stops.','steps':steps},state


def process_suite_children(db,limit=20):
    """Advance only canonical PMS jobs delegated by approved suite workflows."""
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_operator.jobs import process_batch
    ids=[]
    for run in db.query(SuiteRun).filter_by(status='waiting_pms').limit(100):
        child=(run.snapshots or {}).get('pms_children',{}).get(str(run.active_step),{})
        if child.get('kind')=='task':ids.append(child['id'])
    return process_batch(db,limit=limit,run_ids=ids,include_schedulers=False) if ids else {}
