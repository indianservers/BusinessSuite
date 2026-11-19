"""Durable exports and opt-in owner-only digests on the existing worker loop."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import hashlib
import os

from fastapi import HTTPException
from app.apps.srm.reporting_models import SRMReportJob as Job, SRMReportSchedule as Schedule
from app.models.user import User
from app.models.notification import Notification
from app.core.config import settings
from app.access.service import activate_run_context,release_run_context,background_scope
from . import reporting as reports


def aware(value):return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def export_directory():
    return Path(settings.UPLOAD_DIR)/'report_exports'


@contextmanager
def owner_scope(db,row,action='export'):
    user=db.query(User).filter_by(id=row.owner_id,is_active=True).populate_existing().first()
    if not user:raise HTTPException(403,'Report owner is unavailable')
    activate_run_context(db,user,SimpleNamespace(scope_key=f'company:{row.organization_id}'))
    try:
        with background_scope(db,user,'srm',action,branch_id=row.branch_id):
            from app.apps.srm.access import has_any_permission
            if not has_any_permission(user,{'srm_view','srm_invoice_view','srm_collection_view','srm_profitability_view','srm_admin'}):raise HTTPException(403,'Report access revoked')
            from app.business_packs.access import resolve_context
            selected=resolve_context(db,user,db.info['branch_context'])
            if selected is not None:raise HTTPException(409,'Native reporting scope is no longer available')
            from app.business_packs.legacy_boundary import install
            cleanup=install(db,user,row.organization_id)
            try:yield user
            finally:cleanup()
    finally:release_run_context(db)


def prepare_job(identity,route=None):
    from app.db.session import SessionLocal
    from app.db.tenant import current_tenant
    token=current_tenant.set(route) if route is not None else None
    try:
        with SessionLocal() as db:
            row=db.query(Job).filter_by(id=identity,status='queued').with_for_update(skip_locked=True).first()
            if not row:return
            row.status='running';db.commit()
            try:
                with owner_scope(db,row) as user:
                    from .reporting_exports import collect,render,fingerprint
                    data=collect(db,user,row.report,reports.Filters.model_validate(row.filters_json),row.columns_json)
                    content=render(data,row.format);digest=hashlib.sha256(content).hexdigest()
                    directory=export_directory();directory.mkdir(parents=True,exist_ok=True)
                    filename=f'{uuid4().hex}-{digest}.{row.format}';pending=directory/(filename+'.pending')
                    pending.write_bytes(content);os.replace(pending,directory/filename)
                    row.file_path=filename;row.content_sha256=fingerprint(data);row.row_count=len(data['items'])
                    row.status='ready';row.completed_at=datetime.now(timezone.utc);row.error=None
                    db.commit()
            except Exception as error:
                db.rollback();row=db.get(Job,identity)
                row.status='failed';row.completed_at=datetime.now(timezone.utc)
                row.error=error.detail if isinstance(error,HTTPException) and isinstance(error.detail,str) else 'Report preparation failed. Check access and filters, then request a fresh export.'
                db.commit()
    finally:
        if token is not None:current_tenant.reset(token)


def outbox_allowed(db,outbox):
    try:
        identity=int(outbox.event_key.split(':')[1]);row=db.get(Schedule,identity)
        if not row or not row.enabled or row.owner_id!=outbox.recipient_user_id or row.organization_id!=outbox.organization_id or 'email' not in row.config_json.get('channels',[]):return False
        with owner_scope(db,row):return True
    except Exception:return False


def schedule_filters(db,user,config,now):
    from zoneinfo import ZoneInfo
    today=now.astimezone(ZoneInfo(config['timezone'])).date()
    period=config.get('period','yesterday');end=today-timedelta(days=1) if period=='yesterday' else today
    start=end-timedelta(days=6) if period=='last7days' else end
    return reports.Filters(start=start,end=end,include_test=config.get('include_test',False),warehouse_id=config.get('warehouse_id'))


def notify(db,row,user,title,message,event_key):
    channels=row.config_json.get('channels',['in_app'])
    if 'in_app' in channels:
        # Link-only notifications avoid retaining private report rows outside the
        # current owner's authorized reporting surface.
        prior=db.query(Notification.id).filter_by(company_id=row.organization_id,user_id=user.id,event_type=event_key).first()
        if not prior:
            db.add(Notification(company_id=row.organization_id,user_id=user.id,title=title,message=message,
                module='srm',event_type=event_key,related_entity_type='report_schedule',related_entity_id=row.id,
                action_url='/srm/reports?report=stock&low=1' if 'stock' in title.lower() else '/srm/reports?summary=latest',channels=['in_app'],priority='high' if 'stock' in title.lower() else 'normal'))
    if 'email' in channels:
        from app.services.email_dispatch import queue_email,user_can_receive
        if not user_can_receive(db,user.id,user.email,row.organization_id):raise HTTPException(403,'Recipient unavailable')
        queue_email(db,recipient=user.email,user_id=user.id,organization_id=row.organization_id,module='srm',
            event_key=f'srm-report:{row.id}:{event_key}',subject=title,
            body='Your report is ready. Sign in to review current authorized figures:\n'+settings.FRONTEND_PUBLIC_URL.rstrip('/')+'/srm/reports',source_record=row)


def run_schedule(db,row,now):
    from app.services.domain_report_delivery import next_occurrence
    with owner_scope(db,row) as user:
        config=row.config_json;state=dict(row.state_json or {})
        f=schedule_filters(db,user,config,now)
        next_digest=datetime.fromisoformat(state.get('next_digest_at')) if state.get('next_digest_at') else now
        if config.get('digest',True) and aware(next_digest)<=now:
            digest=reports.overview(db,user,reports.resolved(db,user,f))
            # Durable owner-scoped summary; external email contains only a link.
            state['last_digest']={'period':digest['filters'],'totals':digest['items'],'generated_at':now.isoformat()}
            notify(db,row,user,'Your Sales summary is ready','Open Reports to review sales, collections, returns and outstanding balances.',f'digest:{row.id}:{int(next_digest.timestamp())}')
            next_digest=next_occurrence(config,now);state['next_digest_at']=next_digest.isoformat()
        if config.get('watch_low_stock',True):
            last_stock=datetime.fromisoformat(state['last_stock_check']) if state.get('last_stock_check') else None
            if last_stock is None or now-aware(last_stock)>=timedelta(minutes=5):
                alert_filters=f.model_copy(update={'low_only':True})
                current=reports.low_stock_ids(db,user,reports.resolved(db,user,alert_filters));previous=set(state.get('low_ids',[]))
                new=current-previous;recovered=previous-current
                if new:
                    notify(db,row,user,f'Low stock: {len(new)} new items need attention','Open Reports → Stock & reorder planning to review quantities and receive stock.',f'low:{row.id}:{int(now.timestamp())}')
                if recovered:
                    notify(db,row,user,f'Stock replenished: {len(recovered)} alerts cleared','Replenished items have left your low-stock list.',f'recovered:{row.id}:{int(now.timestamp())}')
                state.update(low_ids=sorted(current),last_stock_check=now.isoformat(),low_stock_count=len(current))
        row.state_json=state;row.last_run_at=now;row.last_error=None
        row.next_run_at=(min(aware(next_digest),now+timedelta(minutes=5)) if config.get('digest',True) else now+timedelta(minutes=5)) if config.get('watch_low_stock',True) else next_digest
        db.commit()


def dispatch(db,now=None,limit=3):
    """Called by the existing authenticated email/cron worker; disabled by default."""
    now=now or datetime.now(timezone.utc)
    from app.db.tenant import current_tenant
    pending=[identity for identity, in db.query(Job.id).filter(Job.status=='queued',Job.expires_at>now).order_by(Job.id).limit(limit).all()]
    db.rollback()
    for identity in pending:prepare_job(identity,current_tenant.get())
    count=0
    for _ in range(limit):
        row=db.query(Schedule).filter(Schedule.enabled.is_(True),Schedule.next_run_at<=now).order_by(Schedule.next_run_at,Schedule.id).with_for_update(skip_locked=True).first()
        if not row:break
        identity=row.id
        try:run_schedule(db,row,now)
        except Exception:
            db.rollback();row=db.get(Schedule,identity);row.enabled=False;row.last_error='Report, branch, recipient or owner access is unavailable. Review and save the schedule to resume.';db.commit()
        count+=1
    # Interrupted read-only exports are recoverable; no financial handler is replayed.
    for row in db.query(Job).filter(Job.status=='running',Job.created_at<now-timedelta(minutes=15)).limit(3):
        row.status='failed';row.error='The worker was interrupted. Request a new export.'
    for row in db.query(Job).filter(Job.expires_at<=now,Job.file_path.is_not(None)).limit(10):
        path=export_directory()/row.file_path
        if path.resolve().parent==export_directory().resolve():path.unlink(missing_ok=True)
        row.file_path=None;row.status='expired'
    db.commit()
    return {'exports':len(pending),'schedules':count}
