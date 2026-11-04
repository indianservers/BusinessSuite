"""Task relationship operations using native PMS and CRM authorization."""
from fastapi import HTTPException
from sqlalchemy import or_
from .models import PMSTask, PMSTaskRecordLink
from .task_workspace import scoped_task
from .access import can_access_project
from app.apps.srm.services.commercial import tenant


def target(db, user, kind, ident):
    from app.shared.record_360 import crm_query
    from app.apps.crm.models import CRMContact, CRMLead
    model = CRMContact if kind == 'contact' else CRMLead
    row = crm_query(db, user, 'contacts' if kind == 'contact' else 'leads').filter(model.id == ident).first()
    if not row:
        raise HTTPException(404, 'CRM record is unavailable in your scope')
    return row


def payload(link, row):
    kind = 'contact' if link.contact_id else 'lead'
    return {'id': link.id, 'kind': kind, 'record_id': row.id, 'name': row.full_name, 'url': f'/crm/{kind}s/{row.id}'}


def read_links(db, user, task_id):
    task, project = scoped_task(db, task_id, user)
    items = []
    for link in db.query(PMSTaskRecordLink).filter_by(organization_id=tenant(user), task_id=task.id).order_by(PMSTaskRecordLink.id):
        try:
            row = target(db, user, 'contact' if link.contact_id else 'lead', link.contact_id or link.lead_id)
            items.append(payload(link, row))
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
    return {'items': items, 'can_manage': can_access_project(db, project, user, 'manage_tasks')}


def link_record(db, user, task_id, kind, ident):
    task, project = scoped_task(db, task_id, user, 'manage_tasks')
    # Serialize relationship changes on the existing task, including duplicate submissions.
    db.query(PMSTask).filter_by(id=task.id).with_for_update().one()
    row = target(db, user, kind, ident)
    from app.shared.record_360 import module_access
    from app.apps.srm.commercial_models import CustomerLink, ProjectCommercial
    module_access(db, user, 'project_management')
    commercial = db.get(ProjectCommercial, project.id)
    client = db.query(CustomerLink).filter_by(organization_id=tenant(user), source_type='pms_client', source_id=project.client_id).first() if project.client_id else None
    customer_id = commercial.customer_id if commercial else client.customer_id if client else None
    company_id = getattr(row, 'company_id', None) or getattr(row, 'converted_company_id', None)
    if customer_id and company_id and customer_id != company_id:
        raise HTTPException(422, 'CRM record belongs to a different customer than this task project')
    field = 'contact_id' if kind == 'contact' else 'lead_id'
    link = db.query(PMSTaskRecordLink).filter_by(organization_id=tenant(user), task_id=task.id, **{field: ident}).first()
    if link is None:
        link = PMSTaskRecordLink(organization_id=tenant(user), task_id=task.id, linked_by=user.id, **{field: ident})
        db.add(link)
        from .api.router import _record_activity
        _record_activity(db, project.id, user, 'task.crm_linked', 'task', task.id, f'Linked CRM {kind}', task_id=task.id, metadata={'kind': kind, 'record_id': ident})
        db.flush()
    db.commit()
    return payload(link, row)


def unlink_record(db, user, task_id, link_id):
    task, project = scoped_task(db, task_id, user, 'manage_tasks')
    link = db.query(PMSTaskRecordLink).filter_by(id=link_id, task_id=task.id, organization_id=tenant(user)).with_for_update().first()
    if not link:
        raise HTTPException(404, 'Task link is unavailable')
    from .api.router import _record_activity
    _record_activity(db, project.id, user, 'task.crm_unlinked', 'task', task.id, 'Removed a CRM task link', task_id=task.id)
    db.delete(link)
    db.commit()
    return {'ok': True}


def merge_links(db, kind, winner_id, loser_ids):
    """Called by the existing CRM merge transaction; deduplicate per-task links."""
    from sqlalchemy import inspect
    from app.apps.crm.models import CRMContact, CRMLead
    if not inspect(db.connection()).has_table(PMSTaskRecordLink.__tablename__):
        return
    winner = db.get(CRMContact if kind == 'contact' else CRMLead, winner_id)
    field = getattr(PMSTaskRecordLink, kind + '_id')
    existing = {row.task_id for row in db.query(PMSTaskRecordLink).filter(PMSTaskRecordLink.organization_id == winner.organization_id, field == winner_id)}
    for row in db.query(PMSTaskRecordLink).filter(PMSTaskRecordLink.organization_id == winner.organization_id, field.in_(loser_ids)).order_by(PMSTaskRecordLink.id):
        if row.task_id in existing:
            db.delete(row)
        else:
            setattr(row, kind + '_id', winner_id)
            existing.add(row.task_id)
