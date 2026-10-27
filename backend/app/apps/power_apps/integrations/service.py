"""Central connector dispatch and durable operation journal; no second queue."""

import hashlib
import json
import time
import uuid
from datetime import timedelta
from fastapi import HTTPException
from app.core.deps import RequirePermission
from app.apps.power_apps.runtime import now, utc, scope_values, safe_data
from app.apps.power_apps.service import organization, validate_environment
from app.apps.power_apps.integrations import adapters, database, ai, oauth, vault
from app.apps.power_apps.integrations.models import (
    Operation,
    RequestLog,
    ConnectorGate,
    Connection,
)
from app.apps.power_apps.integrations.registry import REGISTRY, INPUTS, get_action
from app.apps.power_apps.integrations.contracts import IntegrationFailure
from app.apps.power_apps.integrations.providers import PROFILES, execute as provider_execute
from app.apps.power_apps.integrations.transport import scrub


def config_identity(db, user_id, company, environment):
    from app.models.user import User
    from app.core.tenant_boundary import company_ids
    from app.access.service import background_scope

    user = (
        db.query(User).filter_by(id=user_id, is_active=True).populate_existing().first()
    )
    if not user or company not in company_ids(db, user):
        raise HTTPException(403, "Connection authority was revoked")
    user.organization_id = company
    with background_scope(db, user, "power_apps", "view"):
        RequirePermission("power_apps_manage_credentials")(user)
        validate_environment(db, user, environment)
    return user


def typed_action(conn, action_id, data, confirmed):
    try:
        spec = get_action(conn.connector_id, action_id)
        parsed = INPUTS[(conn.connector_id, action_id)].model_validate(data)
        safe_data(data)
    except (ValueError, KeyError, TypeError):
        raise IntegrationFailure(
            "schema", "Action input does not match its declared contract"
        ) from None
    mutates = (
        spec.mutates
        or conn.connector_id == "http"
        and parsed.method not in {"GET", "HEAD"}
    )
    if not conn.enabled:
        raise IntegrationFailure("disabled", "Connection is disabled")
    if mutates and not (conn.writes_enabled and confirmed):
        raise IntegrationFailure(
            "permission",
            "External writes require connection opt-in and explicit action confirmation",
        )
    granted = set(conn.scopes)
    required = set(spec.scopes)
    if (
        conn.connector_id == "google_sheets"
        and "https://www.googleapis.com/auth/spreadsheets" in granted
    ):
        granted.add("https://www.googleapis.com/auth/spreadsheets.readonly")
    for scope in list(granted):
        if scope.startswith("https://www.googleapis.com/auth/") and scope.rsplit("/",1)[-1] in {"documents","presentations","calendar.events","tasks","contacts","forms.body"}:
            granted.add(scope+".readonly")
    if not required <= granted:
        raise IntegrationFailure(
            "scope", "Connection does not grant the required action scopes"
        )
    return parsed, spec, mutates


def reserve(db, conn, key):
    # Lock the connection first to serialize initial gate creation as well as updates.
    db.query(Connection).filter_by(id=conn.id).with_for_update().one()
    gate = (
        db.query(ConnectorGate)
        .filter_by(connection_id=conn.id)
        .with_for_update()
        .first()
    )
    instant = now()
    manifest = REGISTRY[conn.connector_id]
    if not gate:
        gate = ConnectorGate(
            **scope_values(conn),
            connection_id=conn.id,
            window_at=instant,
            leases={},
            request_count=0,
            failures=0,
        )
        db.add(gate)
        db.flush()
    if gate.open_until and utc(gate.open_until) > instant:
        raise IntegrationFailure(
            "circuit_open",
            "Connection circuit is open",
            retryable=True,
            retry_after=max(1, int((utc(gate.open_until) - instant).total_seconds())),
        )
    leases = {k: v for k, v in (gate.leases or {}).items() if v > instant.timestamp()}
    if len(leases) >= manifest.max_concurrent:
        raise IntegrationFailure(
            "bulkhead",
            "Connection concurrency limit reached",
            retryable=True,
            retry_after=5,
        )
    if (instant - utc(gate.window_at)).total_seconds() >= 60:
        gate.window_at = instant
        gate.request_count = 0
    if gate.request_count >= manifest.rate_per_minute:
        raise IntegrationFailure(
            "rate_limit",
            "Connection request budget exhausted",
            retryable=True,
            retry_after=60,
        )
    gate.request_count += 1
    leases[key] = (instant + timedelta(seconds=120)).timestamp()
    gate.leases = leases
    return gate


def release(db, conn, key, error):
    gate = (
        db.query(ConnectorGate)
        .filter_by(connection_id=conn.id)
        .with_for_update()
        .first()
    )
    if not gate:
        return
    gate.leases = {k: v for k, v in (gate.leases or {}).items() if k != key}
    if error:
        gate.failures += 1
        if gate.failures >= 5 or error.category == "rate_limit":
            gate.open_until = now() + timedelta(seconds=max(60, error.retry_after))
    else:
        gate.failures = 0
        gate.open_until = None


def invoke(
    db, user, conn, action_id, data, *, confirmed=False, key, run_id=None, step_id=None
):
    """Commit dispatch intent before IO; uncertain writes never automatically repeat."""
    RequirePermission("power_apps_execute")(user)
    parsed, spec, mutates = typed_action(conn, action_id, data, confirmed)
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    operation_key = hashlib.sha256(
        f"{conn.organization_id}:{conn.environment}:{conn.id}:{user.id}:{key}".encode()
    ).hexdigest()
    db.query(Connection).filter_by(id=conn.id).with_for_update().one()
    op = (
        db.query(Operation)
        .filter_by(operation_key=operation_key)
        .with_for_update()
        .first()
    )
    if op:
        if op.input_hash != digest or op.action_id != action_id:
            raise IntegrationFailure(
                "idempotency_conflict",
                "Operation key was already used with different input",
            )
        if op.status == "succeeded":
            return op.output
        if op.status in {"dispatched", "uncertain"} and op.mutates:
            op.status = "uncertain"
            op.error_category = "reconciliation"
            op.error = "Previous external write may have completed; reconcile with the provider"
            db.commit()
            raise IntegrationFailure("reconciliation", op.error, uncertain=True)
        if op.status == "failed" and mutates:
            raise IntegrationFailure(
                "previous_failure",
                "Create a new explicit request after reviewing the previous write failure",
            )
    else:
        op = Operation(
            **scope_values(conn),
            run_id=run_id,
            step_id=step_id,
            connection_id=conn.id,
            connector_id=conn.connector_id,
            action_id=action_id,
            operation_key=operation_key,
            input_hash=digest,
            mutates=mutates,
            correlation_id=str(uuid.uuid4()),
            status="prepared",
        )
        db.add(op)
        db.flush()
    credential, values = vault.credential_values(db, user, conn)
    values = oauth.access_values(db, conn, credential, values)
    # Refresh can commit: recheck revocation and permission before dispatch.
    conn = vault.connection(db, user, conn.environment, conn.id, lock=True)
    credential, current = vault.credential_values(db, user, conn)
    values = current
    typed_action(conn, action_id, data, confirmed)
    # A refresh releases the initial lock. Another request may have completed
    # this operation while tokens were renewed; fence dispatch a second time.
    op = (
        db.query(Operation)
        .filter_by(id=op.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if op.status == "succeeded":
        return op.output
    if mutates and op.status in {"dispatched", "uncertain"}:
        raise IntegrationFailure(
            "reconciliation",
            "External write is already dispatched; reconcile its outcome",
            uncertain=True,
        )
    if not conn.enabled:
        raise IntegrationFailure("disabled", "Connection was disabled before dispatch")
    reserve(db, conn, operation_key)
    op.status = "dispatched"
    op.dispatched_at = now()
    op.credential_version = credential.version
    op_id = op.id
    connection_id = conn.id
    db.commit()
    started = time.monotonic()
    error = None
    output = None
    try:
        headers = vault.authentication(credential.auth_type, values, conn.config)
        policy = vault.policy_for(db, conn)
        db.commit()
        if conn.connector_id == "postgresql":
            output = database.execute(
                conn, credential, values, action_id, parsed, policy
            )
        elif conn.connector_id == "ai_gateway":
            output = ai.execute(db, user, conn, action_id, data)
        elif conn.connector_id == "smtp":
            output = adapters.smtp_action(action_id, data)
        else:
            transport = adapters.HTTP_FACTORY(policy)
            if conn.connector_id in {"http", "outgoing_webhook"}:
                output = adapters.http_action(
                    conn,
                    parsed,
                    transport,
                    headers,
                    values,
                    operation_key,
                    signed=conn.connector_id == "outgoing_webhook",
                )
            elif conn.connector_id in PROFILES:
                output = provider_execute(conn, action_id, parsed, transport, headers, values, operation_key)
            else:
                output = adapters.provider_action(
                    conn, action_id, parsed, transport, headers, values, operation_key
                )
        output = scrub(output, [*values.values(), *headers.values()])
        safe_data(output)
        if len(json.dumps(output)) > 65536:
            raise IntegrationFailure(
                "response_size",
                "Selected response exceeds the 64 KB step budget",
                uncertain=mutates,
            )
    except IntegrationFailure as exc:
        error = exc
    except Exception:
        error = IntegrationFailure(
            "adapter", "Adapter could not produce a validated result", uncertain=mutates
        )
    # Persist the actual external outcome even if the caller lost its job lease.
    db.rollback()
    conn = db.query(Connection).filter_by(id=connection_id).with_for_update().one()
    op = db.query(Operation).filter_by(id=op_id).with_for_update().one()
    op.finished_at = now()
    op.status = (
        "uncertain" if error and error.uncertain else "failed" if error else "succeeded"
    )
    op.output = output if not error else None
    op.error_category = error.category if error else None
    op.error = str(error)[:400] if error else None
    release(db, conn, operation_key, error)
    if not error and not (conn.connector_id == "openrouter" and action_id == "list_models"):
        conn.health = "healthy"
        conn.last_verified_at = now()
    elif error and error.category in {"authentication", "expired", "credential"}:
        conn.health = "expired" if error.category == "expired" else "unhealthy"
    db.add(
        RequestLog(
            **scope_values(conn),
            operation_id=op.id,
            connection_id=conn.id,
            connector_id=conn.connector_id,
            action_id=action_id,
            run_id=run_id,
            correlation_id=op.correlation_id,
            status=op.status,
            http_status=(
                error.http_status
                if error
                else (
                    output.get("status_code", output.get("http_status"))
                    if isinstance(output, dict)
                    else None
                )
            ),
            duration_ms=int((time.monotonic() - started) * 1000),
            error_category=op.error_category,
            response_preview=output if not error else None,
        )
    )
    db.commit()
    if error:
        raise error
    return output
