"""Bounded deterministic assistant tools. All business writes reuse operator APIs."""
import json
import math
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.ai_agents.api import _require_ai_access, _require_ai_admin
from app.ai_agents.services.audit import AiAuditService
from app.ai_operator.workbench_models import AssistantArtifact, AssistantSignal
from app.ai_operator.models import OperatorRun, OperatorApiLog
from app.ai_operator.schemas import TaskPlan, CommandInput, ApproveInput
from app.ai_operator.service import scope_key, require_enabled, context_for, task_snapshot, validate_plan, digest
from app.ai_operator.extensions import local_context, capacity, goal_findings
from app.apps.project_management.access import get_project_for_action
from app.apps.project_management.models import PMSTask, PMSTaskDependency

router = APIRouter(prefix='/workbench', tags=['Assistant workbench'])


def access(db, user, project_id):
    _require_ai_access(user)
    require_enabled(db, user)
    project = get_project_for_action(db, project_id, user, 'manage_tasks')
    return project, scope_key(db, user, project.workspace_id)


def items(db, user, project_id, kind=None):
    _, scope = access(db, user, project_id)
    q = db.query(AssistantArtifact).filter_by(user_id=user.id, project_id=project_id, scope_key=scope)
    return q.filter_by(kind=kind) if kind else q


def owned(db, user, ident, lock=False):
    q = db.query(AssistantArtifact).filter_by(id=ident, user_id=user.id)
    row = (q.with_for_update() if lock else q).first()
    if not row:
        raise HTTPException(404, 'Assistant item not found')
    if access(db, user, row.project_id)[1] != row.scope_key:
        raise HTTPException(403, 'Project scope changed')
    return row


def public(row):
    return {k: getattr(row, k) for k in ('id','project_id','kind','key','title','payload','revision','updated_at')}


def audit_item(db,user,row,action):
    AiAuditService(db).log(user=user,agent_id=None,module='PMS',action=f'assistant.{row.kind}.{action}',
        input_json={'item_id':row.id,'project_id':row.project_id},output_json={'revision':row.revision},status='success')


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Policy(Strict):
    timezone: str = 'Asia/Kolkata'
    auto_enabled: bool = False
    allowed_tools: list[Literal['update_task']] = Field(default_factory=list, max_length=1)
    max_steps: int = Field(default=3, ge=1, le=3)
    weekdays: list[int] = Field(default_factory=lambda: [0,1,2,3,4], min_length=1, max_length=7)
    holidays: list[date] = Field(default_factory=list, max_length=100)
    hours_per_day: float = Field(default=8, ge=1, le=12)
    skills: dict[str, list[str]] = Field(default_factory=dict)
    away_user_ids: list[int] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def check(self):
        try:ZoneInfo(self.timezone)
        except (ValueError,ZoneInfoNotFoundError):raise ValueError('Unknown calendar timezone')
        if any(d < 0 or d > 6 for d in self.weekdays) or len(self.skills) > 100 or any(len(v)>20 or any(len(s)>80 for s in v) for v in self.skills.values()):
            raise ValueError('Invalid working calendar or skill directory')
        self.skills={key:[skill.strip() for skill in skills if skill.strip()] for key,skills in self.skills.items()}
        return self


class ArtifactInput(Strict):
    project_id: int = Field(gt=0)
    kind: Literal['memory','playbook','policy','teaching','evaluation','rule']
    title: str = Field(min_length=1,max_length=180)
    payload: dict
    revision: int | None = Field(default=None,ge=1)


def validate_artifact(db, user, data):
    access(db,user,data.project_id)
    body=data.payload
    if len(json.dumps(body))>30000:
        raise HTTPException(422,'Assistant item exceeds 30 KB')
    if data.kind=='memory':
        if set(body)-{'text','category'} or not isinstance(body.get('text'),str) or not 1<=len(body['text'])<=2000:
            raise HTTPException(422,'Memory needs text, up to 2000 characters')
        if body.get('category','preference') not in ('preference','decision','terminology','constraint'):
            raise HTTPException(422,'Choose a supported memory category')
    elif data.kind=='policy':
        _require_ai_admin(user)
        policy=Policy.model_validate(body)
        context=local_context(data.project_id,db,user)
        collaborator_ids={str(p['id']) for p in context['collaborators']}
        if set(policy.skills)-collaborator_ids or set(map(str,policy.away_user_ids))-collaborator_ids:
            raise HTTPException(422,'Skills and availability must use current project collaborators')
        return policy.model_dump(mode='json')
    elif data.kind in ('playbook','teaching'):
        plan=TaskPlan.model_validate(body.get('plan'))
        targets=sorted({s.task_id for s in plan.steps}|{s.source_task_id for s in plan.steps if s.source_task_id})
        if not targets or len(targets)>25:
            raise HTTPException(422,'Choose 1–25 target tasks')
        validate_plan(db,user,SimpleNamespace(project_id=data.project_id,selection=targets),plan)
        if not isinstance(body.get('command',''),str) or len(body.get('command',''))>4000:
            raise HTTPException(422,'Example command must be text, up to 4000 characters')
        if data.kind=='teaching' and not body.get('command','').strip():
            raise HTTPException(422,'A teaching example needs the original command')
        return {'plan':plan.model_dump(mode='json',exclude_none=True),'command':str(body.get('command',''))[:4000],
                'approved':False if data.kind=='teaching' else True}
    elif data.kind=='evaluation':
        if not isinstance(body.get('command'),str) or not 1<=len(body['command'])<=4000 or body.get('expected_kind') not in ('ask','answer','task_plan','project_plan','unsupported'):
            raise HTTPException(422,'Evaluation needs a command and expected reply kind')
        tools=body.get('expected_tools',[])
        if not isinstance(tools,list) or len(tools)>9 or any(t not in TOOL_NAMES for t in tools):
            raise HTTPException(422,'Choose supported expected tools')
        return {'command':body['command'],'expected_kind':body['expected_kind'],'expected_tools':tools}
    elif data.kind=='rule':
        if type(body.get('playbook_id')) is not int or any(k in body and type(body[k]) is not bool for k in ('enabled','autonomous')):
            raise HTTPException(422,'Rules require a playbook ID and boolean enabled/autonomous fields')
        playbook=owned(db,user,body.get('playbook_id',0))
        if playbook.project_id!=data.project_id or playbook.kind!='playbook' or body.get('trigger') not in ('overdue','blocked','task_created','status_changed'):
            raise HTTPException(422,'Choose a playbook and supported project event')
        return {'playbook_id':playbook.id,'trigger':body['trigger'],'enabled':bool(body.get('enabled',False)),
                'autonomous':bool(body.get('autonomous',False)),'fingerprint':None,'last_run_id':None}
    return body


TOOL_NAMES={'update_task','schedule_task','add_checklist','move_to_sprint','add_dependency','remove_dependency','update_checklist','remove_checklist','add_comment'}


@router.get('/items')
def list_items(project_id:int, db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return {'items':[public(r) for r in items(db,user,project_id).filter(AssistantArtifact.kind!='run_state').order_by(AssistantArtifact.id.desc()).limit(250)]}


@router.post('/items')
def create_item(data:ArtifactInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    try:body=validate_artifact(db,user,data)
    except (ValueError,TypeError,KeyError):raise HTTPException(422,'Invalid assistant item fields') from None
    if data.kind=='policy' and items(db,user,data.project_id,'policy').first():
        raise HTTPException(409,'Edit the existing policy instead')
    if items(db,user,data.project_id).filter(AssistantArtifact.kind!='run_state').count()>=250:
        raise HTTPException(409,'Remove unused assistant items before adding more')
    row=AssistantArtifact(user_id=user.id,project_id=data.project_id,scope_key=access(db,user,data.project_id)[1],
        kind=data.kind,key='policy' if data.kind=='policy' else str(uuid4()),title=data.title,payload=body)
    try:
        db.add(row);db.flush();audit_item(db,user,row,'created');db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Assistant item already exists; reload before editing') from None
    return public(row)


@router.put('/items/{ident}')
def edit_item(ident:int,data:ArtifactInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,True)
    if row.kind!=data.kind or row.project_id!=data.project_id or row.kind=='run_state':
        raise HTTPException(422,'Item identity cannot change')
    if row.revision!=data.revision:
        raise HTTPException(409,'Item changed; reload before editing')
    try:body=validate_artifact(db,user,data)
    except (ValueError,TypeError,KeyError):raise HTTPException(422,'Invalid assistant item fields') from None
    row.payload=body;row.title=data.title;row.revision+=1
    audit_item(db,user,row,'updated')
    db.commit();return public(row)


@router.delete('/items/{ident}')
def delete_item(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,True)
    if row.kind in ('run_state','policy'):
        if row.kind=='run_state':raise HTTPException(409,'Execution evidence is retained for recovery')
        _require_ai_admin(user)
    audit_item(db,user,row,'deleted');db.delete(row);db.commit();return {'deleted':True}


def policy_for(db,user,project_id):
    row=items(db,user,project_id,'policy').first()
    return Policy.model_validate(row.payload if row else {})


def project_today(db,user,project_id):
    return datetime.now(ZoneInfo(policy_for(db,user,project_id).timezone)).date()


def memory_context(db,user,project_id):
    return [{'id':r.id,'category':r.payload.get('category','preference'),'text':r.payload['text']}
            for r in items(db,user,project_id,'memory').order_by(AssistantArtifact.id.desc()).limit(20)]


class PlanInput(Strict):
    project_id:int=Field(gt=0)
    plan:TaskPlan
    request_key:str=Field(min_length=8,max_length=100)
    mode:Literal['atomic','checkpointed']='atomic'
    input_mode:Literal['voice','text']='text'
    parent_run_id:int | None=None
    parent_plan_hash:str | None=None


@router.post('/plans/preview')
def preview(data:PlanInput,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.api import command
    ids=sorted({s.task_id for s in data.plan.steps}|{s.source_task_id for s in data.plan.steps if s.source_task_id})
    if data.parent_run_id:
        from app.ai_operator.api import owned_run
        ids=owned_run(db,user,data.parent_run_id).selection
    return command(CommandInput(project_id=data.project_id,task_ids=ids,command=data.plan.summary,provider='openai',
        request_key=data.request_key,local_plan=data.plan,background=True,execution_mode=data.mode,input_mode=data.input_mode,
        parent_run_id=data.parent_run_id,parent_plan_hash=data.parent_plan_hash),request,db,user)


@router.post('/impact')
def impact(data:PlanInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    ids=sorted({s.task_id for s in data.plan.steps}|{s.source_task_id for s in data.plan.steps if s.source_task_id})
    _,tasks,_=context_for(db,user,data.project_id,ids)
    validate_plan(db,user,SimpleNamespace(project_id=data.project_id,selection=ids),data.plan)
    by_id={t.id:t for t in tasks};diff=[]
    for step in data.plan.steps:
        t=by_id[step.task_id]
        changes=step.changes.model_dump(exclude_none=True) if step.changes else {
            k:v for k,v in step.model_dump(mode='json',exclude_none=True).items() if k not in ('tool','task_id','depends_on','lag_days')}
        diff.append({'task_id':t.id,'task_key':t.task_key,'title':t.title,'tool':step.tool,
            'changes':[{'field':k,'before':getattr(t,k,None),'after':v} for k,v in changes.items()]})
    dependents=db.query(PMSTaskDependency).filter(PMSTaskDependency.depends_on_task_id.in_(ids)).all()
    linked=db.query(PMSTask).filter(PMSTask.id.in_([d.task_id for d in dependents]),PMSTask.project_id==data.project_id,PMSTask.deleted_at.is_(None)).all()
    return {'changes':diff,'dependent_tasks':[{'id':t.id,'key':t.task_key,'title':t.title,'due_date':t.due_date} for t in linked],
        'assumptions':'Dates, dependencies and permissions validated against current records; downstream tasks are not silently rescheduled.'}


class ScheduleInput(Strict):
    project_id:int=Field(gt=0)
    task_ids:list[int]=Field(min_length=1,max_length=25)
    start_date:date


@router.post('/schedule')
def schedule(data:ScheduleInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    context_for(db,user,data.project_id,data.task_ids)
    policy=policy_for(db,user,data.project_id)
    all_tasks={t.id:t for t in db.query(PMSTask).filter_by(project_id=data.project_id,deleted_at=None).limit(501)}
    if len(all_tasks)>500:raise HTTPException(422,'Narrow scheduling to a project with at most 500 tasks')
    edges=db.query(PMSTaskDependency).filter(PMSTaskDependency.task_id.in_(list(all_tasks))).all()
    holidays=set(policy.holidays)
    def working(day):return day.weekday() in policy.weekdays and day not in holidays
    def next_day(day):
        for _ in range(1500):
            if working(day):return day
            day+=timedelta(days=1)
        raise HTTPException(422,'Calendar has no available working date')
    def end_day(start,duration):
        end=start
        for _ in range(duration-1):end=next_day(end+timedelta(days=1))
        return end
    def start_for_end(end,duration):
        start=end
        for _ in range(duration-1):
            start-=timedelta(days=1)
            while not working(start):start-=timedelta(days=1)
        return start
    planned={};visiting=set();steps=[]
    def place(ident):
        if ident in planned:return planned[ident]
        if ident in visiting:raise HTTPException(422,'Dependency cycle prevents scheduling')
        visiting.add(ident);task=all_tasks[ident];start=next_day(data.start_date)
        duration=max(1,math.ceil(float(task.estimated_hours or policy.hours_per_day)/policy.hours_per_day))
        for edge in edges:
            if edge.task_id!=ident:continue
            if edge.depends_on_task_id not in all_tasks:raise HTTPException(422,'Dependency points outside the accessible project')
            blocker=all_tasks[edge.depends_on_task_id]
            source_start,source_end=place(blocker.id) if blocker.id in data.task_ids else (blocker.start_date,blocker.due_date or blocker.start_date)
            kind=edge.dependency_type or 'Finish To Start'
            anchor=source_end if kind.startswith('Finish') else source_start
            if not anchor:raise HTTPException(422,f'Blocker {blocker.task_key} needs the required dates or must be selected')
            bound=next_day(anchor+timedelta(days=(edge.lag_days or 0)+(1 if kind=='Finish To Start' else 0)))
            if kind in ('Finish To Start','Start To Start'):start=max(start,bound)
            elif kind in ('Finish To Finish','Start To Finish'):start=max(start,start_for_end(bound,duration))
            else:raise HTTPException(422,'Unsupported dependency relationship')
        end=end_day(start,duration)
        planned[ident]=(start,end);visiting.remove(ident)
        steps.append({'tool':'schedule_task','task_id':ident,'start_date':start.isoformat(),'due_date':end.isoformat()})
        return start,end
    for ident in data.task_ids:place(ident)
    plan=TaskPlan.model_validate({'summary':'Schedule selected work around dependencies and the working calendar','steps':steps})
    validate_plan(db,user,SimpleNamespace(project_id=data.project_id,selection=data.task_ids),plan)
    return {'plan':plan.model_dump(mode='json',exclude_none=True),'assumptions':'One person per task; estimates rounded to working days. All four dependency relationships and calendar-day lag are respected. Finish To Start begins the next working day. Calendar uses this assistant policy; preview before applying.'}


@router.get('/insights')
def insights(project_id:int,week_start:date | None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    access(db,user,project_id);today=week_start or project_today(db,user,project_id)
    context=local_context(project_id,db,user);load=capacity(project_id,today,db,user)
    policy=policy_for(db,user,project_id)
    for person in load['items']:
        person['skills']=policy.skills.get(str(person['user_id']),[])
        person['away']=person['user_id'] in policy.away_user_ids
        person['available_hours']=0 if person['away'] else max(0,person['capacity_hours']-person['allocated_hours'])
    people=sorted(load['items'],key=lambda p:(p['away'],-p['available_hours']))
    return {'project':context['project'],'risks':goal_findings(db,project_id,today),'workload':people,
        'status_counts':dict(Counter(t['status'] for t in context['tasks'])),
        'assumptions':load['assumptions']+' Away people are excluded from recommendations; skills are explicitly maintained, not inferred.',
        'complete':context['tasks_complete']}


@router.get('/search')
def search(project_id:int,q:str=Query(min_length=1,max_length=200),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    access(db,user,project_id)
    query=db.query(PMSTask).filter_by(project_id=project_id,deleted_at=None);low=q.lower();filters=[]
    if re.search(r'\boverdue\b',low):query=query.filter(PMSTask.due_date<project_today(db,user,project_id),PMSTask.status!='Done');filters.append('overdue')
    if re.search(r'\b(blocked|blocking|blockers?)\b',low):
        blockers=db.query(PMSTaskDependency.depends_on_task_id).filter(PMSTaskDependency.task_id.in_(db.query(PMSTask.id).filter_by(project_id=project_id,deleted_at=None)))
        query=query.filter((PMSTask.status=='Blocked') | PMSTask.id.in_(blockers));filters.append('blocked or a dependency blocker')
    if re.search(r'\b(done|completed)\b',low):query=query.filter(PMSTask.status=='Done');filters.append('done')
    if re.search(r'\b(high|urgent)\b',low):query=query.filter(PMSTask.priority.in_(['High','Urgent']));filters.append('high or urgent')
    all_rows=query.order_by(PMSTask.id.desc()).limit(501).all()
    if re.search(r'\b(my|mine|assigned to me)\b',low):all_rows=[t for t in all_rows if user.id in t.assignee_user_ids];filters.append('assigned to you')
    phrase=re.sub(r'\b(show|find|which|what|are|the|tasks?|work|overdue|blocked|blocking|blockers?|done|completed|high|urgent|my|mine|assigned|to|me|please|is|this|project)\b',' ',low)
    words=phrase.split()
    if words:all_rows=[t for t in all_rows if all(w in (t.title+' '+t.task_key).lower() for w in words)]
    return {'items':[{'id':t.id,'key':t.task_key,'title':t.title,'status':t.status,'priority':t.priority,'due_date':t.due_date,
        'href':f'/pms/projects/{project_id}/tasks/{t.id}'} for t in all_rows[:50]],'filters':filters,'limit':50}


def remember_run_before(db,run,tasks):
    row=AssistantArtifact(user_id=run.user_id,project_id=run.project_id,scope_key=run.scope_key,kind='run_state',key=f'run:{run.id}',title=f'Run {run.id}',
        payload={'run_id':run.id,'before':{str(t.id):task_snapshot(db,t) for t in tasks}})
    db.add(row)


def remember_run_after(db,run):
    row=db.query(AssistantArtifact).filter_by(user_id=run.user_id,project_id=run.project_id,kind='run_state',key=f'run:{run.id}').first()
    if row:
        db.flush()
        row.payload={**row.payload,'after':{str(t.id):digest(task_snapshot(db,t)) for t in db.query(PMSTask).filter(PMSTask.id.in_(run.selection))}}


def check_standing_consent(db,user,run):
    evidence=db.query(AssistantArtifact).filter_by(user_id=run.user_id,project_id=run.project_id,kind='run_state',key=f'run:{run.id}').first()
    binding=(evidence.payload or {}).get('automatic_policy') if evidence else None
    if not binding:return
    try:_require_ai_admin(user)
    except HTTPException:raise HTTPException(403,'AUTO_POLICY_REVOKED') from None
    policy_row=owned(db,user,binding['policy_id'],True)
    rule=owned(db,user,binding['rule_id'],True)
    if policy_row.project_id!=run.project_id or rule.project_id!=run.project_id or policy_row.kind!='policy' or rule.kind!='rule' or policy_row.revision!=binding['policy_revision'] or rule.revision!=binding['rule_revision']:
        raise HTTPException(403,'AUTO_POLICY_REVOKED')
    policy=Policy.model_validate(policy_row.payload);plan=TaskPlan.model_validate(run.plan)
    if not policy.auto_enabled or not rule.payload.get('enabled') or not rule.payload.get('autonomous') or len(plan.steps)>policy.max_steps or not all(
        s.tool in policy.allowed_tools and s.changes and set(s.changes.model_dump(exclude_none=True))<={'status','priority'} for s in plan.steps):
        raise HTTPException(403,'AUTO_POLICY_REVOKED')


@router.post('/runs/{run_id}/undo-preview')
def undo_preview(run_id:int,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.api import owned_run
    run=owned_run(db,user,run_id)
    state=items(db,user,run.project_id,'run_state').filter_by(key=f'run:{run.id}').with_for_update().first()
    if run.status!='succeeded' or not state or not state.payload.get('after'):
        raise HTTPException(409,'This run has no complete reversible evidence. Use workspace recovery for older or partially completed runs.')
    if state.payload.get('undo_run_id'):
        from app.ai_operator.api import public_run
        previous=owned_run(db,user,state.payload['undo_run_id'])
        if previous.status not in ('cancelled','failed','superseded'):
            return {'run':public_run(previous),'manual':state.payload.get('manual',[])}
    db.query(PMSTask).filter(PMSTask.id.in_(run.selection)).order_by(PMSTask.id).populate_existing().with_for_update().all()
    _,tasks,_=context_for(db,user,run.project_id,run.selection)
    if any(digest(task_snapshot(db,t))!=state.payload['after'].get(str(t.id)) for t in tasks):
        raise HTTPException(409,'Records changed after execution. Review current records before recovery.')
    steps=[];manual=[];before=state.payload['before'];receipts={r['step']:r for r in run.result.get('receipts',[])}
    for position,step in reversed(list(enumerate(run.plan['steps'],1))):
        old=before[str(step['task_id'])];tool=step['tool'];inverse={'task_id':step['task_id']}
        if tool=='update_task':
            changes={k:old.get(k) for k in step['changes'] if old.get(k) is not None}
            if changes.get('status')=='Done' and old.get('recurrence_rule'):
                changes.pop('status');manual.append('Recurring completion requires manual recovery to avoid creating a duplicate recurrence.')
            if len(changes)!=len(step['changes']):manual.append('Clearing nullable fields requires manual recovery.')
            if changes:steps.append({**inverse,'tool':tool,'changes':changes})
        elif tool=='schedule_task' and old.get('start_date') not in ('None',None) and old.get('due_date') not in ('None',None):
            steps.append({**inverse,'tool':tool,'start_date':old['start_date'],'due_date':old['due_date']})
        elif tool=='move_to_sprint' and old.get('sprint_id'):
            steps.append({**inverse,'tool':tool,'sprint_id':old['sprint_id']})
        elif tool=='add_checklist' and receipts.get(position):
            steps.append({**inverse,'tool':'remove_checklist','item_id':receipts[position]['record_id']})
        elif tool=='update_checklist':
            item=next((i for i in old['checklist'] if i['id']==step['item_id']),None)
            if item:steps.append({**inverse,'tool':tool,'item_id':item['id'],'is_completed':item['is_completed']})
        elif tool=='add_dependency' and receipts.get(position):
            steps.append({**inverse,'tool':'remove_dependency','dependency_id':receipts[position]['record_id']})
        else:manual.append(f'{tool} on task {step["task_id"]} requires manual recovery.')
    if not steps:raise HTTPException(409,'No supported inverse actions. '+ ' '.join(manual))
    plan=TaskPlan.model_validate({'summary':f'Recover supported changes from run #{run.id}','steps':steps})
    result=preview(PlanInput(project_id=run.project_id,plan=plan,request_key=f'undo:{run.id}:{state.revision}'),request,db,user)
    state.payload={**state.payload,'undo_run_id':result['id'],'manual':manual};state.revision+=1;db.commit()
    return {'run':result,'manual':manual}


@router.post('/items/{ident}/run')
def run_playbook(ident:int,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident)
    if row.kind!='playbook':raise HTTPException(422,'Select a playbook')
    return preview(PlanInput(project_id=row.project_id,plan=TaskPlan.model_validate(row.payload['plan']),request_key=f'playbook:{row.id}:{uuid4()}'),request,db,user)


@router.post('/items/{ident}/approve-teaching')
def approve_teaching(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _require_ai_admin(user)
    row=db.query(AssistantArtifact).filter_by(id=ident,kind='teaching').with_for_update().first()
    if not row:raise HTTPException(404,'Teaching example not found')
    project,scope=access(db,user,row.project_id)
    if (project.workspace_id is not None and row.scope_key!=scope) or (project.workspace_id is None and row.scope_key.startswith('workspace:')):
        raise HTTPException(403,'Teaching example scope changed')
    row.payload={**row.payload,'approved':True};row.revision+=1;audit_item(db,user,row,'reviewed');db.commit();return public(row)


@router.get('/teaching/review')
def teaching_review(project_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _require_ai_admin(user);project,scope=access(db,user,project_id)
    query=db.query(AssistantArtifact).filter_by(project_id=project_id,kind='teaching')
    query=query.filter(AssistantArtifact.scope_key==scope) if project.workspace_id is not None else query.filter(~AssistantArtifact.scope_key.like('workspace:%'))
    return {'items':[{**public(r),'submitted_by':r.user_id} for r in query.order_by(AssistantArtifact.id.desc()).limit(250)]}


@router.get('/teaching/export')
def export_teaching(project_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _require_ai_admin(user)
    rows=teaching_review(project_id,db,user)['items']
    return {'version':1,'examples':[{'command':r['payload']['command'],'plan':r['payload']['plan']} for r in rows if r['payload'].get('approved')],
        'note':'Reviewed examples for offline training/evaluation. Exporting does not retrain or change deployed weights.'}


class EvaluationResult(Strict):
    actual_kind:Literal['ask','answer','task_plan','project_plan','unsupported','unavailable']
    actual_plan:TaskPlan | None=None
    duration_ms:int=Field(ge=0,le=600000)
    request_key:str=Field(min_length=8,max_length=100)


@router.post('/items/{ident}/evaluate')
def evaluate(ident:int,data:EvaluationResult,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident)
    if row.kind!='evaluation':raise HTTPException(422,'Select an evaluation case')
    tools=sorted({s.tool for s in data.actual_plan.steps}) if data.actual_plan else []
    valid=not (data.actual_kind=='task_plan' and not data.actual_plan) and not (data.actual_kind!='task_plan' and data.actual_plan)
    if data.actual_plan:
        try:validate_plan(db,user,SimpleNamespace(project_id=row.project_id,selection=[s.task_id for s in data.actual_plan.steps]),data.actual_plan)
        except HTTPException:valid=False
    passed=valid and data.actual_kind==row.payload['expected_kind'] and tools==sorted(set(row.payload.get('expected_tools',[])))
    details={'case_id':row.id,'passed':passed,'actual_kind':data.actual_kind,'tools':tools,'duration_ms':data.duration_ms}
    old=db.query(AssistantSignal).filter_by(user_id=user.id,request_key=data.request_key).first()
    if old:
        if old.kind!='evaluation' or old.project_id!=row.project_id or old.details.get('case_id')!=row.id:raise HTTPException(409,'Evaluation request key belongs to another result')
        return old.details
    db.add(AssistantSignal(user_id=user.id,project_id=row.project_id,request_key=data.request_key,kind='evaluation',details=details));db.commit()
    return details


class FeedbackInput(Strict):
    project_id:int=Field(gt=0)
    category:Literal['misunderstood','repeated_question','incorrect_plan','wrong_action','rejected_plan']
    run_id:int | None=None
    request_key:str=Field(min_length=8,max_length=100)


@router.post('/feedback')
def feedback(data:FeedbackInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    access(db,user,data.project_id)
    if data.run_id:
        from app.ai_operator.api import owned_run
        if owned_run(db,user,data.run_id).project_id!=data.project_id:raise HTTPException(422,'Feedback run must belong to this project')
    body={'category':data.category,'run_id':data.run_id}
    old=db.query(AssistantSignal).filter_by(user_id=user.id,request_key=data.request_key).first()
    if old:
        if old.project_id!=data.project_id or old.kind!='feedback' or old.details!=body:raise HTTPException(409,'Feedback request key already used')
        return {'recorded':True}
    db.add(AssistantSignal(user_id=user.id,project_id=data.project_id,request_key=data.request_key,kind='feedback',details=body));db.commit()
    return {'recorded':True}


@router.get('/metrics')
def metrics(project_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _,scope=access(db,user,project_id)
    runs=db.query(OperatorRun).filter_by(user_id=user.id,project_id=project_id).order_by(OperatorRun.id.desc()).limit(100).all()
    signals=db.query(AssistantSignal).filter_by(user_id=user.id,project_id=project_id).order_by(AssistantSignal.id.desc()).limit(100).all()
    logs=db.query(OperatorApiLog).filter_by(user_id=user.id,scope_key=scope).order_by(OperatorApiLog.id.desc()).limit(200).all()
    from app.ai_operator.assistant_models import AssistantConversation
    conversations=db.query(AssistantConversation).filter_by(user_id=user.id,deleted_at=None).order_by(AssistantConversation.id.desc()).limit(200).all()
    turns=[t for c in conversations if (c.references or {}).get('project_id')==project_id and c.references.get('brain_scope')==scope for t in c.references.get('brain_turns',[])]
    evaluations=[s.details for s in signals if s.kind=='evaluation']
    histories=[c.references.get('brain_turns',[]) for c in conversations if (c.references or {}).get('project_id')==project_id and c.references.get('brain_scope')==scope]
    repeated=sum(a.get('reply',{}).get('kind')=='ask' and a.get('reply',{}).get('question')==b.get('reply',{}).get('question') for history in histories for a,b in zip(history,history[1:]))
    return {'run_status':dict(Counter(r.status for r in runs)),'routing':dict(Counter(t.get('runtime','browser') for t in turns)),
        'feedback_counts':dict(Counter(s.details['category'] for s in signals if s.kind=='feedback')),'repeated_questions':repeated,
        'fallback_reasons':dict(Counter(t['fallback_reason'] for t in turns if t.get('fallback_reason'))),
        'evaluations':evaluations,'evaluation_passes':sum(e.get('passed',False) for e in evaluations),
        'providers':[{'provider':p,'requests':len(group:=[l for l in logs if l.provider==p]),'input_tokens':sum(l.input_tokens or 0 for l in group),
            'output_tokens':sum(l.output_tokens or 0 for l in group),'priced_cost':sum(float(l.estimated_cost or 0) for l in group),
            'unpriced_requests':sum(l.estimated_cost is None for l in group),'average_latency_ms':round(sum(l.duration_ms for l in group)/len(group)) if group else 0} for p in ('openai','gemini','claude')],
        'limits':'Latest 100 project runs/evaluations and 200 personal provider calls in this scope; unknown prices are not zero cost.'}


def tick_rules(db,limit=10):
    """Owner permissions are rechecked on every tick; fingerprints suppress repeats."""
    rows=db.query(AssistantArtifact).filter_by(kind='rule').filter(AssistantArtifact.payload['enabled'].as_boolean().is_(True)).order_by(AssistantArtifact.updated_at,AssistantArtifact.id).limit(500).all()
    checked=created=0
    for row in rows:
        if checked>=limit:break
        body=dict(row.payload)
        if not body.get('enabled'):continue
        if body.get('next_check_at') and body['next_check_at']>datetime.now(timezone.utc).isoformat():continue
        checked+=1
        body['next_check_at']=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()
        try:
            user=db.get(User,row.user_id)
            if not user or not user.is_active:raise HTTPException(403,'Owner unavailable')
            owned(db,user,row.id)
            tasks=db.query(PMSTask).filter_by(project_id=row.project_id,deleted_at=None).order_by(PMSTask.id).limit(501).all()
            if len(tasks)>500:raise HTTPException(422,'Project exceeds rule observation limit')
            trigger=body['trigger']
            today=project_today(db,user,row.project_id)
            observed=[(t.id,t.status) for t in tasks if (trigger=='overdue' and t.due_date and t.due_date<today and t.status!='Done') or
                (trigger=='blocked' and t.status=='Blocked') or trigger in ('task_created','status_changed')]
            signature=digest(observed if trigger!='task_created' else [i for i,_ in observed])
            if signature==body.get('fingerprint'):
                row.payload=body;db.commit();continue
            # First observation establishes a baseline for change-based triggers.
            initial=body.get('fingerprint') is None
            old_observed=dict(body.get('observed',[]))
            current_observed=dict(observed)
            body['fingerprint']=signature
            body['observed']=observed
            changed=(bool(set(current_observed)-set(old_observed)) if trigger!='status_changed' else
                any(ident in old_observed and old_observed[ident]!=status for ident,status in current_observed.items()))
            if not observed or (initial and trigger in ('task_created','status_changed')) or (not initial and not changed):
                row.payload=body;db.commit();continue
            playbook=owned(db,user,body['playbook_id'])
            if playbook.kind!='playbook' or playbook.project_id!=row.project_id:raise HTTPException(422,'Playbook scope changed')
            request=Request({'type':'http','method':'POST','path':'/internal/assistant-rule','headers':[],'client':('127.0.0.1',0)})
            result=preview(PlanInput(project_id=row.project_id,plan=TaskPlan.model_validate(playbook.payload['plan']),request_key=f'rule:{row.id}:{signature}:{row.revision}'),request,db,user)
            body['last_run_id']=result['id'];body['error']=None
            row.payload=body;db.commit();created+=1
            policy=policy_for(db,user,row.project_id)
            plan=TaskPlan.model_validate(result['plan'])
            # Standing consent is restricted to small status/priority updates.
            if body.get('autonomous') and policy.auto_enabled and len(plan.steps)<=policy.max_steps and all(
                s.tool in policy.allowed_tools and s.changes and set(s.changes.model_dump(exclude_none=True))<={'status','priority'} for s in plan.steps):
                _require_ai_admin(user)
                from app.ai_operator.api import approve
                policy_row=items(db,user,row.project_id,'policy').first()
                evidence=items(db,user,row.project_id,'run_state').filter_by(key=f'run:{result["id"]}').first()
                if not policy_row or not evidence:raise HTTPException(409,'Automatic run evidence is unavailable')
                evidence.payload={**evidence.payload,'automatic_policy':{'policy_id':policy_row.id,'policy_revision':policy_row.revision,'rule_id':row.id,'rule_revision':row.revision}}
                db.flush()
                approve(result['id'],ApproveInput(plan_hash=result['plan_hash']),db,user)
                AiAuditService(db).log(user=user,agent_id=None,module='PMS',action='assistant.policy.auto_approved',input_json={'rule_id':row.id,'run_id':result['id']},output_json={},status='success')
                db.commit()
        except (HTTPException,ValueError,KeyError) as exc:
            db.rollback()
            current=db.get(AssistantArtifact,row.id)
            current.payload={**current.payload,'enabled':False,'error':'Rule paused: access, policy or plan validation failed.'};db.commit()
    return {'checked':checked,'created':created}
