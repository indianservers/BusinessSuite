"""Authorization-code + PKCE and refresh with encrypted server-only state."""

import hashlib
import json
import secrets
import uuid
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
from fastapi import HTTPException
from app.core.config import settings
from app.services.sso_service import generate_pkce_pair
from app.apps.power_apps.runtime import now, utc, scope_values
from app.apps.power_apps.integrations.models import OAuthState, Credential, Connection
from app.apps.power_apps.integrations.vault import CredentialVault, audit
from app.apps.power_apps.integrations.transport import EgressPolicy, HttpTransport
from app.apps.power_apps.integrations.contracts import IntegrationFailure

PROVIDERS = {
    "google_sheets": (
        "google",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://oauth2.googleapis.com/revoke",
    ),
    "google_drive": (
        "google",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://oauth2.googleapis.com/revoke",
    ),
    "outlook": (
        "microsoft",
        "https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize",
        "https://login.microsoftonline.com/organizations/oauth2/v2.0/token",
        None,
    ),
}


from app.apps.power_apps.integrations.providers import PROFILES
for key, profile in PROFILES.items():
    if profile["scopes"]: PROVIDERS[key] = PROVIDERS["google_sheets"]
from app.apps.power_apps.integrations.automation_catalog import MODULES
for key, info in MODULES.items():
    if info["host"] == "graph.microsoft.com": PROVIDERS[key] = PROVIDERS["outlook"]
PROVIDERS["onedrive"] = (
    "microsoft", "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    "https://login.microsoftonline.com/common/oauth2/v2.0/token", None,
)

def app_config(connector_id, connection=None):
    from app.apps.power_apps.integrations import marketplace_oauth
    if connector_id in marketplace_oauth.PROVIDERS:
        return marketplace_oauth.config(connector_id, connection)
    if connector_id not in PROVIDERS:
        raise HTTPException(422, "This connector has no OAuth authorization flow")
    name, authorize, token, revoke = PROVIDERS[connector_id]
    client_id = getattr(settings, "POWER_" + name.upper() + "_CLIENT_ID", "")
    secret = getattr(settings, "POWER_" + name.upper() + "_CLIENT_SECRET", "")
    redirect = getattr(settings, "POWER_OAUTH_REDIRECT_URI", "")
    if not client_id or not secret or not redirect:
        raise HTTPException(
            503, "Configure the server OAuth application and exact callback URI first"
        )
    expected = (
        settings.BACKEND_PUBLIC_URL.rstrip("/")
        + "/api/v1/power-apps/integrations/oauth/callback"
    )
    parsed = urlsplit(redirect)
    local_development = (
        settings.ENVIRONMENT == "development"
        and parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        and not parsed.username and not parsed.password
    )
    if redirect != expected or (
        parsed.scheme != "https" and settings.ENVIRONMENT != "test" and not local_development
    ):
        raise HTTPException(
            503,
            "OAuth callback must exactly match the configured secure backend callback",
        )
    return dict(
        name=name,
        authorize=authorize,
        token=token,
        revoke=revoke,
        client_id=client_id,
        secret=secret,
        redirect=redirect,
    )


def connection_config(conn):
    from app.apps.power_apps.integrations.marketplace_oauth import PROVIDERS as marketplace_providers
    return app_config(conn.connector_id,conn) if conn.connector_id in marketplace_providers else app_config(conn.connector_id)


def token_request(url, fields):
    transport = HttpTransport(EgressPolicy([urlsplit(url).hostname]))
    response = transport.request(
        "POST",
        url,
        {"Content-Type": "application/x-www-form-urlencoded"},
        urlencode(fields).encode(),
        timeout=10,
    )
    if response.status != 200:
        raise IntegrationFailure(
            "oauth",
            "Provider authorization failed; reconnect before retrying",
            http_status=response.status,
        )
    try:
        result = json.loads(response.body)
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("access_token"), str)
            or not 1 <= len(result["access_token"]) <= 32768
        ):
            raise ValueError()
        if result.get("token_type", "Bearer").lower() != "bearer":
            raise ValueError()
        if not 30 <= int(result.get("expires_in", 3600)) <= 604800:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise IntegrationFailure(
            "oauth", "Provider returned an invalid token response"
        ) from None


def start(db, conn, user, scopes):
    config = connection_config(conn)
    if set(scopes) != set(conn.scopes):
        raise HTTPException(422, "Authorize the exact visible connection scopes")
    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()
    db.add(
        OAuthState(
            **scope_values(conn),
            connection_id=conn.id,
            state_hash=hashlib.sha256(state.encode()).hexdigest(),
            encrypted_verifier=CredentialVault.encrypt({"verifier": verifier}),
            redirect_uri=config["redirect"],
            scopes=scopes,
            expires_at=now() + timedelta(minutes=10),
            connection_revision=conn.revision
        )
    )
    fields = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect"],
        "response_type": "code",
        "state": state,
        "scope": config.get('separator',' ').join(scopes),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if not config.get('pkce',True):
        fields.pop('code_challenge');fields.pop('code_challenge_method')
    if conn.connector_id=='mailchimp': fields.pop('scope',None)
    if conn.connector_id=='trello': fields['prompt']='consent'
    if config["name"] == "google":
        fields.update(access_type="offline", prompt="consent")
    audit(db, conn, user, "oauth_started", {"scopes": scopes})
    db.commit()
    return config["authorize"] + "?" + urlencode(fields)


def store_tokens(db, conn, credential, tokens, allowed_scopes):
    supplied = set(tokens.get("scope", " ".join(allowed_scopes)).replace(',',' ').split())
    if not supplied <= set(allowed_scopes):
        raise IntegrationFailure(
            "oauth_scope",
            "Provider granted unexpected scopes; connection was not enabled",
        )
    from app.apps.power_apps.integrations.marketplace_oauth import PROVIDERS as marketplace_providers
    if conn.connector_id in marketplace_providers and not set(allowed_scopes)<=supplied:
        raise IntegrationFailure('oauth_scope','Provider did not grant the requested scopes; reconnect with the required permissions')
    old = CredentialVault.decrypt(credential)
    value = {"access_token": tokens["access_token"]}
    if tokens.get("refresh_token") or old.get("refresh_token"):
        value["refresh_token"] = tokens.get("refresh_token") or old["refresh_token"]
    credential.encrypted_value = CredentialVault.encrypt(value)
    credential.version += 1
    conn.expires_at = None if conn.connector_id=='mailchimp' and 'expires_in' not in tokens else now() + timedelta(seconds=int(tokens.get("expires_in", 3600)))
    conn.health = "unverified"
    conn.revision += 1


def callback(db, state, code):
    if not state or len(state) > 200 or not code or len(code) > 4096:
        raise HTTPException(400, "Invalid OAuth callback")
    row = (
        db.query(OAuthState)
        .filter_by(state_hash=hashlib.sha256(state.encode()).hexdigest())
        .with_for_update()
        .first()
    )
    if not row or row.consumed_at or utc(row.expires_at) <= now():
        raise HTTPException(400, "OAuth state expired or was already used")
    conn = (
        db.query(Connection)
        .filter_by(
            id=row.connection_id,
            organization_id=row.organization_id,
            environment=row.environment,
            owner_user_id=row.owner_user_id,
        )
        .with_for_update()
        .first()
    )
    if not conn or not conn.enabled or conn.revision != row.connection_revision:
        raise HTTPException(409, "Connection changed; restart authorization")
    from app.apps.power_apps.integrations.service import config_identity

    user = config_identity(db, row.owner_user_id, row.organization_id, row.environment)
    config = connection_config(conn)
    if row.redirect_uri != config["redirect"]:
        raise HTTPException(400, "OAuth redirect configuration changed")
    verifier = CredentialVault.decrypt(
        type("StateSecret", (), {"encrypted_value": row.encrypted_verifier})()
    )["verifier"]
    row.consumed_at = now()
    connection_id = conn.id
    credential_id = conn.credential_id
    expected = conn.revision
    scopes = list(row.scopes)
    db.commit()  # consume state and release locks before network access
    exchange = token_request
    if 'connector_id' in config:
        from app.apps.power_apps.integrations.marketplace_oauth import request_token
        exchange = lambda url, fields: request_token(config, fields)
    tokens = exchange(
        config["token"],
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["redirect"],
            "client_id": config["client_id"],
            "client_secret": config["secret"],
            "code_verifier": verifier,
        },
    )
    conn = (
        db.query(Connection)
        .filter_by(id=connection_id, revision=expected, enabled=True)
        .with_for_update()
        .first()
    )
    if not conn:
        raise HTTPException(409, "Connection changed while authorization completed")
    credential = (
        db.query(Credential)
        .filter_by(id=credential_id, revoked_at=None)
        .with_for_update()
        .one()
    )
    config_identity(db, row.owner_user_id, row.organization_id, row.environment)
    if 'connector_id' in config:
        from app.apps.power_apps.integrations.marketplace_oauth import bind_account
        bind_account(conn,credential,tokens)
    store_tokens(db, conn, credential, tokens, scopes)
    audit(db, conn, user, "oauth_authorized", {"scopes": scopes})
    db.commit()
    return connection_id


def access_values(db, conn, credential, values):
    if credential.auth_type not in {"oauth2", "service_account"}:
        return values
    if conn.connector_id=='mailchimp' and conn.expires_at is None and values.get('access_token'):
        return values
    if (
        conn.expires_at
        and utc(conn.expires_at) > now() + timedelta(seconds=60)
        and values.get("access_token")
    ):
        return values
    account_mode = credential.auth_type == "service_account"
    if not account_mode and not values.get("refresh_token"):
        raise IntegrationFailure(
            "expired", "OAuth authorization expired; reconnect this account"
        )
    config = None if account_mode else connection_config(conn)
    token = str(uuid.uuid4())
    expected_version = credential.version
    expected_revision = conn.revision
    changed = (
        db.query(Connection)
        .filter_by(id=conn.id, enabled=True, revision=expected_revision)
        .filter(
            (Connection.refresh_until.is_(None)) | (Connection.refresh_until < now())
        )
        .update(
            {"refresh_token": token, "refresh_until": now() + timedelta(seconds=30)},
            synchronize_session=False,
        )
    )
    if not changed:
        raise IntegrationFailure(
            "refresh_busy",
            "Token refresh is already running",
            retryable=True,
            retry_after=5,
        )
    connection_id = conn.id
    credential_id = credential.id
    scopes = list(conn.scopes)
    db.commit()
    try:
        if account_mode:
            import jwt

            account = json.loads(values["service_account"])
            instant = int(now().timestamp())
            assertion = jwt.encode(
                {
                    "iss": account["client_email"],
                    "scope": " ".join(scopes),
                    "aud": "https://oauth2.googleapis.com/token",
                    "iat": instant,
                    "exp": instant + 3600,
                },
                account["private_key"],
                algorithm="RS256",
            )
            tokens = token_request(
                "https://oauth2.googleapis.com/token",
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
        else:
            exchange = token_request
            if 'connector_id' in config:
                from app.apps.power_apps.integrations.marketplace_oauth import request_token
                exchange = lambda url, fields: request_token(config, fields)
            tokens = exchange(
                config["token"],
                {
                    "grant_type": "refresh_token",
                    "refresh_token": values["refresh_token"],
                    "client_id": config["client_id"],
                    "client_secret": config["secret"],
                    "scope": " ".join(scopes),
                },
            )
    except Exception:
        db.query(Connection).filter_by(id=connection_id, refresh_token=token).update(
            {"health": "expired", "refresh_token": None, "refresh_until": None},
            synchronize_session=False,
        )
        db.commit()
        raise IntegrationFailure(
            "oauth", "Token renewal failed; reconnect before retrying"
        ) from None
    current = (
        db.query(Connection)
        .filter_by(
            id=connection_id,
            refresh_token=token,
            enabled=True,
            revision=expected_revision,
        )
        .with_for_update()
        .populate_existing()
        .first()
    )
    current_credential = (
        db.query(Credential)
        .filter_by(id=credential_id, revoked_at=None, version=expected_version)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not current or not current_credential:
        raise IntegrationFailure(
            "credential", "Connection authorization changed during refresh"
        )
    if account_mode:
        if not set(tokens.get("scope", " ".join(scopes)).split()) <= set(scopes):
            raise IntegrationFailure(
                "oauth_scope", "Provider granted unexpected scopes"
            )
        current_credential.encrypted_value = CredentialVault.encrypt(
            {**values, "access_token": tokens["access_token"]}
        )
        current_credential.version += 1
        current.expires_at = now() + timedelta(
            seconds=int(tokens.get("expires_in", 3600))
        )
    else:
        store_tokens(db, current, current_credential, tokens, scopes)
    current.refresh_token = None
    current.refresh_until = None
    db.commit()
    return CredentialVault.decrypt(current_credential)


def revoke_remote(db, conn, credential):
    if credential.auth_type != "oauth2":
        return {"remote_revocation": "not_applicable"}
    config = app_config(conn.connector_id)
    values = CredentialVault.decrypt(credential)
    token = values.get("refresh_token") or values.get("access_token")
    if not config["revoke"]:
        return {"remote_revocation": "provider_account_portal_required"}
    if not token:
        return {"remote_revocation": "no_token"}
    response = HttpTransport(
        EgressPolicy([urlsplit(config["revoke"]).hostname])
    ).request(
        "POST",
        config["revoke"],
        {"Content-Type": "application/x-www-form-urlencoded"},
        urlencode({"token": token}).encode(),
        timeout=10,
    )
    return {
        "remote_revocation": (
            "confirmed"
            if response.status == 200
            else "provider_account_portal_required"
        )
    }
