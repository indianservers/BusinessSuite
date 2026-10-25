"""Provider-independent PMS reasoning context and approved tool adapters."""
from datetime import date, datetime, timedelta
from typing import Literal
from uuid import uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import calendar
import re
from fastapi import HTTPException
from pydantic import Field
from app.ai_operator.schemas import TaskPlan
from app.ai_operator.extensions import SetupPlan
from app.ai_operator.suite_tools import Strict


class TaskActions(Strict):
    plan: TaskPlan
    mode: Literal['atomic', 'checkpointed'] = 'checkpointed'


class Kickoff(Strict):
    plan: SetupPlan


class Schedule(Strict):
    task_ids: list[int] = Field(min_length=1, max_length=25)
    start_date: str = Field(min_length=1, max_length=80)


class Remember(Strict):
    title: str = Field(default='Project memory', min_length=1, max_length=180)
    text: str = Field(min_length=1, max_length=2000)
    category: Literal['preference', 'decision', 'terminology', 'constraint'] = 'preference'


class Playbook(Strict):
    title: str = Field(min_length=1, max_length=180)
    plan: TaskPlan


class PlaybookRun(Strict):
    playbook_id: int = Field(gt=0)


class Undo(Strict):
    run_id: int = Field(gt=0)


class Watch(Strict):
    name: str = Field(min_length=1, max_length=180)
    interval_minutes: int = Field(default=60, ge=15, le=10080)
    enabled: bool = True


class EventRule(Strict):
    title: str = Field(min_length=1, max_length=180)
    playbook_id: int = Field(gt=0)
    trigger: Literal['blocked', 'overdue', 'task_created', 'status_changed']
    enabled: bool = True
    autonomous: bool = False


def resolve_date(value, timezone='Asia/Kolkata', today=None):
    """Resolve supported relative dates explicitly; business calendars run next."""
    try:
        zone = ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError):
        raise HTTPException(422, 'Choose a valid timezone') from None
    current = today or datetime.now(zone).date()
    text = value.strip().lower()
    if text in ('today', 'tomorrow'):
        return (current + timedelta(days=text == 'tomorrow')).isoformat()
    if text in ('end of month', 'end of this month'):
        return current.replace(day=calendar.monthrange(current.year, current.month)[1]).isoformat()
    match = re.fullmatch(r'in (\d{1,3}) (day|days|week|weeks)', text)
    if match:
        return (current + timedelta(days=int(match[1]) * (7 if match[2].startswith('week') else 1))).isoformat()
    names = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
    if text.startswith('next ') and text[5:] in names:
        # The next occurrence strictly after today, matching the local parser.
        return (current + timedelta(days=(names.index(text[5:])-current.weekday()) % 7 or 7)).isoformat()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise HTTPException(422, 'Use an ISO date, today, tomorrow, next weekday, in N days/weeks, or end of month') from None


def enrich_context(db, user, project_id, context):
    from app.ai_operator.workbench import items, public, memory_context
    from app.ai_operator.models import OperatorMonitor
    from app.ai_operator.workbench_models import AssistantArtifact
    rows = items(db, user, project_id).filter(AssistantArtifact.kind.in_(['policy','playbook','rule'])).order_by(AssistantArtifact.id.desc()).limit(100).all()
    policy = next((r.payload for r in rows if r.kind == 'policy'), {})
    context['project_memory'] = memory_context(db, user, project_id)
    context['working_calendar'] = {k: policy.get(k, default) for k, default in {
        'timezone':'Asia/Kolkata', 'weekdays':[0,1,2,3,4], 'holidays':[], 'hours_per_day':8}.items()}
    context['saved_playbooks'] = [{'id':r.id,'title':r.title,'revision':r.revision,'plan':r.payload.get('plan')} for r in rows if r.kind=='playbook'][:10]
    context['event_rules'] = [public(r) for r in rows if r.kind=='rule'][:10]
    context['autonomy_policy'] = {'auto_enabled':policy.get('auto_enabled',False),'allowed_tools':policy.get('allowed_tools',[]),'max_steps':policy.get('max_steps',3),
        'instruction':'Standing consent is configured only by an administrator in settings. An LLM cannot enable or expand this policy.'}
    context['delivery_monitors'] = [{'id':r.id,'name':r.name,'enabled':r.enabled,'findings':r.findings,'checked_at':str(r.checked_at)}
        for r in db.query(OperatorMonitor).filter_by(user_id=user.id,project_id=project_id).limit(10)]
    context['agent_capabilities'] = ['task_plan','work_breakdown','calendar_schedule','memory','playbook','delivery_monitor','event_rule','impact','supported_undo']
    return context


def artifact_body(step):
    p = step.payload
    if step.tool == 'pms.remember':
        return {'project_id':step.record_id,'kind':'memory','title':p.get('title','Project memory'),'payload':{'text':p['text'],'category':p.get('category','preference')}}
    if step.tool == 'pms.save_playbook':
        return {'project_id':step.record_id,'kind':'playbook','title':p['title'],'payload':{'plan':p['plan']}}
    if step.tool == 'pms.event_rule':
        return {'project_id':step.record_id,'kind':'rule','title':p['title'],'payload':{k:v for k,v in p.items() if k!='title'}}
    return None


async def prepare_step(app, authorization, db, user, run, step, index, call):
    """Only prepare proposals here. Never approve a child before parent approval."""
    p = step.payload
    key = str(uuid5(NAMESPACE_URL, f'suite-pms:{run.id}:{index}'))
    project_id = step.record_id
    nested = None
    impact = None
    manual = []
    if step.tool == 'pms.schedule':
        suggestion = await call(app,authorization,'POST','/ai-operator/workbench/schedule',{
            'project_id':project_id,'task_ids':p['task_ids'],'start_date':resolve_date(p['start_date'],(run.result or {}).get('request',{}).get('timezone','Asia/Kolkata'))})
        step.tool = 'pms.task_plan'
        step.payload = {'plan':suggestion['plan'],'mode':'checkpointed'}
        p = step.payload
    if step.tool == 'pms.task_plan':
        body = {'project_id':project_id,'plan':p['plan'],'mode':p.get('mode','checkpointed'),'request_key':key,
                'input_mode':(run.result or {}).get('request',{}).get('input_mode','text')}
        nested = await call(app,authorization,'POST','/ai-operator/workbench/plans/preview',body)
        impact = await call(app,authorization,'POST','/ai-operator/workbench/impact',body)
    elif step.tool in ('pms.run_playbook','pms.undo'):
        if step.tool == 'pms.run_playbook':
            from app.ai_operator.workbench import owned
            book = owned(db,user,p['playbook_id'])
            if book.kind!='playbook' or book.project_id!=project_id:
                raise HTTPException(422,'Choose a playbook from the selected project')
            nested = await call(app,authorization,'POST',f'/ai-operator/workbench/items/{book.id}/run')
        else:
            from app.ai_operator.api import owned_run
            source = owned_run(db,user,p['run_id'])
            if source.project_id!=project_id:
                raise HTTPException(422,'Choose an execution from the selected project')
            result = await call(app,authorization,'POST',f'/ai-operator/workbench/runs/{source.id}/undo-preview')
            nested, manual = result['run'], result['manual']
        # Freeze the actual plan, not an instruction to fetch a mutable playbook later.
        step.tool='pms.task_plan'
        step.payload={'plan':nested['plan'],'mode':nested['execution_mode']}
    elif step.tool == 'pms.kickoff':
        nested = await call(app,authorization,'POST','/ai-operator/setup/preview',{
            'brief':run.command[:20000],'provider':(run.result or {}).get('request',{}).get('provider','gemini'),
            'request_key':key,'workspace_id':run.workspace_id,'project_id':project_id,'local_plan':p['plan']})
        return {'kind':'setup','id':nested['id'],'plan_hash':nested['plan_hash'],'project_id':project_id,'preview':nested['payload']['plan']}
    else:
        if step.tool=='pms.event_rule' and p.get('autonomous'):
            from app.ai_operator.workbench import policy_for
            if not policy_for(db,user,project_id).auto_enabled:
                raise HTTPException(422,'Enable bounded status/priority autonomy explicitly in administrator settings first')
        body=artifact_body(step)
        if body:
            from app.ai_operator.workbench import ArtifactInput, validate_artifact
            validate_artifact(db,user,ArtifactInput.model_validate(body))
    if nested:
        if nested['status']!='awaiting_approval':
            raise HTTPException(409,'PMS plan needs a fresh complete preview')
        return {'kind':'task','id':nested['id'],'plan_hash':nested['plan_hash'],'project_id':project_id,'impact':impact,'manual':manual}
    return None


async def execute_step(app, authorization, step, prepared, call):
    if prepared:
        if prepared['kind']=='task':
            result = await call(app,authorization,'POST',f'/ai-operator/runs/{prepared["id"]}/approve',{'plan_hash':prepared['plan_hash']})
            return {'waiting_pms':True,'pms_run_id':result['id']}
        result = await call(app,authorization,'POST',f'/ai-operator/proposals/{prepared["id"]}/approve',{'plan_hash':prepared['plan_hash']})
        if result['status']!='succeeded':
            raise HTTPException(409,'Project creation did not complete')
        return {'id':result['result']['project_id'],'setup_proposal_id':result['id'],'setup_receipts':result['result']}
    body=artifact_body(step)
    if body:
        return await call(app,authorization,'POST','/ai-operator/workbench/items',body)
    if step.tool=='pms.watch':
        return await call(app,authorization,'POST','/ai-operator/monitors',{'project_id':step.record_id,**step.payload})
    raise HTTPException(422,'Unsupported PMS agent execution')
