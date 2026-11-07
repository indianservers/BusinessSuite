"""Restart-safe two-way calendar synchronization for Sales/CRM and PMS."""
import logging
import hashlib
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import or_, update

from app.core.config import settings
from app.models.user import User
from app.module_registry import is_app_enabled
from .models import CRMCalendarIntegration, CRMMeeting
from .calendar_sync_models import CalendarSyncState, CalendarEventLink
from .calendar_transport import CalendarTransport, CalendarSyncError, iso, remote_value, PROPERTY
from .google_calendar import cipher

UTC = timezone.utc
logger = logging.getLogger(__name__)


def organization(user):
    from app.apps.srm.services.commercial import tenant
    return tenant(user)


def state_for(db, connection):
    state = db.get(CalendarSyncState, connection.id)
    if state is None:
        # Serialize initialization, including worker/manual first-run races.
        db.query(CRMCalendarIntegration).filter_by(id=connection.id).with_for_update().first()
        state = db.get(CalendarSyncState, connection.id, populate_existing=True)
        if state is None:
            state = CalendarSyncState(integration_id=connection.id, enabled=True,
                                      import_target="crm" if is_app_enabled("crm") else "pms")
            db.add(state)
            db.flush()
    return state


def account_identity(provider, token):
    import httpx
    from fastapi import HTTPException
    url = "https://openidconnect.googleapis.com/v1/userinfo" if provider == "google" else "https://graph.microsoft.com/v1.0/me?$select=id"
    try:
        response = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
        if response.status_code != 200:
            raise ValueError()
        identity = response.json().get("sub" if provider == "google" else "id")
        if not identity:
            raise ValueError()
    except (httpx.RequestError, ValueError):
        raise HTTPException(400, "Calendar account identity could not be verified. Reconnect and grant the requested permissions.") from None
    return hashlib.sha256(f"{provider}:{identity}".encode()).hexdigest()


def bind_account(db, connection, tokens):
    from fastapi import HTTPException
    key = account_identity(connection.provider, tokens["access_token"])
    db.flush()
    state = state_for(db, connection)
    if state.account_key and state.account_key != key:
        raise HTTPException(409, "This connection belongs to another calendar account. Disconnect it before switching accounts.")
    state.account_key, state.next_run_at = key, None


def status(db, connection):
    state = db.get(CalendarSyncState, connection.id)
    conflicts = db.query(CalendarEventLink).filter_by(integration_id=connection.id, conflict=True).count()
    return {"enabled": state.enabled if state else True, "importTarget": state.import_target if state else "crm",
            "lastSyncedAt": state.last_synced_at if state else None, "nextRunAt": state.next_run_at if state else None,
            "lastError": state.last_error if state else None, "conflicts": conflicts,
            "counts": state.counts if state else {}, "intervalSeconds": settings.CALENDAR_SYNC_INTERVAL_SECONDS,
            "workerEnabled": settings.CALENDAR_SYNC_WORKER_ENABLED and not settings.SERVERLESS}


def local_query(db, connection, module):
    if module == "crm":
        return db.query(CRMMeeting).filter_by(organization_id=connection.organization_id, owner_user_id=connection.user_id)
    from app.apps.project_management.models import PMSCalendarEvent
    return db.query(PMSCalendarEvent).filter_by(owner_id=connection.user_id)


def local_value(record, module):
    if record is None or (module == "crm" and (record.deleted_at or str(record.status).lower() in ("cancelled", "canceled"))):
        return {"deleted": True}
    return {"title": record.title, "description": record.description or "",
            "location": (record.location if module == "crm" else record.meeting_url) or "",
            "start": iso(record.start_time if module == "crm" else record.start_at),
            "end": iso(record.end_time if module == "crm" else record.end_at), "deleted": False}


def comparable(value):
    return {k: v for k, v in value.items() if k != "all_day"}


def restore_key(transport, link):
    return transport.identity(link.module, f"{link.local_id}:restore:{link.remote_id}")


def apply_remote(db, connection, module, record, value):
    if value.get("deleted"):
        if record is not None:
            if module == "crm":
                record.status = "Cancelled"
                record.deleted_at = datetime.now(UTC)
                record.updated_by_user_id = connection.user_id
            else:
                db.delete(record)
        return record
    start, end = (datetime.fromisoformat(value[key]) for key in ("start", "end"))
    if end <= start:
        raise CalendarSyncError("An external event has invalid dates. Correct its dates and retry.")
    if record is None:
        if module == "crm":
            record = CRMMeeting(organization_id=connection.organization_id, owner_user_id=connection.user_id,
                                created_by_user_id=connection.user_id)
        else:
            from app.apps.project_management.models import PMSCalendarEvent
            record = PMSCalendarEvent(owner_id=connection.user_id, visibility="private", kind="meeting", timezone="UTC", revision=1)
        db.add(record)
    record.title = value["title"][:180 if module == "crm" else 220]
    record.description = value["description"]
    if module == "crm":
        record.location = value["location"][:240]
        record.start_time, record.end_time = start, end
        record.status, record.deleted_at = "Scheduled", None
        record.updated_by_user_id = connection.user_id
    else:
        # The planner stores a join URL, not arbitrary locations; preserve plain locations in the link.
        from urllib.parse import urlparse
        url = urlparse(value["location"])
        record.meeting_url = value["location"][:2000] if url.scheme == "https" and url.hostname and not url.username and not url.password else ""
        record.start_at, record.end_at = start, end
        record.revision = (record.revision or 0) + 1
    db.flush()
    return record


def remember(link, record, remote, provider, local_snapshot=None):
    value = remote_value(provider, remote) if remote else {"deleted": True}
    link.local_snapshot = local_snapshot if local_snapshot is not None else local_value(record, link.module)
    link.remote_snapshot = value
    link.remote_etag = (remote or {}).get("etag") or (remote or {}).get("@odata.etag")
    link.remote_metadata = {"all_day": value.get("all_day", False)}
    link.deleted = bool(value.get("deleted"))
    link.conflict, link.conflict_remote, link.resolution = False, None, None
    link.last_synced_at = datetime.now(UTC)
    if record is not None and link.module == "crm":
        record.sync_status = "synced"
        record.external_provider, record.external_event_id = provider, link.remote_id[:180]
        record.last_synced_at = link.last_synced_at


def reconcile(db, transport, connection, link, remote, counts):
    if hasattr(transport, "token"):
        transport.token()
    # Lock the owned record while reading and applying a change. Other tenants' IDs are never loaded.
    record = local_query(db, connection, link.module).filter_by(id=link.local_id).populate_existing().with_for_update().first()
    local = local_value(record, link.module)
    external = remote_value(connection.provider, remote) if remote else {"deleted": True}
    local_changed = local != link.local_snapshot
    remote_changed = external != link.remote_snapshot
    if comparable(local) == comparable(external):
        remember(link, record, remote, connection.provider)
        return
    if link.resolution == "local":
        local_changed, remote_changed = True, False
    elif link.resolution == "remote":
        local_changed, remote_changed = False, True
    elif link.conflict:
        link.conflict_remote = remote or {"id": link.remote_id, "status": "cancelled"}
        return
    if local_changed and remote_changed:
        link.conflict = True
        link.conflict_remote = remote or {"id": link.remote_id, "status": "cancelled"}
        counts["conflicts"] += 1
        return
    if remote_changed:
        # A hard-deleted local event must never be resurrected by remote edits without review.
        if record is None and not external.get("deleted") and link.resolution != "remote":
            link.conflict, link.conflict_remote = True, remote
            counts["conflicts"] += 1
            return
        record = apply_remote(db, connection, link.module, record, external)
        if record is not None and not external.get("deleted"):
            link.local_id = record.id
        if external.get("deleted") and link.module == "pms":
            record = None
        remember(link, record, remote, connection.provider)
        counts["imported"] += 1
    elif local_changed:
        if external.get("deleted") and not local.get("deleted"):
            if link.resolution == "local":
                key = restore_key(transport, link)
                value = {**local, "all_day": link.remote_metadata.get("all_day", False)}
                restored = transport.find(link.module, link.local_id, key) or transport.write(
                    link.module, link.local_id, value, create_key=key)
                link.remote_id = restored["id"]
                remember(link, record, restored, connection.provider, local)
                counts["exported"] += 1
                return
            link.conflict, link.conflict_remote = True, remote or {"id": link.remote_id, "status": "cancelled"}
            counts["conflicts"] += 1
            return
        value = {**local, "all_day": link.remote_metadata.get("all_day", False)}
        value["preserve_schedule"] = all(local.get(k) == link.local_snapshot.get(k) for k in ("start", "end"))
        # Do not erase provider locations that the PMS join-link field cannot represent.
        if link.module == "pms" and local.get("location") == link.local_snapshot.get("location"):
            value["location"] = link.remote_snapshot.get("location", "")
        try:
            result = transport.write(link.module, link.local_id, value, link.remote_id,
                                     (remote or {}).get("etag") or (remote or {}).get("@odata.etag") or link.remote_etag)
        except CalendarSyncError as exc:
            if not exc.conflict:
                raise
            link.conflict = True
            link.conflict_remote = transport.get(link.remote_id) or {"id": link.remote_id, "status": "cancelled"}
            counts["conflicts"] += 1
            return
        # DELETE responses have no event body; patch/create responses are complete provider events.
        remember(link, record, result, connection.provider, local)
        counts["exported"] += 1


def sync_connection(db, connection_id, *, force=False, transport_factory=CalendarTransport):
    """Background work earns the same company and branch scope as an HTTP request."""
    if db.info.get("branch_context") is not None:
        return _sync_connection(db, connection_id, force=force, transport_factory=transport_factory)
    from contextlib import ExitStack
    from app.branches.models import BranchOwnership
    from app.branches.service import context
    from app.branches.boundary import install as install_branch
    from app.core.tenant_boundary import install as install_tenant
    connection = db.get(CRMCalendarIntegration, connection_id)
    if not connection or not connection.is_active or connection.deleted_at:
        return {"skipped": True}
    user = db.get(User, connection.user_id)
    if not user or not user.is_active or organization(user) != connection.organization_id:
        return {"skipped": True}
    branch = db.query(BranchOwnership).filter_by(resource_table="calendar_integrations", resource_key=str(connection_id),
                                                company_id=connection.organization_id).first()
    if not branch:
        return {"error": "Calendar branch ownership is unresolved. Reconnect from the intended branch."}
    with ExitStack() as stack:
        ctx = context(db, user, connection.organization_id, str(branch.branch_id))
        stack.callback(install_tenant(db, user, connection.organization_id))
        stack.callback(install_branch(db, user, ctx))
        return _sync_connection(db, connection_id, force=force, transport_factory=transport_factory)


def _sync_connection(db, connection_id, *, force=False, transport_factory=CalendarTransport):
    connection = db.get(CRMCalendarIntegration, connection_id)
    if not connection or not connection.is_active or connection.deleted_at or connection.provider not in ("google", "outlook"):
        return {"skipped": True}
    user = db.get(User, connection.user_id)
    if not user or not user.is_active or organization(user) != connection.organization_id:
        return {"skipped": True}
    state = state_for(db, connection)
    db.commit()
    now, owner = datetime.now(UTC), str(uuid4())
    conditions = [CalendarSyncState.integration_id == connection_id,
                  or_(CalendarSyncState.lease_until.is_(None), CalendarSyncState.lease_until < now)]
    if not force:
        conditions += [CalendarSyncState.enabled.is_(True),
                       or_(CalendarSyncState.next_run_at.is_(None), CalendarSyncState.next_run_at <= now)]
    claimed = db.execute(update(CalendarSyncState).where(*conditions).values(lease_owner=owner, lease_until=now + timedelta(minutes=5)))
    db.commit()
    if not claimed.rowcount:
        return {"skipped": True}
    state = db.get(CalendarSyncState, connection_id, populate_existing=True)
    counts = {"imported": 0, "exported": 0, "conflicts": 0}

    def checkpoint():
        # Validate lease and disconnect state before committing any tokens or event changes.
        with db.no_autoflush:
            active = db.query(CRMCalendarIntegration.id).filter_by(id=connection_id, is_active=True, deleted_at=None).first()
            owned = db.query(CalendarSyncState.integration_id).filter_by(integration_id=connection_id, lease_owner=owner).first()
        if not active or not owned:
            db.rollback()
            raise CalendarSyncError("Calendar disconnected or sync lease expired.")
        state.lease_until = datetime.now(UTC) + timedelta(minutes=5)
        db.commit()

    transport = transport_factory(connection, checkpoint)
    try:
        # Fixed delta windows are renewed monthly, and all existing links are retained and verified.
        if not state.window_end or datetime.fromisoformat(iso(state.window_end)) < now + timedelta(days=335):
            state.window_start, state.window_end = now - timedelta(days=90), now + timedelta(days=365)
            state.cursor_encrypted = None
        cursor = cipher().decrypt(state.cursor_encrypted.encode()).decode() if state.cursor_encrypted else None
        full_scan = not cursor
        modules = [m for m, enabled in (("crm", is_app_enabled("crm")), ("pms", is_app_enabled("project_management"))) if enabled]
        if state.import_target not in modules:
            raise CalendarSyncError("The selected import app is disabled. Choose an enabled import destination.")
        # Legacy exported IDs/transaction IDs can be adopted without importing duplicate local records.
        identities = {}
        for module in modules:
            for record in local_query(db, connection, module).all():
                identities[transport.identity(module, record.id)] = (module, record.id)
        restorations = {restore_key(transport, link): (link.module, link.local_id)
            for link in db.query(CalendarEventLink).filter_by(integration_id=connection_id, resolution="local").all()}
        identities.update(restorations)
        seen = set()
        final_cursor = None
        for events, next_cursor, final in transport.changes(cursor, state.window_start, state.window_end):
            for event in events:
                remote_id = event["id"]
                seen.add(remote_id)
                link = db.query(CalendarEventLink).filter_by(integration_id=connection_id, remote_id=remote_id).first()
                if connection.provider == "outlook":
                    # Delta deletions can also mean an event moved outside the view. A GET distinguishes them.
                    event = transport.get(remote_id) or {"id": remote_id, "status": "cancelled"}
                key = ((event.get("extendedProperties") or {}).get("private") or {}).get("businessSuiteKey")
                key = key or event.get("transactionId") or (remote_id if connection.provider == "google" else None)
                key = key or next((p.get("value") for p in event.get("singleValueExtendedProperties", []) if p.get("id") == PROPERTY), None)
                if link is None and key in identities:
                    module, local_id = identities[key]
                    link = db.query(CalendarEventLink).filter_by(integration_id=connection_id, module=module, local_id=local_id).first()
                    if link and link.remote_id != remote_id:
                        if key in restorations:
                            link.remote_id = remote_id
                        else:
                            # Ignore old tombstones after a deliberate restore created a replacement ID.
                            continue
                    if link is None:
                        record = local_query(db, connection, module).filter_by(id=local_id).first()
                        link = CalendarEventLink(integration_id=connection_id, module=module, local_id=local_id,
                                                 remote_id=remote_id, local_snapshot=local_value(record, module), remote_snapshot={}, remote_metadata={})
                        db.add(link)
                        db.flush()
                if link:
                    reconcile(db, transport, connection, link, event, counts)
                else:
                    value = remote_value(connection.provider, event)
                    if not value.get("deleted"):
                        if datetime.fromisoformat(value["end"]) < datetime.fromisoformat(iso(state.window_start)) or datetime.fromisoformat(value["start"]) > datetime.fromisoformat(iso(state.window_end)):
                            checkpoint()
                            continue
                        record = apply_remote(db, connection, state.import_target, None, value)
                        link = CalendarEventLink(integration_id=connection_id, module=state.import_target, local_id=record.id, remote_id=remote_id)
                        db.add(link)
                        remember(link, record, event, connection.provider)
                        counts["imported"] += 1
                checkpoint()
            if final:
                final_cursor = next_cursor
            checkpoint()
        if not final_cursor:
            raise CalendarSyncError("Calendar did not return a completed checkpoint. Retry is scheduled.")
        # Check mapped events after a cursor reset and any locally changed copies before writing.
        for link in db.query(CalendarEventLink).filter_by(integration_id=connection_id).all():
            if link.module not in modules or link.remote_id in seen:
                continue
            record = local_query(db, connection, link.module).filter_by(id=link.local_id).first()
            if full_scan or link.conflict or link.resolution or local_value(record, link.module) != link.local_snapshot:
                reconcile(db, transport, connection, link, transport.get(link.remote_id), counts)
                checkpoint()
        # Scan the fixed window for new local records, plus all mapped records above (including deletions).
        for module in modules:
            query = local_query(db, connection, module)
            if module == "crm":
                query = query.filter(CRMMeeting.deleted_at.is_(None), CRMMeeting.end_time >= state.window_start, CRMMeeting.start_time <= state.window_end)
            else:
                from app.apps.project_management.models import PMSCalendarEvent
                query = query.filter(PMSCalendarEvent.end_at >= state.window_start, PMSCalendarEvent.start_at <= state.window_end)
            for record in query.all():
                if db.query(CalendarEventLink.id).filter_by(integration_id=connection_id, module=module, local_id=record.id).first():
                    continue
                value = local_value(record, module)
                if value.get("deleted"):
                    continue
                # Persisted provider markers close the remote-create/DB-commit crash window.
                remote = transport.find(module, record.id)
                if remote:
                    link = CalendarEventLink(integration_id=connection_id, module=module, local_id=record.id,
                                             remote_id=remote["id"], local_snapshot=value, remote_snapshot={}, remote_metadata={})
                    db.add(link)
                    reconcile(db, transport, connection, link, remote, counts)
                else:
                    remote = transport.write(module, record.id, value)
                    link = CalendarEventLink(integration_id=connection_id, module=module, local_id=record.id, remote_id=remote["id"])
                    db.add(link)
                    remember(link, record, remote, connection.provider, value)
                    counts["exported"] += 1
                checkpoint()
        state.cursor_encrypted = cipher().encrypt(final_cursor.encode()).decode()
        state.last_synced_at = datetime.now(UTC)
        state.next_run_at = state.last_synced_at + timedelta(seconds=settings.CALENDAR_SYNC_INTERVAL_SECONDS)
        state.failures, state.last_error, state.counts = 0, None, counts
        state.lease_owner, state.lease_until = None, None
        db.commit()
        return counts
    except Exception as exc:
        db.rollback()
        state = db.get(CalendarSyncState, connection_id, populate_existing=True)
        if state and state.lease_owner == owner:
            state.failures += 1
            # Never persist raw provider response bodies, credentials, or URLs in errors.
            state.last_error = str(exc) if isinstance(exc, CalendarSyncError) else "Calendar sync failed. Reconnect your account or retry."
            if isinstance(exc, CalendarSyncError) and exc.reset:
                state.cursor_encrypted = None
            delay = max(min(3600, 30 * 2 ** min(state.failures, 7)), getattr(exc, "retry_after", 0))
            state.next_run_at = datetime.now(UTC) + timedelta(seconds=delay)
            state.counts = counts
            state.lease_owner, state.lease_until = None, None
            db.commit()
        return {**counts, "error": state.last_error if state else "Calendar sync stopped."}
    finally:
        transport.close()


def run_due(db):
    ids = [row.id for row in db.query(CRMCalendarIntegration).filter(
        CRMCalendarIntegration.is_active.is_(True), CRMCalendarIntegration.deleted_at.is_(None),
        CRMCalendarIntegration.provider.in_(("google", "outlook"))).all()]
    results = []
    for connection_id in ids:
        try:
            results.append(sync_connection(db, connection_id))
        except Exception:
            db.rollback()
            logger.warning("Calendar job failed for connection %s", connection_id)
    return results


def start_worker():
    stop = threading.Event()
    def loop():
        from app.db.session import SessionLocal
        from app.db.tenant import run_for_company_databases
        def tick():
            with SessionLocal() as db:
                run_due(db)
        while not stop.is_set():
            try:
                run_for_company_databases(tick)
            except Exception:
                logger.warning("Calendar background tick failed; retrying next tick")
            stop.wait(min(15, settings.CALENDAR_SYNC_INTERVAL_SECONDS))
    thread = threading.Thread(target=loop, daemon=True, name="businesssuite-calendar-sync")
    thread.start()
    return stop, thread
