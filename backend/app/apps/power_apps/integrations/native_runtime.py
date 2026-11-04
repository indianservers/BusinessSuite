"""Native subscription controller and authenticated, durable notification inbox."""

import copy
import hashlib
import json
import secrets
import time
import uuid
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.ai_operator.providers import cipher
from app.apps.power_apps.runtime import now, utc, scope_values
from app.apps.power_apps.runtime_models import (
    AutomationTrigger as Trigger,
    AutomationDeployment as Deployment,
)
from app.apps.power_apps.models import PowerResource
from app.apps.power_apps.integrations.models import (
    NativeDelivery,
    Connection,
    ConnectorGate,
)
from app.apps.power_apps.integrations import (
    native_specs as specs,
    native_subscriptions as subscriptions,
)
from app.apps.power_apps.integrations import (
    native_sources as sources,
    native_events as events,
)
from app.apps.power_apps.integrations.contracts import IntegrationFailure


def read_private(trigger):
    try:
        return json.loads(cipher().decrypt(trigger.encrypted_secret.encode()))
    except Exception:
        raise HTTPException(
            409, "Native trigger credentials need to be configured again"
        ) from None


def write_private(trigger, value):
    encoded = json.dumps(value, allow_nan=False).encode()
    if len(encoded) > 1048576:
        raise IntegrationFailure(
            "snapshot", "Native private state exceeds 1 MB; narrow the resource watch"
        )
    trigger.encrypted_secret = cipher().encrypt(encoded).decode()


def callback_url(trigger):
    from app.core.config import settings

    base = settings.BACKEND_PUBLIC_URL.rstrip("/")
    parsed = urlsplit(base)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(
            422, "Native webhooks require BACKEND_PUBLIC_URL to be a public HTTPS URL"
        )
    mid = trigger.config["module_id"]
    if mid in specs.SHARED_APPS:
        return (
            base
            + "/api/v1/power-apps/native-apps/"
            + mid
            + "/"
            + subscriptions.q(trigger.config["setup"]["app_id"])
        )
    return base + "/api/v1/power-apps/native-hooks/" + trigger.endpoint


def prepare(db, row, trigger, state, module_id, setup, enabled, provider_secrets):
    trigger.config = trigger.config or {}
    try:
        specs.validate_native(module_id, setup)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from None
    native = trigger.config.get("native", {})
    previous = read_private(trigger) if native.get("managed") else {}
    if set(provider_secrets) - specs.SECRET_FIELDS.get(module_id, {}).keys():
        raise HTTPException(422, "Unknown native provider credential field")
    same = bool(
        native
        and trigger.config.get("version_id") == state.version_id
        and trigger.config.get("setup") == setup
    )
    if same:
        private = previous
        if provider_secrets:
            private["secrets"].update(provider_secrets)
        epoch = native["epoch"]
    else:
        epoch = str(uuid.uuid4())
        retained = list(previous.get("retired", []))
        if previous.get("state"):
            retained.append(
                {
                    "module_id": trigger.config["module_id"],
                    "setup": trigger.config["setup"],
                    "private": {k: v for k, v in previous.items() if k != "retired"},
                }
            )
        private = {
            "epoch": epoch,
            "started_at": now().isoformat(),
            "state": {},
            "retired": retained,
            "secrets": {
                "verification": secrets.token_urlsafe(24),
                **{key:value for key,value in previous.get("secrets",{}).items() if key in specs.SECRET_FIELDS.get(module_id,{})},
                **provider_secrets,
            },
        }
        # Every publication gets a fresh channel/client-state secret. App signing
        # credentials may be reused; old callback secrets remain only for cleanup.
        private["secrets"]["verification"] = secrets.token_urlsafe(24)
    missing = [
        key
        for key in specs.SECRET_FIELDS.get(module_id, {})
        if not private["secrets"].get(key)
    ]
    if "cloud_service_account" in provider_secrets:
        private["secrets"].pop("cloud_access_token",None)
        private["secrets"].pop("cloud_token_until",None)
    if missing and enabled:
        raise HTTPException(
            422, "Provide native provider credentials: " + ", ".join(missing)
        )
    if module_id in specs.SHARED_APPS:
        for other in (
            db.query(Trigger)
            .filter(Trigger.kind == "connector", Trigger.id != trigger.id)
            .all()
        ):
            cfg = other.config
            if (
                cfg.get("native", {}).get("managed")
                and cfg.get("module_id") == module_id
                and cfg.get("setup", {}).get("app_id") == setup.get("app_id")
                and cfg["setup"]["connection_id"] != setup["connection_id"]
            ):
                raise HTTPException(
                    409,
                    "This provider app is already managed through another saved connection; reuse that connection",
                )
    trigger.config = {
        "module_id": module_id,
        "setup": setup,
        "version_id": state.version_id,
        "native": {
            "managed": True,
            "mode": specs.mode(module_id, setup),
            "phase": "pending" if enabled else "pending_cleanup",
            "epoch": epoch,
            "error": None,
        },
        **(
            {"branch_id": trigger.config["branch_id"]}
            if trigger.config.get("branch_id")
            else {}
        ),
    }
    from app.branches.models import BranchOwnership

    ownership = (
        db.query(BranchOwnership)
        .filter_by(
            resource_table="power_apps_resources",
            resource_key=str(row.id),
            company_id=row.organization_id,
        )
        .first()
    )
    if ownership:
        trigger.config = {**trigger.config, "branch_id": ownership.branch_id}
    trigger.enabled = enabled
    trigger.next_at = now()
    write_private(trigger, private)
    if specs.mode(module_id, setup) in {
        "native_webhook",
        "native_pubsub",
    } and module_id not in {"gmail", "google_forms"}:
        callback_url(trigger)
    db.flush()
    return trigger, (
        private["secrets"]["verification"] if module_id == "http" and not same else None
    )


def disable(db, trigger):
    native = {
        **trigger.config["native"],
        "phase": "pending_cleanup",
        "lease": None,
        "lease_until": None,
    }
    trigger.enabled = False
    trigger.config = {**trigger.config, "native": native}
    trigger.next_at = now()
    db.flush()
    return trigger, None


def public_config(trigger):
    return {
        key: value for key, value in trigger.config.items() if key not in {"snapshot"}
    }


def receive(db, *, endpoint=None, module_id=None, app_id=None, query, headers, body):
    """No remote IO: validate provider auth, record encrypted inbox, acknowledge."""
    if len(body) > 262144:
        raise HTTPException(413, "Native notification exceeds 256 KB")
    try:
        data = json.loads(body) if body else {}
        if not isinstance(data, dict):
            raise ValueError()
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, "Invalid native notification JSON") from None
    if endpoint:
        candidates = (
            db.query(Trigger).filter_by(kind="connector", endpoint=endpoint).all()
        )
    elif module_id in specs.SHARED_APPS:
        candidates = (
            db.query(Trigger)
            .filter(
                Trigger.kind == "connector",
                Trigger.config["module_id"].as_string() == module_id,
                Trigger.config["setup"]["app_id"].as_string() == app_id,
            )
            .all()
        )
    else:
        raise HTTPException(404, "Native endpoint is unavailable")
    accepted = False
    for trigger in candidates:
        native = trigger.config.get("native", {})
        if not native.get("managed"):
            continue
        mid = trigger.config["module_id"]
        private = read_private(trigger)
        try:
            answer = events.challenge(mid, private, query, data, headers, body)
            if answer is not None:
                return answer
            events.verify(mid, private, headers, body, data)
        except (AttributeError,TypeError,ValueError,KeyError):
            if endpoint: raise HTTPException(401,"Invalid native provider notification") from None
            continue
        except HTTPException as exc:
            if endpoint:
                raise
            if exc.status_code == 401:
                continue
            raise
        accepted = True
        if not trigger.enabled:
            continue
        # Hint bodies can repeat across real changes (Graph doesn't provide event
        # IDs). Deduplicate hints briefly; hydrated revision IDs deduplicate runs.
        hint = mid in specs.GRAPH | {
            "google_drive",
            "google_calendar",
            "airtable",
            "jira",
        }
        identity = body + (str(int(time.time() // 10)).encode() if hint else b"")
        if mid in {"google_drive", "google_calendar"}:
            identity = (
                headers.get("x-goog-channel-id", "")
                + ":"
                + headers.get("x-goog-message-number", "")
            ).encode()
        if mid == "http" and headers.get("idempotency-key"):
            identity = headers["idempotency-key"].encode()
        message_id = hashlib.sha256(identity).hexdigest()
        if (
            db.query(NativeDelivery.id)
            .filter_by(
                trigger_id=trigger.id, epoch=native["epoch"], message_id=message_id
            )
            .first()
        ):
            continue
        if (
            db.query(NativeDelivery)
            .filter_by(trigger_id=trigger.id, status="pending")
            .count()
            >= 200
        ):
            raise HTTPException(
                429, "Native notification inbox is full; retry delivery"
            )
        recent = (
            db.query(NativeDelivery)
            .filter(
                NativeDelivery.trigger_id == trigger.id,
                NativeDelivery.created_at >= now() - timedelta(minutes=1),
            )
            .count()
        )
        if recent >= trigger.config["setup"].get("max_per_minute", 120):
            raise HTTPException(429, "Native notification rate exceeded")
        safe_headers = {
            k: headers[k]
            for k in (
                "x-github-event",
                "x-goog-channel-id",
                "x-goog-resource-id",
                "x-goog-message-number",
                "x-goog-resource-state",
            )
            if k in headers
        }
        payload = (
            cipher()
            .encrypt(json.dumps({"body": data, "headers": safe_headers}).encode())
            .decode()
        )
        try:
            with db.begin_nested():
                db.add(
                    NativeDelivery(
                        **scope_values(trigger),
                        trigger_id=trigger.id,
                        epoch=native["epoch"],
                        message_id=message_id,
                        encrypted_payload=payload,
                        status="pending",
                        next_at=now()
                    )
                )
                db.flush()
        except IntegrityError:
            continue
        if not native.get("lease_until") or native["lease_until"] <= now().isoformat():
            trigger.next_at = now()
    if not accepted:
        raise HTTPException(401, "Invalid native provider authentication")
    return {"accepted": True}, "application/json"


class StaleWork(Exception):
    pass


def _shared_in_use(db, trigger, mid, setup):
    for other in (
        db.query(Trigger)
        .filter(
            Trigger.kind == "connector",
            Trigger.enabled.is_(True),
            Trigger.id != trigger.id,
        )
        .all()
    ):
        cfg = other.config
        target = cfg.get("setup", {})
        if (
            not cfg.get("native", {}).get("managed")
            or cfg.get("module_id") != mid
            or target.get("connection_id") != setup["connection_id"]
        ):
            continue
        keys = {
            "slack": ["app_id"],
            "whatsapp_business": ["business_account_id"],
            "google_forms": ["form_id"],
        }.get(mid, [])
        if all(target.get(key) == setup.get(key) for key in keys):
            return True
    return False


def _matching(trigger, event):
    if event["event"] != trigger.config["setup"]["event"]:
        return False
    from app.apps.power_apps.integrations.automation_triggers import relay_payload

    try:
        relay_payload(trigger, event)
    except (ValueError, TypeError):
        return False
    return True


def _source_poll(client, mid, setup, private):
    if (
        mid in {"dropbox", "google_drive", "onedrive"}
        or mid == "sharepoint"
        and not setup.get("list_id")
    ):
        return sources.poll_files(client, mid, setup, private), []
    if (
        mid in {"notion", "hubspot", "jira"}
        or mid == "salesforce"
        and setup["event"] != "platform_event"
        or mid == "sharepoint"
        and setup.get("list_id")
    ):
        return sources.poll_inventory(client, mid, setup, private), []
    if mid in {"google_calendar", "microsoft_calendar"}:
        return sources.poll_calendar(client, mid, setup, private), []
    if mid in {"gmail", "google_forms"}:
        return sources.poll_pubsub(client, mid, setup, private)
    if mid == "airtable":
        return sources.poll_airtable(client, setup, private), []
    if mid == "salesforce":
        return sources.poll_stream(client, setup, private), []
    if mid == "http" and setup["event"] == "response_condition_matched":
        from app.apps.power_apps.integrations import adapters
        from app.apps.power_apps.integrations.contracts import HTTPInput
        from app.apps.power_apps.authoring import path

        request = HTTPInput.model_validate(setup["request"])
        # Reuse HTTP's allowlisted hosts and typed request adapter, including auth.
        from app.apps.power_apps.integrations.transport import EgressPolicy

        response = adapters.http_action(
            client.conn,
            request,
            adapters.HTTP_FACTORY(EgressPolicy(client.conn.config["hosts"])),
            client.headers,
            {},
            "native-http-read",
        )
        matched = all(
            path(response["body"], key) == value
            for key, value in setup["condition"].items()
        )
        old = private["state"].get("condition_match", False)
        private["state"]["condition_match"] = matched
        return (
            [
                sources.event(
                    "response_condition_matched",
                    {"response": sources.compact(response)},
                    [sources.digest(response), private["state"].get("sequence", 0)],
                )
            ]
            if matched and not old
            else []
        ), []
    return [], []


def tick(db, limit=1):
    """Lease native work before IO; source cursors commit with enqueued runs."""
    from app.apps.power_apps.runtime_triggers import trigger_identity
    from app.apps.power_apps.runtime import enqueue
    from app.apps.power_apps.integrations import vault, service
    from app.apps.power_apps.integrations.native_http import NativeClient
    from app.access.service import background_scope

    ids = [
        id
        for id, in db.query(Trigger.id)
        .filter(
            Trigger.kind == "connector",
            Trigger.config["native"]["managed"].as_boolean().is_(True),
            Trigger.next_at <= now(),
        )
        .order_by(Trigger.next_at, Trigger.id)
        .limit(limit)
        .all()
    ]
    for id in ids:
        lease = None
        connection_id = None
        reserved = False
        failure = None
        try:
            trigger = (
                db.query(Trigger)
                .filter(Trigger.id == id, Trigger.next_at <= now())
                .with_for_update(skip_locked=True)
                .populate_existing()
                .first()
            )
            if not trigger:
                db.rollback()
                continue
            native = dict(trigger.config["native"])
            if native.get("lease_until") and native["lease_until"] > now().isoformat():
                db.rollback()
                continue
            epoch = native["epoch"]
            cfg = copy.deepcopy(trigger.config)
            mid = cfg["module_id"]
            setup = cfg["setup"]
            lease = "native:" + uuid.uuid4().hex
            native.update(
                lease=lease, lease_until=(now() + timedelta(seconds=120)).isoformat()
            )
            trigger.config = {**cfg, "native": native}
            trigger.next_at = now() + timedelta(seconds=120)
            db.commit()
            private = read_private(trigger)
            row = db.get(PowerResource, trigger.resource_id)
            state = (
                db.query(Deployment).filter_by(resource_id=trigger.resource_id).first()
            )
            removing = (
                not trigger.enabled
                or not row
                or row.archived_at
                or not state
                or state.version_id != cfg["version_id"]
                or state.status not in {"active", "published", "paused"}
            )
            actor = trigger_identity(db, trigger)
            with background_scope(
                db, actor, "power_apps", "create", branch_id=cfg.get("branch_id")
            ):
                conn = vault.connection(
                    db, actor, trigger.environment, setup["connection_id"], lock=True
                )
                connection_id = conn.id
                gate = (
                    db.query(ConnectorGate)
                    .filter_by(connection_id=conn.id)
                    .with_for_update()
                    .first()
                )
                if gate and any(
                    k.startswith("native:") and v > now().timestamp()
                    for k, v in (gate.leases or {}).items()
                ):
                    trigger.config = {
                        **trigger.config,
                        "native": {**native, "lease": None, "lease_until": None},
                    }
                    trigger.next_at = now() + timedelta(seconds=5)
                    db.commit()
                    continue
                service.reserve(db, conn, lease)
                db.commit()
                reserved = True
                client = NativeClient(db, actor, conn)

                def checkpoint():
                    current = (
                        db.query(Trigger)
                        .filter_by(id=id)
                        .with_for_update()
                        .populate_existing()
                        .one()
                    )
                    active = current.config.get("native", {})
                    if active.get("epoch") != epoch:
                        newer = read_private(current)
                        retired = {
                            "module_id": mid,
                            "setup": setup,
                            "private": {
                                k: v for k, v in private.items() if k != "retired"
                            },
                        }
                        newer["retired"] = [
                            r
                            for r in newer.get("retired", [])
                            if r["private"].get("epoch") != private["epoch"]
                        ] + [retired]
                        write_private(current, newer)
                        db.commit()
                        raise StaleWork()
                    write_private(current, private)
                    current.config = {
                        **current.config,
                        "native": {
                            **active,
                            "expires_at": private.get("state", {}).get("expires_at"),
                        },
                    }
                    db.commit()
                    if active.get("lease") != lease:
                        raise StaleWork()

                # Retire old publications/connections before provisioning replacements.
                while private.get("retired"):
                    retired = private["retired"][0]
                    old_conn = vault.connection(
                        db,
                        actor,
                        trigger.environment,
                        retired["setup"]["connection_id"],
                    )
                    subscriptions.remove(
                        NativeClient(db, actor, old_conn),
                        retired["module_id"],
                        retired["setup"],
                        retired["private"],
                        shared_in_use=_shared_in_use(
                            db, trigger, retired["module_id"], retired["setup"]
                        ),
                    )
                    private["retired"].pop(0)
                    checkpoint()
                if removing:
                    subscriptions.remove(
                        client,
                        mid,
                        setup,
                        private,
                        shared_in_use=_shared_in_use(db, trigger, mid, setup),
                    )
                    current = (
                        db.query(Trigger)
                        .filter_by(id=id)
                        .with_for_update()
                        .populate_existing()
                        .one()
                    )
                    if (
                        current.config["native"].get("epoch") != epoch
                        or current.config["native"].get("lease") != lease
                    ):
                        raise StaleWork()
                    private["state"] = {}
                    write_private(current, private)
                    current.enabled = False
                    current.next_at = None
                    current.config = {
                        **current.config,
                        "native": {
                            **current.config["native"],
                            "phase": "disabled",
                            "lease": None,
                            "lease_until": None,
                            "error": None,
                        },
                    }
                    db.commit()
                    continue
                if mid == "slack":
                    for other in (
                        db.query(Trigger)
                        .filter(Trigger.kind == "connector", Trigger.id != id)
                        .all()
                    ):
                        if (
                            other.config.get("native", {}).get("managed")
                            and other.config.get("module_id") == mid
                            and other.config.get("setup", {}).get("app_id")
                            == setup["app_id"]
                        ):
                            previous = (
                                read_private(other)
                                .get("state", {})
                                .get("previous_events")
                            )
                            if previous is not None:
                                private["shared_previous"] = previous
                                break
                callback = (
                    callback_url(trigger)
                    if specs.mode(mid, setup) == "native_webhook"
                    else ""
                )
                subscriptions.ensure(client, mid, setup, private, callback, checkpoint)
                queued = []
                processed = []
                acks = []
                # Keep notifications queued while a publication is paused.
                if state.status == "active":
                    deliveries = (
                        db.query(NativeDelivery)
                        .filter(
                            NativeDelivery.trigger_id == id,
                            NativeDelivery.epoch == epoch,
                            NativeDelivery.status == "pending",
                            NativeDelivery.next_at <= now(),
                        )
                        .order_by(NativeDelivery.id)
                        .limit(30)
                        .all()
                    )
                    for delivery in deliveries:
                        payload = json.loads(
                            cipher().decrypt(delivery.encrypted_payload.encode())
                        )
                        queued.extend(
                            events.normalize(client, mid, setup, private, payload)
                        )
                        processed.append(delivery.id)
                    fresh, acks = _source_poll(client, mid, setup, private)
                    queued.extend(fresh)
                # Fence authority/publication again after OAuth refresh and remote IO.
                db.query(PowerResource).filter_by(id=row.id).with_for_update().one()
                current = (
                    db.query(Trigger)
                    .filter_by(id=id)
                    .with_for_update()
                    .populate_existing()
                    .one()
                )
                current_state = (
                    db.query(Deployment)
                    .filter_by(resource_id=row.id)
                    .populate_existing()
                    .one()
                )
                if (
                    current.config["native"].get("epoch") != epoch
                    or current.config["native"].get("lease") != lease
                    or not current.enabled
                    or current_state.version_id != cfg["version_id"]
                ):
                    raise StaleWork()
                if current_state.status != "active" and (queued or processed):
                    raise StaleWork()
                for item in queued:
                    if not _matching(current, item):
                        continue
                    payload = {**item, "module_id": mid}
                    key = "native:" + sources.digest(
                        [id, epoch, item["event"], item["event_id"]]
                    )
                    enqueue(
                        db, row, actor, payload, key, kind="connector", trigger=current
                    )
                for delivery in (
                    db.query(NativeDelivery)
                    .filter(NativeDelivery.id.in_(processed))
                    .all()
                ):
                    delivery.status = "completed"
                    delivery.encrypted_payload = None
                private["state"]["sequence"] = private["state"].get("sequence", 0) + 1
                write_private(current, private)
                current.config = {
                    **current.config,
                    "native": {
                        **current.config["native"],
                        "phase": "active",
                        "error": None,
                        "lease": None,
                        "lease_until": None,
                        "expires_at": private["state"].get("expires_at"),
                    },
                }
                current.last_at = now()
                current.next_at = now() + timedelta(
                    seconds=(
                        5
                        if mid == "salesforce" and setup["event"] == "platform_event"
                        else setup.get("interval_seconds", 30)
                    )
                )
                db.commit()
                # Acknowledgment follows the durable cursor/run commit. An ack
                # failure may redeliver, but stable event identities prevent reruns.
                if acks:
                    client.request(
                        "POST",
                        "/v1/" + private["state"]["subscription"] + ":acknowledge",
                        {"ackIds": acks},
                        host="pubsub.googleapis.com",
                        bearer=subscriptions.cloud_token(client, private),
                    )
        except StaleWork:
            db.rollback()
        except Exception as exc:
            failure = (
                exc
                if isinstance(exc, IntegrationFailure)
                else IntegrationFailure("native", "Native provider work failed")
            )
            db.rollback()
            trigger = db.query(Trigger).filter_by(id=id).with_for_update().first()
            if trigger and trigger.config.get("native", {}).get("lease") == lease:
                category = (
                    exc.category
                    if isinstance(exc, IntegrationFailure)
                    else (
                        "authorization"
                        if isinstance(exc, HTTPException)
                        else "provider"
                    )
                )
                error = (
                    "Native setup or read failed ("
                    + category
                    + "). Check provider permissions, resource fields and setup credentials."
                )
                native = {
                    **trigger.config["native"],
                    "phase": "retrying",
                    "error": error,
                    "lease": None,
                    "lease_until": None,
                }
                trigger.config = {**trigger.config, "native": native}
                trigger.next_at = now() + timedelta(seconds=60)
                db.commit()
        finally:
            if connection_id and lease and reserved:
                db.rollback()
                conn = db.get(Connection, connection_id)
                if conn:
                    service.release(db, conn, lease, failure)
                    db.commit()
