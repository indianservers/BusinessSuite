"""Personal sync controls; every lookup is scoped to the signed-in account and tenant."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.module_registry import is_app_enabled
from .models import CRMCalendarIntegration
from .calendar_sync_models import CalendarEventLink
from .calendar_sync import organization, state_for, status, sync_connection

router = APIRouter()


def own_connection(db, user, connection_id):
    row = db.query(CRMCalendarIntegration).filter_by(id=connection_id, user_id=user.id,
        organization_id=organization(user), is_active=True, deleted_at=None).first()
    if row is None or row.provider not in ("google", "outlook"):
        raise HTTPException(404, "Connected calendar not found")
    return row


class SyncPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    import_target: Literal["crm", "pms"]


class Resolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keep: Literal["local", "remote"]


@router.get('/calendar-integrations/{connection_id}/sync')
def sync_status(connection_id:int, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    return status(db, own_connection(db, user, connection_id))


@router.put('/calendar-integrations/{connection_id}/sync')
def sync_preferences(connection_id:int, payload:SyncPreferences, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    row = own_connection(db, user, connection_id)
    if not is_app_enabled("crm" if payload.import_target == "crm" else "project_management"):
        raise HTTPException(422, "The selected import app is disabled")
    state = state_for(db, row)
    state.enabled, state.import_target, state.next_run_at = payload.enabled, payload.import_target, None
    db.commit()
    return status(db, row)


@router.post('/calendar-integrations/{connection_id}/sync')
def sync_now(connection_id:int, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    row = own_connection(db, user, connection_id)
    result = sync_connection(db, row.id, force=True)
    if result.get("error"):
        raise HTTPException(502, result["error"])
    return result


@router.get('/calendar-integrations/{connection_id}/conflicts')
def conflicts(connection_id:int, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    own_connection(db, user, connection_id)
    from .calendar_sync import local_query, local_value
    connection = db.get(CRMCalendarIntegration, connection_id)
    rows = db.query(CalendarEventLink).filter_by(integration_id=connection_id, conflict=True).all()
    return {"items": [{"id": row.id, "module": row.module, "localId": row.local_id,
        "local": local_value(local_query(db, connection, row.module).filter_by(id=row.local_id).first(), row.module),
        "remote": row.conflict_remote, "lastSyncedAt": row.last_synced_at} for row in rows]}


@router.post('/calendar-integrations/{connection_id}/conflicts/{link_id}')
def resolve_conflict(connection_id:int, link_id:int, payload:Resolution, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    connection = own_connection(db, user, connection_id)
    # Serialize the choice against an in-flight worker reconciliation.
    row = db.query(CalendarEventLink).filter_by(id=link_id, integration_id=connection_id, conflict=True).with_for_update().first()
    if row is None:
        raise HTTPException(404, "Calendar conflict not found")
    row.resolution = payload.keep
    state = state_for(db, connection)
    state.next_run_at = None
    db.commit()
    return {"queued": True}
