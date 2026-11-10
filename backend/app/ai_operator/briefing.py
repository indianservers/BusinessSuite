"""Live deterministic briefing over existing scoped canonical tools. No model call."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.ai_operator.evidence import records, issue_sources

router = APIRouter(prefix='/suite', tags=['Suite daily briefing'])
DONE = {'done', 'completed', 'closed', 'cancelled', 'canceled'}


def local_date(value, timezone):
    if not value:
        return None
    try:
        text = str(value)
        if len(text) == 10:
            return date.fromisoformat(text)
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
        # Canonical task dates are date-only or timezone-aware timestamps.
        return parsed.astimezone(ZoneInfo(timezone)).date() if parsed.tzinfo else parsed.date()
    except (ValueError, TypeError):
        return None


def rank_items(packets, sources, today, timezone, user_id, mine=True, horizon_days=7):
    source_map = {(s['tool'], s['record_id'], s['href']): s for s in sources}
    from app.ai_operator.evidence import source_link
    items = []
    for packet in packets:
        tool = packet['tool']
        for row in records(packet['records']):
            status = str(row.get('status', '')).strip().lower()
            if status in DONE or (tool == 'hrms.my_leave' and status in {'rejected', 'approved'}):
                continue
            if mine and tool in ('crm.tasks', 'pms.tasks', 'pms.projects'):
                owners = [row.get('owner_user_id'), row.get('assignee_user_id'), *(row.get('assignee_user_ids') or [])]
                if user_id not in owners:
                    continue
            due = local_date(row.get('due_date'), timezone)
            blocked = str(row.get('status', '')).strip().lower() == 'blocked'
            reasons = []
            if blocked:
                reasons.append('Blocked')
            if due:
                if due < today:
                    reasons.append('Overdue')
                elif due == today:
                    reasons.append('Due today')
                elif due <= today + timedelta(days=horizon_days):
                    reasons.append('Due soon')
            if str(row.get('priority', '')).lower() in ('high', 'urgent', 'critical'):
                reasons.append('High priority')
            if tool.startswith('hrms.'):
                reasons.append('Pending HR request')
            if not reasons:
                continue
            href = source_link(tool, row, packet.get('record_id'))
            source = source_map.get((tool, row.get('id'), href))
            if not source:
                continue
            score = (100 if blocked else 0) + (80 if due and due < today else 60 if due == today else 20 if due and due <= today + timedelta(days=horizon_days) else 0) + (30 if 'High priority' in reasons else 0)
            items.append({'module': tool.split('.')[0].upper(), 'title': source['label'], 'record_id': row['id'],
                          'project_id': packet.get('record_id') if tool == 'pms.tasks' else row.get('id') if tool == 'pms.projects' else None,
                          'client_id': packet.get('client_id') if tool == 'pms.tasks' else row.get('client_id'), 'status': row.get('status'), 'due_date': due.isoformat() if due else None,
                          'reasons': reasons, 'score': score, 'source': source})
    return sorted(items, key=lambda item: (-item['score'], item['due_date'] or '9999', item['module'], item['record_id']))


@router.get('/briefing')
async def briefing(request: Request, workspace_id: int | None = Query(None, gt=0),
                   project_id: int | None = Query(None, gt=0), module: str | None = None,
                   mine: bool = True, horizon_days: int = Query(7, ge=1, le=90), timezone: str = 'Asia/Kolkata',
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_operator.suite import authorize, check_tool, Step, api_call, now
    from app.ai_agents.api import _require_ai_rate_limit
    from app.ai_agents.security import limits, company, bounded_result
    from app.ai_operator.suite_tools import minimize
    authorize(db, user, workspace_id)
    _require_ai_rate_limit(db, request, user, bucket='suite_briefing')
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, 'Choose a valid timezone') from None
    if module not in (None, 'CRM', 'PMS', 'HRMS'):
        raise HTTPException(422, 'Choose CRM, PMS or HRMS')
    if project_id and module not in (None, 'PMS'):
        raise HTTPException(422, 'Project filters require PMS')
    budget = min(limits(db, company(user))['max_calls'], 12)
    packets, coverage = [], []
    retrieved_at = now().isoformat()

    async def read(name, ident=None):
        if len(coverage) >= budget:
            coverage.append({'tool': name, 'status': 'budget_limited', 'record_id': ident})
            return []
        try:
            tool = check_tool(db, user, workspace_id, Step(tool=name, record_id=ident), False)
            params = {'per_page': 50} if 'per_page' in tool.fields else {}
            if name == 'hrms.my_tickets':
                params['my_tickets'] = True
            value = await api_call(request.app, request.headers.get('authorization', ''), 'GET', tool.path.format(record_id=ident), params)
            if name == 'pms.projects':
                value = [row for row in records(value) if row.get('workspace_id') == workspace_id]
            rows = records(value)
            total = value.get('total') if isinstance(value, dict) else len(rows)
            safe = bounded_result(db, user, minimize(rows))
            if isinstance(safe, dict) and safe.get('truncated'):
                coverage.append({'tool': name, 'record_id': ident, 'status': 'disclosure_limited'})
                return []
            packets.append({'tool': name, 'record_id': ident, 'records': safe})
            coverage.append({'tool': name, 'record_id': ident, 'status': 'ok', 'sampled': len(records(safe)),
                             'limited': len(rows) >= 50 or (isinstance(total, int) and total > len(rows))})
            return records(safe)
        except HTTPException as exc:
            coverage.append({'tool': name, 'record_id': ident, 'status': 'unavailable', 'http_status': exc.status_code})
            return []

    if module in (None, 'CRM'):
        await read('crm.tasks')
    if module in (None, 'HRMS'):
        await read('hrms.my_leave')
        await read('hrms.my_tickets')
    if module in (None, 'PMS'):
        if project_id:
            await read('pms.tasks', project_id)
            if packets and packets[-1]['tool'] == 'pms.tasks':
                from app.apps.project_management.access import get_project_for_action
                project = get_project_for_action(db, project_id, user, 'browse')
                packets[-1]['client_id'] = project.client_id
        else:
            projects = await read('pms.projects')
            remaining = max(0, budget - len(coverage))
            for project in projects[:remaining]:
                await read('pms.tasks', project['id'])
                if packets and packets[-1]['tool'] == 'pms.tasks' and packets[-1]['record_id'] == project['id']:
                    packets[-1]['client_id'] = project.get('client_id')
            if len(projects) > remaining:
                coverage.append({'tool': 'pms.tasks', 'status': 'budget_limited', 'projects_not_scanned': len(projects) - remaining})
    sources = issue_sources(packets, retrieved_at)
    today = datetime.now(zone).date()
    priorities = rank_items(packets, sources, today, timezone, user.id, mine, horizon_days)
    # Delivery is an all-visible project signal, independently of personal-task filtering.
    risks = [row for row in rank_items(packets, sources, today, timezone, user.id, False, horizon_days)
             if row['module'] == 'PMS' and any(reason in row['reasons'] for reason in ('Overdue', 'Blocked'))]
    return {'generated_at': retrieved_at, 'today': today.isoformat(), 'timezone': timezone,
            'filters': {'module': module, 'mine': mine, 'horizon_days': horizon_days, 'workspace_id': workspace_id, 'project_id': project_id},
            'priorities': priorities[:50], 'delivery_risks': risks[:50], 'coverage': coverage,
            'limited': len(priorities) > 50 or len(risks) > 50 or any(row['status'] != 'ok' or row.get('limited') for row in coverage),
            'note': 'Bounded live source sample. Delivery signals are project-linked; CRM customer matching, capacity forecasts and financial impact are not inferred.'}
