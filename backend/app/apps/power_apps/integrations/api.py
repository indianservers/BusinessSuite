"""Authenticated connector setup and action execution; secrets never leave the vault."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.apps.power_apps.service import organization, validate_environment
from app.apps.power_apps.integrations.registry import catalog
from app.apps.power_apps.integrations import vault, service, oauth
from app.apps.power_apps.integrations.models import (
    Connection,
    Credential,
    RequestLog,
    Operation,
)
from app.apps.power_apps.integrations.contracts import (
    ConnectionCreate,
    ConnectionUpdate,
    Probe,
    OAuthStart,
    SecretRotate,
    IntegrationFailure,
)

router = APIRouter(prefix="/power-apps/integrations", tags=["Power Apps Integrations"])
view = RequirePermission("power_apps_view")
manage = RequirePermission("power_apps_manage_credentials")


@router.get("/catalog")
def connector_catalog(user=Depends(view)):
    items = catalog()
    for item in items:
        item["oauth_ready"] = False
        if "oauth2" in item["authentication"]:
            try:
                oauth.app_config(item["id"])
                item["oauth_ready"] = True
            except HTTPException:
                pass
    return {
        "items": items,
        "live_verification": "Each connection is verified only by an authorized provider request",
    }


@router.get("/connections")
def connections(
    environment: str = "development", db: Session = Depends(get_db), user=Depends(view)
):
    validate_environment(db, user, environment)
    rows = (
        db.query(Connection)
        .filter_by(
            organization_id=organization(user),
            environment=environment,
            owner_user_id=user.id,
        )
        .order_by(Connection.id.desc())
        .limit(200)
        .all()
    )
    return {"items": [vault.public_connection(row) for row in rows]}


@router.post("/connections", status_code=201)
def create_connection(
    data: ConnectionCreate,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(manage),
):
    view(user)
    if data.sharing:
        raise HTTPException(
            422,
            "Connections are owner-scoped in this release; sharing requires a separate authorization review",
        )
    row = vault.create(db, user, environment, data)
    db.commit()
    return vault.public_connection(row)


@router.put("/connections/{id}")
def update_connection(
    id: int,
    data: ConnectionUpdate,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(manage),
):
    view(user)
    row = vault.connection(db, user, environment, id, manage=True, lock=True)
    if data.expected_revision != row.revision:
        raise HTTPException(409, "Connection changed; reload before saving")
    if data.sharing:
        raise HTTPException(422, "Connection sharing is not enabled")
    row.enabled = data.enabled
    row.writes_enabled = data.writes_enabled
    row.revision += 1
    vault.audit(
        db,
        row,
        user,
        "connection_updated",
        {"enabled": row.enabled, "writes_enabled": row.writes_enabled},
    )
    db.commit()
    return vault.public_connection(row)


@router.post("/connections/{id}/rotate")
def rotate(
    id: int,
    data: SecretRotate,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(manage),
):
    view(user)
    row = vault.connection(db, user, environment, id, manage=True, lock=True)
    if row.revision != data.expected_version:
        raise HTTPException(409, "Connection changed; reload before rotating")
    credential = db.get(Credential, row.credential_id)
    values = {k: v.get_secret_value() for k, v in data.secrets.items()}
    vault.validate_config(
        row.connector_id,
        credential.auth_type,
        row.config,
        values,
        row.scopes,
        row.writes_enabled,
    )
    credential.encrypted_value = vault.CredentialVault.encrypt(values)
    credential.version += 1
    row.revision += 1
    row.health = "unverified"
    row.last_verified_at = None
    vault.audit(db, row, user, "credential_rotated")
    db.commit()
    return vault.public_connection(row)


@router.post("/execute")
def execute(
    data: Probe,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_execute")),
):
    view(user)
    conn = vault.connection(db, user, environment, data.connection_id)
    try:
        return {
            "output": service.invoke(
                db,
                user,
                conn,
                data.action_id,
                data.input,
                confirmed=data.confirm_side_effect,
                key="probe:" + data.request_id,
            )
        }
    except IntegrationFailure as exc:
        raise HTTPException(
            409 if exc.uncertain else 422,
            {
                "category": exc.category,
                "message": str(exc),
                "uncertain": exc.uncertain,
                "retryable": exc.retryable,
                "retry_after": exc.retry_after,
            },
        ) from None


@router.get("/monitor")
def monitor(
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_activity_view")),
):
    view(user)
    validate_environment(db, user, environment)
    rows = (
        db.query(RequestLog)
        .filter_by(
            organization_id=organization(user),
            environment=environment,
            owner_user_id=user.id,
        )
        .order_by(RequestLog.id.desc())
        .limit(100)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "connector_id": r.connector_id,
                "action_id": r.action_id,
                "status": r.status,
                "http_status": r.http_status,
                "duration_ms": r.duration_ms,
                "error_category": r.error_category,
                "correlation_id": r.correlation_id,
                "run_id": r.run_id,
            }
            for r in rows
        ]
    }


@router.post("/connections/{id}/oauth")
def authorize(
    id: int,
    data: OAuthStart,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(manage),
):
    view(user)
    conn = vault.connection(db, user, environment, id, manage=True)
    return {"authorization_url": oauth.start(db, conn, user, data.scopes)}


@router.get("/oauth/callback")
def callback(state: str, code: str, db: Session = Depends(get_db)):
    oauth.callback(db, state, code)
    return {
        "connected": True,
        "message": "Authorization saved. Return to Integration Studio to test the connection.",
    }
