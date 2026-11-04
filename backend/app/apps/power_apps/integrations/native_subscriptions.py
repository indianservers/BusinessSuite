"""Provider subscription create/reconcile/renew/delete operations."""

import base64
import copy
import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from app.apps.power_apps.integrations.native_http import segment as q
from app.apps.power_apps.integrations.native_specs import GRAPH, SHARED_APPS, mode
from app.apps.power_apps.integrations.contracts import IntegrationFailure

GITHUB_EVENTS = {
    "push": "push",
    "issue_opened": "issues",
    "issue_updated": "issues",
    "pull_request_opened": "pull_request",
    "pull_request_updated": "pull_request",
    "comment_added": "issue_comment",
    "release_created": "release",
    "workflow_completed": "workflow_run",
}
CLICKUP_EVENTS = {
    "task_created": "taskCreated",
    "task_updated": "taskUpdated",
    "task_deleted": "taskDeleted",
    "status_changed": "taskStatusUpdated",
    "assignee_changed": "taskAssigneeUpdated",
    "comment_added": "taskCommentPosted",
}
BOX_EVENTS = {
    "file_uploaded": "FILE.UPLOADED",
    "file_updated": "FILE.UPLOADED",
    "folder_created": "FOLDER.CREATED",
    "item_moved": "FILE.MOVED",
    "item_deleted": "FILE.TRASHED",
    "collaboration_changed": "COLLABORATION.UPDATED",
}
SLACK_EVENTS = {
    "message_received": [
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim",
    ],
    "mention_received": ["app_mention"],
    "reaction_added": ["reaction_added"],
    "channel_event": ["channel_created", "channel_rename", "channel_archive"],
    "file_shared": ["file_shared"],
}


def iso_after(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def expiry(value, default_seconds=3600):
    if isinstance(value, (int, float)) or isinstance(value, str) and value.isdigit():
        return datetime.fromtimestamp(float(value) / 1000, timezone.utc).isoformat()
    return value or iso_after(default_seconds)


def graph_resource(mid, setup):
    mailbox = "users/" + q(setup["mailbox"]) if setup.get("mailbox") else "me"
    if mid == "outlook":
        return (
            mailbox
            + (
                "/mailFolders/" + q(setup["folder_id"])
                if setup.get("folder_id")
                else ""
            )
            + "/messages"
        )
    if mid == "microsoft_calendar":
        return mailbox + "/events"
    if mid == "microsoft_teams":
        return (
            "chats/" + q(setup["chat_id"]) + "/messages"
            if setup.get("chat_id")
            else "teams/"
            + q(setup["team_id"])
            + "/channels/"
            + q(setup["channel_id"])
            + "/messages"
        )
    if mid == "sharepoint" and setup.get("list_id"):
        return "sites/" + q(setup["site_id"]) + "/lists/" + q(setup["list_id"])
    return "drives/" + q(setup["drive_id"]) + "/root"


def _records(value, key):
    return value if isinstance(value, list) else value.get(key, [])


def ensure(client, mid, setup, private, callback, save):
    """Reconcile by callback identity before creating; checkpoint each owned resource."""
    state = private.setdefault("state", {})
    auth = private["secrets"]
    for retired in list(private.get("retired_channels",[])):
        if retired.get("resource_id"):
            client.request("POST",("/drive/v3" if mid=="google_drive" else "/calendar/v3")+"/channels/stop",{"id":retired["id"],"resourceId":retired["resource_id"]},allow=(404,))
        private["retired_channels"].remove(retired); save()
    delivery = mode(mid, setup)
    if mid=="hubspot" and delivery=="native_journal":
        from app.apps.power_apps.integrations.native_hubspot import ensure as ensure_journal
        return ensure_journal(client,setup,private,save)
    if delivery in {"native_polling", "native_stream"} or mid == "http":
        state.setdefault("registered_at", iso_after(0))
        save()
        return
    if mid in {"gmail", "google_forms"}:
        return ensure_pubsub(client, mid, setup, private, save)
    if state.get("id"):
        return renew(client, mid, setup, private, callback, save)
    state["registration_started"] = True
    state["callback"] = callback
    save()
    if mid in GRAPH:
        resource = graph_resource(mid, setup)
        subscriptions, _ = client.collection("/v1.0/subscriptions")
        found = next(
            (
                s
                for s in subscriptions
                if s.get("notificationUrl") == callback
                and s.get("clientState") == auth["verification"]
            ),
            None,
        )
        if not found:
            found = client.request(
                "POST",
                "/v1.0/subscriptions",
                {
                    "changeType": (
                        "updated"
                        if mid in {"onedrive", "sharepoint"}
                        else "created,updated,deleted"
                    ),
                    "notificationUrl": callback,
                    "lifecycleNotificationUrl": callback,
                    "resource": resource,
                    "expirationDateTime": iso_after(2700),
                    "clientState": auth["verification"],
                },
            )
        state.update(
            id=str(found["id"]),
            resource=resource,
            expires_at=found["expirationDateTime"],
        )
    elif mid == "github":
        path = f"/repos/{q(setup['owner'])}/{q(setup['repository'])}/hooks"
        hooks = client.request("GET", path, query={"per_page": 100})
        found = next(
            (s for s in hooks if s.get("config", {}).get("url") == callback), None
        )
        if not found:
            found = client.request(
                "POST",
                path,
                {
                    "name": "web",
                    "active": True,
                    "events": [GITHUB_EVENTS[setup["event"]]],
                    "config": {
                        "url": callback,
                        "content_type": "json",
                        "insecure_ssl": "0",
                        "secret": auth["verification"],
                    },
                },
            )
        state.update(id=str(found["id"]), path=path)
    elif mid == "clickup":
        path = f"/api/v2/team/{q(setup['team_id'])}/webhook"
        hooks = client.request("GET", path).get("webhooks", [])
        found = next((h for h in hooks if h.get("endpoint") == callback), None)
        if found and not (auth.get("webhook_secret") or found.get("secret")):
            client.request("DELETE", "/api/v2/webhook/" + q(found["id"]), allow=(404,))
            found = None
        if not found:
            found = client.request(
                "POST",
                path,
                {
                    "endpoint": callback,
                    "events": [CLICKUP_EVENTS[setup["event"]]],
                    **{k: setup[k] for k in ("space_id", "list_id") if setup.get(k)},
                },
            )
        hook = found.get("webhook", found)
        auth["webhook_secret"] = (
            hook.get("secret") or found.get("secret") or auth.get("webhook_secret")
        )
        if not auth["webhook_secret"]:
            raise IntegrationFailure(
                "setup", "ClickUp did not return its webhook secret"
            )
        state["id"] = str(hook.get("id", found.get("id")))
    elif mid == "box":
        hooks = client.request("GET", "/2.0/webhooks", query={"limit": 1000})
        if hooks.get("next_marker"):
            raise IntegrationFailure(
                "pagination", "Too many Box webhooks to reconcile safely"
            )
        found = next(
            (h for h in hooks.get("entries", []) if h.get("address") == callback), None
        )
        if not found:
            found = client.request(
                "POST",
                "/2.0/webhooks",
                {
                    "target": {"type": "folder", "id": setup["folder_id"]},
                    "address": callback,
                    "triggers": [BOX_EVENTS[setup["event"]]],
                },
            )
        state["id"] = str(found["id"])
    elif mid == "airtable":
        path = f"/v0/bases/{q(setup['base_id'])}/webhooks"
        hooks = client.request("GET", path).get("webhooks", [])
        found = next((h for h in hooks if h.get("notificationUrl") == callback), None)
        if found and not auth.get("mac_secret"):
            client.request("DELETE", path + "/" + q(found["id"]), allow=(404,))
            found = None
        if not found:
            found = client.request(
                "POST",
                path,
                {
                    "notificationUrl": callback,
                    "specification": {
                        "options": {
                            "filters": {
                                "dataTypes": ["tableData"],
                                "recordChangeScope": setup["table_id"],
                            },
                            "includes": {
                                "includePreviousCellValues": True,
                                "includePreviousFieldDefinitions": True,
                            },
                        }
                    },
                },
            )
            auth["mac_secret"] = found["macSecretBase64"]
        state.update(
            id=str(found["id"]),
            path=path,
            expires_at=found.get("expirationTime", iso_after(6 * 86400)),
            cursor=state.get("cursor", 1),
        )
    elif mid == "zoho_crm":
        channel = str(int(hashlib.sha256(callback.encode()).hexdigest()[:12], 16))
        watch = {
            "channel_id": channel,
            "events": [setup["module"] + ".all"],
            "notify_url": callback,
            "token": auth["verification"],
            "channel_expiry": iso_after(6 * 86400),
            "return_affected_field_values": True,
        }
        value = client.request("POST", "/crm/v8/actions/watch", {"watch": [watch]})
        if any(item.get("status") == "error" for item in value.get("watch", [])):
            raise IntegrationFailure("setup", "Zoho rejected the notification watch")
        state.update(id=channel, expires_at=watch["channel_expiry"])
    elif mid == "jira":
        path = "/rest/webhooks/1.0/webhook"
        hooks = client.request("GET", path)
        found = next(
            (h for h in _records(hooks, "values") if h.get("url") == callback), None
        )
        if not found:
            found = client.request(
                "POST",
                path,
                {
                    "name": "Power Apps " + private["epoch"],
                    "url": callback,
                    "events": [
                        "jira:issue_created",
                        "jira:issue_updated",
                        "jira:issue_deleted",
                        "comment_created",
                    ],
                    "excludeBody": False,
                },
            )
        state.update(
            id=str(found.get("id") or found["self"].rstrip("/").split("/")[-1])
        )
    elif mid in {"google_drive", "google_calendar"}:
        channel = private["epoch"]
        if mid == "google_drive":
            if "cursor" not in state:
                state["cursor"] = client.request(
                    "GET",
                    "/drive/v3/changes/startPageToken",
                    query={
                        **(
                            {"driveId": setup["drive_id"]}
                            if setup.get("drive_id")
                            else {}
                        ),
                        "supportsAllDrives": "true",
                    },
                )["startPageToken"]
                save()
            path = "/drive/v3/changes/watch"
            query = {"pageToken": state["cursor"], "supportsAllDrives": "true"}
            if setup.get("drive_id"):
                query["driveId"] = setup["drive_id"]
        else:
            path = "/calendar/v3/calendars/" + q(setup["calendar_id"]) + "/events/watch"
            query = None
        state["requested_expires_at"]=iso_after(6*86400)
        save()
        found = client.request(
            "POST", path, {
                "id": channel,
                "type": "web_hook",
                "address": callback,
                "token": auth["verification"],
                "expiration": int((time.time() + 6 * 86400) * 1000),
            },
            query=query,
            allow=(409,),
        )
        if found.get("_status") == 409:
            raise IntegrationFailure(
                "reconcile",
                "Google watch already exists; wait for its authenticated sync notification",
            )
        state.update(
            id=found["id"],
            resource_id=found["resourceId"],
            expires_at=expiry(found.get("expiration"), 86400),
        )
    elif mid == "slack":
        token = auth["configuration_token"]
        account = client.request("POST", "/api/auth.test", {})
        state["account_id"] = account["team_id"]
        exported = client.request(
            "POST",
            "/api/apps.manifest.export",
            {"app_id": setup["app_id"]},
            bearer=token,
        )["manifest"]
        manifest = json.loads(exported) if isinstance(exported, str) else exported
        settings = manifest.setdefault("settings", {})
        old = settings.get("event_subscriptions", {})
        if old.get("request_url") and old["request_url"] != callback:
            raise IntegrationFailure(
                "conflict",
                "This Slack app already has a different event callback; use a dedicated app",
            )
        state["previous_events"] = copy.deepcopy(private.get("shared_previous", old))
        save()
        settings["event_subscriptions"] = {
            **old,
            "request_url": callback,
            "bot_events": sorted(
                set(old.get("bot_events", [])) | set(SLACK_EVENTS[setup["event"]])
            ),
        }
        client.request(
            "POST",
            "/api/apps.manifest.update",
            {"app_id": setup["app_id"], "manifest": json.dumps(manifest)},
            bearer=token,
        )
        state["id"] = setup["app_id"]
    elif mid == "whatsapp_business":
        prefix = "/" + q(setup["api_version"])
        app = setup["app_id"]
        waba = setup["business_account_id"]
        app_token = app + "|" + auth["app_secret"]
        apps = client.request(
            "GET", prefix + "/" + q(app) + "/subscriptions", bearer=app_token
        ).get("data", [])
        if not any(a.get("object") == "whatsapp_business_account" for a in apps):
            client.request(
                "POST",
                prefix + "/" + q(app) + "/subscriptions",
                {
                    "object": "whatsapp_business_account",
                    "callback_url": callback,
                    "verify_token": auth["verification"],
                    "fields": "messages",
                },
                bearer=app_token,
            )
        client.request("POST", prefix + "/" + q(waba) + "/subscribed_apps", {})
        client.request(
            "POST",
            prefix + "/" + q(waba) + "/subscribed_apps",
            {"override_callback_uri": callback, "verify_token": auth["verification"]},
        )
        state.update(id=waba, account_id=waba)
    else:
        raise IntegrationFailure(
            "setup", "Native subscription provider is not installed"
        )
    state["registered_at"] = iso_after(0)
    save()


def renew(client, mid, setup, private, callback, save):
    state = private["state"]
    if not state.get("expires_at"):
        return
    if datetime.fromisoformat(
        state["expires_at"].replace("Z", "+00:00")
    ) > datetime.now(timezone.utc) + timedelta(minutes=15):
        return
    if mid in GRAPH:
        value = client.request(
            "PATCH",
            "/v1.0/subscriptions/" + q(state["id"]),
            {"expirationDateTime": iso_after(2700)},
            allow=(404,),
        )
        if value.get("_status") == 404:
            state.pop("id", None)
            save()
            return ensure(client, mid, setup, private, callback, save)
        state["expires_at"] = value["expirationDateTime"]
    elif mid == "airtable":
        value = client.request(
            "POST", state["path"] + "/" + q(state["id"]) + "/refresh", {}
        )
        state["expires_at"] = value.get("expirationTime", iso_after(6 * 86400))
    elif mid == "zoho_crm":
        value = client.request(
            "PUT",
            "/crm/v8/actions/watch",
            {
                "watch": [
                    {
                        "channel_id": state["id"],
                        "events": [setup["module"] + ".all"],
                        "channel_expiry": iso_after(6 * 86400),
                    }
                ]
            },
        )
        if any(v.get("status") == "error" for v in value.get("watch", [])):
            raise IntegrationFailure("remote", "Zoho rejected watch renewal")
        state["expires_at"] = iso_after(6 * 86400)
    elif mid in {"google_drive", "google_calendar"}:
        # Overlap new and old channels. Retired channels are removed after the new
        # channel is durably recorded, so a failed renewal doesn't stop the old one.
        old = {k: state[k] for k in ("id", "resource_id") if k in state}
        private.setdefault("retired_channels",[]).append(old)
        import uuid

        private["epoch"] = str(uuid.uuid4())
        state.pop("id", None)
        ensure(client, mid, setup, private, callback, save)
        if old.get("resource_id"):
            client.request(
                "POST",
                ("/drive/v3" if mid == "google_drive" else "/calendar/v3")
                + "/channels/stop",
                {"id": old["id"], "resourceId": old["resource_id"]},
                allow=(404,),
            )
        private["retired_channels"].remove(old)
    save()


def remove(client, mid, setup, private, *, shared_in_use=False):
    if mid=="hubspot" and mode(mid,setup)=="native_journal":
        from app.apps.power_apps.integrations.native_hubspot import remove as remove_journal
        return remove_journal(client,private,shared_in_use)
    state = private.get("state", {})
    id = state.get("id")
    if mid in {"gmail", "google_forms"}:
        return remove_pubsub(client, mid, setup, private, shared_in_use)
    if not id and state.get("registration_started"):
        callback=state.get("callback")
        found=None
        if mid in GRAPH:
            rows,_=client.collection("/v1.0/subscriptions")
            found=next((r for r in rows if r.get("notificationUrl")==callback and r.get("clientState")==private["secrets"]["verification"]),None)
        elif mid=="github":
            state["path"]=f"/repos/{q(setup['owner'])}/{q(setup['repository'])}/hooks"
            rows=client.request("GET",state["path"],query={"per_page":100})
            found=next((r for r in rows if r.get("config",{}).get("url")==callback),None)
        elif mid=="clickup":
            rows=client.request("GET",f"/api/v2/team/{q(setup['team_id'])}/webhook").get("webhooks",[])
            found=next((r for r in rows if r.get("endpoint")==callback),None)
        elif mid=="box":
            rows=client.request("GET","/2.0/webhooks",query={"limit":1000}).get("entries",[])
            found=next((r for r in rows if r.get("address")==callback),None)
        elif mid=="airtable":
            state["path"]=f"/v0/bases/{q(setup['base_id'])}/webhooks"
            rows=client.request("GET",state["path"]).get("webhooks",[])
            found=next((r for r in rows if r.get("notificationUrl")==callback),None)
        elif mid=="jira":
            rows=client.request("GET","/rest/webhooks/1.0/webhook")
            found=next((r for r in _records(rows,"values") if r.get("url")==callback),None)
            if found and not found.get("id"): found={**found,"id":found["self"].rstrip("/").split("/")[-1]}
        elif mid in {"google_drive","google_calendar"}:
            if state.get("requested_expires_at",iso_after(1))<=iso_after(0): return
            raise IntegrationFailure("reconcile","Awaiting authenticated channel sync data before Google watch cleanup")
        elif mid in {"slack","whatsapp_business","zoho_crm"}:
            found={"id":setup.get("app_id") if mid=="slack" else setup.get("business_account_id") if mid=="whatsapp_business" else str(int(hashlib.sha256(callback.encode()).hexdigest()[:12],16))}
        id=str(found["id"]) if found else None
    if mid=="salesforce" and state.get("client_id") and not id: id="stream"
    if not id: return
    if mid in GRAPH:
        client.request("DELETE", "/v1.0/subscriptions/" + q(id), allow=(404, 410))
    elif mid == "github":
        client.request("DELETE", state["path"] + "/" + q(id), allow=(404,))
    elif mid == "clickup":
        client.request("DELETE", "/api/v2/webhook/" + q(id), allow=(404,))
    elif mid == "box":
        client.request("DELETE", "/2.0/webhooks/" + q(id), allow=(404,))
    elif mid == "airtable":
        client.request("DELETE", state["path"] + "/" + q(id), allow=(404,))
    elif mid == "zoho_crm":
        client.request(
            "DELETE", "/crm/v8/actions/watch", query={"channel_ids": id}, allow=(404,)
        )
    elif mid == "jira":
        client.request("DELETE", "/rest/webhooks/1.0/webhook/" + q(id), allow=(404,))
    elif mid in {"google_drive", "google_calendar"} and state.get("resource_id"):
        client.request(
            "POST",
            ("/drive/v3" if mid == "google_drive" else "/calendar/v3")
            + "/channels/stop",
            {"id": id, "resourceId": state["resource_id"]},
            allow=(404,),
        )
    elif mid == "slack" and not shared_in_use:
        token = private["secrets"]["configuration_token"]
        exported = client.request(
            "POST", "/api/apps.manifest.export", {"app_id": id}, bearer=token
        )["manifest"]
        manifest = json.loads(exported) if isinstance(exported, str) else exported
        manifest.setdefault("settings", {})["event_subscriptions"] = state.get(
            "previous_events", {}
        )
        client.request(
            "POST",
            "/api/apps.manifest.update",
            {"app_id": id, "manifest": json.dumps(manifest)},
            bearer=token,
        )
    elif mid == "whatsapp_business" and not shared_in_use:
        client.request(
            "DELETE",
            "/" + q(setup["api_version"]) + "/" + q(id) + "/subscribed_apps",
            allow=(404,),
        )
    elif mid == "salesforce" and state.get("client_id"):
        client.request(
            "POST",
            "/cometd/" + q(setup["api_version"].removeprefix("v")),
            [{"channel": "/meta/disconnect", "clientId": state["client_id"]}],
            allow=(400, 404),
        )


def cloud_token(client, private):
    auth = private["secrets"]
    if auth.get("cloud_token_until", 0) > time.time() + 60:
        return auth["cloud_access_token"]
    import jwt

    try:
        account = json.loads(auth["cloud_service_account"])
        if (
            account.get("type") != "service_account"
            or account.get("token_uri") != "https://oauth2.googleapis.com/token"
        ):
            raise ValueError()
        assertion = jwt.encode(
            {
                "iss": account["client_email"],
                "scope": "https://www.googleapis.com/auth/pubsub",
                "aud": "https://oauth2.googleapis.com/token",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            account["private_key"],
            algorithm="RS256",
        )
    except Exception:
        raise IntegrationFailure(
            "credential", "Provide a valid Google Cloud service account document"
        ) from None
    from app.apps.power_apps.integrations.oauth import token_request

    value = token_request(
        "https://oauth2.googleapis.com/token",
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
    )
    auth["cloud_access_token"] = value["access_token"]
    auth["cloud_token_until"] = time.time() + min(
        int(value.get("expires_in", 3600)), 3600
    )
    return auth["cloud_access_token"]


def ensure_pubsub(client, mid, setup, private, save):
    state = private.setdefault("state", {})
    token = cloud_token(client, private)
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", setup["cloud_project_id"]):
        raise IntegrationFailure("schema", "Invalid Google Cloud project ID")
    scope_key = f"{client.conn.id}:{setup.get('form_id','mailbox')}"
    suffix = hashlib.sha256(scope_key.encode()).hexdigest()[:20]
    topic = f"projects/{setup['cloud_project_id']}/topics/power-{mid}-{suffix}"
    subscription = (
        f"projects/{setup['cloud_project_id']}/subscriptions/power-{private['epoch']}"
    )
    if not state.get("topic"):
        client.request(
            "PUT",
            "/v1/" + topic,
            {},
            host="pubsub.googleapis.com",
            bearer=token,
            allow=(409,),
        )
        state["topic"] = topic
        save()
        policy = client.request(
            "POST",
            "/v1/" + topic + ":getIamPolicy",
            {},
            host="pubsub.googleapis.com",
            bearer=token,
        )
        publisher = "serviceAccount:" + (
            "gmail-api-push@system.gserviceaccount.com"
            if mid == "gmail"
            else "forms-notifications@system.gserviceaccount.com"
        )
        bindings = policy.setdefault("bindings", [])
        binding = next(
            (
                b
                for b in bindings
                if b.get("role") == "roles/pubsub.publisher" and not b.get("condition")
            ),
            None,
        )
        if binding is None:
            binding = {"role": "roles/pubsub.publisher", "members": []}
            bindings.append(binding)
        if publisher not in binding["members"]:
            binding["members"].append(publisher)
        client.request(
            "POST",
            "/v1/" + topic + ":setIamPolicy",
            {"policy": policy},
            host="pubsub.googleapis.com",
            bearer=token,
        )
        state["iam_ready"] = True
        save()
    if not state.get("iam_ready"):
        # Re-enter IAM setup after an interrupted provisioning transaction.
        state.pop("topic", None)
        return ensure_pubsub(client, mid, setup, private, save)
    if not state.get("subscription"):
        client.request(
            "PUT",
            "/v1/" + subscription,
            {
                "topic": topic,
                "ackDeadlineSeconds": 60,
                "messageRetentionDuration": "604800s",
            },
            host="pubsub.googleapis.com",
            bearer=token,
            allow=(409,),
        )
        state["subscription"] = subscription
        save()
    due = not state.get("expires_at") or datetime.fromisoformat(
        state["expires_at"].replace("Z", "+00:00")
    ) <= datetime.now(timezone.utc) + timedelta(hours=12)
    if not due:
        return
    if mid == "gmail":
        value = client.request(
            "POST",
            "/gmail/v1/users/me/watch",
            {"topicName": topic},
        )
        state.setdefault("history_id", value["historyId"])
        state["expires_at"] = expiry(value["expiration"])
        state["id"] = "gmail-watch"
    else:
        path = "/v1/forms/" + q(setup["form_id"]) + "/watches"
        event = "SCHEMA" if setup["event"] == "form_changed" else "RESPONSES"
        existing = client.request("GET", path).get("watches", [])
        found = next(
            (
                w
                for w in existing
                if w.get("target", {}).get("topic", {}).get("topicName") == topic
                and w.get("eventType") == event
            ),
            None,
        )
        value = (
            client.request("POST", path + "/" + q(found["id"]) + ":renew", {})
            if found
            else client.request(
                "POST",
                path,
                {
                    "watch": {
                        "target": {"topic": {"topicName": topic}},
                        "eventType": event,
                    }
                },
            )
        )
        state.update(id=value["id"], expires_at=value["expireTime"])
    save()


def remove_pubsub(client, mid, setup, private, shared_in_use):
    state = private.get("state", {})
    token = cloud_token(client, private)
    if state.get("subscription"):
        client.request(
            "DELETE",
            "/v1/" + state["subscription"],
            host="pubsub.googleapis.com",
            bearer=token,
            allow=(404,),
        )
    if not shared_in_use:
        if mid == "gmail" and state.get("id"):
            client.request("POST", "/gmail/v1/users/me/stop", {})
        elif state.get("id"):
            client.request(
                "DELETE",
                "/v1/forms/" + q(setup["form_id"]) + "/watches/" + q(state["id"]),
                allow=(404,),
            )
        if state.get("topic"):
            client.request(
                "DELETE",
                "/v1/" + state["topic"],
                host="pubsub.googleapis.com",
                bearer=token,
                allow=(404,),
            )
