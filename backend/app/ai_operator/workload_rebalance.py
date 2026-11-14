"""Server-side assignment recommendations; execution remains a reviewed task plan."""
from collections import defaultdict
from datetime import date, timedelta
from typing import Literal
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field

from app.core.deps import get_db, get_current_user
from app.ai_operator.workload_intelligence import Read, no_store

router = APIRouter(prefix='/suite/pms', tags=['Reviewed workload planning'],
                   dependencies=[Depends(no_store)])


class Rebalance(Read):
    task_ids: list[int] = Field(min_length=1, max_length=25)
    candidate_user_ids: list[int] = Field(min_length=1, max_length=25)


@router.get('/workload/{project_id}/rebalance')
def read_rebalance(project_id:int, start:date, task_ids:list[int]=Query(...,min_length=1,max_length=25),
                   candidate_user_ids:list[int]=Query(...,min_length=1,max_length=25),
                   weeks:int=Query(1,ge=1,le=4), scope:Literal['project','workspace']='project',
                   db=Depends(get_db), user=Depends(get_current_user)):
    try:data=Rebalance(start=start,task_ids=task_ids,candidate_user_ids=candidate_user_ids,weeks=weeks,scope=scope)
    except ValueError:raise HTTPException(422,'Choose a Monday, one to four weeks, selected tasks and eligible candidates') from None
    return rebalance(project_id,data,db,user)


def recommend(native, tasks, candidates):
    """Greedy whole-task moves that reduce overage without overloading a recipient.

    Keep every other assignee and all task dates unchanged. Estimates are taken
    from canonical per-assignee/week cells rather than reimplemented hour rules.
    """
    loads, capacities, shares = {}, {}, defaultdict(dict)
    for row in native['rows']:
        uid = row['user_id']
        for cell in row['cells']:
            week = str(cell['week_start'])
            loads[uid, week] = cell['planned_hours']
            capacities[uid, week] = cell['capacity_hours']
            for item in cell['tasks']:
                shares[item['id']][uid, week] = item['planned_hours']
    steps, changes, skipped = [], [], []
    for task in sorted(tasks, key=lambda t: t.id):
        owners = sorted(set(task.assignee_user_ids or []))
        options = []
        for source in owners:
            effort = {week: hours for (uid, week), hours in shares[task.id].items()
                      if uid == source and hours > 0}
            if not effort:
                continue
            for target in sorted(set(candidates) - set(owners)):
                if any((target, week) not in capacities or
                       loads[target, week] + hours > capacities[target, week] + 0.001
                       for week, hours in effort.items()):
                    continue
                reduction = sum(min(hours, max(0, loads[source, week] - capacities[source, week]))
                                for week, hours in effort.items())
                if reduction <= 0:
                    continue
                peak = max((loads[target, week] + hours) / max(capacities[target, week], 0.001)
                           for week, hours in effort.items())
                options.append((-reduction, peak, source, target, effort))
        if not options:
            skipped.append({'task_id': task.id, 'reason': 'No whole-task move reduces overload within the selected candidates and visible weekly headroom.'})
            continue
        _, _, source, target, effort = min(options, key=lambda value: value[:4])
        after = sorted((set(owners) - {source}) | {target})
        weeks = []
        for week, hours in effort.items():
            weeks.append({'week_start': week, 'moved_hours': hours,
                          'source_before_hours': loads[source, week],
                          'source_after_hours': round(loads[source, week] - hours, 2),
                          'target_before_hours': loads[target, week],
                          'target_after_hours': round(loads[target, week] + hours, 2),
                          'target_snapshot_capacity_hours': capacities[target, week]})
            loads[source, week] = round(loads[source, week] - hours, 2)
            loads[target, week] = round(loads[target, week] + hours, 2)
        steps.append({'tool': 'update_task', 'task_id': task.id,
                      'changes': {'assignee_user_ids': after}})
        changes.append({'task_id': task.id, 'before_assignee_user_ids': owners,
                        'after_assignee_user_ids': after, 'weeks': weeks})
    return steps, changes, skipped


@router.post('/workload/{project_id}/rebalance')
def rebalance(project_id: int, data: Rebalance, db=Depends(get_db), user=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    from app.apps.project_management.access import get_project_for_action, get_task_project_for_action
    from app.apps.project_management.api.router import get_workload_heatmap, _sync_task_planning_links
    from app.ai_operator.workload_guard import issue
    authorize(db, user, None, 'PMS')
    project = get_project_for_action(db, project_id, user, 'manage_tasks')
    if data.after_user_id or data.assignee_user_id is not None:
        raise HTTPException(422, 'Rebalance requires a full workload source without person paging')
    if data.scope == 'workspace' and not project.workspace_id:
        raise HTTPException(422, 'Workspace workload requires a workspace project')
    candidates = sorted(set(data.candidate_user_ids))
    # Canonical validation only normalizes this detached dict; it performs no writes.
    for uid in candidates:
        _sync_task_planning_links(db, project_id, {'assignee_user_ids': [uid]}, user)
    tasks = []
    for tid in sorted(set(data.task_ids)):
        task, parent = get_task_project_for_action(db, tid, user, 'manage_tasks')
        if parent.id != project_id:
            raise HTTPException(422, 'Choose tasks from the selected project')
        tasks.append(task)
    native = get_workload_heatmap(projectId=project_id if data.scope == 'project' else None,
        workspace_id=project.workspace_id if data.scope == 'workspace' else None,
        teamId=None, sprintId=None, from_date=data.start,
        to=data.start + timedelta(weeks=data.weeks-1), basis='hours', db=db, current_user=user)
    steps, changes, skipped = recommend(native, tasks, candidates)
    return {'project_id': project_id, 'mode': 'atomic',
            'workload_guard': issue(project_id, data.start, data.weeks, data.scope, native),
            'plan': {'summary': 'Review proposed workload assignment changes', 'steps': steps} if steps else None,
            'changes': changes, 'skipped': skipped, 'requires_review': True,
            'limitations': [
                'Greedy estimate, not an optimal schedule, skill match, employee performance rating or capacity reservation.',
                'Only selected tasks move; other assignees, dates and dependencies remain unchanged.',
                'Visible authorized workload only; unassigned and out-of-window work are excluded.',
                'Projected hours use native even-split estimates. Hours-based capacity uses personal working hours, dated overrides, holidays and approved leave; it is not the sprint budget.',
                'Submit a nonempty plan, mode and workload_guard through the existing reviewed task-plan workflow; this endpoint performs no writes.']}


def prepare(db, user, data, parent):
    """Local conversation adapter; missing inputs stay in the server run history."""
    from app.ai_operator.suite import Plan
    from app.apps.project_management.access import get_project_for_action
    text = re.sub(r'(?i)^\s*PMS\s*:\s*', '', data.text).strip()
    natural = re.fullmatch(r'(?is)(?:rebalance|balance)\s+(?:the\s+)?(?:team\s+)?workload\s+with\s+([^;:]+)', text)
    if natural:
        text = 'Rebalance workload: candidates=' + re.sub(r'\s+and\s+', ',', natural[1], flags=re.I)
    initial = re.fullmatch(r'(?is)(?:rebalance|balance)\s+(?:the\s+)?(?:team\s+)?workload(?:\s*:\s*(.*))?', text)
    previous = (parent.result or {}).get('rebalance_request') if parent else None
    if previous and parent.status=='needs_clarification' and 'timezone' not in data.model_fields_set:
        data.timezone=(parent.result or {}).get('request',{}).get('timezone',data.timezone)
    if not initial and previous and parent.status=='needs_clarification' and '=' not in text and ';' not in text:
        awaiting = previous.get('_awaiting')
        if awaiting in {'tasks','candidates'} and len(text)<=220 and not re.match(r'(?i)^(?:show|check|create|delete|cancel|stop|start|new|forget|switch)\b',text):
            value = re.sub(r'(?i)^(?:use|choose|select)\s+', '', text).strip()
            if awaiting=='candidates':value=re.sub(r'\s+and\s+', ',', value, flags=re.I)
            if value:text=awaiting+'='+value
        elif awaiting=='project' and re.fullmatch(r'(?i)(?:project\s*#?\s*)?\d+',text):
            text='project='+re.search(r'\d+',text)[0]
        elif awaiting=='start':
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}',text):text='start='+text
            elif text.casefold() in {'this week','next week','this monday','next monday'}:
                from datetime import datetime
                from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
                try:today=datetime.now(ZoneInfo(data.timezone)).date()
                except (ZoneInfoNotFoundError, ValueError):raise HTTPException(422, 'Choose a valid timezone') from None
                monday=today-timedelta(days=today.weekday())
                text='start='+(monday+timedelta(weeks=1 if text.casefold().startswith('next') else 0)).isoformat()
    follow = bool(previous and re.match(r'(?i)^(?:project|tasks|candidates|start|weeks|scope)=', text))
    if not initial and not follow:
        return None, None
    if data.module not in (None, 'PMS') and not re.match(r'(?i)^\s*PMS\s*:', data.text):
        return None, None
    if parent and parent.status == 'awaiting_approval':
        raise HTTPException(409, 'Finish or cancel the pending action before changing the rebalance request')
    data.module = 'PMS'
    draft = dict(previous) if follow else {
        'project_id': data.project_id, 'task_ids': list(data.task_ids or []),
        'candidate_user_ids': [], 'weeks': 1, 'scope': 'workspace' if data.workspace_id else 'project'}
    draft.pop('review', None)

    def ask(question, awaiting=None):
        if awaiting:draft['_awaiting']=awaiting
        return Plan(summary='Clarify the workload rebalance request.', question=question, steps=[]), draft

    for part in ((initial[1] or '') if initial else text).split(';'):
        if not part.strip():
            continue
        key, sep, value = part.strip().partition('=')
        if not sep or key not in {'project', 'tasks', 'candidates', 'start', 'weeks', 'scope'}:
            return ask('Use project=ID; tasks=ID,ID; candidates=ID,ID; start=YYYY-MM-DD (Monday); weeks=1..4; scope=project or workspace.')
        try:
            if key in {'tasks', 'candidates'}:
                if not re.fullmatch(r'\s*\d+(?:\s*,\s*\d+)*\s*', value):
                    labels = [item.strip() for item in value.split(',')]
                    if len(labels)>25 or any(not item or len(item)>(120 if key=='candidates' else 220) for item in labels):
                        raise ValueError()
                    draft['candidate_labels' if key=='candidates' else 'task_labels'] = labels
                    draft['candidate_user_ids' if key=='candidates' else 'task_ids'] = []
                    continue
                ids = [int(item.strip()) for item in value.split(',')]
                if not ids or len(ids)>25 or any(item <= 0 for item in ids):
                    raise ValueError()
                draft['task_ids' if key == 'tasks' else 'candidate_user_ids'] = sorted(set(ids))
                if key == 'candidates':draft.pop('candidate_labels', None)
                if key == 'tasks':draft.pop('task_labels', None)
            else:
                draft[{'project':'project_id'}.get(key,key)] = int(value) if key in {'project','weeks'} else value.strip()
        except ValueError:
            return ask('Use positive record IDs and at most 25 tasks or candidate users.')
    if not draft.get('project_id'):
        return ask('Which project should I rebalance? Reply project=ID.', 'project')
    project = get_project_for_action(db, draft['project_id'], user, 'manage_tasks')
    if project.workspace_id != data.workspace_id:
        raise HTTPException(409, 'Choose a project in the current conversation workspace')
    # Freeze each resolved selection in the normal request context even while
    # collecting other fields, so later clarification cannot switch targets.
    data.project_id = project.id
    if draft.get('task_labels'):
        ids, question = resolve_tasks(db, user, project, draft['task_labels'])
        if question:return ask(question, 'tasks')
        draft['task_ids'] = ids
    if draft.get('task_ids'):
        data.task_ids = sorted(set(draft['task_ids']))
    if draft.get('candidate_labels'):
        ids, question = resolve_candidates(db, user, project, draft['candidate_labels'])
        if question:return ask(question, 'candidates')
        draft['candidate_user_ids'] = ids
    if not draft.get('task_ids'):
        return ask('Which tasks may I move? Reply with a title, task key or tasks=ID,ID.', 'tasks')
    if not draft.get('candidate_user_ids'):
        return ask('Which collaborators may receive work? Reply with a name or candidates=ID,ID.', 'candidates')
    if not draft.get('start'):
        return ask('Which Monday should the workload check start? Reply with a date, this week or next week; optionally weeks=1..4.', 'start')
    try:
        inputs = Rebalance.model_validate({k:v for k,v in draft.items() if k not in {'project_id','candidate_labels','task_labels','_awaiting'}})
    except ValueError:
        return ask('Choose a Monday start date, one to four weeks, and scope=project or workspace.', 'start')
    data.project_id = project.id
    data.task_ids = list(inputs.task_ids)
    draft.pop('_awaiting', None)
    proposal = rebalance(project.id, inputs, db, user)
    if not proposal['plan']:
        return Plan(summary='No whole-task reassignment reduces overload within these candidates and the visible weekly capacity. No assignments changed.', steps=[]), draft
    draft['review'] = {'project_id':project.id, 'source_sha256':proposal['workload_guard']['source_sha256'],
                       'changes':proposal['changes'], 'limitations':proposal['limitations'][:4]}
    return Plan(summary=f'Review {len(proposal["changes"])} proposed assignment changes based on estimated workload; no assignments have changed yet.',
        steps=[{'tool':'pms.task_plan', 'record_id':project.id, 'payload':{
            'plan':proposal['plan'], 'mode':'atomic', 'workload_guard':proposal['workload_guard']}}]), draft


def resolve_candidates(db, actor, project, labels):
    from app.apps.project_management.api.router import _project_user_query, _user_display_name, _sync_task_planning_links
    from app.models.user import User
    people = _project_user_query(db, project).order_by(User.id).limit(201).all()
    if len(people)>200:
        return [], 'This project has many collaborators. Please choose candidates by user ID.'
    eligible = []
    for person in people:
        try:
            _sync_task_planning_links(db, project.id, {'assignee_user_ids':[person.id]}, actor)
        except HTTPException as exc:
            if exc.status_code != 422:raise
            continue
        eligible.append(person)
    chosen = []
    for label in labels:
        normalized = ' '.join(label.casefold().split())
        exact = [person for person in eligible if ' '.join((_user_display_name(person) or '').casefold().split()) == normalized]
        matches = exact or [person for person in eligible if (_user_display_name(person) or '').casefold().startswith(normalized+' ')]
        if len(matches)!=1:
            choices = ', '.join(str(person.id) for person in matches[:10])
            return [], ('More than one eligible collaborator matches. Reply candidates=ID,ID. Matching user IDs: '+choices
                        if matches else 'No eligible project collaborator matches that name. Reply candidates=Name or candidates=ID.')
        chosen.append(matches[0].id)
    return sorted(set(chosen)), None


def resolve_tasks(db, actor, project, labels):
    from app.apps.project_management.models import PMSTask
    from app.apps.project_management.access import get_task_project_for_action
    tasks = db.query(PMSTask).filter(PMSTask.project_id==project.id,
        PMSTask.deleted_at.is_(None)).order_by(PMSTask.id).limit(201).all()
    if len(tasks)>200:
        return [], 'This project has many tasks. Please choose tasks by record ID.'
    chosen = []
    normalize = lambda text: ' '.join((text or '').casefold().split())
    for label in labels:
        matches = [task for task in tasks if normalize(label) in {normalize(task.title), normalize(task.task_key)}]
        if len(matches)!=1:
            choices = ', '.join(str(task.id) for task in matches[:10])
            return [], ('More than one project task matches. Reply tasks=ID,ID. Matching task IDs: '+choices
                        if matches else 'No current task in this project matches that title or key. Reply tasks=Title or tasks=ID.')
        task, parent = get_task_project_for_action(db, matches[0].id, actor, 'manage_tasks')
        if parent.id != project.id:raise HTTPException(409, 'Task project changed')
        chosen.append(task.id)
    return sorted(set(chosen)), None


def enforce_source_guards(plan, context):
    """A provider cannot drop workload preconditions when turning a read into writes."""
    from app.ai_operator.workload_guard import WorkloadGuard
    from app.ai_operator.schemas import TaskPlan
    sources = {}
    reviews = []
    for source in context:
        if source.get('tool') != 'pms.rebalance_workload':continue
        value=source.get('records')
        if not isinstance(value,dict) or not value.get('workload_guard'):continue
        guard=WorkloadGuard.model_validate(value['workload_guard']).model_dump(mode='json')
        sources.setdefault(source.get('record_id'),[]).append(guard)
        reviews.append((source.get('record_id'),guard,value))
    for step in plan.steps:
        if step.tool in {'pms.run_playbook','pms.undo'} and step.record_id in sources:
            raise HTTPException(422,'Expand workload-based assignment changes into a guarded pms.task_plan before review')
        if step.tool!='pms.task_plan' or step.record_id not in sources:continue
        supplied=step.payload.get('workload_guard')
        try:validated=WorkloadGuard.model_validate(supplied).model_dump(mode='json') if supplied is not None else None
        except ValueError:raise HTTPException(422,'Invalid workload recommendation source guard') from None
        if validated not in sources[step.record_id]:
            raise HTTPException(422,'Workload-based task plans must retain an authorized recommendation source guard')
        if len(plan.steps)==1:
            for pid,guard,value in reviews:
                if pid!=step.record_id or guard!=validated or not value.get('plan'):continue
                try:
                    proposed=TaskPlan.model_validate(step.payload['plan']).model_dump(mode='json',exclude_none=True)
                    recommended=TaskPlan.model_validate(value['plan']).model_dump(mode='json',exclude_none=True)
                except (ValueError,KeyError):continue
                if proposed['steps']==recommended['steps'] and not proposed.get('clarification'):
                    return {'project_id':pid,'source_sha256':guard['source_sha256'],
                            'changes':value['changes'],'limitations':value['limitations'][:4]}
    return None
