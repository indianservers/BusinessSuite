"""HubSpot v4 subscriptions and native journal consumption (provider beta API)."""

import json
import re
import time
from urllib.parse import urlsplit
from app.apps.power_apps.integrations.native_http import segment as q
from app.apps.power_apps.integrations.contracts import IntegrationFailure

OBJECTS = {
    "contacts": "0-1",
    "companies": "0-2",
    "deals": "0-3",
    "tickets": "0-5",
    "tasks": "0-27",
}
SCOPES = "developer.webhooks_journal.read developer.webhooks_journal.subscriptions.read developer.webhooks_journal.subscriptions.write"


def token(private):
    auth = private["secrets"]
    if auth.get("journal_token_until", 0) > time.time() + 60:
        return auth["journal_access_token"]
    from app.apps.power_apps.integrations.oauth import token_request

    value = token_request(
        "https://api.hubapi.com/oauth/2026-03/token",
        {
            "grant_type": "client_credentials",
            "client_id": auth["client_id"],
            "client_secret": auth["client_secret"],
            "scope": SCOPES,
        },
    )
    auth["journal_access_token"] = value["access_token"]
    auth["journal_token_until"] = time.time() + min(
        int(value.get("expires_in", 1800)), 3600
    )
    return auth["journal_access_token"]


def ensure(client, setup, private, save):
    state = private["state"]
    access = token(private)
    if state.get("id"):
        return
    object_type = OBJECTS.get(setup["object_type"], setup["object_type"])
    if not re.fullmatch(r"[02]-[0-9]+", object_type):
        raise IntegrationFailure(
            "schema", "Provide a supported HubSpot object type or object type ID"
        )
    if not state.get("portal_id"):
        account = client.request("GET", "/account-info/v3/details")
        state["portal_id"] = int(account["portalId"])
        save()
    if "journal_offset" not in state:
        latest = client.request(
            "GET",
            "/webhooks-journal/journal/v4/latest",
            bearer=access,
            allow=(404, 204),
        )
        state["journal_offset"] = latest.get("currentOffset")
        save()
    rows = client.request(
        "GET", "/webhooks-journal/subscriptions/v4", bearer=access
    ).get("results", [])
    fields = sorted(
        set(setup.get("watched_fields", []))
        | (
            {"dealstage", "pipeline"}
            if setup["object_type"] == "deals"
            else (
                {"hs_pipeline_stage", "hs_pipeline"}
                if setup["object_type"] == "tickets"
                else set()
            )
        )
    )
    found = next(
        (
            r
            for r in rows
            if r.get("portalId") == state["portal_id"]
            and r.get("objectTypeId") == object_type
            and r.get("subscriptionType") == "OBJECT"
            and set(r.get("properties", [])) == set(fields)
            and set(r.get("actions", [])) == {"CREATE", "UPDATE"}
        ),
        None,
    )
    if not found:
        found = client.request(
            "POST",
            "/webhooks-journal/subscriptions/v4",
            {
                "subscriptionType": "OBJECT",
                "objectTypeId": object_type,
                "portalId": state["portal_id"],
                "actions": ["CREATE", "UPDATE"],
                **({"properties": fields} if fields else {}),
            },
            bearer=access,
        )
        state["owned"] = True
    else:
        state["owned"] = False
    state.update(id=str(found["id"]), object_type_id=object_type)
    save()


def remove(client, private, shared_in_use):
    state = private.get("state", {})
    if state.get("id") and state.get("owned") and not shared_in_use:
        client.request(
            "DELETE",
            "/webhooks-journal/subscriptions/v4/" + q(state["id"]),
            bearer=token(private),
            allow=(404,),
        )


def poll(client, setup, private):
    from app.apps.power_apps.integrations import adapters
    from app.apps.power_apps.integrations.transport import EgressPolicy
    from app.apps.power_apps.integrations.native_sources import event, compact, digest

    state = private["state"]
    offset = state.get("journal_offset")
    access = token(private)
    path = (
        "/webhooks-journal/journal/v4/offset/" + q(offset) + "/next"
        if offset
        else "/webhooks-journal/journal/v4/latest"
    )
    value = client.request("GET", path, bearer=access, allow=(204, 404))
    if value.get("_status") in {204, 404}:
        return []
    target = urlsplit(value.get("url", ""))
    if (
        target.scheme != "https"
        or target.username
        or target.password
        or not target.hostname
        or not re.fullmatch(
            r"(?:[a-zA-Z0-9.-]+\.)?s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com",
            target.hostname,
        )
    ):
        raise IntegrationFailure(
            "egress", "HubSpot returned an unapproved journal content host"
        )
    policy = EgressPolicy(
        [target.hostname],
        safe_query_keys={
            "X-Amz-Credential",
            "X-Amz-Signature",
            "X-Amz-Security-Token",
            "AWSAccessKeyId",
            "Signature",
        },
    )
    response = adapters.HTTP_FACTORY(policy).request(
        "GET", value["url"], headers={"Accept": "application/json"}, timeout=10
    )
    adapters.status_error(response)
    try:
        document = json.loads(response.body)
    except (ValueError, UnicodeDecodeError):
        raise IntegrationFailure(
            "response", "Invalid HubSpot journal content"
        ) from None
    result = []
    for index, row in enumerate(document.get("journalEvents", [])):
        if (
            row.get("portalId") != state["portal_id"]
            or row.get("objectTypeId") != state["object_type_id"]
            or row.get("type") != "crmObject"
            or row.get("action") not in {"CREATE", "UPDATE"}
        ):
            continue
        if row.get("occurredAt", "") < private["started_at"]:
            continue
        changes = row.get("propertyChanges", {})
        name = "record_created" if row.get("action") == "CREATE" else "record_updated"
        if setup["event"] == "deal_stage_changed":
            if "dealstage" not in changes:
                continue
            name = "deal_stage_changed"
        elif setup["event"] == "ticket_changed":
            if state["object_type_id"] != "0-5" or row.get("action") != "UPDATE":
                continue
            name = "ticket_changed"
        data = {
            "id": str(row["objectId"]),
            "object_type": setup["object_type"],
            "portal_id": state["portal_id"],
            "pipeline_id": changes.get("pipeline", changes.get("hs_pipeline")),
            "stage_id": changes.get("dealstage", changes.get("hs_pipeline_stage")),
            "changed_fields": list(changes),
            "changes": compact(changes),
            "occurred_at": row.get("occurredAt"),
        }
        result.append(
            event(
                name,
                data,
                [document.get("offset", value["currentOffset"]), index, digest(row)],
            )
        )
    state["journal_offset"] = value["currentOffset"]
    return result
