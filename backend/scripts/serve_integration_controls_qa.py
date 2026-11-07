"""Loopback-only integration UI QA with synthetic records and no external delivery."""
import os
import httpx
import serve_project_portfolio_qa as fixture

attempts = 0
def local_receiver(url, **kwargs):
    global attempts
    if url != 'https://integration-audit.invalid/webhook':
        raise RuntimeError('External webhook delivery is disabled in this QA fixture')
    attempts += 1
    return httpx.Response(503 if attempts == 1 else 200, text='Synthetic receiver unavailable' if attempts == 1 else 'Synthetic receiver accepted')
fixture.qa.app.state.integration_audit_receiver = True
httpx.post = local_receiver

# Exercise the real sync engine with the same deterministic provider used by tests.
from datetime import datetime, timedelta, timezone
from app.apps.crm import calendar_sync_api
from app.apps.crm.calendar_sync import sync_connection as real_sync
from app.apps.crm.google_calendar import store_tokens
from app.apps.crm.models import CRMCalendarIntegration, CRMMeeting
from tests.test_calendar_sync import FakeTransport
remote = {}
def simulated_sync(db, identity, **kwargs):
    return real_sync(db, identity, transport_factory=lambda row, persist: FakeTransport(row, persist, remote), **kwargs)
calendar_sync_api.sync_connection = simulated_sync
with fixture.qa.SessionLocal() as db:
    actor = db.query(fixture.qa.User).filter_by(email='admin@suiteqa.example.com').one()
    connection = CRMCalendarIntegration(organization_id=1, user_id=actor.id, provider='google', is_active=True, created_by_user_id=actor.id)
    store_tokens(connection, {'access_token':'synthetic-provider-token', 'refresh_token':'synthetic-refresh-token'})
    start = datetime.now(timezone.utc) + timedelta(days=1)
    event = CRMMeeting(organization_id=1, owner_user_id=actor.id, title='Synthetic calendar sync check', start_time=start, end_time=start+timedelta(hours=1), status='Scheduled', created_by_user_id=actor.id)
    db.add_all([connection,event]);db.flush()
    from test_identity_utils import own_workflow_records
    own_workflow_records(db, connection, event)
    db.commit()

if __name__ == '__main__':
    import uvicorn
    try:
        uvicorn.run(fixture.qa.app, host='127.0.0.1', port=int(os.environ.get('PROJECTS_QA_PORT', '1586')), log_level='warning')
    finally:
        fixture.qa.engine.dispose()
        fixture.qa.temporary.cleanup()
