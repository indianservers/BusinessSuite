from tests.rich_text_test_utils import organization_context
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib

import pytest
from sqlalchemy import create_engine, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.apps.crm.models import CRMCalendarIntegration, CRMMeeting
from app.apps.crm.calendar_sync_models import CalendarSyncState, CalendarEventLink
from app.apps.crm.calendar_sync import sync_connection, state_for, run_due, bind_account
from app.apps.crm.calendar_transport import CalendarSyncError, remote_value
from app.apps.crm.google_calendar import store_tokens, cipher
from app.apps.project_management.models import PMSCalendarEvent
from app.models.user import User

UTC = timezone.utc


class FakeTransport:
    """Stateful provider simulator; tests exercise the real engine, DB checkpoints and leases."""
    def __init__(self, connection, persist, remote):
        self.integration, self.persist, self.remote = connection, persist, remote
        self.provider = connection.provider

    def close(self): pass

    def identity(self, module, local_id):
        local_key = str(local_id) if module == "crm" else f"pms:{local_id}"
        return hashlib.sha256(f"business-suite:{self.integration.organization_id}:{self.integration.id}:{local_key}".encode()).hexdigest()

    def get(self, key):
        return deepcopy(self.remote.get(key))

    def changes(self, cursor, start, end):
        # Deliberately repeat events, as retries/delta feeds may do.
        yield list(deepcopy(self.remote).values()), "checkpoint-1", True

    def find(self, module, local_id, key=None):
        return self.get(key or self.identity(module, local_id))

    def write(self, module, local_id, value, event_id=None, etag=None, create_key=None):
        key = event_id or create_key or self.identity(module, local_id)
        if value.get("deleted"):
            event = {"id": key, "status": "cancelled"}
        elif self.provider == "google":
            event = {"id": key, "summary": value["title"], "description": value["description"], "location": value["location"],
                     "start": {"dateTime": value["start"]}, "end": {"dateTime": value["end"]}, "etag": str(datetime.now(UTC)),
                     "extendedProperties": {"private": {"businessSuiteKey": self.identity(module, local_id)}}}
        else:
            event = {"id": key, "subject": value["title"], "body": {"content": value["description"]},
                     "location": {"displayName": value["location"]}, "start": {"dateTime": value["start"], "timeZone": "UTC"},
                     "end": {"dateTime": value["end"], "timeZone": "UTC"}, "@odata.etag": str(datetime.now(UTC)),
                     "transactionId": self.identity(module, local_id)}
        self.remote[key] = event
        return deepcopy(event)


@pytest.fixture(params=["google", "outlook"])
def setup(db, superuser_headers, request):
    user = db.query(User).filter_by(is_superuser=True).first()
    connection = CRMCalendarIntegration(user_id=user.id, organization_id=1, provider=request.param, is_active=True)
    store_tokens(connection, {"access_token": "test", "refresh_token": "refresh"})
    db.add(connection); db.commit()
    remote = {}
    factory = lambda row, persist: FakeTransport(row, persist, remote)
    def tick():
        return sync_connection(db, connection.id, force=True, transport_factory=factory)
    return user, connection, remote, factory, tick


def meeting(db, user, title="Sales call", organization=1):
    start = datetime.now(UTC) + timedelta(days=1)
    row = CRMMeeting(owner_user_id=user.id, organization_id=organization, title=title, description="Agenda", location="Office",
                     start_time=start, end_time=start+timedelta(hours=1), status="Scheduled")
    db.add(row); db.commit()
    return row


def change(remote, provider, title):
    remote["summary" if provider == "google" else "subject"] = title


def test_crm_roundtrip_updates_deletion_and_restart_idempotency(db, setup):
    user, connection, remote, _, tick = setup
    row = meeting(db, user)
    assert tick()["exported"] == 1
    link = db.query(CalendarEventLink).one()
    assert cipher().decrypt(db.get(CalendarSyncState, connection.id).cursor_encrypted.encode()) == b"checkpoint-1"
    assert tick()["exported"] == 0
    assert len(remote) == 1
    change(remote[link.remote_id], connection.provider, "Calendar edit")
    assert tick()["imported"] == 1
    db.refresh(row); assert row.title == "Calendar edit"
    row.title = "Local edit"; db.commit()
    assert tick()["exported"] == 1
    assert remote_value(connection.provider, remote[link.remote_id])["title"] == "Local edit"
    remote[link.remote_id] = {"id": link.remote_id, "status": "cancelled"}
    assert tick()["imported"] == 1
    db.refresh(row); assert row.deleted_at and row.status == "Cancelled"
    assert tick()["exported"] == 0
    assert db.query(CRMMeeting).count() == 1


def test_pms_import_and_local_hard_delete_propagate(db, setup):
    _, connection, remote, factory, tick = setup
    state_for(db, connection).import_target = "pms"; db.commit()
    fake = factory(connection, lambda: None)
    start = datetime.now(UTC) + timedelta(days=1)
    fake.write("crm", 9999, {"title": "External", "description": "Notes", "location": "Office",
                             "start": start.isoformat(), "end": (start+timedelta(hours=1)).isoformat()})
    assert tick()["imported"] == 1
    event = db.query(PMSCalendarEvent).one()
    assert event.visibility == "private" and event.owner_id == connection.user_id
    assert db.query(CRMMeeting).count() == 0
    assert tick()["exported"] == 0  # Plain provider location is not erased by the planner's URL field.
    event.title = "Planner edit"; db.commit()
    assert tick()["exported"] == 1
    assert remote_value(connection.provider, next(iter(remote.values())))["location"] == "Office"
    db.delete(event); db.commit()
    assert tick()["exported"] == 1
    assert next(iter(remote.values()))["status"] == "cancelled"
    assert tick()["imported"] == 0


@pytest.mark.parametrize("keep", ["local", "remote"])
def test_conflicts_preserve_both_versions_then_resolve(db, setup, keep):
    user, connection, remote, _, tick = setup
    row = meeting(db, user); tick()
    link = db.query(CalendarEventLink).one()
    row.title = "Local changed"; db.commit()
    change(remote[link.remote_id], connection.provider, "Remote changed")
    assert tick()["conflicts"] == 1
    db.refresh(row); assert row.title == "Local changed"
    db.refresh(link); assert link.conflict and link.conflict_remote
    assert tick()["exported"] == 0
    link.resolution = keep; db.commit(); tick()
    db.refresh(row); db.refresh(link)
    assert row.title == ("Local changed" if keep == "local" else "Remote changed")
    assert not link.conflict


def test_remote_delete_conflict_can_keep_local(db, setup):
    user, connection, remote, _, tick = setup
    row = meeting(db, user); tick()
    link = db.query(CalendarEventLink).one(); old_id = link.remote_id
    row.title = "Keep this"; db.commit()
    remote[old_id] = {"id": old_id, "status": "cancelled"}
    assert tick()["conflicts"] == 1
    link.resolution = "local"; db.commit()
    assert tick()["exported"] == 1
    db.refresh(link)
    assert link.remote_id != old_id and not link.conflict
    assert tick()["exported"] == 0
    assert db.query(CRMMeeting).count() == 1


def test_isolation_pause_lease_and_retry_state(db, setup):
    user, connection, remote, factory, tick = setup
    meeting(db, user, "Other organization", organization=99)
    other = User(email="other-sync@example.test", hashed_password="unused", is_active=True)
    db.add(other); db.commit(); meeting(db, other, "Other user")
    assert tick()["exported"] == 0 and not remote
    state = db.get(CalendarSyncState, connection.id)
    state.enabled = False; state.next_run_at = None; db.commit()
    assert sync_connection(db, connection.id, transport_factory=factory) == {"skipped": True}
    state.lease_owner = "other-process"; state.lease_until = datetime.now(UTC)+timedelta(minutes=5); db.commit()
    assert tick() == {"skipped": True}
    state.lease_until = datetime.now(UTC)-timedelta(seconds=1); db.commit()
    class Failed(FakeTransport):
        def changes(self, *args):
            raise CalendarSyncError("Rate limited", retry_after=120)
    result = sync_connection(db, connection.id, force=True, transport_factory=lambda r,p: Failed(r,p,remote))
    assert result["error"] == "Rate limited"
    db.refresh(state)
    assert state.failures == 1 and state.lease_owner is None and state.next_run_at


def test_invalid_checkpoint_resets_without_forgetting_mappings(db, setup):
    user, connection, remote, _, tick = setup
    meeting(db, user); tick()
    class Expired(FakeTransport):
        def changes(self, *args):
            raise CalendarSyncError("Expired", reset=True)
    sync_connection(db, connection.id, force=True, transport_factory=lambda r,p: Expired(r,p,remote))
    assert db.get(CalendarSyncState, connection.id).cursor_encrypted is None
    assert db.query(CalendarEventLink).count() == 1
    assert tick()["exported"] == 0
    assert db.query(CRMMeeting).count() == 1


def test_sync_api_controls_and_cross_user_access(client, db, superuser_headers, monkeypatch):
    user = db.query(User).filter_by(is_superuser=True).first()
    connection = CRMCalendarIntegration(user_id=user.id, organization_id=1, provider="google", is_active=True)
    store_tokens(connection, {"access_token":"token","refresh_token":"refresh"})
    db.add(connection); db.commit()
    base = f"/api/v1/crm/calendar-integrations/{connection.id}"
    other = User(email="api-other@example.test", hashed_password="unused", is_active=True)
    db.add(other); db.commit()
    from app.core.deps import get_current_user
    client.app.dependency_overrides[get_current_user] = lambda: other
    try:
        assert client.get(base+"/sync", headers=superuser_headers).status_code == 404
    finally:
        client.app.dependency_overrides.pop(get_current_user, None)
    response = client.put(base+"/sync", headers=superuser_headers, json={"enabled":False,"import_target":"pms"})
    assert response.status_code == 200, response.text
    assert response.json()["enabled"] is False and response.json()["importTarget"] == "pms"
    assert client.get('/api/v1/project-management/planner/connections',headers=superuser_headers).status_code == 200
    monkeypatch.setattr("app.apps.crm.calendar_sync_api.sync_connection", lambda *args,**kwargs:{"imported":1,"exported":2,"conflicts":0})
    assert client.post(base+"/sync",headers=superuser_headers).json()["imported"] == 1


def test_account_switch_rejected_without_destroying_old_mappings(db, setup, monkeypatch):
    _, connection, _, _, _ = setup
    state = state_for(db, connection); state.account_key = "existing"; db.commit()
    monkeypatch.setattr("app.apps.crm.calendar_sync.account_identity", lambda *args: "different")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        bind_account(db, connection, {"access_token":"new-account-token"})
    assert error.value.status_code == 409


def test_sync_schema_upgrade_is_repeatable():
    from app.apps.crm.calendar_sync_schema import upgrade, downgrade
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE calendar_integrations (id INTEGER PRIMARY KEY)")
        op = Operations(MigrationContext.configure(connection))
        upgrade(op); upgrade(op)
        assert "calendar_event_links" in inspect(connection).get_table_names()
        downgrade(op)
        assert "calendar_event_links" not in inspect(connection).get_table_names()


def test_changes_bridge_both_calendars_through_one_local_record(db, superuser_headers):
    user = db.query(User).filter_by(is_superuser=True).first()
    stores, connections = {}, {}
    for provider in ("google", "outlook"):
        row = CRMCalendarIntegration(user_id=user.id, organization_id=1, provider=provider, is_active=True)
        store_tokens(row, {"access_token":"token","refresh_token":"refresh"})
        db.add(row); db.commit()
        connections[provider], stores[provider] = row, {}
    factory = lambda row,persist: FakeTransport(row,persist,stores[row.provider])
    def tick(provider):
        result = sync_connection(db,connections[provider].id,force=True,transport_factory=factory)
        assert "error" not in result, result
        return result
    now = datetime.now(UTC)+timedelta(days=1)
    factory(connections["google"],lambda:None).write("crm",9999,{"title":"From Google","description":"","location":"",
        "start":now.isoformat(),"end":(now+timedelta(hours=1)).isoformat()})
    assert tick("google")["imported"] == 1
    assert tick("outlook")["exported"] == 1
    assert db.query(CRMMeeting).count() == 1
    remote_outlook = next(iter(stores["outlook"].values()))
    remote_outlook["subject"] = "Edited in Outlook"
    assert tick("outlook")["imported"] == 1
    assert tick("google")["exported"] == 1
    assert db.query(CRMMeeting).one().title == "Edited in Outlook"
    remote_google = next(iter(stores["google"]))
    stores["google"][remote_google] = {"id":remote_google,"status":"cancelled"}
    assert tick("google")["imported"] == 1
    assert tick("outlook")["exported"] == 1
    assert db.query(CRMMeeting).count() == 1


def test_background_worker_runs_and_stops(monkeypatch):
    import threading
    from contextlib import contextmanager
    from app.apps.crm import calendar_sync
    called = threading.Event()
    @contextmanager
    def session():
        yield object()
    monkeypatch.setattr("app.db.session.SessionLocal",session)
    monkeypatch.setattr("app.db.tenant.run_for_company_databases",lambda callback:callback())
    monkeypatch.setattr(calendar_sync,"run_due",lambda db:called.set())
    stop, thread = calendar_sync.start_worker()
    try:
        assert called.wait(3)
    finally:
        stop.set(); thread.join(timeout=3)
    assert not thread.is_alive()
