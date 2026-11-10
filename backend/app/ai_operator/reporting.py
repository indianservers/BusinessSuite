"""Bounded, permission-checked native reports. Totals never mix currencies."""
import csv
import io
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from app.ai_operator.suite_tools import Strict
from app.ai_operator.evidence import records, issue_sources
from app.core.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter(prefix='/suite', tags=['Suite native reports'])
SOURCES = {('CRM', 'tasks'): 'crm.tasks', ('CRM', 'deals'): 'crm.deals', ('PMS', 'tasks'): 'pms.tasks',
           ('HRMS', 'leave'): 'hrms.my_leave', ('SRM', 'invoices'): 'srm.invoices'}


class ReportFilters(Strict):
    entity: Literal['tasks', 'deals', 'leave', 'invoices'] = 'tasks'
    workspace_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, max_length=80)
    priority: str | None = Field(default=None, max_length=30)
    owner_id: int | None = Field(default=None, gt=0)
    customer_id: int | None = Field(default=None, gt=0)
    search: str | None = Field(default=None, max_length=200)
    date_from: date | None = None
    date_to: date | None = None
    group_by: list[Literal['status', 'priority', 'owner', 'customer', 'currency']] = Field(default_factory=lambda: ['status'], max_length=3)
    measures: list[Literal['count', 'amount']] = Field(default_factory=lambda: ['count'], min_length=1, max_length=2)
    max_records: int = Field(default=200, ge=1, le=500)
    format: Literal['json', 'csv'] = 'json'
    timezone: str = Field(default='Asia/Kolkata', max_length=80)

    @model_validator(mode='after')
    def valid_range(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Choose a valid timezone') from None
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError('Report end date precedes start date')
        if len(set(self.group_by)) != len(self.group_by) or len(set(self.measures)) != len(self.measures):
            raise ValueError('Duplicate dimensions or measures')
        return self


def validate_report(module, data):
    if (module, data.entity) not in SOURCES:
        raise HTTPException(422, 'Unsupported module/entity report')
    if module == 'PMS' and not data.project_id:
        raise HTTPException(422, 'Select a project for PMS reports')
    if module != 'PMS' and data.project_id:
        raise HTTPException(422, 'Project filter applies only to PMS tasks')
    if module == 'HRMS' and (data.owner_id or data.customer_id or data.priority or set(data.group_by) - {'status'}):
        raise HTTPException(422, 'Personal leave reports support status and date filters only')
    if module == 'PMS' and (data.customer_id or 'customer' in data.group_by):
        raise HTTPException(422, 'PMS task reports do not infer customer links')
    if module == 'SRM' and (data.owner_id or 'owner' in data.group_by):
        raise HTTPException(422, 'Invoice reports do not define task ownership')
    if 'amount' in data.measures and (data.entity not in ('deals', 'invoices') or 'currency' not in data.group_by):
        raise HTTPException(422, 'Amount reports require invoices/deals grouped by currency')
    if data.entity not in ('deals', 'invoices') and 'currency' in data.group_by:
        raise HTTPException(422, 'Currency is not available for this report')
    if data.entity in ('deals', 'invoices') and (data.priority or 'priority' in data.group_by):
        raise HTTPException(422, 'Priority applies only to task reports')


def filtered_rows(rows, data):
    result = []
    for row in rows:
        if data.status and row.get('status') != data.status:
            continue
        if data.priority and row.get('priority') != data.priority:
            continue
        owners = [row.get('owner_user_id'), row.get('assignee_user_id'), *(row.get('assignee_user_ids') or [])]
        if data.owner_id and data.owner_id not in owners:
            continue
        if data.customer_id and row.get('customer_id', row.get('company_id')) != data.customer_id:
            continue
        if data.search and data.search.casefold() not in str(row.get('title') or row.get('name') or row.get('invoice_number') or '').casefold():
            continue
        date_field = 'from_date' if data.entity == 'leave' else 'expected_close_date' if data.entity == 'deals' else 'due_date'
        from app.ai_operator.briefing import local_date
        value = local_date(row.get(date_field), data.timezone)
        if (data.date_from or data.date_to) and (not value or data.date_from and value < data.date_from or data.date_to and value > data.date_to):
            continue
        result.append(row)
    return result


def aggregate(rows, data):
    groups = defaultdict(lambda: {'count': 0, 'amount': Decimal('0'), 'missing_amounts': 0})
    for row in rows:
        values = {'status': row.get('status'), 'priority': row.get('priority'),
                  'owner': row.get('owner_user_id', row.get('assignee_user_id')),
                  'customer': row.get('customer_id', row.get('company_id')), 'currency': row.get('currency')}
        key = tuple(str(values[field]) if values[field] is not None else 'Unspecified' for field in data.group_by)
        group = groups[key]
        group['count'] += 1
        if 'amount' in data.measures:
            value = row.get('total_amount') if data.entity == 'invoices' else row.get('amount')
            try:
                amount = Decimal(str(value))
                if not amount.is_finite() or not row.get('currency'):
                    raise InvalidOperation
                group['amount'] += amount
            except (InvalidOperation, TypeError, ValueError):
                group['missing_amounts'] += 1
    return [{**dict(zip(data.group_by, key)), **({'count': value['count']} if 'count' in data.measures else {}),
             **({'amount': str(value['amount']), 'missing_amounts': value['missing_amounts']} if 'amount' in data.measures else {})}
            for key, value in sorted(groups.items())]


def csv_cell(value):
    text = str(value if value is not None else '')
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else text


async def run_report(module, data, request, db, user):
    from app.ai_operator.suite import authorize, check_tool, Step, api_call, now
    from app.ai_operator.suite_tools import validate_payload, minimize
    from app.ai_agents.security import limits, company, bounded_result
    from app.ai_agents.api import _require_ai_rate_limit
    from app.access.service import check_background_access
    authorize(db, user, data.workspace_id, module)
    validate_report(module, data)
    _require_ai_rate_limit(db, request, user, bucket='suite_reports')
    if data.format == 'csv':
        check_background_access(db, user, {'CRM': 'crm', 'PMS': 'project_management', 'HRMS': 'hrms', 'SRM': 'srm'}[module], 'export')
        from app.access.catalog import permission_objects
        if not user.is_superuser and not {p.name for p in permission_objects(user)}.intersection({'analytics_export', 'analytics_admin'}):
            raise HTTPException(403, 'Analytics export permission required')
    name = SOURCES[module, data.entity]
    tool = check_tool(db, user, data.workspace_id, Step(tool=name, record_id=data.project_id), False)
    allowed_calls = min(10, limits(db, company(user))['max_calls'])
    found, complete, pages = [], False, 0
    seen = set()
    for page in range(1, allowed_calls + 1):
        size = min(50, data.max_records - len(found))
        if not size:
            break
        params = {'skip': len(found), 'limit': 50} if module == 'PMS' else {'page': page, 'per_page': 50}
        if data.status:
            params['status'] = data.status
        # Every query still passes the canonical module's visibility and scope checks.
        params = {key: value for key, value in params.items() if key in tool.fields}
        validate_payload(tool, params)
        raw = await api_call(request.app, request.headers.get('authorization', ''), 'GET', tool.path.format(record_id=data.project_id), params)
        batch = records(raw)
        safe = minimize(batch[:size])
        candidate = bounded_result(db, user, safe)
        if isinstance(candidate, dict) and candidate.get('truncated'):
            break
        if len(json.dumps([*found, *candidate], default=str).encode('utf-8')) > limits(db, company(user))['max_result_bytes']:
            break
        if any(row.get('id') in seen for row in safe):
            break  # A source that ignores pagination cannot create a false complete report.
        seen.update(row.get('id') for row in safe)
        found = [*found, *candidate]
        pages += 1
        total = raw.get('total') if isinstance(raw, dict) else None
        if (len(batch) < 50 and len(batch) <= size) or isinstance(total, int) and len(found) >= total:
            complete = True
            break
    rows = filtered_rows(found, data)
    retrieved_at = now().isoformat()
    result = {'module': module, 'entity': data.entity, 'filters': data.model_dump(mode='json'),
              'items': rows, 'groups': aggregate(rows, data), 'matched_records': len(rows), 'scanned_records': len(found),
              'complete': complete, 'pages': pages, 'retrieved_at': retrieved_at,
              'date_basis': 'from_date' if data.entity == 'leave' else 'expected_close_date' if data.entity == 'deals' else 'due_date',
              'sources': issue_sources([{'tool': name, 'record_id': data.project_id, 'records': rows}], retrieved_at),
              'note': 'Totals cover all scanned authorized records only. Partial coverage is not a company-wide total. Amounts are separated by currency.'}
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user, agent_id=None, module=module, action='suite.report.export' if data.format == 'csv' else 'suite.report.preview',
                         input_json={'entity': data.entity, 'format': data.format}, output_json={'matched': len(rows), 'complete': complete}, status='success')
    db.commit()
    return result


@router.get('/reports/{module}')
async def report(module: Literal['CRM', 'PMS', 'HRMS', 'SRM'], request: Request,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    values = dict(request.query_params)
    for key in ('group_by', 'measures'):
        if key in values:
            values[key] = [item for raw in request.query_params.getlist(key) for item in raw.split(',') if item]
    try:
        data = ReportFilters.model_validate(values)
    except ValueError:
        raise HTTPException(422, 'Invalid report filters, dimensions or measures') from None
    result = await run_report(module, data, request, db, user)
    if data.format == 'json':
        return JSONResponse(result, headers={'Cache-Control': 'no-store'})
    stream = io.StringIO(newline='')
    columns = [*data.group_by, *data.measures, *(['missing_amounts'] if 'amount' in data.measures else []), 'coverage', 'retrieved_at', 'filters']
    writer = csv.writer(stream)
    writer.writerow(columns)
    for group in result['groups']:
        values = {**group, 'coverage': 'complete' if result['complete'] else 'partial', 'retrieved_at': result['retrieved_at'],
                  'filters': json.dumps(result['filters'], ensure_ascii=False)}
        writer.writerow([csv_cell(values.get(column)) for column in columns])
    return Response(stream.getvalue(), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="{module.lower()}-{data.entity}-report.csv"', 'Cache-Control': 'no-store'})
