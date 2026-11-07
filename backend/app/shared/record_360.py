"""Read-only record workspace adapters. Mutations remain in their source domains."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select, func
from app.core.deps import get_db, get_current_user
from app.apps.srm.services.commercial import tenant

router = APIRouter(prefix='/record-360', tags=['Record 360'])
Source = Literal['crm', 'srm', 'project_management']
Kind = Literal['company', 'contact', 'lead', 'deal', 'project', 'task']


def module_access(db, user, source):
    from app.module_registry import is_app_enabled
    from app.apps.business_os.services.module_service import is_module_enabled
    if not is_app_enabled(source) or not is_module_enabled(db, source, company_id=tenant(user)):
        raise HTTPException(403, 'Module is unavailable')
    grant = getattr(user, '_suite_grants', None)
    if not user.is_superuser and grant is not None:
        policy = grant.get(source, {})
        if not policy.get('enabled') or 'view' not in policy.get('actions', []):
            raise HTTPException(403, 'Module access is required')


def context(db, user, kind, ident, source):
    module_access(db, user, source)
    from app.shared.master_data import owner
    customer_id = None
    project = None
    if kind in ('project', 'task'):
        if source != 'project_management':
            raise HTTPException(422, 'Use the PMS source for delivery records')
        from app.apps.project_management.access import get_project_for_action
        from app.apps.project_management.task_workspace import scoped_task
        from app.apps.srm.commercial_models import CustomerLink, ProjectCommercial
        if kind == 'task':
            row, project = scoped_task(db, ident, user)
        else:
            row = project = get_project_for_action(db, ident, user)
        commercial = db.get(ProjectCommercial, project.id)
        link = db.query(CustomerLink).filter_by(organization_id=tenant(user), source_type='pms_client', source_id=project.client_id).first() if project.client_id else None
        customer_id = commercial.customer_id if commercial else link.customer_id if link else None
    elif kind == 'company':
        row = owner(db, user, 'company', ident, source)
        customer_id = row.id
    elif kind == 'contact':
        row = owner(db, user, 'contact', ident, source)
        customer_id = row.company_id
    else:
        # CRM lead/deal permissions cannot be supplied by SRM/PMS membership.
        module_access(db, user, 'crm')
        from app.apps.crm.api import router as crm
        entity = {'lead': 'leads', 'deal': 'deals'}[kind]
        crm._assert_entity_permission(entity, user, 'view')
        resource = crm._get_resource(entity)
        row = crm._get_record(db, resource, ident, tenant(user))
        crm._assert_record_visible(db, resource, ident, tenant(user), user)
        customer_id = getattr(row, 'company_id', None) or getattr(row, 'converted_company_id', None)
    customer = None
    if customer_id:
        try:
            customer = owner(db, user, 'company', customer_id, source)
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
    return row, project, customer


def project_query_for_customer(db, user, customer_id):
    from app.apps.project_management.models import PMSProject
    from app.apps.project_management.task_visibility import project_action_query
    from app.apps.srm.commercial_models import CustomerLink, ProjectCommercial
    from app.apps.srm.models import SRMEngagement
    module_access(db, user, 'project_management')
    clients = select(CustomerLink.source_id).where(CustomerLink.organization_id == tenant(user), CustomerLink.source_type == 'pms_client', CustomerLink.customer_id == customer_id)
    commercial = select(ProjectCommercial.project_id).where(ProjectCommercial.customer_id == customer_id)
    engagements = select(SRMEngagement.pms_project_id).where(func.coalesce(SRMEngagement.organization_id, 1) == tenant(user), SRMEngagement.customer_id == customer_id, SRMEngagement.deleted_at.is_(None))
    return project_action_query(db, user).filter(or_(PMSProject.client_id.in_(clients), PMSProject.id.in_(commercial), PMSProject.id.in_(engagements)))


def projects_for_customer(db, user, customer_id):
    return project_query_for_customer(db, user, customer_id).all()


@router.get('/{kind}/{ident}')
def summary(kind: Kind, ident: int, source: Source = 'crm', db=Depends(get_db), user=Depends(get_current_user)):
    row, project, customer = context(db, user, kind, ident, source)
    result = {'kind': kind, 'id': row.id, 'name': getattr(row, 'name', None) or getattr(row, 'full_name', None) or getattr(row, 'title', None),
              'status': getattr(row, 'status', None), 'customer': {'id': customer.id, 'name': customer.name} if customer else None,
              'fields': {key: getattr(row, key, None) for key in ('email', 'phone', 'phone_country_code', 'website', 'industry', 'priority', 'due_date', 'next_follow_up_at', 'owner_user_id')},
              'projects': [], 'project_count': None, 'relations': [], 'allowed_actions': [], 'sections': {}}
    if kind in ('company', 'contact', 'lead', 'deal'):
        from app.apps.crm.api import router as crm
        for action, entity in [('note', 'notes'), ('task', 'tasks'), ('call', 'calls'), ('meeting', 'meetings')]:
            try:
                module_access(db, user, 'crm')
                crm._assert_entity_permission(entity, user, 'manage')
                # A shared customer from SRM/PMS must also be a visible CRM
                # record before offering CRM mutations against that identity.
                resource = crm._get_resource({'company':'companies','contact':'contacts','lead':'leads','deal':'deals'}[kind])
                crm._assert_record_visible(db, resource, ident, tenant(user), user)
                result['allowed_actions'].append(action)
            except HTTPException as exc:
                if exc.status_code not in (403, 404):
                    raise
    if kind == 'company':
        from app.apps.crm.models import CRMContact, CRMDeal
        for entity, model, target in [('contacts', CRMContact, 'contact'), ('deals', CRMDeal, 'deal')]:
            try:
                for related in crm_query(db, user, entity).filter(model.company_id == ident).order_by(model.id.desc()).limit(10):
                    result['relations'].append({'id': related.id, 'kind': target, 'name': getattr(related, 'full_name', None) or getattr(related, 'name', None), 'url': f'/crm/{entity}/{related.id}'})
            except HTTPException as exc:
                if exc.status_code not in (403, 404):
                    raise
    if customer and kind == 'company':
        try:
            projects = project_query_for_customer(db, user, customer.id)
            result['project_count'] = projects.count()
            result['projects'] = [{'id': p.id, 'name': p.name, 'status': p.status} for p in projects.order_by(projects.column_descriptions[0]['entity'].id).limit(10)]
            result['sections']['projects'] = 'ready'
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
            result['sections']['projects'] = 'restricted'
    if project:
        result['project'] = {'id': project.id, 'name': project.name}
    return result


def crm_query(db, user, entity):
    module_access(db, user, 'crm')
    from app.apps.crm.api import router as crm
    crm._assert_entity_permission(entity, user, 'view')
    resource = crm._get_resource(entity)
    return crm._apply_record_visibility(crm._base_query(db, resource, tenant(user)), resource, user, db)


def service_query(db, user, kind, ident):
    from app.shared.follow_ups import access, visible, FollowUp
    access(user, db=db)
    column = {'company': 'customer_id', 'lead': 'lead_id', 'contact': 'contact_id', 'deal': 'deal_id'}.get(kind)
    return visible(db, user).filter(getattr(FollowUp, column) == ident) if column else visible(db, user).filter(False)


def iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()
    return value.isoformat()


def work_sources(db, user, kind=None, ident=None, customer=None, project=None):
    """SQL source queries; row permission checks are repeated before serialization."""
    from app.apps.project_management.models import PMSTask, PMSProject, PMSTaskUpdateEntry, PMSTaskRecordLink
    from app.apps.project_management.access import accessible_project_query, can_access_project
    from app.apps.project_management.task_workspace import scoped_task
    from app.shared.follow_ups import FollowUp
    from app.apps.crm.models import CRMTask, CRMActivity, CRMMeeting
    sources, states = [], {}
    try:
        module_access(db, user, 'project_management')
        from app.apps.project_management.task_visibility import visible_task_query
        tasks = visible_task_query(db, user)
        if project:
            tasks = tasks.filter(PMSTask.project_id == project.id)
        elif kind == 'company' and customer:
            project_ids = project_query_for_customer(db, user, customer.id).with_entities(PMSProject.id)
            related = []
            from app.apps.crm.models import CRMContact, CRMLead
            for entity, model, column, company_column in [('contacts', CRMContact, PMSTaskRecordLink.contact_id, CRMContact.company_id), ('leads', CRMLead, PMSTaskRecordLink.lead_id, CRMLead.converted_company_id)]:
                try:
                    target_ids = crm_query(db, user, entity).filter(company_column == customer.id).with_entities(model.id)
                    related.append(column.in_(target_ids))
                except HTTPException as exc:
                    if exc.status_code not in (403, 404):
                        raise
            links = select(PMSTaskRecordLink.task_id).where(PMSTaskRecordLink.organization_id == tenant(user), or_(*related)) if related else select(PMSTaskRecordLink.task_id).where(False)
            tasks = tasks.filter(or_(PMSTask.project_id.in_(project_ids), PMSTask.id.in_(links)))
        elif kind in ('contact', 'lead'):
            links = select(PMSTaskRecordLink.task_id).where(PMSTaskRecordLink.organization_id == tenant(user), getattr(PMSTaskRecordLink, kind + '_id') == ident)
            tasks = tasks.filter(PMSTask.id.in_(links))
        elif kind is not None:
            tasks = tasks.filter(False)
        if kind == 'task':
            tasks = tasks.filter(PMSTask.id == ident)
        sources.append(('pms_task', tasks, PMSTask.due_date, PMSTask.id))
        entries = db.query(PMSTaskUpdateEntry).filter(PMSTaskUpdateEntry.task_id.in_(tasks.with_entities(PMSTask.id)), PMSTaskUpdateEntry.deleted_at.is_(None), PMSTaskUpdateEntry.kind == 'followup')
        sources.append(('pms_followup', entries, PMSTaskUpdateEntry.follow_up_date, PMSTaskUpdateEntry.id))
        states['pms'] = 'ready'
    except HTTPException as exc:
        if exc.status_code not in (403, 404):
            raise
        states['pms'] = 'restricted'
    if kind is None or kind in ('company', 'lead', 'contact', 'deal'):
        try:
            from app.shared.follow_ups import access, visible
            if kind is None:
                access(user, db=db)
                q = visible(db, user)
            else:
                q = service_query(db, user, kind, ident)
            sources.append(('service_followup', q, FollowUp.due_at, FollowUp.id))
            states['service_followups'] = 'ready'
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
            states['service_followups'] = 'restricted'
    if kind is None or kind in ('company', 'lead', 'contact', 'deal'):
        try:
            for entity, model, source, due in [('tasks', CRMTask, 'crm_task', CRMTask.due_date), ('activities', CRMActivity, 'crm_activity', func.coalesce(CRMActivity.due_date, CRMActivity.activity_date)), ('meetings', CRMMeeting, 'crm_meeting', CRMMeeting.start_time)]:
                q = crm_query(db, user, entity)
                if source == 'crm_activity':
                    # Related records emit timeline copies. Keep those in history,
                    # while the native task/meeting remains the actionable work.
                    q = q.filter(~func.coalesce(CRMActivity.metadata_json['sourceEntity'].as_string(), '').in_(
                        ['tasks', 'meetings', 'calls', 'notes', 'emails', 'quotations', 'deals']))
                if kind:
                    q = q.filter(getattr(model, {'company': 'company_id', 'lead': 'lead_id', 'contact': 'contact_id', 'deal': 'deal_id'}[kind]) == ident)
                sources.append((source, q, due, model.id))
            states['crm'] = 'ready'
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
            states['crm'] = 'restricted'
    return sources, states


def work_payload(db, user, source, row, task_access=None):
    from app.apps.project_management.task_workspace import scoped_task
    if source in ('pms_task', 'pms_followup'):
        task_id = row.id if source == 'pms_task' else row.task_id
        if task_access is None:
            task, project = scoped_task(db, task_id, user)
        else:
            # Request-local only: follow-ups share the same native task check.
            # The next page/request always rechecks current permissions.
            if task_id not in task_access:
                task_access[task_id] = scoped_task(db, task_id, user)
            task, project = task_access[task_id]
        return {'id': f'{source}:{row.id}', 'source': source, 'source_id': row.id,
                'title': task.title if source == 'pms_task' else row.body, 'status': task.status if source == 'pms_task' else 'Completed' if row.resolved else 'Scheduled',
                'due_at': iso(task.due_date if source == 'pms_task' else row.follow_up_date),
                'assignee_id': task.assignee_user_id if source == 'pms_task' else row.responsible_user_id or row.author_id,
                'assignee_ids': task.assignee_user_ids if source == 'pms_task' else [row.responsible_user_id or row.author_id],
                'created_by': task.reporter_user_id if source == 'pms_task' else row.author_id,
                'project_id': project.id, 'project_name': project.name, 'priority': task.priority,
                'url': f'/pms/tasks/{task.id}' + ('?tab=followups' if source == 'pms_followup' else '')}
    return {'id': f'{source}:{row.id}', 'source': source, 'source_id': row.id, 'title': row.title or getattr(row, 'subject', None), 'status': row.status,
            'timezone': row.timezone if source == 'service_followup' else 'Asia/Kolkata',
            'due_at': iso(row.due_at if source == 'service_followup' else row.start_time if source == 'crm_meeting' else row.due_date or getattr(row, 'activity_date', None)), 'assignee_id': row.assigned_user_id if source == 'service_followup' else row.owner_user_id,
            'created_by': row.created_by if source == 'service_followup' else row.created_by_user_id, 'priority': getattr(row, 'priority', None),
            'url': f'/pms/follow-ups/{row.id}' if source == 'service_followup' else f'/crm/leads/{row.lead_id}' if getattr(row,'lead_id',None) else '/crm/calendar' if source == 'crm_meeting' else '/crm/activities' if source == 'crm_activity' else '/crm/tasks'}


def work_page(db, user, kind=None, ident=None, customer=None, project=None, page=1, per_page=25, view='all', search='', source_filter='', assigned=None, cursor=None, cursor_mode=False, cursor_scope=None):
    from app.shared.record_paging import bounded_page, scope_key
    from app.shared.record_work_filters import filtered
    sources, states = work_sources(db, user, kind, ident, customer, project)
    sources = [(name, filtered(query, name, due, user, view=view, search=search, assigned=assigned), due, key) for name, query, due, key in sources if not source_filter or source_filter == name]
    scope = scope_key(db, user, ['work', kind, ident, view, search, source_filter, assigned, project.id if project else None, customer.id if customer else None, cursor_scope, per_page])
    result = bounded_page(sources, scope=scope, cursor=cursor, page=page, per_page=per_page, include_total=not cursor_mode)
    items, task_access = [], {}
    for stamp, source, identity, row in result['rows']:
        try:
            items.append(work_payload(db, user, source, row, task_access))
        except HTTPException as exc:
            if exc.status_code in (403, 404):
                raise HTTPException(409, 'Work access changed. Refresh this view.')
            raise
    return {'items': items, 'total': result['total'], 'page': page, 'per_page': per_page, 'sections': states, 'has_more': result['has_more'], 'next_cursor': result['next_cursor']}


@router.get('/{kind}/{ident}/work')
def record_work(kind: Kind, ident: int, source: Source = 'crm', page: int = Query(1, ge=1, le=200), per_page: int = Query(25, ge=1, le=100), db=Depends(get_db), user=Depends(get_current_user), cursor: str | None = None, cursor_mode: bool = False):
    row, project, customer = context(db, user, kind, ident, source)
    result = work_page(db, user, kind, ident, customer, project, page, per_page, view='active', cursor=cursor, cursor_mode=cursor_mode, cursor_scope=source)
    for item in result['items']:
        if item['source'] == 'service_followup':
            item['url'] = f'/{"pms" if source == "project_management" else source}/follow-ups/{item["source_id"]}'
    return result


@router.get('/work/queue/items')
def queue(page: int = Query(1, ge=1, le=200), per_page: int = Query(25, ge=1, le=100), view: Literal['all', 'today', 'overdue', 'upcoming', 'mine', 'assigned', 'completed'] = 'mine', search: str = Query('', max_length=200), source_filter: str = '', project_id: int | None = None, customer_id: int | None = None, db=Depends(get_db), user=Depends(get_current_user), cursor: str | None = None, cursor_mode: bool = False):
    module_access(db, user, 'project_management')
    from app.apps.project_management.access import get_project_for_action
    from app.shared.master_data import owner
    project = get_project_for_action(db, project_id, user) if project_id else None
    customer = owner(db, user, 'company', customer_id, 'project_management') if customer_id else None
    if project and customer and project.id not in {p.id for p in projects_for_customer(db, user, customer.id)}:
        raise HTTPException(422, 'Project is not linked to this customer')
    # Customer scope must filter every provider, not only the PMS projects.
    return work_page(db, user, 'company' if customer else 'project' if project else None, customer_id if customer else project_id, customer, project, page, per_page, view, search, source_filter, cursor=cursor, cursor_mode=cursor_mode, cursor_scope='project_management')


@router.get('/{kind}/{ident}/events')
def events(kind: Kind, ident: int, source: Source = 'crm', page: int = Query(1, ge=1, le=200), per_page: int = Query(25, ge=1, le=100), event_type: Literal['all', 'activity', 'note', 'file', 'history', 'followup', 'commercial', 'email', 'whatsapp', 'call', 'meeting'] = 'all', db=Depends(get_db), user=Depends(get_current_user), cursor: str | None = None, cursor_mode: bool = False):
    row, project, customer = context(db, user, kind, ident, source)
    from app.shared.record_paging import bounded_page, scope_key
    sources, metadata, states = [], {}, {}
    def append(query, date_column, prefix, category, title, body, actor):
        if event_type != 'all' and category != event_type:
            return
        model = query.column_descriptions[0]['entity']
        sources.append((prefix, query, date_column, model.id))
        metadata[prefix] = (category, title, body, actor, date_column.key)
    if kind in ('company', 'lead', 'contact', 'deal'):
        from app.apps.crm.models import CRMActivity, CRMNote, CRMFileAsset, CRMCallLog, CRMMeeting
        field = {'company': 'company_id', 'lead': 'lead_id', 'contact': 'contact_id', 'deal': 'deal_id'}[kind]
        for entity, model, prefix, category, title, body, actor in [
            ('activities', CRMActivity, 'crm_activity', 'activity', lambda r: r.subject, lambda r: r.description or r.body, lambda r: r.created_by_user_id),
            ('notes', CRMNote, 'crm_note', 'note', lambda r: 'Note', lambda r: r.body, lambda r: r.author_user_id),
            ('files', CRMFileAsset, 'crm_file', 'file', lambda r: r.original_name, lambda r: None, lambda r: r.uploaded_by_user_id),
            ('calls', CRMCallLog, 'crm_call', 'call', lambda r: r.outcome or 'Call', lambda r: r.notes, lambda r: r.created_by_user_id),
            ('meetings', CRMMeeting, 'crm_meeting', 'meeting', lambda r: r.title, lambda r: r.description, lambda r: r.created_by_user_id),
        ]:
            try:
                q = crm_query(db, user, entity).filter(getattr(model, field) == ident)
                append(q, model.created_at, prefix, category, title, body, actor)
                states[prefix] = 'ready'
            except HTTPException as exc:
                if exc.status_code not in (403, 404):
                    raise
                states[prefix] = 'restricted'
        try:
            from app.shared.follow_ups import FollowUpActivity, FollowUp
            followups = service_query(db, user, kind, ident).with_entities(FollowUp.id)
            q = db.query(FollowUpActivity).filter(FollowUpActivity.follow_up_id.in_(followups))
            append(q, FollowUpActivity.created_at, 'service_followup', 'followup', lambda r: 'Follow-up ' + r.action, lambda r: r.details.get('notes', ''), lambda r: r.actor_id)
            states['service_followups'] = 'ready'
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
            states['service_followups'] = 'restricted'
        try:
            module_access(db, user, 'crm')
            from app.apps.crm.api import router as crm
            from app.apps.crm.models import CRMTimelineEvent
            entity = {'company':'companies','lead':'leads','contact':'contacts','deal':'deals'}[kind]
            crm._assert_entity_permission(entity, user, 'view')
            crm._assert_record_visible(db, crm._get_resource(entity), ident, tenant(user), user)
            q = db.query(CRMTimelineEvent).filter(CRMTimelineEvent.organization_id == tenant(user), CRMTimelineEvent.record_type == crm.ENTITY_TYPE_BY_CANONICAL[entity], CRMTimelineEvent.record_id == ident)
            # Activity bodies are supplied by the activity provider; this stream
            # contains only recorded changes to avoid duplicate note/call rows.
            q = q.filter(CRMTimelineEvent.event_type.notin_(['note','call','meeting','task','activity']))
            append(q, CRMTimelineEvent.occurred_at, 'crm_history', 'history', lambda r:r.title, lambda r:r.description, lambda r:r.actor_user_id)
            states['history'] = 'ready'
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
            states['history'] = 'restricted'
        try:
            from app.apps.srm.services.commercial import require
            from app.apps.communication.models import CommunicationTimelineEvent
            require(user, 'communication_view', 'communication_email_send')
            for channel in ('email', 'whatsapp', 'call'):
                q = db.query(CommunicationTimelineEvent).filter(CommunicationTimelineEvent.organization_id == tenant(user), CommunicationTimelineEvent.record_type == ('account' if kind == 'company' else kind), CommunicationTimelineEvent.record_id == ident, CommunicationTimelineEvent.channel == channel)
                append(q, CommunicationTimelineEvent.created_at, 'communication_' + channel, channel, lambda r: r.subject or r.event_type, lambda r:r.summary, lambda r:r.actor_user_id)
            states['communication'] = 'ready'
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
            states['communication'] = 'restricted'
    if project:
        from app.apps.project_management.models import PMSActivity, PMSTaskUpdateEntry
        from app.apps.project_management.task_workspace import scoped_task
        q = db.query(PMSActivity).filter_by(project_id=project.id)
        if kind == 'task':
            q = q.filter_by(task_id=ident)
        # Project history can include tasks an intern cannot browse. Keep the
        # project adapter to project events; task events use scoped_task above.
        else:
            q = q.filter(PMSActivity.task_id.is_(None))
        append(q, PMSActivity.created_at, 'pms_history', 'history', lambda r: r.summary, lambda r: None, lambda r: r.actor_user_id)
        if kind == 'task':
            q = db.query(PMSTaskUpdateEntry).filter_by(task_id=ident, deleted_at=None)
            if event_type == 'followup':
                q = q.filter_by(kind='followup')
            append(q, PMSTaskUpdateEntry.created_at, 'pms_update', 'followup' if event_type == 'followup' else 'activity', lambda r: 'Task ' + r.kind, lambda r: r.body, lambda r: r.author_id)
        states['pms'] = 'ready'
    if kind == 'company':
        from app.apps.srm.models import SRMInvoice, SRMSalesOrder
        from app.apps.srm.services.commercial import require, invoice_query
        from app.apps.srm.access import sales_order_query
        from app.shared.master_data import owner
        for provider in ('invoices', 'orders'):
            try:
                module_access(db, user, 'srm')
                owner(db, user, 'company', ident, 'srm')
                if provider == 'invoices':
                    require(user, 'srm_invoice_view', 'srm_invoice_create', 'srm_admin', 'srm_collection_view')
                    q = invoice_query(db, user).filter(SRMInvoice.customer_id == ident)
                    append(q, SRMInvoice.created_at, 'srm_invoice', 'commercial', lambda r: r.invoice_number, lambda r: f'{r.status} · {r.currency} {r.total_amount}', lambda r: None)
                else:
                    require(user, 'srm_view', 'srm_manage', 'srm_admin')
                    q = sales_order_query(db, user).filter(SRMSalesOrder.customer_id == ident)
                    append(q, SRMSalesOrder.created_at, 'srm_order', 'commercial', lambda r: r.order_number, lambda r: r.status, lambda r: r.assigned_user_id)
                states[provider] = 'ready'
            except HTTPException as exc:
                if exc.status_code not in (403, 404):
                    raise
                states[provider] = 'restricted'
    scope = scope_key(db, user, ['events', source, kind, ident, event_type, per_page])
    result = bounded_page(sources, scope=scope, cursor=cursor, page=page, per_page=per_page, descending=True, snapshot=True, include_total=not cursor_mode)
    page_rows = []
    for stamp, prefix, identity, item in result['rows']:
        category, title, body, actor, date_key = metadata[prefix]
        page_rows.append({'id': f'{prefix}:{item.id}', 'source_id': item.id, 'type': category, 'title': title(item), 'body': body(item), 'occurred_at': iso(getattr(item, date_key)), 'actor_id': actor(item), 'source': prefix})
    from app.models.user import User
    actors = {}
    for identity in {event['actor_id'] for event in page_rows if event['actor_id']}:
        account = db.get(User, identity)
        profile = getattr(account, 'person', None) if account and tenant(account) == tenant(user) else None
        actors[identity] = getattr(profile, 'display_name', None) or f'User #{identity}'
    for event in page_rows:
        event['actor_name'] = actors.get(event['actor_id'], 'System')
        if event['source'] in ('srm_invoice', 'srm_order'):
            event['url'] = f'/srm/{"invoices" if event["source"] == "srm_invoice" else "sales-orders"}/{event["source_id"]}'
    return {'items': page_rows, 'total': result['total'], 'page': page, 'per_page': per_page, 'sections': states, 'has_more': result['has_more'], 'next_cursor': result['next_cursor']}
