"""Connector event ingress and durable row/update cursors on the existing worker.

Sheet polling requires a complete bounded snapshot and stable unique row keys.
Incomplete pages and duplicate keys fail closed instead of reporting false deletes.
Other providers use the existing HMAC relay protocol, not unsigned public ingress.
"""

import hashlib
import json
import secrets
from datetime import timedelta

from fastapi import HTTPException
from app.ai_operator.providers import cipher
from app.apps.power_apps.integrations.automation_catalog import (
    MODULES,
    trigger_schema,
    EVENT_RESOURCE_FIELDS,
)


def validate_setup(module_id, config):
    if module_id not in MODULES:
        raise ValueError("Unsupported connector trigger")
    schema = trigger_schema(module_id)
    if (
        set(config) - schema["properties"].keys()
        or set(schema["required"]) - config.keys()
    ):
        raise ValueError("Provide exactly the declared trigger setup fields")
    if config.get("event") not in MODULES[module_id]["events"]:
        raise ValueError("Unsupported connector event")
    for key, field in schema["properties"].items():
        if key not in config:
            continue
        value = config[key]
        typ = {
            "integer": int,
            "string": str,
            "array": list,
            "object": dict,
            "boolean": bool,
        }[field["type"]]
        if type(value) is not typ or typ is str and not value.strip():
            raise ValueError(f"Invalid trigger field: {key}")
        if typ is int and not field.get("minimum", 1) <= value <= field.get(
            "maximum", 2**31 - 1
        ):
            raise ValueError(f"Trigger field outside limits: {key}")
        if typ is list and any(not isinstance(item, str) or not item for item in value):
            raise ValueError(f"Trigger field must contain nonempty names: {key}")
    if any(not isinstance(v, str) or not v for v in config.get("watched_columns", [])):
        raise ValueError("Watched columns must be nonempty names")
    if config.get("event") == "condition_matched" and not config.get("condition"):
        raise ValueError("Condition matched requires column/value conditions")
    if len(json.dumps(config, allow_nan=False)) > 16384:
        raise ValueError("Trigger configuration exceeds 16 KB")
    return dict(config)


def configure(db, row, user, enabled, config, provider_secrets=None):
    from app.apps.power_apps.runtime_models import (
        AutomationTrigger as Trigger,
        AutomationDeployment as Deployment,
    )
    from app.apps.power_apps.models import PowerVersion
    from app.apps.power_apps.runtime import now, scope_values
    from app.apps.power_apps.integrations import vault

    state = db.query(Deployment).filter_by(resource_id=row.id).with_for_update().first()
    if (
        not state
        or not state.version_id
        or state.status not in {"published", "paused", "active"}
    ):
        raise HTTPException(409, "Publish before configuring connector triggers")
    if user.id != row.owner_user_id:
        raise HTTPException(
            403, "Only the workflow owner may configure connector triggers"
        )
    if (
        enabled
        and state.policy.get("identity") != "service"
        and not (
            state.policy.get("identity") == "owner"
            and state.policy.get("delegated_owner")
        )
    ):
        raise HTTPException(
            422, "Background triggers require explicit owner delegation at publication"
        )
    nodes = db.get(PowerVersion, state.version_id).snapshot["definition"]["nodes"]
    root = next(
        (n for n in nodes if n["type"].startswith("integration_trigger_")), None
    )
    if not root:
        raise HTTPException(422, "Publication needs a connector trigger node")
    module_id = root["type"].removeprefix("integration_trigger_")
    # The selected node is the source of setup; runtime UI can only enable it.
    setup = root.get("config", {}).get("setup", {})
    if config and config != setup:
        raise HTTPException(
            422, "Edit trigger setup in the workflow builder and publish it first"
        )
    try:
        setup = validate_setup(module_id, setup)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from None
    trigger = (
        db.query(Trigger)
        .filter_by(resource_id=row.id, kind="connector")
        .with_for_update()
        .first()
    )
    if trigger and not enabled:
        if trigger.config.get("native",{}).get("managed"):
            from app.apps.power_apps.integrations.native_runtime import disable
            return disable(db,trigger)
        trigger.enabled = False
        trigger.next_at = None
        db.flush()
        return trigger, None
    if not trigger:
        trigger = Trigger(
            **scope_values(row),
            resource_id=row.id,
            kind="connector",
            endpoint=secrets.token_urlsafe(24),
        )
        db.add(trigger)
    from app.apps.power_apps.runtime_triggers import trigger_identity

    # Use the same execution principal that will read the connection in the worker.
    actor = trigger_identity(db, trigger)
    from app.access.service import background_scope

    with background_scope(db, actor, "power_apps", "view"):
        conn = vault.connection(db, actor, row.environment, setup["connection_id"])
        if conn.connector_id != module_id or not conn.enabled:
            raise HTTPException(422, "Choose an enabled connection for this connector")
        if enabled and module_id == "telegram":
            from app.apps.power_apps.telegram import bot_request

            bot = bot_request(db, actor, conn, "getMe")
            if bot_request(db, actor, conn, "getWebhookInfo").get("url"):
                raise HTTPException(
                    409, "Remove the bot's existing webhook before enabling polling"
                )
            for other in (
                db.query(Trigger)
                .filter(Trigger.enabled.is_(True), Trigger.id != trigger.id)
                .all()
            ):
                if other.config.get("bot_id") == bot["id"]:
                    raise HTTPException(
                        409, "This bot already has an active polling listener"
                    )
            bot_id = bot["id"]
        else:
            bot_id = None
    version_id = state.version_id
    from app.apps.power_apps.integrations.native_specs import POLLING
    if module_id not in POLLING:
        from app.apps.power_apps.integrations.native_runtime import prepare
        return prepare(db,row,trigger,state,module_id,setup,enabled,provider_secrets or {})
    preserve = bool(
        trigger.config
        and trigger.config.get("version_id") == version_id
        and trigger.config.get("setup") == setup
    )
    previous = trigger.config if preserve else {}
    trigger.config = {
        "module_id": module_id,
        "setup": setup,
        "version_id": version_id,
        "schema": {"type": "object", "additionalProperties": True},
        "max_per_minute": setup.get("max_per_minute", 30),
        "snapshot": previous.get("snapshot"),
        "offset": previous.get("offset", 0),
        "generation": previous.get("generation", 0),
        "bot_id": bot_id or previous.get("bot_id"),
        "started_at": previous.get("started_at", int(now().timestamp())),
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
    trigger.next_at = (
        now() if module_id in {"telegram", "google_sheets", "excel_online"} else None
    )
    secret = None
    if (
        module_id not in {"telegram", "google_sheets", "excel_online"}
        and not trigger.encrypted_secret
    ):
        secret = secrets.token_urlsafe(32)
        trigger.encrypted_secret = cipher().encrypt(secret.encode()).decode()
    db.flush()
    return trigger, secret


def rows_snapshot(headers, rows, key_column):
    if len(headers) != len(set(headers)) or any(
        not isinstance(h, str) or not h for h in headers
    ):
        raise ValueError("Spreadsheet headers must be nonempty and unique")
    if key_column not in headers:
        raise ValueError("Unique key column is missing")
    if len(rows) > 1000:
        raise ValueError("Watch at most 1000 rows per trigger")
    result = {}
    for values in rows:
        if not isinstance(values, list) or len(values) > len(headers):
            raise ValueError("Row does not match headers")
        if not any(v not in (None, "") for v in values):
            continue
        record = {
            h: values[i] if i < len(values) else "" for i, h in enumerate(headers)
        }
        key = record[key_column]
        if key is None or key == "":
            raise ValueError("Every nonempty row needs a stable key")
        key = str(key)
        if key in result:
            raise ValueError("Duplicate unique row key")
        result[key] = record
    if len(json.dumps(result, allow_nan=False).encode()) > 65536:
        raise ValueError("Watched spreadsheet snapshot exceeds 64 KB; narrow the range")
    return result


def row_events(previous, current, setup):
    if previous is None and not setup.get("emit_initial", False):
        return []
    previous = previous or {}
    selected = setup["event"]
    watched = setup.get("watched_columns", [])
    available = set().union(
        *(r.keys() for r in [*previous.values(), *current.values()])
    )
    if available and watched and set(watched) - available:
        raise ValueError("A watched column is missing")
    events = []
    for key in sorted(previous.keys() | current.keys()):
        old = previous.get(key)
        new = current.get(key)
        changed = [
            c
            for c in sorted((old or {}).keys() | (new or {}).keys())
            if (old or {}).get(c) != (new or {}).get(c)
        ]
        event = (
            "row_added"
            if old is None
            else "row_deleted" if new is None else "row_updated"
        )
        if not changed or watched and not set(changed) & set(watched):
            continue
        if selected == "condition_matched":
            condition = setup.get("condition", {})
            if not condition:
                raise ValueError(
                    "Condition matched requires at least one column/value condition"
                )
            matches = lambda row: row is not None and all(
                row.get(k) == v for k, v in condition.items()
            )
            if not matches(new) or matches(old):
                continue
            event = "condition_matched"
        elif selected == "cell_changed":
            if old is None or new is None:
                continue
            event = "cell_changed"
        elif selected != event:
            continue
        events.append(
            dict(
                event=event,
                row_key=key,
                previous=old,
                current=new,
                changed_columns=changed,
            )
        )
    if len(events) > 100:
        raise ValueError(
            "More than 100 changes; narrow the watched range before retrying"
        )
    return events


def telegram_events(updates, setup, offset=0, started_at=0):
    names = {
        "message": "message_received",
        "channel_post": "channel_post",
        "edited_message": "edited_message",
        "edited_channel_post": "edited_message",
        "callback_query": "callback_query",
        "my_chat_member": "membership_updated",
        "chat_member": "membership_updated",
    }
    result = []
    for update in sorted(updates, key=lambda x: x["update_id"]):
        if update["update_id"] < offset:
            continue
        offset = update["update_id"] + 1
        for field, event in names.items():
            if field not in update or setup["event"] != event:
                continue
            value = update[field]
            message = value.get("message", value)
            # Callback messages may be old even when the button click is new.
            # Edited messages carry the edit timestamp separately from send time.
            if value.get("edit_date", value.get("date", started_at)) < started_at:
                continue
            chat = message.get("chat", {}).get("id")
            if setup.get("chat_id") and str(chat) != setup["chat_id"]:
                continue
            result.append(
                dict(
                    event=event,
                    event_id=str(update["update_id"]),
                    chat_id=str(chat) if chat is not None else None,
                    text=message.get("text", message.get("caption", "")),
                    message=message,
                    update=update,
                )
            )
    return result, offset


def relay_payload(trigger, data):
    setup = trigger.config["setup"]
    if data.get("event") != setup["event"] or not isinstance(data.get("data"), dict):
        raise ValueError(
            "Relay requires the configured event and an object data payload"
        )
    if (
        not isinstance(data.get("event_id"), str)
        or not 1 <= len(data["event_id"]) <= 180
    ):
        raise ValueError("Relay requires a stable provider event_id")
    if any(data["data"].get(k) != v for k, v in setup.get("filters", {}).items()):
        raise ValueError("Event does not match the configured filters")
    for token in EVENT_RESOURCE_FIELDS.get(trigger.config["module_id"], "").split():
        key = token.partition(":")[0]
        if key not in setup or setup[key] == []:
            continue
        value = data["data"]
        if key in {"text_contains", "subject_contains"}:
            matches = setup[key] in str(value.get(key.removesuffix("_contains"), ""))
        elif key == "path_prefix":
            matches = str(value.get("path", "")).startswith(setup[key])
        elif key == "label_id":
            matches = setup[key] in value.get("label_ids", [])
        elif key == "watched_fields":
            matches = bool(set(setup[key]) & set(value.get("changed_fields", [])))
        else:
            matches = value.get(key) == setup[key]
        if not matches:
            raise ValueError("Event does not match the selected provider resource")
    return {
        "event": data["event"],
        "event_id": data["event_id"],
        "data": data["data"],
        "module_id": trigger.config["module_id"],
    }


def poll_tick(db, limit=10):
    from app.apps.power_apps.runtime_models import (
        AutomationTrigger as Trigger,
        AutomationDeployment as Deployment,
    )
    from app.apps.power_apps.models import PowerResource
    from app.apps.power_apps.runtime import now, utc, enqueue
    from app.apps.power_apps.runtime_triggers import trigger_identity
    from app.apps.power_apps.integrations import vault, service
    from app.access.service import background_scope

    ids = [
        id
        for id, in db.query(Trigger.id)
        .filter(
            Trigger.kind == "connector",
                Trigger.config["native"]["managed"].as_boolean().is_not(True),
            Trigger.enabled.is_(True),
            Trigger.next_at <= now(),
        )
        .order_by(Trigger.next_at, Trigger.id)
        .limit(limit)
        .all()
    ]
    for id in ids:
        try:
            trigger = (
                db.query(Trigger)
                .filter(
                    Trigger.id == id,
                    Trigger.enabled.is_(True),
                    Trigger.next_at <= now(),
                )
                .with_for_update(skip_locked=True)
                .first()
            )
            if not trigger:
                db.rollback()
                continue
            config = dict(trigger.config)
            if config.get("native",{}).get("managed"):
                db.rollback()
                continue
            setup = config["setup"]
            mid = config["module_id"]
            state = (
                db.query(Deployment)
                .filter_by(resource_id=trigger.resource_id, status="active")
                .first()
            )
            row = db.get(PowerResource, trigger.resource_id)
            if (
                not state
                or state.version_id != config["version_id"]
                or not row
                or row.archived_at
            ):
                trigger.next_at = now() + timedelta(seconds=30)
                db.commit()
                continue
            # Claim before invoke (which commits its journal). Other workers skip this lease.
            trigger.next_at = now() + timedelta(seconds=120)
            db.commit()
            actor = trigger_identity(db, trigger)
            with background_scope(
                db, actor, "power_apps", "create", branch_id=config.get("branch_id")
            ):
                conn = vault.connection(
                    db, actor, trigger.environment, setup["connection_id"]
                )
                if conn.connector_id != mid or not conn.enabled:
                    raise ValueError("Connection is unavailable")
                generation = config.get("generation", 0)
                # A failed sample must fetch fresh data on retry, rather than
                # replaying an earlier successful read from the operation journal.
                request_key = f"trigger:{id}:{config['version_id']}:{generation}:{secrets.token_hex(8)}"
                if mid == "telegram":
                    from app.apps.power_apps.telegram import bot_request

                    updates = bot_request(
                        db,
                        actor,
                        conn,
                        "getUpdates",
                        {
                            "offset": config.get("offset", 0),
                            "limit": 100,
                            "timeout": 0,
                            "allowed_updates": [
                                "message",
                                "channel_post",
                                "edited_message",
                                "edited_channel_post",
                                "callback_query",
                                "my_chat_member",
                                "chat_member",
                            ],
                        },
                    )
                    events, offset = telegram_events(
                        updates, setup, config.get("offset", 0), config["started_at"]
                    )
                    snapshot = config.get("snapshot")
                else:
                    previous = (
                        json.loads(cipher().decrypt(config["snapshot"].encode()))
                        if config.get("snapshot")
                        else None
                    )
                    if mid == "google_sheets":
                        result = service.invoke(
                            db,
                            actor,
                            conn,
                            "get_values",
                            {k: setup[k] for k in ["spreadsheet_id", "range"]},
                            key=request_key,
                        )["data"]
                        values = result.get("values", [])
                        if not values:
                            raise ValueError(
                                "Spreadsheet range must include a header row"
                            )
                        current = rows_snapshot(
                            values[0], values[1:], setup["key_column"]
                        )
                    elif mid == "excel_online":
                        identifiers = {
                            k: setup[k] for k in ["drive_id", "workbook_id", "table_id"]
                        }
                        result = service.invoke(
                            db,
                            actor,
                            conn,
                            "list_rows",
                            identifiers,
                            key=request_key + ":rows",
                        )["data"]
                        columns = service.invoke(
                            db,
                            actor,
                            conn,
                            "list_columns",
                            identifiers,
                            key=request_key + ":columns",
                        )["data"]
                        if result.get("@odata.nextLink") or columns.get(
                            "@odata.nextLink"
                        ):
                            raise ValueError(
                                "Watch a complete table of at most 1000 rows"
                            )
                        headers = [
                            c["name"]
                            for c in sorted(
                                columns.get("value", []), key=lambda c: c["index"]
                            )
                        ]
                        current = rows_snapshot(
                            headers,
                            [r["values"][0] for r in result.get("value", [])],
                            setup["key_column"],
                        )
                    else:
                        raise ValueError("Connector requires a signed event relay")
                    events = row_events(previous, current, setup)
                    snapshot = (
                        cipher()
                        .encrypt(json.dumps(current, allow_nan=False).encode())
                        .decode()
                    )
                    offset = 0
                # Recheck revocation/publication after network IO and journal commits.
                db.query(PowerResource).filter_by(id=row.id).with_for_update().one()
                trigger = (
                    db.query(Trigger)
                    .filter_by(id=id)
                    .with_for_update()
                    .populate_existing()
                    .one()
                )
                state = (
                    db.query(Deployment)
                    .filter_by(resource_id=row.id)
                    .populate_existing()
                    .one()
                )
                if (
                    not trigger.enabled
                    or trigger.config != config
                    or state.status != "active"
                    or state.version_id != config["version_id"]
                ):
                    db.rollback()
                    continue
                for event in events:
                    event["module_id"] = mid
                    event["timestamp"] = now().isoformat()
                    identity = (
                        event.get("event_id")
                        or hashlib.sha256(
                            json.dumps(
                                {k: v for k, v in event.items() if k != "timestamp"},
                                sort_keys=True,
                            ).encode()
                        ).hexdigest()
                    )
                    enqueue(
                        db,
                        row,
                        actor,
                        event,
                        f"connector:{id}:{config['version_id']}:{generation}:{identity}",
                        kind="connector",
                        trigger=trigger,
                    )
                trigger.config = {
                    **config,
                    "snapshot": snapshot,
                    "offset": offset,
                    "generation": generation + 1,
                    "error": None,
                }
                trigger.last_at = now()
                trigger.next_at = now() + timedelta(
                    seconds=setup.get("interval_seconds", 30)
                )
                db.commit()
        except Exception:
            db.rollback()
            trigger = db.query(Trigger).filter_by(id=id).with_for_update().first()
            if trigger:
                trigger.config = {
                    **trigger.config,
                    "error": "Polling failed. Check connection permissions, headers, unique keys and snapshot limits.",
                }
                trigger.next_at = now() + timedelta(seconds=60)
                db.commit()
