"""Secured ingress and calendar claims. Registered event providers are deployment code."""

import hashlib
import hmac
import ipaddress
import json
import secrets
from datetime import timedelta
from fastapi import HTTPException
from app.apps.power_apps.runtime import now, utc, enqueue, authority, scope_values
from app.apps.power_apps.runtime_models import (
    AutomationTrigger as Trigger,
    AutomationReplay as Replay,
    AutomationDeployment as Deployment,
    AutomationEvent as Event,
)
from app.apps.power_apps.models import PowerResource, PowerVersion, PowerEnvironment
from app.apps.power_apps.runtime_schedule import next_occurrence
from app.apps.power_apps.runtime_contracts import ScheduleConfig
from app.ai_operator.providers import cipher

# Registration requires server code and an authorization callback. No native provider installed.
EVENT_PROVIDERS = {}


def register_event_provider(name, authorize):
    if name in EVENT_PROVIDERS or not callable(authorize):
        raise ValueError("Invalid event provider registration")
    EVENT_PROVIDERS[name] = authorize


def schema_check(value, schema, depth=0):
    if (
        depth > 8
        or not isinstance(schema, dict)
        or set(schema)
        - {
            "type",
            "properties",
            "required",
            "additionalProperties",
            "items",
            "maxItems",
            "maxLength",
            "enum",
        }
    ):
        raise ValueError("Unsupported input schema")
    types = {
        "object": dict,
        "array": list,
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "null": type(None),
    }
    expected = schema.get("type")
    if expected not in types:
        raise ValueError("Input schema requires a supported type")
    if (
        not isinstance(value, types[expected])
        or expected in {"number", "integer"}
        and isinstance(value, bool)
    ):
        raise ValueError("Trigger payload has an incompatible type")
    if "enum" in schema and not any(
        (
            type(value) is type(item)
            or type(value) in (int, float)
            and type(item) in (int, float)
        )
        and value == item
        for item in schema["enum"]
    ):
        raise ValueError("Value is not in the allowed enum")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if not isinstance(properties, dict) or len(properties) > 100:
            raise ValueError("Invalid schema properties")
        if set(schema.get("required", [])) - value.keys():
            raise ValueError("Required trigger field is missing")
        if (
            schema.get("additionalProperties", False) is False
            and value.keys() - properties.keys()
        ):
            raise ValueError("Unknown trigger field")
        for key, child in properties.items():
            if key in value:
                schema_check(value[key], child, depth + 1)
    if isinstance(value, list):
        if len(value) > min(schema.get("maxItems", 1000), 1000):
            raise ValueError("Too many trigger items")
        for item in value:
            schema_check(item, schema.get("items", {}), depth + 1)
    if isinstance(value, str) and len(value) > min(
        schema.get("maxLength", 32768), 32768
    ):
        raise ValueError("Trigger string exceeds limit")


def validate_schema(schema, depth=0):
    if not isinstance(schema, dict) or depth > 8 or len(json.dumps(schema)) > 16384:
        raise ValueError("Invalid input schema")
    dummy = {
        "object": {},
        "array": [],
        "string": "",
        "number": 0,
        "integer": 0,
        "boolean": False,
        "null": None,
    }
    if schema.get("type") not in dummy:
        raise ValueError("Unknown schema type")
    if set(schema) - {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "maxItems",
        "maxLength",
        "enum",
    }:
        raise ValueError("Unsupported input schema keyword")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict) or len(properties) > 100:
        raise ValueError("Invalid input schema properties")
    required = schema.get("required", [])
    if (
        not isinstance(required, list)
        or any(not isinstance(key, str) for key in required)
        or len(required) > 100
        or set(required) - properties.keys()
    ):
        raise ValueError("Required fields must be declared properties")
    if (
        "additionalProperties" in schema
        and type(schema["additionalProperties"]) is not bool
    ):
        raise ValueError("additionalProperties must be boolean")
    for key, maximum in [("maxItems", 1000), ("maxLength", 32768)]:
        if key in schema and (
            type(schema[key]) is not int or not 0 <= schema[key] <= maximum
        ):
            raise ValueError("Invalid input schema bound")
    if "enum" in schema and (
        not isinstance(schema["enum"], list) or not 1 <= len(schema["enum"]) <= 100
    ):
        raise ValueError("Input enum must contain 1-100 values")
    for value in properties.values():
        validate_schema(value, depth + 1)
    if schema.get("type") == "array":
        validate_schema(schema.get("items", {}), depth + 1)


def configure(db, row, user, kind, enabled, config):
    state = db.query(Deployment).filter_by(resource_id=row.id).with_for_update().first()
    if (
        not state
        or not state.version_id
        or state.status not in {"published", "paused", "active"}
    ):
        raise HTTPException(409, "Publish before configuring triggers")
    if user.id != row.owner_user_id:
        raise HTTPException(
            403, "Only the workflow owner may delegate background triggers"
        )
    if (
        enabled
        and state.policy.get("identity") != "service"
        and (
            state.policy.get("identity") != "owner"
            or not state.policy.get("delegated_owner")
        )
    ):
        raise HTTPException(
            422, "Background triggers require explicit owner delegation at publication"
        )
    if kind not in {"scheduled", "webhook", "internal"}:
        raise HTTPException(422, "Unknown trigger kind")
    definition = db.get(PowerVersion, state.version_id).snapshot["definition"]
    root = next(
        n
        for n in definition["nodes"]
        if n["type"]
        in {
            "manual_trigger",
            "scheduled_trigger",
            "webhook_trigger",
            "record_created",
            "record_updated",
            "status_changed",
        }
    )
    expected = {
        "scheduled": {"scheduled_trigger"},
        "webhook": {"webhook_trigger"},
        "internal": {"record_created", "record_updated", "status_changed"},
    }
    if root["type"] not in expected[kind]:
        raise HTTPException(422, "Configured trigger does not match the publication")
    next_at = None
    try:
        if kind == "scheduled":
            parsed = ScheduleConfig.model_validate(config)
            config = parsed.model_dump(mode="json")
            next_at = next_occurrence(config, now())
            if enabled and next_at is None:
                raise ValueError("Schedule has no future occurrence")
        elif kind == "webhook":
            if set(config) - {"schema", "ip_allowlist", "max_per_minute"}:
                raise ValueError("Unknown webhook policy")
            if "schema" not in config:
                raise ValueError("An explicit webhook input schema is required")
            validate_schema(config["schema"])
            if config["schema"].get("type") != "object":
                raise ValueError("Webhook root must be an object")
            networks = config.get("ip_allowlist", [])
            if not isinstance(networks, list) or len(networks) > 20:
                raise ValueError("IP allowlist is too large")
            for network in networks:
                ipaddress.ip_network(network, strict=False)
            if (
                not isinstance(config.get("max_per_minute", 30), int)
                or not 1 <= config.get("max_per_minute", 30) <= 120
            ):
                raise ValueError("Webhook rate must be 1–120 requests per minute")
        else:
            if (
                set(config) - {"provider", "event", "schema"}
                or config.get("provider") not in EVENT_PROVIDERS
            ):
                raise ValueError("Internal event provider is not registered")
            if not EVENT_PROVIDERS[config["provider"]](
                db, user, row.organization_id, config.get("event")
            ):
                raise ValueError("Event subscription is not authorized")
            validate_schema(config.get("schema", {}))
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from None
    trigger = (
        db.query(Trigger)
        .filter_by(resource_id=row.id, kind=kind)
        .with_for_update()
        .first()
    )
    if not trigger:
        trigger = Trigger(
            **scope_values(row),
            resource_id=row.id,
            kind=kind,
            endpoint=secrets.token_urlsafe(24),
        )
        db.add(trigger)
    trigger.enabled = enabled
    trigger.config = config
    trigger.next_at = next_at
    secret = None
    if kind == "webhook" and not trigger.encrypted_secret:
        secret = secrets.token_urlsafe(32)
        trigger.encrypted_secret = cipher().encrypt(secret.encode()).decode()
    db.add(
        Event(
            **scope_values(row),
            resource_id=row.id,
            kind="trigger_configured",
            details={"actor_user_id": user.id, "kind": kind, "enabled": enabled},
        )
    )
    db.flush()
    return trigger, secret


def trigger_identity(db, trigger):
    state = (
        db.query(Deployment)
        .filter_by(
            resource_id=trigger.resource_id, organization_id=trigger.organization_id
        )
        .first()
    )
    service = bool(state and state.policy.get("identity") == "service")
    user_id = state.policy["service_user_id"] if service else trigger.owner_user_id
    return authority(
        db,
        user_id,
        trigger.organization_id,
        trigger.environment,
        trigger.owner_user_id,
        service=service,
    )


def webhook(db, endpoint, body, timestamp, nonce, signature, client_ip):
    if len(body) > 32768:
        raise HTTPException(413, "Webhook payload exceeds 32 KB")
    hint = (
        db.query(Trigger)
        .filter_by(endpoint=endpoint, kind="webhook", enabled=True)
        .first()
    )
    if not hint:
        raise HTTPException(404, "Webhook is unavailable")
    db.query(PowerResource).filter_by(id=hint.resource_id).with_for_update().one()
    trigger = (
        db.query(Trigger)
        .filter_by(id=hint.id, enabled=True)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not trigger:
        raise HTTPException(404, "Webhook is unavailable")
    try:
        epoch = int(timestamp)
        if abs(now().timestamp() - epoch) > 300 or not 8 <= len(nonce) <= 180:
            raise ValueError()
        networks = trigger.config.get("ip_allowlist", [])
        if networks and not any(
            ipaddress.ip_address(client_ip) in ipaddress.ip_network(net, strict=False)
            for net in networks
        ):
            raise ValueError()
        secret = cipher().decrypt(trigger.encrypted_secret.encode())
        signed = timestamp.encode() + b"." + nonce.encode() + b"." + body
        expected = hmac.new(secret, signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature.removeprefix("sha256=")):
            raise ValueError()
    except Exception:
        raise HTTPException(401, "Invalid webhook authentication") from None
    nonce_hash = hashlib.sha256(nonce.encode()).hexdigest()
    if db.query(Replay).filter_by(trigger_id=trigger.id, nonce_hash=nonce_hash).first():
        raise HTTPException(409, "Webhook replay rejected")
    recent = (
        db.query(Replay)
        .filter_by(trigger_id=trigger.id)
        .filter(Replay.created_at >= now() - timedelta(minutes=1))
        .count()
    )
    if recent >= trigger.config.get("max_per_minute", 30):
        raise HTTPException(429, "Webhook rate limit reached")
    try:
        data = json.loads(body)
        schema_check(data, trigger.config["schema"])
    except (ValueError, TypeError, KeyError):
        raise HTTPException(
            422, "Webhook payload does not match its input contract"
        ) from None
    user = trigger_identity(db, trigger)
    row = (
        db.query(PowerResource)
        .filter_by(
            id=trigger.resource_id,
            organization_id=trigger.organization_id,
            environment=trigger.environment,
        )
        .one()
    )
    db.add(
        Replay(
            **scope_values(trigger),
            trigger_id=trigger.id,
            nonce_hash=nonce_hash,
            created_at=now(),
        )
    )
    root = enqueue(
        db,
        row,
        user,
        data,
        f"webhook:{trigger.id}:{nonce_hash}",
        kind="webhook",
        trigger=trigger,
    )
    db.flush()
    return root


def scheduler_tick(db, limit=100):
    count = 0
    ids = [
        r[0]
        for r in db.query(Trigger.id)
        .filter_by(kind="scheduled", enabled=True)
        .filter(Trigger.next_at <= now())
        .order_by(Trigger.next_at)
        .limit(limit)
        .all()
    ]
    for trigger_id in ids:
        # Lock publication owner first, consistent with trigger configuration and publication.
        hint = db.get(Trigger, trigger_id)
        row = (
            db.query(PowerResource)
            .filter_by(id=hint.resource_id)
            .with_for_update(skip_locked=True)
            .first()
        )
        if not row:
            db.rollback()
            continue
        trigger = (
            db.query(Trigger)
            .filter_by(id=trigger_id, enabled=True)
            .filter(Trigger.next_at <= now())
            .with_for_update(skip_locked=True)
            .populate_existing()
            .first()
        )
        if not trigger:
            db.rollback()
            continue
        state = db.query(Deployment).filter_by(resource_id=row.id).first()
        if not state or state.status != "active":
            db.rollback()
            continue
        due = utc(trigger.next_at)
        try:
            user = trigger_identity(db, trigger)
            enqueue(
                db,
                row,
                user,
                {"scheduled_at": due.isoformat()},
                f"schedule:{trigger.id}:{due.isoformat()}",
                kind="scheduled",
                trigger=trigger,
            )
            trigger.last_at = due
            # Missed ticks coalesce to one run; no unbounded catch-up storm.
            trigger.next_at = next_occurrence(trigger.config, max(due, now()))
            if trigger.next_at is None:
                trigger.enabled = False
            db.commit()
            count += 1
        except HTTPException as exc:
            db.rollback()
            if exc.status_code not in {429, 409}:
                trigger = db.get(Trigger, trigger_id)
                trigger.enabled = False
                db.add(
                    Event(
                        **scope_values(trigger),
                        resource_id=trigger.resource_id,
                        kind="trigger_authorization_failed",
                        details={"trigger_id": trigger.id},
                    )
                )
                db.commit()
    return count


def emit_event(db, provider, event_name, company, environment, event_id, data, actor):
    if provider not in EVENT_PROVIDERS or not EVENT_PROVIDERS[provider](
        db, actor, company, event_name
    ):
        raise HTTPException(403, "Internal event provider is not authorized")
    ids = []
    for trigger in (
        db.query(Trigger)
        .filter_by(
            organization_id=company,
            environment=environment,
            kind="internal",
            enabled=True,
        )
        .all()
    ):
        if (
            trigger.config.get("provider") != provider
            or trigger.config.get("event") != event_name
        ):
            continue
        schema_check(data, trigger.config["schema"])
        user = authority(
            db, trigger.owner_user_id, company, environment, trigger.owner_user_id
        )
        row = (
            db.query(PowerResource)
            .filter_by(
                id=trigger.resource_id, organization_id=company, environment=environment
            )
            .one()
        )
        root = enqueue(
            db,
            row,
            user,
            data,
            f"event:{provider}:{hashlib.sha256(event_id.encode()).hexdigest()}",
            kind="internal",
            trigger=trigger,
        )
        ids.append(root.id)
    return ids
