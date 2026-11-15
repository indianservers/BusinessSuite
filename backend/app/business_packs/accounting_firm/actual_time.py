"""Explicit worked time through the canonical native PMS creation operation."""
from app.apps.srm.models import SRMEngagement
from app.apps.project_management.schemas import PMSTimeLogCreate
from app.business_packs.common_core import _native_authority
from . import service
from .models import AccountsCommand
from .pms_sources import create_actual_time, project_for_action


def record(ident, data, db, actor, *, commit=True):
    scope = service.authority(db, actor, 'time.record', write=True)
    epoch = _native_authority(db, actor, scope.company_id)
    service.lock_tenant(db, actor)
    service.authority(db, actor, 'time.record', write=True)
    if epoch != _native_authority(db, actor, scope.company_id):
        service.fail('Native time authority changed while waiting')
    row = service.record(db, actor, scope, ident)
    engagement = db.get(SRMEngagement, row.engagement_id)
    if engagement.pms_project_id is None:
        service.fail('Link a canonical PMS delivery project before recording actual time', 409)
    project_for_action(db, actor, engagement.pms_project_id, 'log_time')
    old = service.replay(db, actor, scope, 'time.record', ident, data)
    if old is not None:
        return old
    service.source(db, actor, scope, row.engagement_id, row.client_id, require_open=True)
    if row.revision != data.expected_revision:
        service.fail('Period changed; reload its current revision', 409)
    from app.services.metrics.queries import business_day
    if not row.starts_on <= data.log_date <= min(row.ends_on, business_day(db, actor)):
        service.fail('Record actual work within this service period and no later than today', 422)
    if not data.description.strip():
        service.fail('Describe the actual work performed', 422)
    with db.begin_nested():
        result = create_actual_time(db, actor, engagement.pms_project_id, PMSTimeLogCreate(
            project_id=engagement.pms_project_id, log_date=data.log_date, duration_minutes=data.duration_minutes,
            description=data.description.strip(), is_billable=False, approval_status='Pending'))
        db.add(AccountsCommand(**service.fields(scope, actor), period_id=row.id, request_key=str(data.request_key),
            request_sha256=service.fingerprint('time.record', ident, data), action='time.record', reason='', result=result))
        db.flush()
    if commit:
        db.commit()
    return result
