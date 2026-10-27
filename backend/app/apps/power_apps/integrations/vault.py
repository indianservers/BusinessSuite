"""One encrypted vault, scoped ownership/sharing and metadata-only audit."""

import base64
import json
import re
from datetime import timedelta
from urllib.parse import urlsplit
from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import or_
from app.ai_operator.providers import cipher
from app.apps.power_apps.service import organization, validate_environment, serialize
from app.apps.power_apps.runtime import now, utc, scope_values
from app.apps.power_apps.integrations.models import (
    Credential,
    Connection,
    ConnectionAudit,
    EgressGrant,
)
from app.apps.power_apps.integrations.registry import REGISTRY, get_action
from app.apps.power_apps.integrations.contracts import IntegrationFailure
from app.apps.power_apps.integrations.transport import EgressPolicy, scrub

SECRET_FIELDS = {
    "none": set(),
    "api_key": {"api_key"},
    "bearer": {"access_token"},
    "basic": {"username", "password"},
    "database": {"username", "password"},
    "signing": {"signing_secret"},
    "oauth2": {"access_token", "refresh_token"},
    "service_account": {"service_account"},
    "gateway": set(),
    "platform_smtp": set(),
}
PROVIDER_HOSTS = {
    "github": ["api.github.com"],
    "google_sheets": ["sheets.googleapis.com"],
    "google_drive": ["www.googleapis.com"],
    "outlook": ["graph.microsoft.com"],
}

from app.apps.power_apps.integrations.providers import PROFILES
PROVIDER_HOSTS.update({key: [value["host"]] for key,value in PROFILES.items()})


class CredentialVault:
    @staticmethod
    def encrypt(value):
        return cipher().encrypt(json.dumps(value, allow_nan=False).encode()).decode()

    @staticmethod
    def decrypt(row):
        try:
            return json.loads(cipher().decrypt(row.encrypted_value.encode()))
        except (InvalidToken, ValueError):
            raise IntegrationFailure(
                "credential", "Credential cannot be decrypted; reconnect or rotate it"
            ) from None


def allowed(row, user):
    return row.organization_id == organization(user) and (
        row.owner_user_id == user.id
        or user.id in (row.sharing or [])
        or user.is_superuser
    )


def connection(db, user, environment, id, *, manage=False, lock=False):
    validate_environment(db, user, environment)
    query = db.query(Connection).filter_by(
        id=id, organization_id=organization(user), environment=environment
    )
    if lock:
        query = query.with_for_update()
    row = query.populate_existing().first()
    if not row or not allowed(row, user):
        raise HTTPException(404, "Connection not found")
    if manage and not (user.id == row.owner_user_id or user.is_superuser):
        raise HTTPException(
            403, "Only the connection owner may change its authorization"
        )
    return row


def public_connection(row):
    data = {
        k: v
        for k, v in serialize(row).items()
        if k not in {"refresh_token", "refresh_until"}
    }
    if row.expires_at and utc(row.expires_at) <= now():
        data["health"] = "expired"
    data["live_verified"] = bool(row.last_verified_at and data["health"] == "healthy")
    return data


def audit(db, row, user, action, details=None):
    db.add(
        ConnectionAudit(
            **scope_values(row),
            connection_id=row.id if isinstance(row, Connection) else None,
            credential_id=row.credential_id if isinstance(row, Connection) else row.id,
            actor_user_id=user.id,
            action=action,
            details=scrub(details or {})
        )
    )


def hosts_for(conn):
    return PROVIDER_HOSTS.get(conn.connector_id, conn.config.get("hosts", []))


def policy_for(db, conn):
    grants = (
        db.query(EgressGrant)
        .filter_by(
            organization_id=conn.organization_id,
            environment=conn.environment,
            enabled=True,
        )
        .all()
    )
    return EgressPolicy(
        hosts_for(conn), {(g.host, g.port): g.addresses for g in grants}
    )


def validate_config(connector_id, auth_type, config, secrets, scopes, writes):
    from app.apps.power_apps.runtime import safe_data

    if (
        connector_id not in REGISTRY
        or auth_type not in REGISTRY[connector_id].authentication
    ):
        raise HTTPException(422, "Unsupported connector authentication")
    if len(json.dumps(config)) > 16384:
        raise HTTPException(422, "Connection configuration exceeds 16 KB")
    try:
        safe_data(config)
    except (ValueError, TypeError):
        raise HTTPException(
            422, "Public connection settings must not contain secrets or unsafe fields"
        ) from None
    required = SECRET_FIELDS[auth_type]
    if set(secrets) != required and auth_type != "oauth2":
        raise HTTPException(
            422,
            "Provide exactly the required write-only credential fields: "
            + ", ".join(sorted(required)),
        )
    if auth_type == "oauth2" and secrets:
        raise HTTPException(
            422, "OAuth tokens must be obtained by the server authorization flow"
        )
    if any(not isinstance(v, str) or not v or len(v) > 32768 for v in secrets.values()):
        raise HTTPException(422, "Invalid credential value")
    permitted = {
        "hosts",
        "header_name",
        "database",
        "port",
        "tables",
        "provider",
        "test_url",
        "spreadsheet_id",
        "schema_name",
        "label",
    }
    if set(config) - permitted:
        raise HTTPException(422, "Unknown public connection setting")
    if connector_id in {"http", "outgoing_webhook", "postgresql"}:
        hosts = config.get("hosts", [])
        if (
            not isinstance(hosts, list)
            or not 1 <= len(hosts) <= 10
            or any(
                not isinstance(h, str) or not re.fullmatch(r"[a-zA-Z0-9.-]{1,253}", h)
                for h in hosts
            )
        ):
            raise HTTPException(
                422, "Provide 1–10 exact hostnames, without a scheme or path"
            )
    if auth_type == "api_key" and not re.fullmatch(
        r"X-[A-Za-z0-9-]{1,60}", config.get("header_name", "X-API-Key")
    ):
        raise HTTPException(422, "API key header must be an explicit X- header")
    if connector_id == "postgresql":
        if (
            len(config["hosts"]) != 1
            or not isinstance(config.get("database"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,63}", config["database"])
        ):
            raise HTTPException(
                422, "Choose one database host and an explicit database name"
            )
        if (
            type(config.get("port", 5432)) is not int
            or not 1 <= config.get("port", 5432) <= 65535
        ):
            raise HTTPException(422, "Invalid database port")
        tables = config.get("tables", [])
        if (
            not isinstance(tables, list)
            or not 1 <= len(tables) <= 30
            or any(
                not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*", t)
                for t in tables
            )
        ):
            raise HTTPException(422, "Approve an explicit schema.table allowlist")
        from app.core.config import settings
        from sqlalchemy.engine import make_url

        app_url = make_url(settings.SQLALCHEMY_DATABASE_URI)
        if (
            config["database"] == app_url.database
            or secrets.get("username") == app_url.username
        ):
            raise HTTPException(
                422,
                "Application databases and application roles cannot be used as connector credentials",
            )
    permitted_scopes = {s for a in REGISTRY[connector_id].actions for s in a.scopes}
    if connector_id == "outlook":
        permitted_scopes.add("offline_access")
    if not set(scopes) <= permitted_scopes:
        raise HTTPException(422, "Requested scopes are outside this connector manifest")
    if not writes and any(
        s in scopes
        for s in {
            "issues:write",
            "Mail.Send",
            "https://www.googleapis.com/auth/spreadsheets",
        }
    ):
        raise HTTPException(422, "Write scopes require explicit write opt-in")
    if auth_type == "service_account":
        try:
            account = json.loads(secrets["service_account"])
            if (
                set(account)
                - {
                    "type",
                    "project_id",
                    "private_key_id",
                    "private_key",
                    "client_email",
                    "client_id",
                    "auth_uri",
                    "token_uri",
                    "auth_provider_x509_cert_url",
                    "client_x509_cert_url",
                    "universe_domain",
                }
                or account.get("type") != "service_account"
                or not account.get("client_email")
                or not account.get("private_key")
                or account.get("token_uri") != "https://oauth2.googleapis.com/token"
            ):
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                422,
                "Use a valid Google service-account document with the official token endpoint",
            ) from None


def create(db, user, environment, data):
    validate_environment(db, user, environment)
    secret_values = {k: v.get_secret_value() for k, v in data.secrets.items()}
    validate_config(
        data.connector_id,
        data.auth_type,
        data.config,
        secret_values,
        data.scopes,
        data.writes_enabled,
    )
    if data.auth_type == "platform_smtp":
        from app.core.deps import RequirePermission

        RequirePermission("power_apps_manage_environment")(user)
    for shared in data.sharing:
        from app.models.user import User
        from app.core.tenant_boundary import company_ids

        person = db.get(User, shared)
        if not person or organization(user) not in company_ids(db, person):
            raise HTTPException(
                422, "Sharing is restricted to current-company identities"
            )
    values = dict(
        organization_id=organization(user),
        environment=environment,
        owner_user_id=user.id,
    )
    credential = Credential(
        **values,
        connector_id=data.connector_id,
        name=data.name,
        auth_type=data.auth_type,
        encrypted_value=CredentialVault.encrypt(secret_values),
        hosts=PROVIDER_HOSTS.get(data.connector_id, data.config.get("hosts", [])),
        sharing=data.sharing
    )
    db.add(credential)
    db.flush()
    row = Connection(
        **values,
        connector_id=data.connector_id,
        name=data.name,
        credential_id=credential.id,
        config=data.config,
        scopes=data.scopes,
        sharing=data.sharing,
        writes_enabled=data.writes_enabled,
        health="authorization_required" if data.auth_type == "oauth2" else "unverified"
    )
    db.add(row)
    db.flush()
    audit(db, row, user, "connection_created")
    return row


def credential_values(db, user, conn):
    row = (
        db.query(Credential)
        .filter_by(
            id=conn.credential_id,
            organization_id=conn.organization_id,
            environment=conn.environment,
        )
        .first()
    )
    if (
        not row
        or row.revoked_at
        or not allowed(row, user)
        or row.connector_id != conn.connector_id
        or set(hosts_for(conn)) - set(row.hosts)
    ):
        raise IntegrationFailure(
            "credential", "Connection credential is revoked or unavailable"
        )
    audit(db, conn, user, "credential_used", {"version": row.version})
    return row, CredentialVault.decrypt(row)


def authentication(auth_type, secrets, config):
    if auth_type == "bearer" or auth_type == "oauth2" or auth_type == "service_account":
        return {"Authorization": "Bearer " + secrets["access_token"]}
    if auth_type == "api_key":
        return {config.get("header_name", "X-API-Key"): secrets["api_key"]}
    if auth_type == "basic":
        return {
            "Authorization": "Basic "
            + base64.b64encode(
                (secrets["username"] + ":" + secrets["password"]).encode()
            ).decode()
        }
    return {}
