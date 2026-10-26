"""Gemini suite operator. All business effects go through existing ASGI APIs.

Execution is checkpointed, not a cross-module transaction. An in-flight write
whose outcome is unknown requires reconciliation and is never automatically retried.
"""
from app.access.catalog import permission_objects
import json
from typing import Literal
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import uuid4
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.core.deps import get_db, get_current_user
from app.core.security import create_access_token, verify_access_token
from app.models.user import User
from app.ai_agents.api import _require_ai_access, _require_ai_rate_limit
from app.ai_agents.models import AiActionApproval
from app.ai_agents.services.audit import AiAuditService
from app.ai_agents.services.advanced_security import AiSecuritySettingsService, AiDataRedactionService, AiUsageService, company_id_for
from app.ai_operator.service import digest, scope_key, require_enabled
from app.ai_operator.provider_scope import resolve_provider
from app.ai_operator.providers import generate_json
from app.ai_operator.suite_models import SuiteRun
from app.ai_operator.models import OperatorApiLog
from app.ai_operator.suite_tools import Strict, TOOLS, catalog, validate_payload, minimize
from app.ai_operator.schemas import Provider
from app.module_registry import is_app_enabled
from app.apps.business_os.services.module_service import assert_module_enabled

router = APIRouter(prefix='/suite', tags=['Suite Gemini operator'])
MODULES = {'HRMS': 'hrms', 'CRM': 'crm', 'SRM': 'srm', 'FAM': 'fam', 'PMS': 'project_management'}


def now():
    return datetime.now(timezone.utc)


class Step(Strict):
    tool: str = Field(min_length=1, max_length=70)
    record_id: int | dict | None = None
    payload: dict = Field(default_factory=dict)


class Plan(Strict):
    summary: str = Field(min_length=1, max_length=2000)
    question: str | None = Field(default=None, max_length=1500)
    steps: list[Step] = Field(default_factory=list, max_length=12)

    @model_validator(mode='after')
    def complete(self):
        if self.question and self.steps:
            raise ValueError('Ask a question without proposing incomplete actions')
        return self


class Command(Strict):
    request_key: str = Field(min_length=8, max_length=100)
    text: str = Field(min_length=3, max_length=6000)
    workspace_id: int | None = Field(default=None, gt=0)
    context: list[Step] = Field(default_factory=list, max_length=6)
    local_plan: Plan | None = None
    mode: Literal['auto', 'summary'] = 'auto'
    provider: Provider = 'gemini'
    project_id: int | None = Field(default=None,gt=0)
    task_ids: list[int] = Field(default_factory=list,max_length=25)
    parent_run_id: int | None = Field(default=None,gt=0)
    timezone: str = 'Asia/Kolkata'
    input_mode: Literal['text','voice'] = 'text'

    @model_validator(mode='after')
    def valid_context(self):
        try:ZoneInfo(self.timezone)
        except (ValueError,ZoneInfoNotFoundError):raise ValueError('Choose a valid timezone')
        if self.task_ids and not self.project_id and not self.parent_run_id:
            raise ValueError('Selected tasks require a project')
        return self


class Summary(Strict):
    summary: str = Field(min_length=1, max_length=2000)


class Approval(Strict):
    plan_hash: str = Field(min_length=64, max_length=64)


def authorize(db, user, workspace_id, module=None):
    from app.ai_agents.security import ORIGIN,company
    ORIGIN.set({"company_id":company(user)})
    from app.access.service import check_background_access
    check_background_access(db, user, "ai", "view")
    _require_ai_access(user)
    assert_module_enabled(db, 'ai', company_id_for(user) or 1)
    AiUsageService(db).check_limits(user=user, agent=None, module='CROSS')
    scope = scope_key(db, user, workspace_id)
    AiSecuritySettingsService(db).ensure_enabled(user=user, module='CROSS')
    if module:
        if module not in MODULES or not is_app_enabled(MODULES[module]):
            raise HTTPException(403, 'Module is not installed')
        assert_module_enabled(db, MODULES[module], company_id_for(user) or 1)
        AiSecuritySettingsService(db).ensure_enabled(user=user, module=module)
    return scope


def check_tool(db, user, workspace_id, step, write=None):
    tool = TOOLS.get(step.tool)
    if not tool:
        raise HTTPException(422, 'Unsupported suite tool')
    from app.ai_agents.security import authorize_tool
    authorize_tool(db,user,"suite",step.tool,tool)
    authorize(db, user, workspace_id, tool.module)
    from app.access.service import check_background_access
    check_background_access(db, user, MODULES[tool.module], "view" if tool.method == "GET" else "create" if tool.method == "POST" else "edit")
    if write is not None and (tool.method != 'GET') != write:
        raise HTTPException(422, 'Select read tools for context and action tools for plans')
    if step.tool in ('hrms.my_leave', 'hrms.leave_balance', 'hrms.request_leave', 'hrms.create_ticket') and not getattr(user, 'employee', None):
        raise HTTPException(422, 'An employee profile is required for personal HR actions and records')
    permissions = {p.name for p in permission_objects(user)}
    if tool.permissions and not user.is_superuser and not permissions.intersection(tool.permissions):
        raise HTTPException(403, 'Action permission required')
    if ('{record_id}' in tool.path or (tool.project_target and not tool.optional_project)) and step.record_id is None:
        raise HTTPException(422, 'Select a record ID')
    if '{record_id}' not in tool.path and not tool.project_target and step.record_id is not None:
        raise HTTPException(422, 'This tool does not accept a record ID')
    if isinstance(step.record_id, int) and (isinstance(step.record_id, bool) or step.record_id <= 0):
        raise HTTPException(422, 'Record IDs must be positive integers')
    if tool.module == 'PMS' and isinstance(step.record_id, int):
        from app.apps.project_management.access import get_project_for_action
        project = get_project_for_action(db, step.record_id, user, 'manage_tasks' if tool.method != 'GET' else 'browse')
        if project.workspace_id != workspace_id:
            raise HTTPException(422, 'PMS project must match the selected workspace')
    if len(json.dumps(step.payload)) > 16000:
        raise HTTPException(422, 'Tool payload is too large')
    if set(step.payload) - set(tool.fields):
        raise HTTPException(422, 'Unsupported tool fields')
    return tool


def references(value, position, steps, receipts=None):
    if isinstance(value, dict):
        if '$step' in value:
            index = value.get('$step')
            if set(value) != {'$step', 'field'} or value.get('field') != 'id' or type(index) is not int or not 1 <= index < position:
                raise HTTPException(422, 'References must use an earlier step ID')
            if TOOLS.get(steps[index-1].tool, None) is None or TOOLS[steps[index-1].tool].method == 'GET':
                raise HTTPException(422, 'Reference must target a creation/action receipt')
            if steps[index-1].tool in ('pms.task_plan','pms.schedule','pms.run_playbook','pms.undo'):
                raise HTTPException(422,'Task execution IDs are not newly created business record IDs')
            if receipts is None:
                return 1  # Validate the shape now; resolve the authoritative ID at execution.
            receipt = next((r for r in receipts if r['step'] == index), None)
            if not receipt or type(receipt.get('record_id')) is not int:
                raise HTTPException(409, 'Referenced record is unavailable')
            return receipt['record_id']
        return {k: references(v, position, steps, receipts) for k, v in value.items()}
    if isinstance(value, list):
        return [references(v, position, steps, receipts) for v in value]
    return value


async def api_call(app, authorization, method, path, payload=None):
    from app.ai_agents.security import delegated_token
    authorization=delegated_token(authorization,method,'/api/v1'+path,payload)
    from app.core.security import verify_access_token
    selected=verify_access_token(authorization.partition(' ')[2])['ai_origin']['company_id']
    # Fixed local ASGI transport invokes canonical routers AND their dependencies.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                 base_url='http://suite-internal', headers={'Authorization': authorization,'X-Suite-Organization':str(selected)}, follow_redirects=False) as client:
        response = await client.request(method, '/api/v1'+path, params=payload if method == 'GET' else None,
                                        json=payload if method != 'GET' else None)
    if not 200 <= response.status_code < 300:
        raise HTTPException(response.status_code if response.status_code in (400, 401, 403, 404, 409, 422) else 502,
                            f'CANONICAL_API_HTTP_{response.status_code}')
    return response.json()


async def preflight(app, authorization, db, user, workspace_id, plan, run=None):
    from app.ai_agents.security import limits,company
    if len(plan.steps)>limits(db,company(user))["max_calls"]:raise HTTPException(422,"AI tool-call budget exceeded")
    snapshots = {}
    prepared = {}
    total_task_steps=0
    for index, step in enumerate(plan.steps, 1):
        tool = check_tool(db, user, workspace_id, step, True)
        payload = references(step.payload, index, plan.steps)
        references(step.record_id, index, plan.steps)
        validate_payload(tool, payload)
        if tool.project_target:
            selected_project=(run.result or {}).get('request',{}).get('project_id')
            if selected_project and step.record_id!=selected_project:
                raise HTTPException(422,'Action must retain the selected project')
            if isinstance(step.record_id,dict):
                raise HTTPException(422,'Create the project first or use one complete work breakdown before preparing task changes')
            from app.ai_operator.pms_agent import prepare_step
            child=await prepare_step(app,authorization,db,user,run,step,index,api_call)
            if child:
                prepared[str(index)]=child
                # Persist staged draft links so a later validation error can retire them.
                run.snapshots={**snapshots,'pms_children':dict(prepared)}
                db.commit()
            if step.tool=='pms.task_plan':
                total_task_steps+=len(step.payload['plan']['steps'])
                selected=(run.result or {}).get('request',{}).get('task_ids',[])
                targets={s['task_id'] for s in step.payload['plan']['steps']}
                if selected and not targets.issubset(set(selected)):
                    raise HTTPException(422,'Task plan exceeds the frozen selected tasks')
                if total_task_steps>75:raise HTTPException(422,'Prepare at most 75 task actions in one approval')
        if tool.guard and isinstance(step.record_id, int):
            path = tool.guard.format(record_id=step.record_id)
            record = await api_call(app, authorization, 'GET', path)
            snapshots[str(index)] = digest(record)
        if tool.module == 'PMS' and isinstance(step.record_id, int):
            from app.apps.project_management.access import get_project_for_action
            project = get_project_for_action(db, step.record_id, user, 'manage_tasks')
            if project.workspace_id != workspace_id:
                raise HTTPException(422, 'PMS project must match the selected workspace')
    if prepared:snapshots['pms_children']=prepared
    return snapshots


def public(run):
    return {'pms_previews':(run.snapshots or {}).get('pms_children',{}), **{k: getattr(run, k) for k in ('id', 'workspace_id', 'scope_key', 'command', 'status', 'plan', 'plan_hash',
        'approval_id', 'receipts', 'result', 'active_step', 'error_code', 'created_at', 'updated_at')}}


def retire_drafts(db,run):
    from app.ai_operator.models import OperatorRun, OperatorProposal
    for child in (run.snapshots or {}).get('pms_children',{}).values():
        row=db.get(OperatorRun if child['kind']=='task' else OperatorProposal,child['id'])
        if row and row.user_id==run.user_id and row.status=='awaiting_approval':
            row.status='cancelled'
            approval=db.get(AiActionApproval,row.approval_id)
            if approval and approval.status=='pending':approval.status='cancelled'


def owned(db, user, ident, lock=False):
    query = db.query(SuiteRun).filter_by(id=ident, user_id=user.id)
    run = (query.with_for_update().populate_existing() if lock else query).first()
    if not run:
        raise HTTPException(404, 'Suite run not found')
    from app.ai_agents.security import verify
    verify(db,user,run.security_context,history=True)
    if authorize(db, user, run.workspace_id) != run.scope_key:
        raise HTTPException(403, 'Suite scope changed')
    return run


@router.get('/tools')
def tools(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    authorize(db, user, None)
    return {'provider': 'gemini', 'tools': catalog(), 'execution_mode': 'checkpointed',
            'limits': '12 actions; 6 context reads; each source is capped at 50 records. Workspace selects provider/PMS scope; other modules retain company/role visibility.'}


@router.get('/runs')
def runs(workspace_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scope = authorize(db, user, workspace_id)
    rows = db.query(SuiteRun).filter_by(user_id=user.id, scope_key=scope).order_by(SuiteRun.id.desc()).limit(50).all()
    from app.ai_agents.security import visible_history
    return {'items': [public(r) for r in visible_history(db,user,rows)]}


@router.get('/runs/{ident}')
def get_run(ident: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return public(owned(db, user, ident))


@router.post('/commands')
async def command(data: Command, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scope = authorize(db, user, data.workspace_id)
    parent = owned(db,user,data.parent_run_id) if data.parent_run_id else None
    if parent:
        if parent.scope_key!=scope or parent.workspace_id!=data.workspace_id:
            raise HTTPException(409,'Continue in the original workspace')
        prior=(parent.result or {}).get('request',{})
        if data.project_id is not None and data.project_id!=prior.get('project_id'):
            raise HTTPException(409,'A follow-up must retain its project; start a fresh request to switch')
        if data.task_ids and data.task_ids!=prior.get('task_ids',[]):
            raise HTTPException(409,'A follow-up must retain its selected tasks')
        data.project_id=data.project_id or prior.get('project_id')
        data.task_ids=data.task_ids or prior.get('task_ids',[])
        if parent.status in ('planning','queued','executing','waiting_pms','cancelling'):
            raise HTTPException(409,'Wait for active work before revising it')
    fingerprint = digest(data.model_dump(mode='json', exclude={'request_key'}))
    previous = db.query(SuiteRun).filter_by(user_id=user.id, request_key=data.request_key).first()
    if previous:
        if previous.request_hash != fingerprint or previous.scope_key != scope:
            raise HTTPException(409, 'Request key already belongs to another command')
        return public(previous)
    _require_ai_rate_limit(db, request, user, bucket='suite_operator')
    config = resolve_provider(db, user, data.provider, data.workspace_id)
    if not data.local_plan and (not config or not config.enabled or not config.data_sharing_allowed):
        raise HTTPException(409, 'Selected LLM is unavailable in this scope')
    header = request.headers.get('authorization', '')
    claims = verify_access_token(header.partition(' ')[2]) or {}
    run = SuiteRun(user_id=user.id, session_id=claims.get('sid'), workspace_id=data.workspace_id, scope_key=scope,
                   request_key=data.request_key, request_hash=fingerprint, command=data.text, receipts=[],result={'request':{
                       'project_id':data.project_id,'task_ids':data.task_ids,'provider':data.provider,'timezone':data.timezone,
                       'input_mode':data.input_mode,'parent_run_id':data.parent_run_id}})
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = db.query(SuiteRun).filter_by(user_id=user.id, request_key=data.request_key).first()
        if not previous or previous.request_hash != fingerprint:
            raise HTTPException(409, 'Conflicting request') from None
        return public(previous)
    try:
        if data.mode == 'summary' and data.local_plan and data.local_plan.steps:
            raise HTTPException(422, 'Summary mode cannot contain actions')
        context = []
        project_context=None
        if data.project_id:
            from app.ai_operator.extensions import local_context
            from app.ai_operator.service import context_for
            from app.ai_operator.pms_agent import enrich_context
            from app.apps.project_management.access import get_project_for_action
            project=get_project_for_action(db,data.project_id,user,'manage_tasks')
            if project.workspace_id!=data.workspace_id:raise HTTPException(422,'Choose a project in the selected workspace')
            project_context=local_context(project.id,db,user)
            selected_snapshots=[]
            if data.task_ids:
                _,selected_tasks,packet=context_for(db,user,project.id,data.task_ids)
                selected_snapshots=[{**s,'task_key':t.task_key} for t,s in zip(selected_tasks,packet['tasks'])]
            available=project_context['tasks']
            project_context['tasks']=(selected_snapshots+[t for t in available if t['id'] not in data.task_ids])[:60]
            project_context['tasks_complete']=project_context.get('tasks_complete',False) and len(available)<=60
            project_context['selected_task_ids']=data.task_ids
            enrich_context(db,user,project.id,project_context)
            from app.ai_operator.models import OperatorRun
            project_context['execution_history']=[]
            from app.ai_agents.security import verify
            for r in db.query(OperatorRun).filter_by(user_id=user.id,project_id=project.id).order_by(OperatorRun.id.desc()).limit(5):
                try: verify(db,user,r.security_context,history=True)
                except HTTPException: continue
                project_context['execution_history'].append({'id':r.id,'status':r.status,'plan':r.plan,'result':r.result})
        for step in data.context:
            tool = check_tool(db, user, data.workspace_id, step, False)
            if not isinstance(step.record_id, (int, type(None))):
                raise HTTPException(422, 'Context needs existing record IDs')
            params = {**step.payload}
            if 'per_page' in tool.fields:
                params['per_page'] = min(int(params.get('per_page', 50)), 50)
            value = await api_call(request.app, header, 'GET', tool.path.format(record_id=step.record_id), params)
            if step.tool == 'pms.projects':
                value = [p for p in value if p.get('workspace_id') == data.workspace_id]
            from app.ai_agents.security import bounded_result
            context.append({'tool': step.tool, 'record_id': step.record_id, 'records': bounded_result(db,user,minimize(value)), 'limit': 50})
        if data.local_plan:
            plan = data.local_plan
        else:
            history=[]
            ancestor=parent
            for _ in range(6):
                if not ancestor:break
                history.append({'command':ancestor.command,'plan':ancestor.plan,'status':ancestor.status,'receipts':ancestor.receipts})
                previous_id=(ancestor.result or {}).get('request',{}).get('parent_run_id')
                ancestor=owned(db,user,previous_id) if previous_id else None
            outbound = AiDataRedactionService().redact_for_ai(user, 'CROSS', {
                'command': data.text, 'authorized_context': context, 'tools': [] if data.mode == 'summary' else catalog(), 'current_time': now().isoformat(),
                'project_context':project_context,'conversation_newest_first':history,'timezone':data.timezone,
                'current_local_date':datetime.now(ZoneInfo(data.timezone)).date().isoformat(),
                'pms_instructions':'Use pms.kickoff for complete projects/milestones/tasks/subtasks/blockers with draft keys pointing to earlier tasks. Use pms.task_plan for ALL existing-task tools including status, priority, assignee_user_ids, title, description, estimated_hours, story_points, schedule_task, move_to_sprint, add_dependency, add/update_checklist, add_comment. Resolve selected-task pronouns and collaborator names only from fresh context. Ask one focused question when ambiguous. pms.schedule deterministically uses calendar/dependencies; its start_date can be relative. Reuse project memory and prior collected facts. Do not repeat completed receipts. Playbooks, monitoring and rules are separate tools; an LLM cannot enable standing autonomy consent. Dates inside task/work-breakdown plans must be ISO. All changes remain drafts until approved.',
                'instructions': ('Summarize only the supplied minimized records. Distinguish empty samples from company-wide absence. State source limits. Return only the summary field, without actions, questions or invented facts.' if data.mode == 'summary' else 'Return summary grounded in supplied records, or a complete action plan. Ask question if any required field/ID is missing. Never invent IDs. Steps only use action tools; reads belong in selected context. For a summary return steps []. For missing information return question and steps []. A later step may reference a newly created record via {"$step":1,"field":"id"}. Never claim a draft was executed. No outbound messages, payroll changes, approvals of leave, posting financial entries or money movement.')})
            module = '+'.join(sorted({TOOLS[s.tool].module for s in data.context}|({'PMS'} if data.project_id else set()))) or 'CROSS'
            output_type = Summary if data.mode == 'summary' else Plan
            result = await run_in_threadpool(generate_json, db, user, config, prompt=json.dumps(outbound), schema=output_type.model_json_schema(),
                output_type=output_type, purpose='suite_summary' if data.mode == 'summary' else 'suite_plan', usage_scope=scope, module=module, suite_run_id=run.id)
            plan = Plan(summary=result['summary']) if data.mode == 'summary' else Plan.model_validate(result)
        snapshots = await preflight(request.app, header, db, user, data.workspace_id, plan, run)
        if plan.steps:
            request_log = db.query(OperatorApiLog).filter_by(suite_run_id=run.id).order_by(OperatorApiLog.id.desc()).first()
            if request_log:
                request_log.module = '+'.join(sorted({TOOLS[s.tool].module for s in plan.steps}))
        run.plan = plan.model_dump(mode='json', exclude_none=True)
        run.plan_hash = digest(run.plan)
        run.snapshots = snapshots
        run.status = 'needs_clarification' if plan.question else 'awaiting_approval' if plan.steps else 'answered'
        if plan.steps:
            approval = AiActionApproval(user_id=user.id, module='CROSS', action_type='EXECUTE_SUITE_OPERATOR_PLAN',
                proposed_action_json={'input': {'suite_run_id': run.id, 'plan_hash': run.plan_hash}, 'preview': run.plan},
                status='pending', execution_status='pending', idempotency_key=f'suite:{run.id}:{run.plan_hash}')
            db.add(approval)
            db.flush()
            run.approval_id = approval.id
            if parent and parent.status in ('awaiting_approval','needs_clarification'):
                parent.status='superseded'
                retire_drafts(db,parent)
                if parent.approval_id:
                    previous_approval=db.get(AiActionApproval,parent.approval_id)
                    if previous_approval and previous_approval.status=='pending':previous_approval.status='cancelled'
        AiAuditService(db).log(user=user, agent_id=None, module='CROSS', action='suite.plan',
            input_json={'suite_run_id': run.id, 'scope': scope}, output_json={'status': run.status}, status='success')
        db.commit()
    except HTTPException as exc:
        # Keep sanitized usage even for failed generation/domain validation.
        run.status = 'failed'
        run.error_code = f'AI_POLICY_HTTP_{exc.status_code}'[:80] if isinstance(exc.detail, str) else 'PLAN_VALIDATION_FAILED'
        retire_drafts(db,run)
        db.commit()
    return public(run)


@router.post('/runs/{ident}/approve')
def approve(ident: int, data: Approval, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = owned(db, user, ident, True)
    from app.ai_agents.security import verify
    sealed=db.get(AiActionApproval,run.approval_id)
    if sealed:verify(db,user,sealed.security_context,payload=sealed.proposed_action_json,confirmation=True)
    if run.plan_hash != data.plan_hash or digest(run.plan) != data.plan_hash:
        raise HTTPException(409, 'Plan changed; review the current draft')
    if run.status in ('queued', 'executing', 'waiting_pms', 'succeeded'):
        return public(run)
    if run.status != 'awaiting_approval':
        raise HTTPException(409, 'This plan is not awaiting approval')
    created = run.created_at.replace(tzinfo=timezone.utc) if run.created_at.tzinfo is None else run.created_at
    if now() - created > timedelta(minutes=30):
        raise HTTPException(409, 'Approval expired; prepare a fresh plan')
    for step in Plan.model_validate(run.plan).steps:
        check_tool(db, user, run.workspace_id, step, True)
    from app.ai_operator.models import OperatorRun, OperatorProposal
    for child in (run.snapshots or {}).get('pms_children',{}).values():
        nested=db.get(OperatorRun if child['kind']=='task' else OperatorProposal,child['id'])
        if not nested or nested.user_id!=user.id or nested.plan_hash!=child['plan_hash'] or nested.status!='awaiting_approval':
            raise HTTPException(409,'PMS preview changed; prepare a fresh plan')
    approval = db.get(AiActionApproval, run.approval_id)
    if not approval or approval.status != 'pending':
        raise HTTPException(409, 'Approval was withdrawn or changed; prepare a fresh plan')
    approval.status = 'approved'
    approval.approved_by = user.id
    approval.approved_at = now()
    approval.execution_status = 'queued'
    run.status = 'queued'
    AiAuditService(db).log(user=user, agent_id=None, module='CROSS', action='suite.approved',
        input_json={'suite_run_id': run.id, 'plan_hash': run.plan_hash}, output_json={'status': run.status}, status='success')
    db.commit()
    return public(run)


@router.post('/runs/{ident}/cancel')
async def cancel(ident: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = owned(db, user, ident, True)
    if run.status not in ('awaiting_approval', 'queued', 'executing', 'waiting_pms', 'paused'):
        raise HTTPException(409, 'This run cannot be cancelled')
    if run.status in ('waiting_pms','paused') and run.active_step:
        child=(run.snapshots or {}).get('pms_children',{}).get(str(run.active_step))
        if child and child['kind']=='task':
            from app.ai_operator.models import OperatorRun
            nested=db.get(OperatorRun,child['id'])
            if nested and nested.status=='succeeded':
                finish_step(db,run,run.active_step,'pms.task_plan',{'pms_run_id':nested.id,
                    'task_receipts':(nested.result or {}).get('receipts',[]),'manual':child.get('manual',[])})
            if nested and nested.status not in ('succeeded','failed','cancelled'):
                await api_call(request.app,request.headers.get('authorization',''),'POST',f'/ai-operator/runs/{nested.id}/cancel')
                db.refresh(nested)
            if nested:
                run.result={**(run.result or {}),'pms_progress':{'run_id':nested.id,'status':nested.status,'result':nested.result}}
        run.active_step=None
    run.status = 'cancelling' if run.active_step else 'cancelled'
    retire_drafts(db,run)
    approval = db.get(AiActionApproval, run.approval_id)
    if approval:
        approval.execution_status = run.status
        if run.status == 'cancelled':
            approval.status = 'cancelled'
    db.commit()
    return public(run)


@router.post('/runs/{ident}/resume')
async def resume(ident: int, data: Approval, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run=owned(db,user,ident,True)
    approval=db.get(AiActionApproval,run.approval_id)
    child=(run.snapshots or {}).get('pms_children',{}).get(str(run.active_step))
    if run.status!='paused' or run.plan_hash!=data.plan_hash or digest(run.plan)!=data.plan_hash or not approval or approval.status!='approved' or not child or child['kind']!='task':
        raise HTTPException(409,'Only an unchanged approved PMS checkpoint can resume')
    await api_call(request.app,request.headers.get('authorization',''),'POST',f'/ai-operator/runs/{child["id"]}/resume',{'plan_hash':child['plan_hash']})
    run.status='waiting_pms'
    run.error_code=None
    approval.execution_status=run.status
    db.commit()
    return public(run)


def finish_step(db,run,index,tool,response):
    receipt={'step':index,'tool':tool,'record_id':response.get('id') or response.get('invoice_id'),'status':'succeeded',
             **{k:v for k,v in response.items() if k in ('pms_run_id','task_receipts','manual','setup_proposal_id','setup_receipts')}}
    run.receipts=[*run.receipts,receipt]
    run.active_step=None
    run.lease_until=None
    run.status='cancelled' if run.status=='cancelling' else 'succeeded' if index==len(run.plan['steps']) else 'queued'
    approval=db.get(AiActionApproval,run.approval_id)
    approval.execution_status=run.status
    approval.execution_result_json={'success':run.status=='succeeded','receipts':run.receipts}
    if run.status=='succeeded':approval.executed_at=now()
    AiAuditService(db).log(user=db.get(User,run.user_id),agent_id=None,module=TOOLS[tool].module,action='suite.step.completed',
        input_json={'suite_run_id':run.id,'step':index,'tool':tool},output_json=receipt,status='success')


async def process_suite_batch(db, app, limit=10):
    processed = 0
    # Yield to the canonical PMS worker rather than waiting inside its own loop.
    from app.ai_operator.models import OperatorRun
    for waiting in db.query(SuiteRun).filter_by(status='waiting_pms').with_for_update(skip_locked=True).all():
        child=(waiting.snapshots or {}).get('pms_children',{}).get(str(waiting.active_step),{})
        nested=db.get(OperatorRun,child.get('id'))
        if not nested or nested.user_id!=waiting.user_id or nested.plan_hash!=child.get('plan_hash'):
            waiting.status,waiting.error_code='needs_reconciliation','PMS_CHILD_CHANGED'
        elif nested.status=='succeeded':
            finish_step(db,waiting,waiting.active_step,'pms.task_plan',{'pms_run_id':nested.id,
                'task_receipts':(nested.result or {}).get('receipts',[]),'manual':child.get('manual',[])})
        elif nested.status in ('paused','failed','cancelled','needs_reconciliation'):
            waiting.status='cancelled' if nested.status=='cancelled' else 'paused'
            waiting.error_code='PMS_'+nested.status.upper()
            waiting.result={**(waiting.result or {}),'pms_progress':{'run_id':nested.id,'status':nested.status,'result':nested.result}}
        approval=db.get(AiActionApproval,waiting.approval_id)
        if approval:approval.execution_status=waiting.status
    db.commit()
    # Never replay a write after a crashed/timed-out executor.
    for expired in db.query(SuiteRun).filter(SuiteRun.status.in_(['executing', 'cancelling']), SuiteRun.lease_until < now()).with_for_update(skip_locked=True).all():
        expired.status = 'needs_reconciliation'
        expired.error_code = 'IN_FLIGHT_OUTCOME_UNKNOWN'
        approval = db.get(AiActionApproval, expired.approval_id)
        if approval:
            approval.execution_status = expired.status
            approval.execution_error = expired.error_code
    db.commit()
    for _ in range(limit):
        run = db.query(SuiteRun).filter_by(status='queued').order_by(SuiteRun.id).with_for_update(skip_locked=True).first()
        if not run:
            break
        ident = run.id
        started = False
        try:
            user = db.get(User, run.user_id)
            if not user or not user.is_active:
                raise HTTPException(403, 'Initiator unavailable')
            from app.access.service import activate_run_context
            activate_run_context(db,user,run)
            authorize(db, user, run.workspace_id)
            from app.ai_agents.security import verify
            verify(db,user,run.security_context)
            approval = db.get(AiActionApproval, run.approval_id)
            if not approval or approval.status != 'approved' or approval.approved_by != user.id or digest(run.plan) != run.plan_hash:
                raise HTTPException(409, 'Approval is unavailable or changed')
            verify(db,user,approval.security_context,payload=approval.proposed_action_json,confirmation=True)
            approved_input = (approval.proposed_action_json or {}).get('input', {})
            if approved_input.get('plan_hash') != run.plan_hash or approved_input.get('suite_run_id') != run.id:
                raise HTTPException(409, 'Approval hash changed')
            from app.ai_agents.security import execution_budget
            execution_budget(db,user,run)
            plan = Plan.model_validate(run.plan)
            index = len(run.receipts) + 1
            step = plan.steps[index-1]
            tool = check_tool(db, user, run.workspace_id, step, True)
            record_id = references(step.record_id, index, plan.steps, run.receipts)
            payload = references(step.payload, index, plan.steps, run.receipts)
            validate_payload(tool, payload)
            if step.tool == 'pms.create_task':
                from app.apps.project_management.access import get_project_for_action
                project = get_project_for_action(db, record_id, user, 'manage_tasks')
                if project.workspace_id != run.workspace_id:
                    raise HTTPException(403, 'PMS project workspace changed')
            if step.tool == 'pms.create_project':
                payload['workspace_id'] = run.workspace_id
            authorization = 'Bearer ' + create_access_token(str(user.id), expires_delta=timedelta(minutes=5), session_id=run.session_id,ai_origin={'company_id':user.organization_id})
            if tool.guard and str(index) in run.snapshots:
                current = await api_call(app, authorization, 'GET', tool.guard.format(record_id=record_id))
                if digest(current) != run.snapshots[str(index)]:
                    raise HTTPException(409, 'Target changed since preview')
            run.status = 'executing'
            run.active_step = index
            run.lease_until = now() + timedelta(minutes=5)
            db.commit()
            started = True
            # The canonical router verifies the original session, role, tenancy,
            # module access and business rules immediately before its own write.
            if step.tool == 'srm.draft_invoice':
                from uuid import uuid5, NAMESPACE_URL
                payload['request_id'] = str(uuid5(NAMESPACE_URL, f'suite:{ident}:{index}'))
            if tool.project_target:
                from app.ai_operator.pms_agent import execute_step
                response=await execute_step(app,authorization,step,(run.snapshots or {}).get('pms_children',{}).get(str(index)),api_call)
            else:
                response = await api_call(app, authorization, tool.method, tool.path.format(record_id=record_id), payload)
            run = db.query(SuiteRun).filter_by(id=ident).with_for_update().populate_existing().one()
            if run.active_step != index or run.status not in ('executing', 'cancelling'):
                raise HTTPException(409, 'Executor lost its claim')
            if response.get('waiting_pms'):
                if run.status=='cancelling':
                    await api_call(app,authorization,'POST',f'/ai-operator/runs/{response["pms_run_id"]}/cancel')
                    nested=db.get(OperatorRun,response['pms_run_id'])
                    if nested:
                        db.refresh(nested)
                        run.result={**(run.result or {}),'pms_progress':{'run_id':nested.id,'status':nested.status,'result':nested.result}}
                    run.status='cancelled'
                    run.active_step=None
                    run.lease_until=None
                    db.get(AiActionApproval,run.approval_id).execution_status=run.status
                    db.commit()
                    processed+=1
                    continue
                run.status='waiting_pms'
                run.lease_until=None
                db.get(AiActionApproval,run.approval_id).execution_status=run.status
                db.commit()
                processed+=1
                continue
            finish_step(db,run,index,step.tool,response)
            db.commit()
        except Exception as exc:
            # Logical/API failures do not invalidate this session's transaction.
            # Canonical steps have already committed independently. Roll back
            # only a failed SQL transaction before recording reconciliation.
            if not db.is_active:
                db.rollback()
            run = db.query(SuiteRun).filter_by(id=ident).with_for_update().populate_existing().one()
            run.status = 'needs_reconciliation' if started else 'paused'
            run.error_code = f'CANONICAL_STEP_{exc.status_code}' if isinstance(exc, HTTPException) else 'SUITE_STEP_FAILED'
            approval = db.get(AiActionApproval, run.approval_id)
            if approval:
                approval.execution_status = run.status
                approval.execution_error = run.error_code
            db.commit()
        finally:
            from app.access.service import release_run_context
            release_run_context(db)
        processed += 1
    return processed
