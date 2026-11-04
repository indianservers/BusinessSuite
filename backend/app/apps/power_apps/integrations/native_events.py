"""Provider authentication, challenges, and native payload normalization."""

import base64
import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from app.apps.power_apps.integrations.native_specs import GRAPH
from app.apps.power_apps.integrations.native_sources import event, compact, digest
from app.apps.power_apps.integrations.native_http import segment as q


def equal(left, right):
    return (
        isinstance(left, str)
        and isinstance(right, str)
        and hmac.compare_digest(left, right)
    )


def verify(mid, private, headers, body, data):
    auth = private["secrets"]
    state = private.get("state", {})
    signature = headers.get("x-hub-signature-256", "")
    if mid in {"github", "whatsapp_business"}:
        key = auth["verification"] if mid == "github" else auth["app_secret"]
        valid = equal(
            signature,
            "sha256=" + hmac.new(key.encode(), body, hashlib.sha256).hexdigest(),
        )
    elif mid == "slack":
        stamp = headers.get("x-slack-request-timestamp", "")
        try:
            fresh = abs(time.time() - int(stamp)) <= 300
        except (ValueError, TypeError):
            fresh = False
        valid = fresh and equal(
            headers.get("x-slack-signature", ""),
            "v0="
            + hmac.new(
                auth["signing_secret"].encode(),
                b"v0:" + stamp.encode() + b":" + body,
                hashlib.sha256,
            ).hexdigest(),
        )
    elif mid == "clickup":
        valid = (
            equal(
                headers.get("x-signature", ""),
                hmac.new(
                    auth.get("webhook_secret", "").encode(), body, hashlib.sha256
                ).hexdigest(),
            )
            and bool(auth.get("webhook_secret"))
            and str(data.get("webhook_id")) == str(state.get("id"))
        )
    elif mid == "box":
        stamp = headers.get("box-delivery-timestamp", "")
        try:
            fresh = (
                abs(
                    time.time()
                    - datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
                )
                <= 600
            )
        except (ValueError, TypeError):
            fresh = False
        expected = base64.b64encode(
            hmac.new(
                auth["primary_signature_key"].encode(),
                body + stamp.encode(),
                hashlib.sha256,
            ).digest()
        ).decode()
        valid = (
            fresh
            and equal(headers.get("box-signature-primary", ""), expected)
            and str(data.get("webhook", {}).get("id")) == str(state.get("id"))
        )
    elif mid == "airtable":
        try:
            secret = base64.b64decode(auth.get("mac_secret", ""), validate=True)
        except (ValueError, TypeError):
            secret = b""
        valid = (
            bool(secret)
            and equal(
                headers.get("x-airtable-content-mac", ""),
                "hmac-sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest(),
            )
            and str(data.get("webhook", {}).get("id")) == str(state.get("id"))
        )
    elif mid in {"google_drive", "google_calendar"}:
        valid = equal(
            headers.get("x-goog-channel-token", ""), auth["verification"]
        ) and equal(
            headers.get("x-goog-channel-id", ""), state.get("id", private["epoch"])
        )
        if state.get("resource_id"):
            valid = valid and equal(
                headers.get("x-goog-resource-id", ""), state["resource_id"]
            )
    elif mid == "zoho_crm":
        valid = equal(data.get("token"), auth["verification"]) and str(
            data.get("channel_id")
        ) == str(state.get("id"))
    elif mid in GRAPH:
        notifications = data.get("value", [])
        valid = bool(notifications) and all(
            equal(n.get("clientState"), auth["verification"])
            and (not state.get("id") or n.get("subscriptionId") == state["id"])
            for n in notifications
        )
    elif mid == "jira":
        # Jira admin webhooks are unsigned. Their unguessable endpoint only wakes
        # an authorized REST read; their body never becomes workflow input.
        valid = True
    elif mid == "http":
        valid = equal(
            headers.get("authorization", ""), "Bearer " + auth["verification"]
        )
    else:
        valid = False
    if not valid:
        raise HTTPException(401, "Invalid native provider authentication")


def challenge(mid, private, query, data, headers, body):
    if mid in GRAPH and "validationToken" in query:
        token = query["validationToken"]
        if not isinstance(token, str) or len(token) > 4096:
            raise HTTPException(422, "Invalid validation token")
        return token, "text/plain"
    if mid == "whatsapp_business" and query.get("hub.mode") == "subscribe":
        if not equal(query.get("hub.verify_token"), private["secrets"]["verification"]):
            raise HTTPException(401, "Invalid verification token")
        return str(query.get("hub.challenge", ""))[:4096], "text/plain"
    if mid == "slack" and data.get("type") == "url_verification":
        verify(mid, private, headers, body, data)
        return {"challenge": str(data.get("challenge", ""))[:4096]}, "application/json"
    return None


def normalize(client, mid, setup, private, delivery):
    data = delivery["body"]
    headers = delivery.get("headers", {})
    state = private["state"]
    if mid == "github":
        repo = data.get("repository", {})
        owner = repo.get("owner", {}).get("login", "")
        if (
            owner.casefold() != setup["owner"].casefold()
            or repo.get("name", "").casefold() != setup["repository"].casefold()
        ):
            return []
        action = data.get("action", "")
        name = None
        if "pusher" in data and "ref" in data:
            name = "push"
        elif "pull_request" in data:
            name = (
                "pull_request_opened" if action == "opened" else "pull_request_updated"
            )
        elif "comment" in data and "issue" in data:
            name = "comment_added"
        elif "issue" in data:
            name = "issue_opened" if action == "opened" else "issue_updated"
        elif "release" in data and action in {"created", "published"}:
            name = "release_created"
        elif "workflow_run" in data and action == "completed":
            name = "workflow_completed"
        if not name:
            return []
        record = {
            "owner": setup["owner"],
            "repository": setup["repository"],
            "branch": data.get("ref", "").removeprefix("refs/heads/"),
            "action": action,
            "payload": compact(data),
        }
        return [event(name, record, digest(data))]
    if mid == "slack":
        if (
            data.get("type") != "event_callback"
            or data.get("team_id") != state.get("account_id")
            or data.get("api_app_id") != setup["app_id"]
        ):
            return []
        item = data.get("event", {})
        typ = item.get("type")
        name = {
            "app_mention": "mention_received",
            "reaction_added": "reaction_added",
            "file_shared": "file_shared",
        }.get(typ)
        if typ == "message":
            if item.get("subtype") in {"message_changed", "message_deleted"}:
                return []
            name = "message_received"
        if typ in {"channel_created", "channel_rename", "channel_archive"}:
            name = "channel_event"
        if not name:
            return []
        channel = item.get("channel") or item.get("item", {}).get("channel")
        if isinstance(channel, dict):
            channel = channel.get("id")
        return [
            event(
                name,
                {
                    "channel_id": channel,
                    "user_id": item.get("user"),
                    "text": item.get("text", ""),
                    "message": compact(item),
                },
                data["event_id"],
            )
        ]
    if mid == "whatsapp_business":
        result = []
        for entry in data.get("entry", []):
            if str(entry.get("id")) != setup["business_account_id"]:
                continue
            for change in entry.get("changes", []):
                value = change.get("value", {})
                phone = value.get("metadata", {}).get("phone_number_id")
                for message in value.get("messages", []):
                    typ = message.get("type")
                    name = (
                        "interactive_reply"
                        if typ in {"interactive", "button"}
                        else (
                            "media_received"
                            if typ in {"image", "video", "document", "audio", "sticker"}
                            else "message_received"
                        )
                    )
                    result.append(
                        event(
                            name,
                            {
                                "phone_number_id": phone,
                                "sender": message.get("from"),
                                "message_type": typ,
                                "message": compact(message),
                                "contacts": compact(value.get("contacts", [])),
                            },
                            message["id"],
                        )
                    )
                for status in value.get("statuses", []):
                    result.append(
                        event(
                            "message_status",
                            {
                                "phone_number_id": phone,
                                "status": status["status"],
                                "message": compact(status),
                            },
                            [status["id"], status["status"], status.get("timestamp")],
                        )
                    )
        return result
    if mid == "clickup":
        from app.apps.power_apps.integrations.native_subscriptions import CLICKUP_EVENTS

        name = next(
            (k for k, v in CLICKUP_EVENTS.items() if v == data.get("event")), None
        )
        if not name:
            return []
        record = {
            "team_id": setup["team_id"],
            "space_id": data.get("space_id"),
            "list_id": data.get("list_id"),
            "task_id": data.get("task_id"),
            "payload": compact(data),
        }
        if name == "status_changed":
            record["status"] = next(
                (
                    (
                        i.get("after", {}).get("status")
                        if isinstance(i.get("after"), dict)
                        else i.get("after")
                    )
                    for i in data.get("history_items", [])
                    if i.get("field") == "status"
                ),
                None,
            )
        return [
            event(
                name,
                record,
                [
                    data.get("webhook_id"),
                    data.get("event"),
                    [i.get("id") for i in data.get("history_items", [])],
                    data.get("task_id"),
                    digest(data),
                ],
            )
        ]
    if mid == "box":
        typ = data.get("trigger")
        source = data.get("source", {})
        name = {
            "FILE.UPLOADED": "file_uploaded",
            "FOLDER.CREATED": "folder_created",
            "FILE.MOVED": "item_moved",
            "FILE.TRASHED": "item_deleted",
            "COLLABORATION.UPDATED": "collaboration_changed",
        }.get(typ)
        if (
            typ == "FILE.UPLOADED"
            and setup["event"] == "file_updated"
            and source.get("created_at") != source.get("modified_at")
        ):
            name = "file_updated"
        if not name:
            return []
        return [
            event(
                name,
                {
                    "folder_id": setup["folder_id"],
                    "source": compact(source),
                    "created_by": compact(data.get("created_by")),
                },
                data.get("id") or digest(data),
            )
        ]
    if mid == "zoho_crm":
        if str(data.get("module")) != setup["module"]:
            return []
        operation = str(data.get("operation", "")).casefold()
        name = (
            "record_created"
            if operation in {"insert", "create"}
            else "record_updated" if operation in {"update", "edit"} else None
        )
        if not name:
            return []
        fields = data.get("affected_fields", [])
        if isinstance(fields, dict):
            fields = list(fields)
        if setup["event"] == "stage_changed" and any(
            f in fields for f in {"Stage", "Pipeline"}
        ):
            name = "stage_changed"
        if setup["event"] == "owner_changed" and "Owner" in fields:
            name = "owner_changed"
        result = []
        for id in data.get("ids", [])[:100]:
            value = client.request(
                "GET", "/crm/v8/" + q(setup["module"]) + "/" + q(id), allow=(404,)
            )
            if value.get("_status") == 404:
                continue
            record = (value.get("data") or [{}])[0]
            result.append(
                event(
                    name,
                    {
                        "module": setup["module"],
                        "id": str(id),
                        "owner_id": record.get("Owner", {}).get("id"),
                        "changed_fields": fields,
                        "record": compact(record),
                    },
                    [id, name, record.get("Modified_Time"), digest(data)],
                )
            )
        return result
    if mid in GRAPH:
        if mid in {"onedrive", "sharepoint"}:
            return []  # Delta/list cursors are authoritative.
        result = []
        for notification in data.get("value", []):
            if notification.get("lifecycleEvent"):
                if notification["lifecycleEvent"] == "subscriptionRemoved":
                    state.pop("id", None)
                if notification["lifecycleEvent"] == "reauthorizationRequired":
                    state["needs_reauthorize"] = True
                if notification["lifecycleEvent"] == "missed":
                    state["needs_resync"] = True
                continue
            id = notification.get("resourceData", {}).get("id")
            if not id:
                continue
            change = notification.get("changeType")
            if mid == "microsoft_teams" and change == "deleted":
                continue
            user = "users/" + q(setup["mailbox"]) if setup.get("mailbox") else "me"
            if mid == "outlook":
                path = "/v1.0/" + user + "/messages/" + q(id)
            elif mid == "microsoft_calendar":
                path = (
                    "/v1.0/"
                    + user
                    + (
                        "/calendars/" + q(setup["calendar_id"])
                        if setup.get("calendar_id")
                        else ""
                    )
                    + "/events/"
                    + q(id)
                )
                if (
                    change == "deleted"
                    and setup.get("calendar_id")
                    and id not in state.get("calendar", {})
                ):
                    continue
            elif setup.get("chat_id"):
                path = "/v1.0/chats/" + q(setup["chat_id"]) + "/messages/" + q(id)
            else:
                path = (
                    "/v1.0/teams/"
                    + q(setup["team_id"])
                    + "/channels/"
                    + q(setup["channel_id"])
                    + "/messages/"
                    + q(id)
                )
                resource = str(notification.get("resource", ""))
                match = re.search(r"/messages/([^/]+)/replies/[^/]+$", resource)
                if match:
                    from urllib.parse import unquote

                    path = (
                        path.rsplit("/messages/", 1)[0]
                        + "/messages/"
                        + q(unquote(match.group(1)))
                        + "/replies/"
                        + q(id)
                    )
            record = (
                {"id": id}
                if change == "deleted"
                else client.request("GET", path, allow=(404,))
            )
            if record.get("_status") == 404:
                continue
            if mid == "microsoft_calendar":
                from app.apps.power_apps.integrations.native_sources import (
                    calendar_changes,
                )

                result.extend(calendar_changes(setup, state, [record], change=change))
                continue
            common = {
                "id": id,
                "mailbox": setup.get("mailbox"),
                "calendar_id": setup.get("calendar_id"),
                "team_id": setup.get("team_id"),
                "channel_id": setup.get("channel_id"),
                "chat_id": setup.get("chat_id"),
                "message": compact(record),
            }
            if mid == "outlook":
                if change == "deleted":
                    continue
                common.update(
                    folder_id=setup.get("folder_id") or record.get("parentFolderId"),
                    actual_folder_id=record.get("parentFolderId"),
                    sender=record.get("from", {})
                    .get("emailAddress", {})
                    .get("address"),
                    subject=record.get("subject", ""),
                    has_attachments=record.get("hasAttachments", False),
                )
                name = "email_received" if change == "created" else "message_updated"
                if change == "created" and setup["event"] == "folder_message_received":
                    name = "folder_message_received"
                if change == "created" and setup["event"] == "attachment_received":
                    if not record.get("hasAttachments"):
                        continue
                    common["attachments"] = compact(
                        client.request("GET", path + "/attachments").get("value", [])
                    )
                    name = "attachment_received"
            elif mid == "microsoft_calendar":
                name = {
                    "created": "event_created",
                    "updated": "event_updated",
                    "deleted": "event_deleted",
                }.get(change)
            else:
                name = (
                    "message_updated"
                    if change == "updated"
                    else (
                        "chat_message_received"
                        if setup.get("chat_id")
                        else "channel_message_received"
                    )
                )
                common["user_id"] = record.get("from", {}).get("user", {}).get("id")
                common["text"] = record.get("body", {}).get("content", "")
                if setup["event"] == "mention_received" and record.get("mentions"):
                    name = "mention_received"
            if name:
                result.append(
                    event(
                        name,
                        common,
                        [
                            id,
                            name,
                            record.get("changeKey")
                            or record.get("etag")
                            or record.get("lastModifiedDateTime")
                            or digest(record),
                        ],
                    )
                )
        return result
    if mid == "jira":
        if data.get("webhookEvent") != "comment_created":
            return []
        issue_id = data.get("issue", {}).get("id")
        comment_id = data.get("comment", {}).get("id")
        if not issue_id or not comment_id:
            return []
        path = "/rest/api/3/issue/" + q(issue_id)
        comment = client.request(
            "GET", path + "/comment/" + q(comment_id), allow=(404,)
        )
        if comment.get("_status") == 404:
            return []
        try:
            if datetime.fromisoformat(
                comment["created"].replace("Z", "+00:00")
            ) < datetime.fromisoformat(private["started_at"]):
                return []
        except (ValueError, KeyError):
            return []
        issue = client.request("GET", path, query={"fields": "project"}, allow=(404,))
        if issue.get("_status") == 404:
            return []
        return [
            event(
                "comment_added",
                {
                    "issue_id": str(issue_id),
                    "project_key": issue.get("fields", {})
                    .get("project", {})
                    .get("key"),
                    "comment": compact(comment),
                },
                str(comment_id),
            )
        ]
    if mid == "http":
        return [event("webhook_received", data, digest(data))]
    return []
