"""Bounded selectors over existing owned PMS sources and exact native actions."""
from fastapi import HTTPException
from sqlalchemy import exists, select
from app.apps.project_management.models import PMSProject, PMSTask
from app.apps.srm.models import SRMEngagement, SRMInvoice
from app.business_packs.models import PackRecordOwnership
from app.branches.models import BranchOwnership
from app.apps.srm.services.commercial import require, invoice_for
from . import service
from .models import AccountsCommand, AccountsPeriod
from .pms_sources import project_for_action, upload_task_access


def _bounds(after, limit):
    if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 100:
        service.fail('Choose a valid delivery cursor and limit from 1 to 100', 422)


def _owned(table, scope):
    owners, branches = PackRecordOwnership.__table__, BranchOwnership.__table__
    return (exists().where(owners.c.resource_table == table.name, owners.c.resource_key == table.c.id.cast(
        owners.c.resource_key.type), owners.c.company_id == scope.company_id, owners.c.branch_id == scope.branch_id,
        owners.c.context_id == scope.context_id),
        exists().where(branches.c.resource_table == table.name, branches.c.resource_key == table.c.id.cast(
            branches.c.resource_key.type), branches.c.company_id == scope.company_id, branches.c.branch_id == scope.branch_id))


def _select_page(candidates, mapper, limit):
    items=[]
    for ident in candidates[:500]:
        try:
            item=mapper(ident)
        except HTTPException as exc:
            if exc.status_code not in {403,404}:
                raise
            continue
        if item is None:
            continue
        items.append(item)
        if len(items)>limit:
            return {'items':items[:limit],'next':items[limit-1]['id']}
    if len(candidates)>500:
        service.fail('Too many unavailable delivery sources; narrow the selector search',503)
    return {'items':items,'next':None}


def projects(ident, db, actor, *, after=0, limit=50, search=''):
    _bounds(after,limit)
    scope=service.authority(db,actor,'engagements.manage')
    period=service.record(db,actor,scope,ident)
    if db.get(SRMEngagement,period.engagement_id).pms_project_id is not None:
        return {'items':[],'next':None}
    table=PMSProject.__table__
    statement=select(table.c.id).where(table.c.organization_id==scope.company_id,
        table.c.branch_id==scope.branch_id,table.c.deleted_at.is_(None),table.c.id>after,*_owned(table,scope))
    if search:
        statement=statement.where(table.c.name.contains(search,autoescape=True))
    candidates=list(db.connection().scalars(statement.order_by(table.c.id).limit(501)))
    def dto(project_id):
        row=project_for_action(db,actor,project_id)
        from .project_links import reconcile_commercial, IncompatibleCommercialSource
        try:
            reconcile_commercial(db,scope,period.engagement_id,period.client_id,project_id,project_source=row)
        except IncompatibleCommercialSource:
            return None
        return {'id':row.id,'name':row.name,'currency':row.currency}
    return _select_page(candidates,dto,limit)


def tasks(ident, db, actor, *, after=0, limit=50, search=''):
    _bounds(after,limit)
    scope=service.authority(db,actor,'documents.request')
    period=service.record(db,actor,scope,ident)
    project_id=db.get(SRMEngagement,period.engagement_id).pms_project_id
    if project_id is None:
        return {'items':[],'next':None}
    project_for_action(db,actor,project_id,'upload')
    table=PMSTask.__table__
    statement=select(table.c.id).where(table.c.project_id==project_id,table.c.deleted_at.is_(None),
        table.c.id>after,*_owned(table,scope))
    if search:
        statement=statement.where(table.c.title.contains(search,autoescape=True))
    candidates=list(db.connection().scalars(statement.order_by(table.c.id).limit(501)))
    def dto(task_id):
        upload_task_access(db,actor,project_id,task_id)
        title=db.connection().scalar(select(table.c.title).where(table.c.id==task_id,table.c.project_id==project_id))
        return {'id':task_id,'title':title}
    return _select_page(candidates,dto,limit)


def delivery(ident, db, actor):
    scope=service.read_authority(db,actor)
    row=service.record(db,actor,scope,ident)
    engagement=db.get(SRMEngagement,row.engagement_id)
    global_caps=service.capabilities(db,actor)
    project=project_for_action(db,actor,engagement.pms_project_id) if engagement.pms_project_id else None
    from app.apps.srm.api.router import _require_open_engagement
    try:
        _require_open_engagement(engagement)
        opened=True
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        opened=False
    preparing=row.state in {'draft','returned'}
    invoice_command=service.scoped(db,AccountsCommand,scope).filter_by(period_id=row.id,action='invoice').one_or_none()
    linked_before_work = not service.scoped(db,AccountsPeriod,scope).filter(
        AccountsPeriod.engagement_id==engagement.id,AccountsPeriod.work_revision>0).first()
    invoices=SRMInvoice.__table__
    has_native_invoice=bool(db.connection().scalar(select(exists().where(
        invoices.c.engagement_id==engagement.id,invoices.c.organization_id==scope.company_id))))
    from .project_links import _commands as project_commands
    flags={'project_link':opened and global_caps['engagements_manage'] and project is None and linked_before_work and not has_native_invoice and not project_commands(db,scope,engagement.id),
        'documents_view':global_caps['documents_view'],
        'documents_request':opened and preparing and global_caps['documents_request'],
        'documents_upload':opened and preparing and project is not None and global_caps['documents_request'],
        'time_record':opened and project is not None and global_caps['time_record'],
        'billing_prepare':opened and row.state=='approved' and row.approved_work_revision==row.work_revision
            and invoice_command is None and global_caps['billing_prepare'],
        'billing_view':global_caps['billing_view'],
        'payments_record':False,'invoice_issue':False}
    # Native action-specific PMS rights can only narrow visible controls.
    if flags['time_record']:
        try:
            project_for_action(db,actor,project.id,'log_time')
        except HTTPException as exc:
            if exc.status_code not in {403,404}:raise
            flags['time_record']=False
    if flags['documents_upload']:
        try:
            project_for_action(db,actor,project.id,'upload')
        except HTTPException as exc:
            if exc.status_code not in {403,404}:raise
            flags['documents_upload']=False
    invoice=None
    if invoice_command is not None and global_caps['billing_view']:
        native=invoice_for(db,invoice_command.result['invoice_id'],actor)
        invoice={'id':native.id,'status':native.status}
        flags['payments_record']=global_caps['payments_record'] and native.status not in {'draft','pending_approval','cancelled'} and native.balance_amount>0
        if native.status in {'draft','pending_approval'} and global_caps['billing_prepare']:
            from app.access.service import check_background_access
            try:
                require(actor,'srm_invoice_approve','srm_admin')
                check_background_access(db,actor,'srm','approve',administrative_read=False,stamp=False)
                flags['invoice_issue']=True
            except HTTPException as exc:
                if exc.status_code!=403:raise
    return {'project':{'id':project.id,'name':project.name,'currency':project.currency} if project else None,
        'engagement_status':engagement.status,'capabilities':flags,'invoice':invoice}
