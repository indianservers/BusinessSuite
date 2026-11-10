"""Read-only operational views composed from canonical, currently authorized APIs."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.ai_operator.suite_tools import Strict
from app.ai_operator.evidence import records
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

router = APIRouter(prefix='/suite/operations', tags=['Suite operations'])


class OutcomeReview(Strict):
    suite_run_id: int = Field(gt=0)
    supported: bool
    correct: bool


@router.post('/reviews')
def review(data: OutcomeReview, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_operator.suite import owned
    from app.ai_operator.workbench import access as project_access
    from app.ai_operator.workbench_models import AssistantSignal
    from app.ai_operator.models import OperatorApiLog
    run = owned(db,user,data.suite_run_id,True)
    project_id = (run.result or {}).get('request',{}).get('project_id')
    if not project_id or run.status not in {'answered','awaiting_approval','succeeded'}:
        raise HTTPException(422,'Review a completed answer or validated plan with an original project context')
    from app.ai_agents.security import scoped
    access(db,user,run.workspace_id)
    with scoped(db,user,'project_management'):
        project_access(db,user,project_id)
    if not db.query(OperatorApiLog).filter_by(suite_run_id=run.id,user_id=user.id,status='success').first():
        raise HTTPException(422,'Only successful cloud outcomes contribute model ratings')
    key = f'suite-review-v1:{run.id}'
    row = db.query(AssistantSignal).filter_by(user_id=user.id,request_key=key).with_for_update().first()
    body = {**data.model_dump(), 'version':1, 'basis':'Owner assessment; not independent factual verification'}
    if row: row.details=body
    else: db.add(AssistantSignal(user_id=user.id,project_id=project_id,request_key=key,kind='suite_quality_v1',details=body))
    db.commit()
    return private_result(db,user,{'recorded':True,'basis':body['basis']})


@router.get('/routing')
def routing(project_id: int = Query(gt=0), workspace_id: int | None = Query(None,gt=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_operator.routing import measurements
    from app.apps.project_management.access import get_project_for_action
    from app.ai_agents.security import scoped
    access(db,user,workspace_id)
    with scoped(db,user,'project_management'):
        if get_project_for_action(db,project_id,user,'browse').workspace_id != workspace_id:
            raise HTTPException(422,'Choose the original workspace')
    return private_result(db,user,{'version':1,'items':measurements(db,user,workspace_id,project_id),
        'policy':'Opt-in measured routing requires at least 3 owner-rated successes and 80% review pass and technical success. Rechecks current provider configuration and circuit state.'})


def private_result(db, user, value):
    from app.ai_agents.security import bounded_result
    result = bounded_result(db, user, jsonable_encoder(value))
    if result.get('truncated'):
        raise HTTPException(413, 'Operational view exceeds the disclosure budget; narrow the project or source scope')
    return JSONResponse(result, headers={'Cache-Control': 'no-store'})


def access(db, user, workspace_id, module='PMS'):
    from app.ai_operator.suite import authorize, MODULES
    from app.access.service import check_background_access
    scope = authorize(db, user, workspace_id, module)
    check_background_access(db, user, MODULES[module], 'view')
    return scope


def source(kind, ident, label, retrieved_at, project_id):
    href = {'project': f'/pms/projects/{project_id}', 'task': f'/pms/tasks/{ident}',
            'customer': '/crm/companies', 'deal': '/crm/deals', 'invoice': '/srm/invoices'}[kind]
    return {'id': f'{kind}:{ident}', 'record_id': ident, 'label': str(label)[:220],
            'href': href, 'retrieved_at': retrieved_at}


@router.get('/delivery')
async def delivery(request: Request, project_id: int = Query(gt=0), workspace_id: int | None = Query(None, gt=0),
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_operator.suite import check_tool, Step, api_call, now
    from app.ai_agents.api import _require_ai_rate_limit
    from app.ai_agents.security import limits, company
    from app.ai_operator.briefing import DONE, local_date
    from app.apps.project_management.access import get_project_for_action
    from app.ai_agents.security import scoped
    access(db, user, workspace_id)
    _require_ai_rate_limit(db, request, user, bucket='suite_operations')
    with scoped(db, user, 'project_management'):
        project = get_project_for_action(db, project_id, user, 'browse')
        if project.workspace_id != workspace_id:
            raise HTTPException(422, 'Choose a project in the selected workspace')
        project_name = project.name
    at = now().isoformat()
    budget = min(8, limits(db, company(user))['max_calls'])
    coverage, calls = [], 0

    async def read(name, path, module, params=None):
        nonlocal calls
        if calls >= budget:
            coverage.append({'source': name, 'status': 'budget_limited'}); return None
        calls += 1
        try:
            access(db, user, workspace_id, module)
            if name == 'deal':
                check_tool(db, user, workspace_id, Step(tool='crm.deal', record_id=deal_id), False)
            value = await api_call(request.app, request.headers.get('authorization', ''), 'GET', path, params or {})
            coverage.append({'source': name, 'status': 'available', 'retrieved_at': at})
            return value
        except HTTPException as exc:
            coverage.append({'source': name, 'status': 'unavailable', 'code': exc.status_code})
            return None

    # Validate the independent allowlist before invoking the existing task adapter.
    tool = check_tool(db, user, workspace_id, Step(tool='pms.tasks', record_id=project_id), False)
    task_data = await read('tasks', tool.path.format(record_id=project_id), 'PMS', {'limit': 50})
    task_rows = records(task_data)[:50]
    # The canonical billing endpoint enforces project, finance and invoice-row visibility.
    billing = await read('commercial', f'/srm/projects/{project_id}/billing', 'SRM')
    billing = billing if isinstance(billing, dict) else {}
    commercial = billing.get('commercial') or {}
    customer_id, deal_id = commercial.get('customer_id'), commercial.get('opportunity_id')
    customer = deal = None
    if type(customer_id) is int:
        customer = await read('customer', f'/crm/companies/{customer_id}', 'CRM')
    if type(deal_id) is int:
        deal = await read('deal', f'/crm/deals/{deal_id}', 'CRM')
    nodes = [{'kind': 'project', 'id': project_id, 'label': project_name,
              'source': source('project', project_id, project_name, at, project_id)}]
    edges, gaps = [], []
    for kind, row, ident in [('customer', customer, customer_id), ('deal', deal, deal_id)]:
        if isinstance(row, dict) and row.get('id') == ident:
            label = row.get('name') or row.get('title') or f'{kind} {ident}'
            nodes.append({'kind': kind, 'id': ident, 'label': label, 'source': source(kind, ident, label, at, project_id)})
            edges.append({'from': f'{kind}:{ident}', 'to': f'project:{project_id}', 'basis': 'ProjectCommercial.' + ('customer_id' if kind == 'customer' else 'opportunity_id')})
        else:
            gaps.append(f'{kind.capitalize()} link missing or unavailable under current access')
    signals = []
    today = now().date()
    for row in task_rows:
        if str(row.get('status', '')).lower() in DONE:
            continue
        due = local_date(row.get('due_date'), 'UTC')
        if str(row.get('status', '')).lower() == 'blocked' or due and due < today:
            signals.append({'reason': 'Blocked' if str(row.get('status', '')).lower() == 'blocked' else 'Overdue',
                            'source': source('task', row['id'], row.get('title') or 'Task', at, project_id)})
    invoices = records(billing.get('invoices', []))[:200]
    amounts = defaultdict(lambda: Decimal('0'))
    for row in invoices:
        ident = row.get('id')
        if type(ident) is not int:
            continue
        label = row.get('invoice_number') or f'Invoice {ident}'
        nodes.append({'kind': 'invoice', 'id': ident, 'label': label, 'status': row.get('status'),
                      'source': source('invoice', ident, label, at, project_id)})
        edges.append({'from': f'project:{project_id}', 'to': f'invoice:{ident}', 'basis': 'Canonical project billing relation'})
        currency = row.get('currency')
        try:
            amount = Decimal(str(row.get('total_amount')))
            if currency and amount.is_finite(): amounts[currency] += amount
        except (ValueError, ArithmeticError):
            gaps.append(f'Invoice {ident} has no usable amount')
    return private_result(db, user, {'nodes': nodes, 'edges': edges, 'delivery_signals': signals, 'gaps': gaps,
            'invoice_totals': [{'currency': key, 'amount': format(value, '.2f')} for key, value in sorted(amounts.items())],
            'coverage': coverage, 'retrieved_at': at, 'task_sample_size': len(task_rows),
            'task_coverage': 'bounded_sample', 'invoice_coverage': 'bounded_to_200',
            'note': 'Explicit commercial links only. Risk signals describe visible tasks; they do not predict revenue loss. Amounts are sampled invoice face values, not receivables.'})


class CapacityScenario(Strict):
    workspace_id: int | None = Field(default=None, gt=0)
    project_id: int = Field(gt=0)
    week_start: date = Field(ge=date(1970,1,1), le=date(2100,12,31))
    additional_hours: dict[int, float] = Field(default_factory=dict, max_length=10)
    required_skills: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def bounded(self):
        import math
        if any(uid <= 0 or not math.isfinite(hours) or hours < 0 or hours > 168 for uid, hours in self.additional_hours.items()):
            raise ValueError('Use actual people and 0–168 additional hours')
        if any(not skill.strip() or len(skill) > 80 for skill in self.required_skills):
            raise ValueError('Use up to 20 nonempty skill labels, each at most 80 characters')
        return self


@router.post('/capacity-scenario')
async def scenario(data: CapacityScenario, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_operator.suite import api_call, now
    from app.ai_agents.api import _require_ai_rate_limit
    from app.ai_agents.security import limits, company
    access(db, user, data.workspace_id)
    _require_ai_rate_limit(db, request, user, bucket='suite_operations')
    from app.apps.project_management.access import get_project_for_action
    from app.ai_agents.security import scoped
    with scoped(db, user, 'project_management'):
        project = get_project_for_action(db, data.project_id, user, 'manage_tasks')
        if project.workspace_id != data.workspace_id:
            raise HTTPException(422, 'Project must match the selected workspace')
        from app.ai_operator.workbench import policy_for
        policy = policy_for(db,user,data.project_id)
        from app.apps.project_management.models import PMSTask, PMSTaskDependency
        tasks = db.query(PMSTask).filter_by(project_id=data.project_id,deleted_at=None).order_by(PMSTask.id).limit(501).all()
        by_id = {task.id:task for task in tasks[:500]}
        edges = db.query(PMSTaskDependency).filter(PMSTaskDependency.task_id.in_(by_id),PMSTaskDependency.depends_on_task_id.in_(by_id)).order_by(PMSTaskDependency.id).limit(501).all()
        conflicts, unknown = [], 0
        for edge in edges[:500]:
            parent, child = by_id[edge.depends_on_task_id], by_id[edge.task_id]
            kind = edge.dependency_type or 'Finish To Start'
            anchor = parent.due_date if kind.startswith('Finish') else parent.start_date
            target = child.start_date if kind.endswith('Start') else child.due_date
            if not anchor or not target:
                unknown += 1
            elif (target-anchor).days < (edge.lag_days or 0)+(1 if kind=='Finish To Start' else 0):
                conflicts.append({'source_task_id':parent.id,'target_task_id':child.id,'relationship':kind,'lag_days':edge.lag_days or 0})
    # Existing assistant capacity validates project membership and visible workload.
    baseline = await api_call(request.app, request.headers.get('authorization', ''), 'GET', '/ai-operator/capacity',
                              {'project_id': data.project_id, 'week_start': data.week_start.isoformat()})
    people = baseline.get('items', [])
    if set(data.additional_hours) - {p['user_id'] for p in people}:
        raise HTTPException(422, 'Scenario people must be authorized project collaborators')
    start = data.week_start - timedelta(days=data.week_start.weekday())
    result = []
    budget = max(0, min(10, limits(db, company(user))['max_calls'] - 1))
    for person in people[:budget]:
        uid = person['user_id']
        entry = {'user_id': uid, 'allocated_hours': person['allocated_hours'], 'unscheduled_tasks': person['unscheduled_tasks'],
                 'additional_hours': data.additional_hours.get(uid, 0), 'available_hours': None, 'overload_hours': None, 'status': 'unavailable'}
        skills = policy.skills.get(str(uid),[])
        entry.update(skills=skills, missing_skills=sorted(set(skill.strip().casefold() for skill in data.required_skills)-{skill.casefold() for skill in skills}),
                     skills_basis='Owner-maintained project policy; not independently verified', policy_away=uid in policy.away_user_ids)
        try:
            native = await api_call(request.app, request.headers.get('authorization', ''), 'GET', '/project-management/management/capacity',
                                    {'user_id': uid, 'start': start.isoformat(), 'end': (start + timedelta(days=6)).isoformat()})
            available = 0 if entry['policy_away'] else native['capacity_hours']
            entry.update(available_hours=available, overload_hours=round(max(0, person['allocated_hours'] + entry['additional_hours'] - available), 2), status='available')
        except HTTPException:
            pass
        result.append(entry)
    return private_result(db, user, {'week_start': start, 'items': result, 'omitted_people': max(0, len(people) - len(result)), 'workload_partial': baseline.get('workload_partial', True), 'retrieved_at': now().isoformat(),
            'projection': True, 'writes': False,
            'dependency_conflicts': conflicts[:25], 'unknown_dependencies': unknown,
            'dependency_coverage': 'bounded_to_500_tasks_and_edges', 'dependency_partial': len(tasks)>500 or len(edges)>500,
            'assumptions': ['Native working schedules, weekly overrides, applicable holidays and approved leave determine availability.',
                            'Visible open estimates are spread over weekdays and assignees; hidden workload and missing estimates are excluded.',
                            'Additional hours and maintained skill/away policy are user assumptions. Dependency checks compare existing dates and lags only; hidden or unsampled relationships are excluded. No reassignment or scheduling occurs.']})


@router.get('/health')
def health(workspace_id: int | None = Query(None, gt=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_operator.suite import authorize, now
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_operator.models import OperatorApiLog
    from app.ai_agents.security import verify
    scope = authorize(db, user, workspace_id)
    rows = db.query(SuiteRun).filter_by(user_id=user.id, scope_key=scope).order_by(SuiteRun.id.desc()).limit(201).all()
    visible = []
    for row in rows[:200]:
        try:
            verify(db, user, row.security_context, history=True)
            visible.append(row)
        except HTTPException:
            pass
    logs = db.query(OperatorApiLog).filter_by(user_id=user.id, scope_key=scope).filter(
        OperatorApiLog.suite_run_id.in_([r.id for r in visible]),
        OperatorApiLog.created_at >= now() - timedelta(days=30)).order_by(OperatorApiLog.id.desc()).limit(501).all()
    groups = defaultdict(list)
    for log in logs[:500]: groups[(log.provider, log.model)].append(log)
    providers = []
    for (provider, model), group in groups.items():
        priced = [r for r in group if r.estimated_cost is not None]
        providers.append({'provider': provider, 'model': model, 'calls': len(group), 'successes': sum(r.status == 'success' for r in group),
                          'failures': sum(r.status != 'success' for r in group), 'mean_duration_ms': round(sum(r.duration_ms for r in group) / len(group)),
                          'priced_calls': len(priced), 'known_cost': str(sum((r.estimated_cost for r in priced), Decimal(0))),
                          'input_tokens': sum(r.input_tokens or 0 for r in group), 'output_tokens': sum(r.output_tokens or 0 for r in group),
                          'missing_usage_calls': sum(r.input_tokens is None or r.output_tokens is None for r in group),
                          'quality': 'not_evaluated'})
    return private_result(db, user, {'retrieved_at': now().isoformat(), 'scope': 'Current owner, company, branch and workspace', 'run_counts': dict(Counter(r.status for r in visible)),
            'attention': [{'id': r.id, 'status': r.status, 'error_code': r.error_code, 'receipt_count': len(r.receipts or [])} for r in visible if r.status in {'partial', 'failed', 'paused', 'needs_reconciliation', 'reconciliation_required'}],
            'providers': providers, 'partial': len(rows) > 200 or len(logs) > 500,
            'policy_denials': sum(r.error_code in {'AI_POLICY_HTTP_403','AI_POLICY_HTTP_401'} for r in visible),
            'note': 'Bounded owner telemetry. Availability and known cost are measured; reasoning quality and competitor superiority are not established. Missing costs are not zero.'})
