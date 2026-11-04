"""Native provider cursors, snapshots and streaming; authoritative event hydration."""

import base64
import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

from app.apps.power_apps.integrations.native_http import segment as q
from app.apps.power_apps.integrations.native_specs import GRAPH
from app.apps.power_apps.integrations.native_subscriptions import (
    cloud_token,
    graph_resource,
)
from app.apps.power_apps.integrations.contracts import IntegrationFailure


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def event(name, record, identity=None):
    return {
        "event": name,
        "event_id": str(identity or digest([name, record])),
        "data": record,
    }


def compact(value, depth=0):
    if depth > 7:
        return None
    if isinstance(value, dict):
        return {str(k): compact(v, depth + 1) for k, v in list(value.items())[:80]}
    if isinstance(value, list):
        return [compact(v, depth + 1) for v in value[:50]]
    if isinstance(value, str):
        return value[:4096]
    return value


def snapshot_events(mid, setup, state, records):
    """Only complete snapshots are accepted. Baselines never emit historical rows."""
    if len(records) > 1000:
        raise IntegrationFailure(
            "snapshot", "Narrow the native watch to at most 1000 records"
        )
    current = {str(r["id"]): compact(r) for r in records}
    if len(current) != len(records) or len(json.dumps(current).encode()) > 524288:
        raise IntegrationFailure(
            "snapshot", "Native snapshot contains duplicate keys or exceeds 512 KB"
        )
    previous = state.get("snapshot")
    result = []
    if previous is not None:
        for id in sorted(previous.keys() | current.keys()):
            old = previous.get(id)
            new = current.get(id)
            if old == new:
                continue
            changed = [
                k
                for k in sorted((old or {}).keys() | (new or {}).keys())
                if (old or {}).get(k) != (new or {}).get(k)
            ]
            data = {
                "id": id,
                "current": new,
                "previous": old,
                "changed_fields": changed,
            }
            if mid == "notion":
                data.update(page_id=id, data_source_id=setup.get("data_source_id"))
                name = (
                    ("entry_created" if setup.get("data_source_id") else "page_created")
                    if old is None
                    else (
                        "entry_updated"
                        if setup.get("data_source_id")
                        else "page_updated"
                    )
                )
            elif mid == "hubspot":
                data.update(object_type=setup["object_type"])
                props = (new or {}).get("properties", {})
                before = (old or {}).get("properties", {})
                data.update(
                    pipeline_id=props.get("pipeline"), stage_id=props.get("dealstage")
                )
                changed = [
                    k
                    for k in sorted(before.keys() | props.keys())
                    if before.get(k) != props.get(k)
                ]
                data["changed_fields"] = changed
                name = "record_created" if old is None else "record_updated"
                if (
                    setup["event"] == "deal_stage_changed"
                    and old
                    and before.get("dealstage") != props.get("dealstage")
                ):
                    name = "deal_stage_changed"
                if (
                    setup["event"] == "ticket_changed"
                    and old
                    and setup["object_type"] == "tickets"
                ):
                    name = "ticket_changed"
            elif mid == "salesforce":
                data.update(object_type=setup["object_type"])
                name = (
                    "record_created"
                    if old is None
                    else "record_deleted" if new is None else "record_updated"
                )
                if old and new and setup["event"] == "field_changed":
                    name = "field_changed"
            elif mid == "jira":
                fields = (new or {}).get("fields", {})
                old_fields = (old or {}).get("fields", {})
                data.update(
                    project_key=fields.get("project", {}).get("key"),
                    issue_type=fields.get("issuetype", {}).get("name"),
                    status=fields.get("status", {}).get("name"),
                    assignee_id=(fields.get("assignee") or {}).get("accountId"),
                )
                name = "issue_created" if old is None else "issue_updated"
                if (
                    old
                    and new
                    and setup["event"] == "status_changed"
                    and old_fields.get("status") != fields.get("status")
                ):
                    name = "status_changed"
                if (
                    old
                    and new
                    and setup["event"] == "assignment_changed"
                    and old_fields.get("assignee") != fields.get("assignee")
                ):
                    name = "assignment_changed"
            elif mid == "sharepoint":
                data.update(site_id=setup.get("site_id"), list_id=setup.get("list_id"))
                name = (
                    "item_created"
                    if old is None
                    else "item_deleted" if new is None else "item_updated"
                )
            else:
                continue
            if new is None and mid not in {"salesforce", "sharepoint"}:
                continue
            if setup["event"] == "condition_matched":
                condition = setup.get("condition", {})
                matches = (
                    lambda value: value is not None
                    and bool(condition)
                    and all(value.get(k) == v for k, v in condition.items())
                )
                if not matches(new) or matches(old):
                    continue
                name = "condition_matched"
            result.append(
                event(
                    name,
                    data,
                    [
                        id,
                        name,
                        (new or old).get("last_edited_time")
                        or (new or old).get("updatedAt")
                        or digest(new or old),
                        state.get("sample", 0),
                    ],
                )
            )
    state["snapshot"] = current
    state["sample"] = state.get("sample", 0) + 1
    return result


def poll_inventory(client, mid, setup, private):
    state = private["state"]
    if mid == "notion":
        if setup.get("data_source_id"):
            rows, _ = client.collection(
                "/v1/data_sources/" + q(setup["data_source_id"]) + "/query",
                "results",
                method="POST",
                body={"page_size": 100},
            )
        elif setup.get("page_id"):
            rows = [client.request("GET", "/v1/pages/" + q(setup["page_id"]))]
        else:
            rows, _ = client.collection(
                "/v1/search",
                "results",
                method="POST",
                body={
                    "filter": {"property": "object", "value": "page"},
                    "page_size": 100,
                },
            )
        for row in rows:
            row.pop("last_edited_by", None)
        return snapshot_events(mid, setup, state, rows)
    if mid == "hubspot":
        properties = sorted(
            set(setup.get("watched_fields", []))
            | {
                "hs_lastmodifieddate",
                "pipeline",
                "dealstage",
                "hs_pipeline",
                "hs_pipeline_stage",
            }
        )
        rows, _ = client.collection(
            "/crm/v3/objects/" + q(setup["object_type"]),
            "results",
            query={"limit": 100, "properties": ",".join(properties)},
        )
        return snapshot_events(mid, setup, state, rows)
    if mid == "salesforce":
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", setup["object_type"]):
            raise IntegrationFailure("schema", "Invalid Salesforce object API name")
        fields = set(setup.get("watched_fields", [])) | {
            "Id",
            "CreatedDate",
            "SystemModstamp",
        }
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", field) for field in fields):
            raise IntegrationFailure("schema", "Invalid Salesforce field API name")
        path = "/services/data/" + q(setup["api_version"]) + "/query"
        value = client.request(
            "GET",
            path,
            query={
                "q": "SELECT "
                + ",".join(sorted(fields))
                + " FROM "
                + setup["object_type"]
                + " LIMIT 1001"
            },
        )
        if not value.get("done", True):
            raise IntegrationFailure(
                "snapshot", "Narrow the Salesforce watch to a complete collection"
            )
        rows = [{**r, "id": r["Id"]} for r in value.get("records", [])]
        return snapshot_events(mid, setup, state, rows)
    if mid == "jira":
        jql = (
            "project = " + json.dumps(setup["project_key"])
            if setup.get("project_key")
            else "ORDER BY updated DESC"
        )
        rows = []
        page = None
        for _ in range(11):
            value = client.request(
                "GET",
                "/rest/api/3/search/jql",
                query={
                    "jql": jql,
                    "maxResults": 100,
                    "fields": "summary,status,assignee,project,issuetype,updated,created",
                    **({"nextPageToken": page} if page else {}),
                },
            )
            rows.extend(value.get("issues", []))
            page = value.get("nextPageToken")
            if not page:
                break
        if page or len(rows) > 1000:
            raise IntegrationFailure(
                "snapshot", "Narrow the Jira project watch to at most 1000 issues"
            )
        return snapshot_events(mid, setup, state, rows)
    if mid == "sharepoint":
        path = f"/v1.0/sites/{q(setup['site_id'])}/lists/{q(setup['list_id'])}/items"
        rows, _ = client.collection(path, query={"$expand": "fields", "$top": 200})
        return snapshot_events(mid, setup, state, rows)
    raise IntegrationFailure("source", "Native inventory source is not installed")


def file_events(mid, setup, state, entries, initial=False):
    inventory = state.setdefault("files", {})
    result = []
    for item in entries:
        id = str(item.get("id") or item.get("path_lower") or "")
        if not id:
            continue
        old = inventory.get(id)
        deleted = bool(
            item.get("deleted") is not None
            or item.get(".tag") == "deleted"
            or item.get("removed")
        )
        if item.get(".tag") == "deleted":
            pair = next(
                (
                    (key, value)
                    for key, value in inventory.items()
                    if value.get("path_lower") == item.get("path_lower")
                ),
                None,
            )
            if pair:
                id, old = pair
        record = compact(item)
        name = (
            "file_deleted"
            if deleted
            else (
                "folder_created"
                if old is None
                and (
                    "folder" in item
                    or item.get(".tag") == "folder"
                    or item.get("mimeType") == "application/vnd.google-apps.folder"
                )
                else "file_created" if old is None else "file_updated"
            )
        )
        parent = lambda r: (r or {}).get(
            "parentReference", (r or {}).get("parents", (r or {}).get("path_lower"))
        )
        if old and not deleted and parent(old) != parent(record):
            name = "file_moved"
        if mid == "dropbox" and name == "file_created":
            name = "file_created"
        if mid == "google_drive":
            if deleted:
                name = "permission_changed"
            elif item.get("trashed"):
                name = "file_trashed"
            elif old and old.get("permissions") != record.get("permissions"):
                name = "permission_changed"
        elif (
            old
            and not deleted
            and old.get("shared") != record.get("shared")
            and setup["event"] == "permission_changed"
        ):
            name = "permission_changed"
        if deleted:
            inventory.pop(id, None)
        else:
            inventory[id] = record
        if initial or old == record:
            continue
        data = {
            "id": id,
            "file": record,
            "previous": old,
            "drive_id": setup.get("drive_id"),
            "namespace_id": setup.get("namespace_id"),
            "path": item.get("path_display", item.get("path_lower", "")),
        }
        actual_parent = (
            item.get("parentReference", {}).get("id")
            or (item.get("parents") or [None])[0]
        )
        data["folder_id"] = actual_parent
        data["mime_type"] = item.get("mimeType") or item.get("file", {}).get("mimeType")
        if setup.get("folder_id") and actual_parent != setup["folder_id"]:
            continue
        result.append(
            event(
                name,
                data,
                [
                    id,
                    name,
                    item.get("rev")
                    or item.get("eTag")
                    or item.get("modifiedTime")
                    or digest(record),
                ],
            )
        )
    if len(inventory) > 1000 or len(json.dumps(inventory).encode()) > 524288:
        raise IntegrationFailure(
            "snapshot", "Narrow the native file watch to at most 1000 files and 512 KB"
        )
    return result


def poll_files(client, mid, setup, private):
    state = private["state"]
    result = []
    if mid == "dropbox":
        cursor = state.get("cursor")
        initial = not cursor
        value = (
            client.request("POST", "/2/files/list_folder/continue", {"cursor": cursor})
            if cursor
            else client.request(
                "POST",
                "/2/files/list_folder",
                {
                    "path": setup.get("path", setup.get("path_prefix", "")),
                    "recursive": True,
                    "include_deleted": True,
                    "limit": 1000,
                },
            )
        )
        for _ in range(10):
            result.extend(
                file_events(mid, setup, state, value.get("entries", []), initial)
            )
            state["cursor"] = value["cursor"]
            if not value.get("has_more"):
                break
            value = client.request(
                "POST", "/2/files/list_folder/continue", {"cursor": value["cursor"]}
            )
        else:
            raise IntegrationFailure(
                "pagination", "Dropbox watch has too many unprocessed pages"
            )
        return result
    if mid == "google_drive":
        if "files" not in state:
            rows, _ = client.collection(
                "/drive/v3/files",
                "files",
                query={
                    "pageSize": 1000,
                    "fields": "nextPageToken,files(id,name,mimeType,parents,modifiedTime,createdTime,trashed,permissions)",
                    "supportsAllDrives": "true",
                    "includeItemsFromAllDrives": "true",
                    **(
                        {"driveId": setup["drive_id"], "corpora": "drive"}
                        if setup.get("drive_id")
                        else {}
                    ),
                },
            )
            file_events(mid, setup, state, rows, True)
        page = state["cursor"]
        for _ in range(10):
            value = client.request(
                "GET",
                "/drive/v3/changes",
                query={
                    "pageToken": page,
                    "pageSize": 1000,
                    "supportsAllDrives": "true",
                    "includeItemsFromAllDrives": "true",
                    "fields": "nextPageToken,newStartPageToken,changes(fileId,removed,time,file(id,name,mimeType,parents,modifiedTime,createdTime,trashed,permissions))",
                    **({"driveId": setup["drive_id"]} if setup.get("drive_id") else {}),
                },
            )
            entries = [
                {
                    **c.get("file", {}),
                    "id": c["fileId"],
                    **({"removed": True} if c.get("removed") else {}),
                }
                for c in value.get("changes", [])
                if c.get("fileId")
            ]
            result.extend(file_events(mid, setup, state, entries))
            page = value.get("nextPageToken")
            if not page:
                state["cursor"] = value["newStartPageToken"]
                break
        else:
            raise IntegrationFailure(
                "pagination", "Drive changes need a narrower watch"
            )
        return result
    path = f"/v1.0/drives/{q(setup['drive_id'])}/root/delta"
    initial = not state.get("delta_link")
    value = (
        client.follow(state["delta_link"], path)
        if not initial
        else client.request("GET", path, query={"$top": 200})
    )
    for _ in range(20):
        result.extend(file_events(mid, setup, state, value.get("value", []), initial))
        if not value.get("@odata.nextLink"):
            if not value.get("@odata.deltaLink"):
                raise IntegrationFailure(
                    "cursor", "Graph did not return a delta cursor"
                )
            state["delta_link"] = value["@odata.deltaLink"]
            break
        value = client.follow(value["@odata.nextLink"], path)
    else:
        raise IntegrationFailure("pagination", "Graph delta has too many pages")
    return result


def poll_calendar(client, mid, setup, private):
    state = private["state"]
    if mid == "google_calendar":
        path = "/calendar/v3/calendars/" + q(setup["calendar_id"]) + "/events"
        query = {"maxResults": 1000, "showDeleted": "true"}
        if state.get("sync_token"):
            query["syncToken"] = state["sync_token"]
        rows, tail = client.collection(path, "items", query=query)
        initial = not state.get("sync_token")
        state["sync_token"] = tail["nextSyncToken"]
    else:
        user = "users/" + q(setup["mailbox"]) if setup.get("mailbox") else "me"
        path = (
            "/v1.0/"
            + user
            + (
                "/calendars/" + q(setup["calendar_id"])
                if setup.get("calendar_id")
                else ""
            )
            + "/calendarView"
        )
        current = datetime.now(timezone.utc)
        rows, _ = client.collection(
            path,
            query={
                "startDateTime": (current - timedelta(days=1)).isoformat(),
                "endDateTime": (current + timedelta(days=90)).isoformat(),
                "$top": 200,
            },
        )
        initial = "calendar" not in state
    inventory = state.setdefault("calendar", {})
    result = []
    for row in rows:
        id = row["id"]
        old = inventory.get(id)
        record = compact(row)
        deleted = row.get("status") == "cancelled" or row.get("isCancelled")
        name = (
            "event_deleted"
            if deleted
            else "event_created" if old is None else "event_updated"
        )
        if (
            old
            and old.get("attendees") != record.get("attendees")
            and setup["event"] == "attendee_response_changed"
        ):
            name = "attendee_response_changed"
        inventory[id] = record
        if not initial and old != record:
            result.append(
                event(
                    name,
                    {
                        "id": id,
                        "calendar_id": setup.get("calendar_id"),
                        "mailbox": setup.get("mailbox"),
                        "current": record,
                        "previous": old,
                    },
                )
            )
    if setup["event"] == "event_approaching":
        lead = setup.get("minutes_before", 15) * 60
        now = time.time()
        for id, row in inventory.items():
            start = row.get("start", {}).get("dateTime")
            if not start or row.get("status") == "cancelled" or row.get("isCancelled"):
                continue
            try:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    from zoneinfo import ZoneInfo

                    tz = row.get("start", {}).get("timeZone", "UTC")
                    if tz == "UTC":
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.replace(tzinfo=ZoneInfo(tz))
                if 0 <= dt.timestamp() - now <= lead:
                    result.append(
                        event(
                            "event_approaching",
                            {
                                "id": id,
                                "calendar_id": setup.get("calendar_id"),
                                "mailbox": setup.get("mailbox"),
                                "minutes_before": setup.get("minutes_before", 15),
                                "current": row,
                            },
                            [id, start, lead],
                        )
                    )
            except (ValueError, KeyError):
                raise IntegrationFailure(
                    "timezone", "Calendar event has an unsupported timezone"
                ) from None
    if len(inventory) > 1000 or len(json.dumps(inventory).encode()) > 524288:
        raise IntegrationFailure("snapshot", "Narrow the calendar watch")
    return result


def gmail_messages(client, setup, private):
    state = private["state"]
    page = None
    events = []
    latest = state["history_id"]
    for _ in range(10):
        value = client.request(
            "GET",
            "/gmail/v1/users/me/history",
            query={
                "startHistoryId": state["history_id"],
                **({"pageToken": page} if page else {}),
            },
            allow=(404,),
        )
        if value.get("_status") == 404:
            raise IntegrationFailure(
                "cursor_expired",
                "Gmail history expired; re-enable the trigger to establish a new baseline",
            )
        for history in value.get("history", []):
            added = (
                history.get("labelsAdded", [])
                if setup["event"] == "label_added"
                else history.get("messagesAdded", [])
            )
            for change in added:
                id = change["message"]["id"]
                message = client.request(
                    "GET",
                    "/gmail/v1/users/me/messages/" + q(id),
                    query={"format": "full"},
                    allow=(404,),
                )
                if message.get("_status") == 404:
                    continue
                headers = {
                    h["name"].casefold(): h["value"]
                    for h in message.get("payload", {}).get("headers", [])
                }

                def attachments(part):
                    found = []
                    if part.get("filename") and part.get("body", {}).get(
                        "attachmentId"
                    ):
                        found.append(
                            {
                                "filename": part["filename"],
                                "attachment_id": part["body"]["attachmentId"],
                                "mime_type": part.get("mimeType"),
                            }
                        )
                    for child in part.get("parts", []):
                        found.extend(attachments(child))
                    return found

                files = attachments(message.get("payload", {}))
                labels = message.get("labelIds", [])
                if (
                    setup["event"] != "label_added"
                    and "SENT" in labels
                    and "INBOX" not in labels
                ):
                    continue
                data = {
                    "id": id,
                    "thread_id": message.get("threadId"),
                    "label_ids": labels,
                    "sender": parseaddr(headers.get("from", ""))[1],
                    "subject": headers.get("subject", ""),
                    "has_attachments": bool(files),
                    "attachments": files,
                    "snippet": message.get("snippet", ""),
                    "history_id": history["id"],
                }
                name = setup["event"]
                if name == "attachment_received" and not files:
                    continue
                events.append(event(name, data, [history["id"], id, name]))
        latest = value.get("historyId", latest)
        page = value.get("nextPageToken")
        if not page:
            state["history_id"] = latest
            return events
    raise IntegrationFailure(
        "pagination", "Gmail has too many unprocessed history pages"
    )


def poll_pubsub(client, mid, setup, private):
    state = private["state"]
    token = cloud_token(client, private)
    value = client.request(
        "POST",
        "/v1/" + state["subscription"] + ":pull",
        {"maxMessages": 20},
        host="pubsub.googleapis.com",
        bearer=token,
    )
    received = value.get("receivedMessages", [])
    if not received:
        return [], []
    if mid == "gmail":
        result = gmail_messages(client, setup, private)
    elif setup["event"] == "form_changed":
        form = client.request("GET", "/v1/forms/" + q(setup["form_id"]))
        revision = form.get("revisionId") or digest(form)
        result = [
            event(
                "form_changed",
                {
                    "form_id": setup["form_id"],
                    "revision_id": revision,
                    "form": compact(form),
                },
                [setup["form_id"], revision],
            )
        ]
    else:
        rows, _ = client.collection(
            "/v1/forms/" + q(setup["form_id"]) + "/responses",
            "responses",
            query={
                "pageSize": 1000,
                "filter": "timestamp > "
                + state.get("response_after", private["started_at"]),
            },
        )
        result = [
            event(
                "response_received",
                {"form_id": setup["form_id"], "response": compact(row)},
                [
                    row["responseId"],
                    row.get("lastSubmittedTime", row.get("createTime")),
                ],
            )
            for row in rows
        ]
        if rows:
            state["response_after"] = max(
                r.get("lastSubmittedTime", r["createTime"]) for r in rows
            )
    return result, [r["ackId"] for r in received]


def poll_airtable(client, setup, private):
    state = private["state"]
    result = []
    for _ in range(5):
        value = client.request(
            "GET",
            state["path"] + "/" + q(state["id"]) + "/payloads",
            query={"cursor": state.get("cursor", 1), "limit": 50},
        )
        for payload in value.get("payloads", []):
            table = payload.get("changedTablesById", {}).get(setup["table_id"], {})
            common = {
                "base_id": setup["base_id"],
                "table_id": setup["table_id"],
                "view_id": setup.get("view_id"),
            }
            for key, name in [
                ("createdRecordsById", "record_created"),
                ("changedRecordsById", "record_updated"),
            ]:
                for id, record in table.get(key, {}).items():
                    current = record.get("current", record).get(
                        "cellValuesByFieldId", {}
                    )
                    previous = record.get("previous", {}).get("cellValuesByFieldId", {})
                    fields = sorted(current.keys() | previous.keys())
                    data = {
                        **common,
                        "id": id,
                        "current": current,
                        "previous": previous,
                        "changed_fields": fields,
                    }
                    event_name = (
                        "field_changed"
                        if name == "record_updated"
                        and setup["event"] == "field_changed"
                        else name
                    )
                    condition = setup.get("condition", {})
                    if setup["event"] == "condition_matched":
                        if (
                            not condition
                            or not all(
                                current.get(k) == v for k, v in condition.items()
                            )
                            or all(previous.get(k) == v for k, v in condition.items())
                        ):
                            continue
                        event_name = "condition_matched"
                    result.append(
                        event(
                            event_name,
                            data,
                            [payload.get("baseTransactionNumber"), id, event_name],
                        )
                    )
            for id in table.get("destroyedRecordIds", []):
                result.append(
                    event(
                        "record_deleted",
                        {**common, "id": id},
                        [payload.get("baseTransactionNumber"), id, "deleted"],
                    )
                )
        state["cursor"] = value["cursor"]
        if not value.get("mightHaveMore"):
            break
    return result


def poll_stream(client, setup, private):
    state = private["state"]
    path = "/cometd/" + q(setup["api_version"].removeprefix("v"))
    channel = setup["stream_channel"]
    if not re.fullmatch(r"/(?:event|data)/[A-Za-z][A-Za-z0-9_]*", channel):
        raise IntegrationFailure("schema", "Select a valid Salesforce event channel")
    if not state.get("client_id"):
        messages = client.request(
            "POST",
            path,
            [
                {
                    "channel": "/meta/handshake",
                    "version": "1.0",
                    "minimumVersion": "1.0",
                    "supportedConnectionTypes": ["long-polling"],
                }
            ],
        )
        handshake = next(
            (m for m in messages if m.get("channel") == "/meta/handshake"), {}
        )
        if not handshake.get("successful"):
            raise IntegrationFailure("stream", "Salesforce streaming handshake failed")
        state["client_id"] = handshake["clientId"]
        subscribed = client.request(
            "POST",
            path,
            [
                {
                    "channel": "/meta/subscribe",
                    "clientId": state["client_id"],
                    "subscription": channel,
                    "ext": {"replay": {channel: state.get("replay_id", -1)}},
                }
            ],
        )
        if not any(m.get("successful") for m in subscribed):
            state.pop("client_id", None)
            raise IntegrationFailure(
                "stream", "Salesforce rejected the event subscription"
            )
    messages = client.request(
        "POST",
        path,
        [
            {
                "channel": "/meta/connect",
                "clientId": state["client_id"],
                "connectionType": "long-polling",
                "advice": {"timeout": 0},
            }
        ],
    )
    result = []
    for message in messages:
        if message.get("channel") == channel and message.get("data"):
            data = message["data"]
            replay = data.get("event", {}).get("replayId")
            result.append(
                event(
                    "platform_event",
                    {"channel": channel, "payload": compact(data)},
                    [channel, replay or digest(data)],
                )
            )
            if replay is not None:
                state["replay_id"] = replay
        if (
            message.get("advice", {}).get("reconnect") == "handshake"
            or message.get("successful") is False
        ):
            state.pop("client_id", None)
    return result
