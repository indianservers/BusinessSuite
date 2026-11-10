"""Deployment-owned REST operations for the workflow automation connector library.

Paths and origins are code, never workflow input. Structured bodies retain provider
types; each action publishes precisely the fields consumed by its adapter.
"""

import base64
import json
import re
import time
from typing import Any
from urllib.parse import quote, urlencode, urlsplit, urljoin

from pydantic import Field, create_model
from app.apps.power_apps.integrations.contracts import Strict, IntegrationFailure

MODULES = {}
OPERATIONS = {}
MODELS = {}
INSTALLED = set()
EVENT_RESOURCE_FIELDS = {
    "gmail": "label_id sender subject_contains has_attachments:bool",
    "outlook": "mailbox folder_id sender subject_contains has_attachments:bool",
    "whatsapp_business": "phone_number_id sender message_type status",
    "slack": "channel_id user_id text_contains",
    "microsoft_teams": "team_id channel_id chat_id user_id text_contains",
    "google_drive": "drive_id folder_id mime_type",
    "onedrive": "drive_id folder_id",
    "sharepoint": "site_id drive_id folder_id list_id",
    "dropbox": "path_prefix namespace_id",
    "box": "folder_id",
    "google_calendar": "calendar_id minutes_before:int",
    "microsoft_calendar": "mailbox calendar_id minutes_before:int",
    "google_forms": "form_id",
    "notion": "page_id data_source_id",
    "airtable": "base_id table_id view_id watched_fields:list",
    "hubspot": "object_type pipeline_id stage_id watched_fields:list",
    "salesforce": "object_type watched_fields:list",
    "zoho_crm": "module owner_id watched_fields:list",
    "jira": "project_key issue_type status assignee_id",
    "clickup": "team_id space_id list_id status assignee_id",
    "github": "owner repository branch action",
}
G = "https://www.googleapis.com/auth/"


def module(id, name, category, host, base, docs, events, *, scopes=(), headers=None):
    MODULES[id] = dict(
        id=id,
        name=name,
        category=category,
        host=host,
        base=base,
        docs=docs,
        events=events.split(),
        scopes=list(scopes),
        headers=headers or {},
    )
    return id


def op(
    module_id,
    id,
    method,
    path,
    fields="",
    *,
    body=None,
    query=None,
    transform=None,
    read=False,
    scope=None,
    host=None,
):
    """Field syntax: name, optional?, object:json, array:list, integer:int, flag:bool."""
    definitions = {}
    for token in fields.split():
        optional = token.endswith("?")
        token = token.rstrip("?")
        name, _, kind = token.partition(":")
        typ = {"json": dict, "list": list, "int": int, "bool": bool, "any": Any}.get(
            kind, str
        )
        constraints = (
            {"max_length": 32768}
            if typ is str
            else {"max_length": 1000} if typ in (dict, list) else {}
        )
        definitions[name] = (
            typ | None if optional else typ,
            Field(default=None, **constraints) if optional else Field(**constraints),
        )
    for name in re.findall(r"\{(\w+)\}", MODULES[module_id]["base"] + path):
        if name != "bot_token" and name not in definitions:
            definitions[name] = (str, Field(min_length=1, max_length=1000))
    model = create_model(f"Automation_{module_id}_{id}", __base__=Strict, **definitions)
    MODELS[module_id, id] = model
    OPERATIONS[module_id, id] = dict(
        id=id,
        method=method,
        path=path,
        body=body or {},
        query=query or {},
        transform=transform,
        mutates=not read and method not in {"GET", "HEAD"},
        scope=scope,
        host=host,
    )


m = module(
    "gmail",
    "Gmail",
    "Email",
    "gmail.googleapis.com",
    "/gmail/v1/users/me",
    "https://developers.google.com/workspace/gmail/api/reference/rest",
    "email_received email_matching attachment_received label_added",
    scopes=[
        G + "gmail.readonly",
        G + "gmail.send",
        G + "gmail.modify",
        G + "gmail.compose",
    ],
)
op(
    m,
    "list_messages",
    "GET",
    "/messages",
    "q? max_results:int? page_token? label_ids:list?",
    query={
        "q": "q",
        "maxResults": "max_results",
        "pageToken": "page_token",
        "labelIds": "label_ids",
    },
    scope=G + "gmail.readonly",
)
op(
    m,
    "get_message",
    "GET",
    "/messages/{message_id}",
    "format?",
    query={"format": "format"},
    scope=G + "gmail.readonly",
)
op(m, "get_thread", "GET", "/threads/{thread_id}", scope=G + "gmail.readonly")
op(
    m,
    "get_attachment",
    "GET",
    "/messages/{message_id}/attachments/{attachment_id}",
    scope=G + "gmail.readonly",
)
op(m, "list_labels", "GET", "/labels", scope=G + "gmail.readonly")
for id, path in [
    ("send_message", "/messages/send"),
    ("reply", "/messages/send"),
    ("forward", "/messages/send"),
    ("create_draft", "/drafts"),
]:
    op(
        m,
        id,
        "POST",
        path,
        "to subject text cc? bcc? reply_to? html? thread_id? in_reply_to? references? attachments:list?",
        transform="gmail",
        scope=G + ("gmail.compose" if id == "create_draft" else "gmail.send"),
    )
op(
    m,
    "send_draft",
    "POST",
    "/drafts/send",
    "draft_id",
    body={"id": "draft_id"},
    scope=G + "gmail.compose",
)
op(
    m,
    "modify_labels",
    "POST",
    "/messages/{message_id}/modify",
    "add_label_ids:list? remove_label_ids:list?",
    body={"addLabelIds": "add_label_ids", "removeLabelIds": "remove_label_ids"},
    scope=G + "gmail.modify",
)
for id, add, remove in [
    ("mark_read", [], ["UNREAD"]),
    ("mark_unread", ["UNREAD"], []),
    ("archive", [], ["INBOX"]),
]:
    op(
        m,
        id,
        "POST",
        "/messages/{message_id}/modify",
        transform=("gmail_labels", tuple(add), tuple(remove)),
        scope=G + "gmail.modify",
    )
for id in ("trash", "untrash"):
    op(m, id, "POST", "/messages/{message_id}/" + id, scope=G + "gmail.modify")
op(
    m,
    "create_label",
    "POST",
    "/labels",
    "name",
    body={"name": "name"},
    scope=G + "gmail.modify",
)

m = module(
    "outlook",
    "Microsoft Outlook",
    "Email",
    "graph.microsoft.com",
    "/v1.0",
    "https://learn.microsoft.com/en-us/graph/api/resources/message",
    "email_received message_updated attachment_received folder_message_received",
)
for id, path in [
    ("read_messages", "/users/{mailbox}/mailFolders/{folder_id}/messages"),
    ("search_messages", "/users/{mailbox}/messages"),
]:
    op(
        m,
        id,
        "GET",
        path,
        "filter? search? top:int? skip:int?",
        query={
            "$filter": "filter",
            "$search": "search",
            "$top": "top",
            "$skip": "skip",
        },
        scope="Mail.Read",
    )
op(m, "get_message", "GET", "/users/{mailbox}/messages/{message_id}", scope="Mail.Read")
op(m, "list_folders", "GET", "/users/{mailbox}/mailFolders", scope="Mail.Read")
op(
    m,
    "list_attachments",
    "GET",
    "/users/{mailbox}/messages/{message_id}/attachments",
    scope="Mail.Read",
)
op(
    m,
    "get_attachment",
    "GET",
    "/users/{mailbox}/messages/{message_id}/attachments/{attachment_id}",
    scope="Mail.Read",
)
op(
    m,
    "send_message",
    "POST",
    "/users/{mailbox}/sendMail",
    "message:json save_to_sent_items:bool?",
    body={"message": "message", "saveToSentItems": "save_to_sent_items"},
    scope="Mail.Send",
)
op(
    m,
    "create_draft",
    "POST",
    "/users/{mailbox}/messages",
    "message:json",
    transform="message",
    scope="Mail.ReadWrite",
)
for id in ("reply", "replyAll", "forward"):
    op(
        m,
        id,
        "POST",
        "/users/{mailbox}/messages/{message_id}/" + id,
        "comment? to_recipients:list?",
        body={"comment": "comment", "toRecipients": "to_recipients"},
        scope="Mail.Send",
    )
op(
    m,
    "move_message",
    "POST",
    "/users/{mailbox}/messages/{message_id}/move",
    "destination_id",
    body={"destinationId": "destination_id"},
    scope="Mail.ReadWrite",
)
op(
    m,
    "update_message",
    "PATCH",
    "/users/{mailbox}/messages/{message_id}",
    "is_read:bool? categories:list?",
    body={"isRead": "is_read", "categories": "categories"},
    scope="Mail.ReadWrite",
)
op(
    m,
    "delete_message",
    "DELETE",
    "/users/{mailbox}/messages/{message_id}",
    scope="Mail.ReadWrite",
)

m = module(
    "telegram",
    "Telegram",
    "Communication",
    "api.telegram.org",
    "/bot{bot_token}",
    "https://core.telegram.org/bots/api",
    "message_received channel_post edited_message callback_query membership_updated",
)
op(
    m,
    "get_updates",
    "POST",
    "/getUpdates",
    "offset:int? limit:int? allowed_updates:list?",
    body={"offset": "offset", "limit": "limit", "allowed_updates": "allowed_updates"},
    read=True,
)
op(m, "get_chat", "POST", "/getChat", "chat_id", body={"chat_id": "chat_id"}, read=True)
op(m, "get_file", "POST", "/getFile", "file_id", body={"file_id": "file_id"}, read=True)
op(
    m,
    "download_file",
    "GET",
    "/file/bot{bot_token}/{file_path}",
    transform="telegram_download",
)
for id, remote, extra in [
    ("send_photo", "sendPhoto", "photo"),
    ("send_document", "sendDocument", "document"),
    ("send_voice", "sendVoice", "voice"),
]:
    op(
        m,
        id,
        "POST",
        "/" + remote,
        "chat_id " + extra + " caption? reply_parameters:json? reply_markup:json?",
        body={
            k: k
            for k in ["chat_id", extra, "caption", "reply_parameters", "reply_markup"]
        },
    )
op(
    m,
    "send_text",
    "POST",
    "/sendMessage",
    "chat_id text parse_mode? reply_parameters:json? reply_markup:json?",
    body={
        k: k
        for k in ["chat_id", "text", "parse_mode", "reply_parameters", "reply_markup"]
    },
)
op(
    m,
    "edit_message",
    "POST",
    "/editMessageText",
    "chat_id message_id:int text reply_markup:json?",
    body={k: k for k in ["chat_id", "message_id", "text", "reply_markup"]},
)
op(
    m,
    "delete_message",
    "POST",
    "/deleteMessage",
    "chat_id message_id:int",
    body={"chat_id": "chat_id", "message_id": "message_id"},
)
op(
    m,
    "answer_callback",
    "POST",
    "/answerCallbackQuery",
    "callback_query_id text? show_alert:bool?",
    body={k: k for k in ["callback_query_id", "text", "show_alert"]},
)

m = module(
    "whatsapp_business",
    "WhatsApp Business",
    "Communication",
    "graph.facebook.com",
    "/{api_version}",
    "https://developers.facebook.com/docs/whatsapp/cloud-api",
    "message_received media_received interactive_reply message_status",
)
op(
    m,
    "send_message",
    "POST",
    "/{phone_number_id}/messages",
    "to type text:json? template:json? image:json? document:json? interactive:json? context:json?",
    transform="whatsapp",
)
op(
    m,
    "mark_read",
    "POST",
    "/{phone_number_id}/messages",
    "message_id",
    transform="whatsapp_read",
)
op(m, "get_media", "GET", "/{media_id}")

m = module(
    "google_sheets",
    "Google Sheets",
    "Productivity",
    "sheets.googleapis.com",
    "/v4/spreadsheets",
    "https://developers.google.com/workspace/sheets/api/reference/rest",
    "row_added row_updated row_deleted cell_changed condition_matched",
    scopes=[G + "spreadsheets", G + "spreadsheets.readonly"],
)
op(
    m,
    "get_spreadsheet",
    "GET",
    "/{spreadsheet_id}",
    "include_grid_data:bool?",
    query={"includeGridData": "include_grid_data"},
    scope=G + "spreadsheets.readonly",
)
op(
    m,
    "get_values",
    "GET",
    "/{spreadsheet_id}/values/{range}",
    "value_render_option?",
    query={"valueRenderOption": "value_render_option"},
    scope=G + "spreadsheets.readonly",
)
op(
    m,
    "create_spreadsheet",
    "POST",
    "",
    "title",
    transform="sheet_create",
    scope=G + "spreadsheets",
)
op(
    m,
    "update_values",
    "PUT",
    "/{spreadsheet_id}/values/{range}",
    "values:list value_input_option?",
    body={"values": "values"},
    query={"valueInputOption": "value_input_option"},
    scope=G + "spreadsheets",
)
op(
    m,
    "append_values",
    "POST",
    "/{spreadsheet_id}/values/{range}:append",
    "values:list value_input_option? insert_data_option?",
    body={"values": "values"},
    query={
        "valueInputOption": "value_input_option",
        "insertDataOption": "insert_data_option",
    },
    scope=G + "spreadsheets",
)
op(
    m,
    "clear_values",
    "POST",
    "/{spreadsheet_id}/values/{range}:clear",
    scope=G + "spreadsheets",
)
op(
    m,
    "batch_update",
    "POST",
    "/{spreadsheet_id}:batchUpdate",
    "requests:list",
    body={"requests": "requests"},
    scope=G + "spreadsheets",
)
op(
    m,
    "create_tab",
    "POST",
    "/{spreadsheet_id}:batchUpdate",
    "title",
    transform="sheet_tab",
    scope=G + "spreadsheets",
)
op(
    m,
    "delete_rows",
    "POST",
    "/{spreadsheet_id}:batchUpdate",
    "sheet_id:int start_index:int end_index:int",
    transform="sheet_delete",
    scope=G + "spreadsheets",
)
op(
    m,
    "format_range",
    "POST",
    "/{spreadsheet_id}:batchUpdate",
    "grid_range:json format:json fields",
    transform="sheet_format",
    scope=G + "spreadsheets",
)

m = module(
    "excel_online",
    "Excel Online",
    "Productivity",
    "graph.microsoft.com",
    "/v1.0/drives/{drive_id}/items/{workbook_id}/workbook",
    "https://learn.microsoft.com/en-us/graph/api/resources/excel",
    "row_added row_updated row_deleted cell_changed condition_matched",
)
for id, path in [
    ("list_worksheets", "/worksheets"),
    ("list_tables", "/tables"),
    ("list_rows", "/tables/{table_id}/rows"),
    ("get_row", "/tables/{table_id}/rows/{row_index}"),
]:
    op(m, id, "GET", path, scope="Files.ReadWrite")
op(m, "list_columns", "GET", "/tables/{table_id}/columns", scope="Files.ReadWrite")
op(
    m,
    "get_range",
    "GET",
    "/worksheets/{worksheet_id}/range(address='{range}')",
    scope="Files.ReadWrite",
)
op(
    m,
    "add_rows",
    "POST",
    "/tables/{table_id}/rows/add",
    "values:list index:int?",
    body={"values": "values", "index": "index"},
    scope="Files.ReadWrite",
)
op(
    m,
    "update_row",
    "PATCH",
    "/tables/{table_id}/rows/{row_index}",
    "values:list",
    body={"values": "values"},
    scope="Files.ReadWrite",
)
op(
    m,
    "delete_row",
    "DELETE",
    "/tables/{table_id}/rows/{row_index}",
    scope="Files.ReadWrite",
)
op(
    m,
    "write_range",
    "PATCH",
    "/worksheets/{worksheet_id}/range(address='{range}')",
    "values:list? formulas:list?",
    body={"values": "values", "formulas": "formulas"},
    scope="Files.ReadWrite",
)
op(
    m,
    "clear_range",
    "POST",
    "/worksheets/{worksheet_id}/range(address='{range}')/clear",
    "apply_to?",
    body={"applyTo": "apply_to"},
    scope="Files.ReadWrite",
)
op(
    m,
    "create_worksheet",
    "POST",
    "/worksheets",
    "name",
    body={"name": "name"},
    scope="Files.ReadWrite",
)

m = module(
    "google_drive",
    "Google Drive",
    "File Storage",
    "www.googleapis.com",
    "/drive/v3",
    "https://developers.google.com/workspace/drive/api/reference/rest",
    "file_created folder_created file_updated file_moved file_trashed permission_changed",
    scopes=[G + "drive.file"],
)
op(
    m,
    "search_files",
    "GET",
    "/files",
    "q? page_token? page_size:int? drive_id? corpora?",
    query={
        "q": "q",
        "pageToken": "page_token",
        "pageSize": "page_size",
        "driveId": "drive_id",
        "corpora": "corpora",
    },
    scope=G + "drive.file",
)
op(
    m,
    "create_folder",
    "POST",
    "/files",
    "name parent_id?",
    transform="drive_folder",
    scope=G + "drive.file",
)
op(
    m,
    "upload_file",
    "POST",
    "/upload/drive/v3/files",
    "name content_base64 mime_type parent_id?",
    transform="drive_upload",
    scope=G + "drive.file",
)
op(
    m,
    "download_file",
    "GET",
    "/files/{file_id}",
    transform="drive_download",
    scope=G + "drive.file",
)
op(
    m,
    "export_file",
    "GET",
    "/files/{file_id}/export",
    "mime_type",
    query={"mimeType": "mime_type"},
    transform="binary",
    scope=G + "drive.file",
)
op(
    m,
    "update_metadata",
    "PATCH",
    "/files/{file_id}",
    "name? description? trashed:bool?",
    body={k: k for k in ["name", "description", "trashed"]},
    scope=G + "drive.file",
)
op(
    m,
    "move_file",
    "PATCH",
    "/files/{file_id}",
    "add_parents remove_parents",
    query={"addParents": "add_parents", "removeParents": "remove_parents"},
    scope=G + "drive.file",
)
op(
    m,
    "copy_file",
    "POST",
    "/files/{file_id}/copy",
    "name? parents:list?",
    body={"name": "name", "parents": "parents"},
    scope=G + "drive.file",
)
op(
    m,
    "share_file",
    "POST",
    "/files/{file_id}/permissions",
    "type role email_address?",
    body={"type": "type", "role": "role", "emailAddress": "email_address"},
    scope=G + "drive.file",
)
op(m, "list_permissions", "GET", "/files/{file_id}/permissions", scope=G + "drive.file")
op(m, "list_revisions", "GET", "/files/{file_id}/revisions", scope=G + "drive.file")

for id, name in [("onedrive", "OneDrive"), ("sharepoint", "SharePoint")]:
    m = module(
        id,
        name,
        "File Storage",
        "graph.microsoft.com",
        "/v1.0",
        "https://learn.microsoft.com/en-us/graph/api/resources/driveitem",
        "file_created folder_created file_updated file_moved file_deleted permission_changed"
        + (" item_created item_updated item_deleted" if id == "sharepoint" else ""),
    )
    for aid, path in [
        ("list_files", "/drives/{drive_id}/items/{folder_id}/children"),
        ("get_file", "/drives/{drive_id}/items/{file_id}"),
        ("list_versions", "/drives/{drive_id}/items/{file_id}/versions"),
        ("list_permissions", "/drives/{drive_id}/items/{file_id}/permissions"),
    ]:
        op(m, aid, "GET", path, scope="Files.Read")
    op(
        m,
        "search_files",
        "GET",
        "/drives/{drive_id}/root/search(q='{query}')",
        scope="Files.Read",
    )
    op(
        m,
        "create_folder",
        "POST",
        "/drives/{drive_id}/items/{parent_id}/children",
        "name conflict_behavior?",
        transform="graph_folder",
        scope="Files.ReadWrite",
    )
    op(
        m,
        "upload_file",
        "PUT",
        "/drives/{drive_id}/items/{parent_id}:/{name}:/content",
        "content_base64 mime_type?",
        transform="upload",
        scope="Files.ReadWrite",
    )
    op(
        m,
        "download_file",
        "GET",
        "/drives/{drive_id}/items/{file_id}/content",
        transform="binary",
        scope="Files.Read",
    )
    op(
        m,
        "update_file",
        "PATCH",
        "/drives/{drive_id}/items/{file_id}",
        "name? parent_reference:json?",
        body={"name": "name", "parentReference": "parent_reference"},
        scope="Files.ReadWrite",
    )
    op(
        m,
        "copy_file",
        "POST",
        "/drives/{drive_id}/items/{file_id}/copy",
        "name? parent_reference:json",
        body={"name": "name", "parentReference": "parent_reference"},
        scope="Files.ReadWrite",
    )
    op(
        m,
        "create_sharing_link",
        "POST",
        "/drives/{drive_id}/items/{file_id}/createLink",
        "type scope?",
        body={"type": "type", "scope": "scope"},
        scope="Files.ReadWrite",
    )
    op(
        m,
        "delete_file",
        "DELETE",
        "/drives/{drive_id}/items/{file_id}",
        scope="Files.ReadWrite",
    )
    op(
        m,
        "restore_version",
        "POST",
        "/drives/{drive_id}/items/{file_id}/versions/{version_id}/restoreVersion",
        scope="Files.ReadWrite",
    )
    op(
        m,
        "delta",
        "GET",
        "/drives/{drive_id}/root/delta",
        "delta_token?",
        query={"token": "delta_token"},
        scope="Files.Read",
    )
    if id == "sharepoint":
        for aid, path in [
            ("list_sites", "/sites"),
            ("list_libraries", "/sites/{site_id}/drives"),
            ("list_lists", "/sites/{site_id}/lists"),
            ("list_items", "/sites/{site_id}/lists/{list_id}/items?expand=fields"),
            (
                "get_item",
                "/sites/{site_id}/lists/{list_id}/items/{item_id}?expand=fields",
            ),
        ]:
            op(m, aid, "GET", path, scope="Sites.Read.All")
        op(
            m,
            "create_item",
            "POST",
            "/sites/{site_id}/lists/{list_id}/items",
            "fields:json",
            body={"fields": "fields"},
            scope="Sites.ReadWrite.All",
        )
        op(
            m,
            "update_item",
            "PATCH",
            "/sites/{site_id}/lists/{list_id}/items/{item_id}/fields",
            "fields:json",
            transform="fields",
            scope="Sites.ReadWrite.All",
        )
        op(
            m,
            "delete_item",
            "DELETE",
            "/sites/{site_id}/lists/{list_id}/items/{item_id}",
            scope="Sites.ReadWrite.All",
        )

m = module(
    "dropbox",
    "Dropbox",
    "File Storage",
    "api.dropboxapi.com",
    "/2",
    "https://www.dropbox.com/developers/documentation/http/documentation",
    "file_created folder_created file_updated file_moved file_deleted",
)
for aid, remote, fields in [
    ("list_files", "files/list_folder", "path recursive:bool?"),
    ("list_changes", "files/list_folder/continue", "cursor"),
    ("search_files", "files/search_v2", "query"),
    ("get_metadata", "files/get_metadata", "path"),
    ("list_revisions", "files/list_revisions", "path"),
    ("list_shared_links", "sharing/list_shared_links", "path?"),
]:
    op(
        m,
        aid,
        "POST",
        "/" + remote,
        fields,
        body={
            x.split(":")[0].rstrip("?"): x.split(":")[0].rstrip("?")
            for x in fields.split()
        },
        read=True,
    )
for aid, remote, fields in [
    ("create_folder", "files/create_folder_v2", "path autorename:bool?"),
    ("copy_file", "files/copy_v2", "from_path to_path autorename:bool?"),
    ("move_file", "files/move_v2", "from_path to_path autorename:bool?"),
    ("delete_file", "files/delete_v2", "path"),
    ("restore_file", "files/restore", "path rev"),
    (
        "create_sharing_link",
        "sharing/create_shared_link_with_settings",
        "path settings:json?",
    ),
]:
    op(
        m,
        aid,
        "POST",
        "/" + remote,
        fields,
        body={
            x.split(":")[0].rstrip("?"): x.split(":")[0].rstrip("?")
            for x in fields.split()
        },
    )
op(
    m,
    "upload_file",
    "POST",
    "/files/upload",
    "path content_base64 mode? autorename:bool?",
    transform="dropbox_upload",
    host="content.dropboxapi.com",
)
op(
    m,
    "download_file",
    "POST",
    "/files/download",
    "path",
    transform="dropbox_download",
    host="content.dropboxapi.com",
    read=True,
)

m = module(
    "box",
    "Box",
    "File Storage",
    "api.box.com",
    "/2.0",
    "https://developer.box.com/reference/",
    "file_uploaded file_updated folder_created item_moved item_deleted collaboration_changed",
)
for aid, path in [
    ("list_files", "/folders/{folder_id}/items"),
    ("get_file", "/files/{file_id}"),
    ("list_versions", "/files/{file_id}/versions"),
    ("list_comments", "/files/{file_id}/comments"),
    ("list_collaborations", "/folders/{folder_id}/collaborations"),
]:
    op(m, aid, "GET", path)
op(
    m,
    "search_files",
    "GET",
    "/search",
    "query limit:int? offset:int?",
    query={"query": "query", "limit": "limit", "offset": "offset"},
)
op(m, "create_folder", "POST", "/folders", "name parent_id", transform="box_folder")
op(
    m,
    "upload_file",
    "POST",
    "/files/content",
    "name parent_id content_base64 mime_type?",
    transform="box_upload",
    host="upload.box.com",
)
op(m, "download_file", "GET", "/files/{file_id}/content", transform="binary")
op(
    m,
    "update_file",
    "PUT",
    "/files/{file_id}",
    "name? parent_id? description?",
    transform="box_update",
)
op(
    m,
    "copy_file",
    "POST",
    "/files/{file_id}/copy",
    "parent_id name?",
    transform="box_update",
)
op(
    m,
    "share_file",
    "PUT",
    "/files/{file_id}",
    "shared_link:json",
    body={"shared_link": "shared_link"},
)
op(m, "add_comment", "POST", "/comments", "file_id message", transform="box_comment")
op(
    m,
    "add_collaborator",
    "POST",
    "/collaborations",
    "item:json accessible_by:json role",
    body={k: k for k in ["item", "accessible_by", "role"]},
)
op(m, "delete_file", "DELETE", "/files/{file_id}")
op(
    m,
    "restore_file",
    "POST",
    "/files/{file_id}",
    "name? parent_id?",
    transform="box_update",
)

m = module(
    "google_calendar",
    "Google Calendar",
    "Productivity",
    "www.googleapis.com",
    "/calendar/v3",
    "https://developers.google.com/workspace/calendar/api/v3/reference",
    "event_created event_updated event_deleted event_approaching attendee_response_changed",
    scopes=[G + "calendar.events"],
)
op(
    m,
    "get_event",
    "GET",
    "/calendars/{calendar_id}/events/{event_id}",
    scope=G + "calendar.events.readonly",
)
op(
    m,
    "search_events",
    "GET",
    "/calendars/{calendar_id}/events",
    "q? time_min? time_max? page_token?",
    query={
        "q": "q",
        "timeMin": "time_min",
        "timeMax": "time_max",
        "pageToken": "page_token",
    },
    scope=G + "calendar.events.readonly",
)
op(
    m,
    "insert_event",
    "POST",
    "/calendars/{calendar_id}/events",
    "event:json send_updates?",
    transform="event",
    query={"sendUpdates": "send_updates"},
    scope=G + "calendar.events",
)
op(
    m,
    "update_event",
    "PATCH",
    "/calendars/{calendar_id}/events/{event_id}",
    "event:json send_updates?",
    transform="event",
    query={"sendUpdates": "send_updates"},
    scope=G + "calendar.events",
)
op(
    m,
    "delete_event",
    "DELETE",
    "/calendars/{calendar_id}/events/{event_id}",
    scope=G + "calendar.events",
)
op(
    m,
    "check_availability",
    "POST",
    "/freeBusy",
    "time_min time_max items:list time_zone?",
    body={
        "timeMin": "time_min",
        "timeMax": "time_max",
        "items": "items",
        "timeZone": "time_zone",
    },
    read=True,
    scope=G + "calendar.events.freebusy",
)

m = module(
    "microsoft_calendar",
    "Microsoft Calendar",
    "Productivity",
    "graph.microsoft.com",
    "/v1.0",
    "https://learn.microsoft.com/en-us/graph/api/resources/event",
    "event_created event_updated event_deleted event_approaching attendee_response_changed",
)
for aid, path in [
    ("list_calendars", "/users/{mailbox}/calendars"),
    ("list_events", "/users/{mailbox}/calendars/{calendar_id}/events"),
    ("get_event", "/users/{mailbox}/events/{event_id}"),
]:
    op(m, aid, "GET", path, scope="Calendars.Read")
op(
    m,
    "create_event",
    "POST",
    "/users/{mailbox}/calendars/{calendar_id}/events",
    "event:json",
    transform="event",
    scope="Calendars.ReadWrite",
)
op(
    m,
    "update_event",
    "PATCH",
    "/users/{mailbox}/events/{event_id}",
    "event:json",
    transform="event",
    scope="Calendars.ReadWrite",
)
op(
    m,
    "delete_event",
    "DELETE",
    "/users/{mailbox}/events/{event_id}",
    scope="Calendars.ReadWrite",
)
op(
    m,
    "cancel_event",
    "POST",
    "/users/{mailbox}/events/{event_id}/cancel",
    "comment?",
    body={"comment": "comment"},
    scope="Calendars.ReadWrite",
)
op(
    m,
    "check_availability",
    "POST",
    "/users/{mailbox}/calendar/getSchedule",
    "schedules:list start_time:json end_time:json availability_view_interval:int?",
    body={
        "schedules": "schedules",
        "startTime": "start_time",
        "endTime": "end_time",
        "availabilityViewInterval": "availability_view_interval",
    },
    read=True,
    scope="Calendars.Read",
)
for aid in ["accept", "decline", "tentativelyAccept"]:
    op(
        m,
        aid,
        "POST",
        "/users/{mailbox}/events/{event_id}/" + aid,
        "comment? send_response:bool?",
        body={"comment": "comment", "sendResponse": "send_response"},
        scope="Calendars.ReadWrite",
    )

m = module(
    "google_forms",
    "Google Forms",
    "Productivity",
    "forms.googleapis.com",
    "/v1",
    "https://developers.google.com/workspace/forms/api/reference/rest",
    "response_received form_changed",
    scopes=[G + "forms.body", G + "forms.responses.readonly"],
)
op(
    m,
    "get_response",
    "GET",
    "/forms/{form_id}/responses/{response_id}",
    scope=G + "forms.responses.readonly",
)
op(
    m,
    "update_form",
    "POST",
    "/forms/{form_id}:batchUpdate",
    "requests:list",
    body={"requests": "requests"},
    scope=G + "forms.body",
)
op(
    m,
    "set_publish_settings",
    "POST",
    "/forms/{form_id}:setPublishSettings",
    "publish_settings:json",
    body={"publishSettings": "publish_settings"},
    scope=G + "forms.body",
)

m = module(
    "notion",
    "Notion",
    "Productivity",
    "api.notion.com",
    "/v1",
    "https://developers.notion.com/reference/intro",
    "page_created page_updated entry_created entry_updated condition_matched",
    headers={"Notion-Version": "2025-09-03"},
)
op(
    m,
    "search",
    "POST",
    "/search",
    "query? filter:json? start_cursor? page_size:int?",
    body={k: k for k in ["query", "filter", "start_cursor", "page_size"]},
    read=True,
)
for aid, path in [
    ("read_page", "/pages/{page_id}"),
    ("read_blocks", "/blocks/{block_id}/children"),
    ("get_data_source", "/data_sources/{data_source_id}"),
]:
    op(m, aid, "GET", path)
op(
    m,
    "query_data_source",
    "POST",
    "/data_sources/{data_source_id}/query",
    "filter:json? sorts:list? start_cursor? page_size:int?",
    body={k: k for k in ["filter", "sorts", "start_cursor", "page_size"]},
    read=True,
)
op(
    m,
    "create_entry",
    "POST",
    "/pages",
    "parent:json properties:json children:list?",
    body={k: k for k in ["parent", "properties", "children"]},
)
op(
    m,
    "update_page",
    "PATCH",
    "/pages/{page_id}",
    "properties:json? archived:bool?",
    body={"properties": "properties", "archived": "archived"},
)
op(
    m,
    "append_blocks",
    "PATCH",
    "/blocks/{block_id}/children",
    "children:list",
    body={"children": "children"},
)

m = module(
    "airtable",
    "Airtable",
    "Productivity",
    "api.airtable.com",
    "/v0",
    "https://airtable.com/developers/web/api/introduction",
    "record_created record_updated record_deleted field_changed condition_matched",
)
op(m, "list_bases", "GET", "/meta/bases")
op(m, "get_schema", "GET", "/meta/bases/{base_id}/tables")
op(
    m,
    "find_records",
    "GET",
    "/{base_id}/{table_id}",
    "view? filter_by_formula? offset? page_size:int?",
    query={
        "view": "view",
        "filterByFormula": "filter_by_formula",
        "offset": "offset",
        "pageSize": "page_size",
    },
)
op(m, "get_record", "GET", "/{base_id}/{table_id}/{record_id}")
op(
    m,
    "create_records",
    "POST",
    "/{base_id}/{table_id}",
    "records:list typecast:bool?",
    body={"records": "records", "typecast": "typecast"},
)
op(
    m,
    "update_record",
    "PATCH",
    "/{base_id}/{table_id}/{record_id}",
    "fields:json typecast:bool?",
    body={"fields": "fields", "typecast": "typecast"},
)
op(
    m,
    "upsert_records",
    "PATCH",
    "/{base_id}/{table_id}",
    "records:list perform_upsert:json typecast:bool?",
    body={
        "records": "records",
        "performUpsert": "perform_upsert",
        "typecast": "typecast",
    },
)
op(m, "delete_record", "DELETE", "/{base_id}/{table_id}/{record_id}")

m = module(
    "hubspot",
    "HubSpot",
    "CRM",
    "api.hubapi.com",
    "",
    "https://developers.hubspot.com/docs/api/overview",
    "record_created record_updated deal_stage_changed ticket_changed",
)
op(
    m,
    "list_records",
    "GET",
    "/crm/v3/objects/{object_type}",
    "limit:int? after? properties?",
    query={"limit": "limit", "after": "after", "properties": "properties"},
)
op(
    m,
    "get_record",
    "GET",
    "/crm/v3/objects/{object_type}/{record_id}",
    "properties?",
    query={"properties": "properties"},
)
op(
    m,
    "search_records",
    "POST",
    "/crm/v3/objects/{object_type}/search",
    "filter_groups:list? properties:list? query? limit:int? after:int?",
    body={
        "filterGroups": "filter_groups",
        "properties": "properties",
        "query": "query",
        "limit": "limit",
        "after": "after",
    },
    read=True,
)
op(
    m,
    "create_record",
    "POST",
    "/crm/v3/objects/{object_type}",
    "properties:json associations:list?",
    body={"properties": "properties", "associations": "associations"},
)
op(
    m,
    "update_record",
    "PATCH",
    "/crm/v3/objects/{object_type}/{record_id}",
    "properties:json",
    body={"properties": "properties"},
)
op(m, "list_pipelines", "GET", "/crm/v3/pipelines/{object_type}")
op(
    m,
    "associate_records",
    "PUT",
    "/crm/v4/objects/{object_type}/{record_id}/associations/default/{to_object_type}/{to_record_id}",
)

m = module(
    "salesforce",
    "Salesforce",
    "CRM",
    None,
    "/services/data/{api_version}",
    "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/",
    "record_created record_updated record_deleted field_changed platform_event",
)
op(m, "query_records", "GET", "/query", "q", query={"q": "q"})
op(m, "describe_object", "GET", "/sobjects/{object_type}/describe")
op(m, "get_record", "GET", "/sobjects/{object_type}/{record_id}")
op(
    m,
    "create_record",
    "POST",
    "/sobjects/{object_type}",
    "fields:json",
    transform="fields",
)
op(
    m,
    "update_record",
    "PATCH",
    "/sobjects/{object_type}/{record_id}",
    "fields:json",
    transform="fields",
)
op(
    m,
    "upsert_record",
    "PATCH",
    "/sobjects/{object_type}/{external_id_field}/{external_id}",
    "fields:json",
    transform="fields",
)
op(m, "delete_record", "DELETE", "/sobjects/{object_type}/{record_id}")
op(
    m,
    "create_bulk_job",
    "POST",
    "/jobs/ingest",
    "object operation external_id_field_name?",
    body={
        "object": "object",
        "operation": "operation",
        "externalIdFieldName": "external_id_field_name",
    },
)

m = module(
    "zoho_crm",
    "Zoho CRM",
    "CRM",
    None,
    "/crm/v8",
    "https://www.zoho.com/crm/developer/docs/api/v8/",
    "record_created record_updated stage_changed owner_changed",
)
op(
    m,
    "get_records",
    "GET",
    "/{module}",
    "fields? page:int? per_page:int?",
    query={"fields": "fields", "page": "page", "per_page": "per_page"},
)
op(
    m,
    "search_records",
    "GET",
    "/{module}/search",
    "criteria? email? phone?",
    query={"criteria": "criteria", "email": "email", "phone": "phone"},
)
op(m, "get_record", "GET", "/{module}/{record_id}")
for aid, method, path in [
    ("create_records", "POST", "/{module}"),
    ("update_records", "PUT", "/{module}"),
    ("upsert_records", "POST", "/{module}/upsert"),
]:
    op(
        m,
        aid,
        method,
        path,
        "data:list trigger:list? duplicate_check_fields:list?",
        body={k: k for k in ["data", "trigger", "duplicate_check_fields"]},
    )
op(m, "get_related_records", "GET", "/{module}/{record_id}/{related_list}")
op(m, "get_modules", "GET", "/settings/modules")
op(m, "get_fields", "GET", "/settings/fields", "module", query={"module": "module"})

m = module(
    "jira",
    "Jira",
    "Project Management",
    None,
    "/rest/api/3",
    "https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/",
    "issue_created issue_updated status_changed comment_added assignment_changed",
)
op(
    m,
    "search_issues",
    "GET",
    "/search/jql",
    "jql? next_page_token? max_results:int?",
    query={
        "jql": "jql",
        "nextPageToken": "next_page_token",
        "maxResults": "max_results",
    },
)
for aid, path in [
    ("get_issue", "/issue/{issue_id}"),
    ("list_comments", "/issue/{issue_id}/comment"),
    ("list_transitions", "/issue/{issue_id}/transitions"),
    ("list_worklogs", "/issue/{issue_id}/worklog"),
    ("list_projects", "/project/search"),
]:
    op(m, aid, "GET", path)
op(m, "create_issue", "POST", "/issue", "fields:json", body={"fields": "fields"})
op(
    m,
    "update_issue",
    "PUT",
    "/issue/{issue_id}",
    "fields:json? update:json?",
    body={"fields": "fields", "update": "update"},
)
op(
    m,
    "transition_issue",
    "POST",
    "/issue/{issue_id}/transitions",
    "transition_id fields:json?",
    transform="jira_transition",
)
op(
    m,
    "assign_issue",
    "PUT",
    "/issue/{issue_id}/assignee",
    "account_id",
    body={"accountId": "account_id"},
)
op(
    m,
    "add_comment",
    "POST",
    "/issue/{issue_id}/comment",
    "body:json",
    body={"body": "body"},
)
op(
    m,
    "log_work",
    "POST",
    "/issue/{issue_id}/worklog",
    "time_spent_seconds:int started",
    body={"timeSpentSeconds": "time_spent_seconds", "started": "started"},
)

m = module(
    "clickup",
    "ClickUp",
    "Project Management",
    "api.clickup.com",
    "/api/v2",
    "https://developer.clickup.com/reference",
    "task_created task_updated task_deleted status_changed assignee_changed comment_added",
)
for aid, path in [
    ("get_workspaces", "/team"),
    ("get_spaces", "/team/{team_id}/space"),
    ("get_lists", "/folder/{folder_id}/list"),
    ("get_tasks", "/list/{list_id}/task"),
    ("get_task", "/task/{task_id}"),
    ("get_comments", "/task/{task_id}/comment"),
    ("get_custom_fields", "/list/{list_id}/field"),
]:
    op(m, aid, "GET", path)
op(
    m,
    "create_task",
    "POST",
    "/list/{list_id}/task",
    "name description? assignees:list? status? parent? custom_fields:list?",
    body={
        k: k
        for k in [
            "name",
            "description",
            "assignees",
            "status",
            "parent",
            "custom_fields",
        ]
    },
)
op(
    m,
    "update_task",
    "PUT",
    "/task/{task_id}",
    "name? description? status? assignees:json?",
    body={k: k for k in ["name", "description", "status", "assignees"]},
)
op(
    m,
    "add_comment",
    "POST",
    "/task/{task_id}/comment",
    "comment_text assignee:int?",
    body={"comment_text": "comment_text", "assignee": "assignee"},
)
op(
    m,
    "set_custom_field",
    "POST",
    "/task/{task_id}/field/{field_id}",
    "value:any",
    body={"value": "value"},
)
op(
    m,
    "create_time_entry",
    "POST",
    "/team/{team_id}/time_entries",
    "start:int duration:int tid? description?",
    body={k: k for k in ["start", "duration", "tid", "description"]},
)
op(m, "delete_task", "DELETE", "/task/{task_id}")

m = module(
    "slack",
    "Slack",
    "Communication",
    "slack.com",
    "/api",
    "https://docs.slack.dev/reference/methods/",
    "message_received mention_received reaction_added channel_event file_shared",
)
for aid, path, fields in [
    ("read_history", "conversations.history", "channel cursor? limit:int? oldest?"),
    ("read_replies", "conversations.replies", "channel ts cursor? limit:int?"),
    ("list_channels", "conversations.list", "cursor? types? limit:int?"),
    ("list_users", "users.list", "cursor? limit:int?"),
    ("get_file", "files.info", "file"),
]:
    op(
        m,
        aid,
        "GET",
        "/" + path,
        fields,
        query={
            x.split(":")[0].rstrip("?"): x.split(":")[0].rstrip("?")
            for x in fields.split()
        },
    )
for aid, path, fields in [
    ("post_message", "chat.postMessage", "channel text thread_ts? blocks:list?"),
    ("update_message", "chat.update", "channel ts text blocks:list?"),
    ("delete_message", "chat.delete", "channel ts"),
    ("add_reaction", "reactions.add", "channel timestamp name"),
    ("create_channel", "conversations.create", "name is_private:bool?"),
    ("invite_users", "conversations.invite", "channel users"),
    ("open_direct_message", "conversations.open", "users"),
]:
    op(
        m,
        aid,
        "POST",
        "/" + path,
        fields,
        body={
            x.split(":")[0].rstrip("?"): x.split(":")[0].rstrip("?")
            for x in fields.split()
        },
    )

m = module(
    "microsoft_teams",
    "Microsoft Teams",
    "Communication",
    "graph.microsoft.com",
    "/v1.0",
    "https://learn.microsoft.com/en-us/graph/api/resources/teams-api-overview",
    "channel_message_received chat_message_received mention_received message_updated",
)
for aid, path, scope in [
    ("list_teams", "/me/joinedTeams", "Team.ReadBasic.All"),
    ("list_channels", "/teams/{team_id}/channels", "Channel.ReadBasic.All"),
    (
        "read_messages",
        "/teams/{team_id}/channels/{channel_id}/messages",
        "ChannelMessage.Read.All",
    ),
    (
        "read_replies",
        "/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies",
        "ChannelMessage.Read.All",
    ),
    ("read_chat", "/chats/{chat_id}/messages", "Chat.Read"),
    ("list_members", "/teams/{team_id}/members", "TeamMember.Read.All"),
]:
    op(m, aid, "GET", path, scope=scope)
for aid, path, scope in [
    (
        "post_message",
        "/teams/{team_id}/channels/{channel_id}/messages",
        "ChannelMessage.Send",
    ),
    (
        "reply_message",
        "/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies",
        "ChannelMessage.Send",
    ),
    ("send_chat", "/chats/{chat_id}/messages", "ChatMessage.Send"),
]:
    op(
        m,
        aid,
        "POST",
        path,
        "body:json attachments:list?",
        body={"body": "body", "attachments": "attachments"},
        scope=scope,
    )
op(
    m,
    "create_channel",
    "POST",
    "/teams/{team_id}/channels",
    "display_name description? membership_type?",
    body={
        "displayName": "display_name",
        "description": "description",
        "membershipType": "membership_type",
    },
    scope="Channel.Create",
)
op(
    m,
    "add_member",
    "POST",
    "/teams/{team_id}/members",
    "member:json",
    transform="member",
    scope="TeamMember.ReadWrite.All",
)

m = module(
    "github",
    "GitHub",
    "Developer Tools",
    "api.github.com",
    "",
    "https://docs.github.com/en/rest",
    "push issue_opened issue_updated pull_request_opened pull_request_updated comment_added release_created workflow_completed",
)
for aid, path in [
    ("get_issue", "/repos/{owner}/{repository}/issues/{issue_number}"),
    ("list_comments", "/repos/{owner}/{repository}/issues/{issue_number}/comments"),
    ("list_pull_requests", "/repos/{owner}/{repository}/pulls"),
    ("get_pull_request", "/repos/{owner}/{repository}/pulls/{pull_number}"),
    ("read_file", "/repos/{owner}/{repository}/contents/{file_path}"),
    ("list_commits", "/repos/{owner}/{repository}/commits"),
    ("list_workflow_runs", "/repos/{owner}/{repository}/actions/runs"),
]:
    op(m, aid, "GET", path)
op(
    m,
    "update_issue",
    "PATCH",
    "/repos/{owner}/{repository}/issues/{issue_number}",
    "title? body? state? labels:list? assignees:list?",
    body={k: k for k in ["title", "body", "state", "labels", "assignees"]},
)
op(
    m,
    "add_comment",
    "POST",
    "/repos/{owner}/{repository}/issues/{issue_number}/comments",
    "body",
    body={"body": "body"},
)
op(
    m,
    "create_pull_request",
    "POST",
    "/repos/{owner}/{repository}/pulls",
    "title head base body? draft:bool?",
    body={k: k for k in ["title", "head", "base", "body", "draft"]},
)
op(
    m,
    "dispatch_workflow",
    "POST",
    "/repos/{owner}/{repository}/actions/workflows/{workflow_id}/dispatches",
    "ref inputs:json?",
    body={"ref": "ref", "inputs": "inputs"},
)
op(
    m,
    "write_file",
    "PUT",
    "/repos/{owner}/{repository}/contents/{file_path}",
    "message content branch? sha?",
    body={k: k for k in ["message", "content", "branch", "sha"]},
)

# Supplemental operations keep provider-specific setup in the published schema.
op(
    "google_drive",
    "update_content",
    "PATCH",
    "/upload/drive/v3/files/{file_id}",
    "content_base64 mime_type?",
    transform="drive_update",
    scope=G + "drive.file",
)
op(
    "google_calendar",
    "list_calendars",
    "GET",
    "/users/me/calendarList",
    scope=G + "calendar.calendarlist.readonly",
)
op("gmail", "delete_draft", "DELETE", "/drafts/{draft_id}", scope=G + "gmail.compose")
op("gmail", "get_draft", "GET", "/drafts/{draft_id}", scope=G + "gmail.readonly")
op(
    "outlook",
    "send_draft",
    "POST",
    "/users/{mailbox}/messages/{message_id}/send",
    scope="Mail.Send",
)
op(
    "microsoft_teams",
    "create_meeting",
    "POST",
    "/me/onlineMeetings",
    "subject start_date_time end_date_time participants:json?",
    body={
        "subject": "subject",
        "startDateTime": "start_date_time",
        "endDateTime": "end_date_time",
        "participants": "participants",
    },
    scope="OnlineMeetings.ReadWrite",
)
op(
    "slack",
    "upload_file",
    "POST",
    "/files.getUploadURLExternal",
    "filename content_base64 channel_id? initial_comment? thread_ts?",
    transform="slack_upload",
)
op(
    "jira",
    "add_attachment",
    "POST",
    "/issue/{issue_id}/attachments",
    "filename content_base64 mime_type?",
    transform="jira_attachment",
)
op(
    "zoho_crm",
    "add_attachment",
    "POST",
    "/{module}/{record_id}/Attachments",
    "filename content_base64 mime_type?",
    transform="zoho_attachment",
)
op(
    "zoho_crm",
    "add_note",
    "POST",
    "/{module}/{record_id}/Notes",
    "title content",
    transform="zoho_note",
)
op("zoho_crm", "create_task", "POST", "/Tasks", "fields:json", transform="zoho_record")
op(
    "zoho_crm",
    "assign_owner",
    "PUT",
    "/{module}/{record_id}",
    "owner_id",
    transform="zoho_owner",
)
op(
    "hubspot",
    "create_task",
    "POST",
    "/crm/v3/objects/tasks",
    "properties:json associations:list?",
    body={"properties": "properties", "associations": "associations"},
)
op(
    "hubspot",
    "create_note",
    "POST",
    "/crm/v3/objects/notes",
    "properties:json associations:list?",
    body={"properties": "properties", "associations": "associations"},
)
op(
    "hubspot",
    "list_associations",
    "GET",
    "/crm/v4/objects/{object_type}/{record_id}/associations/{to_object_type}",
)
op(
    "salesforce",
    "create_query_job",
    "POST",
    "/jobs/query",
    "query operation?",
    transform="salesforce_query_job",
)
op("salesforce", "get_job", "GET", "/jobs/{job_type}/{job_id}")
op(
    "salesforce",
    "get_query_results",
    "GET",
    "/jobs/query/{job_id}/results",
    transform="binary",
)
op(
    "salesforce",
    "upload_job_data",
    "PUT",
    "/jobs/ingest/{job_id}/batches",
    "content_base64 mime_type?",
    transform="upload",
)
op(
    "salesforce",
    "close_job",
    "PATCH",
    "/jobs/ingest/{job_id}",
    transform="salesforce_close_job",
)
op("clickup", "get_folders", "GET", "/space/{space_id}/folder")
op(
    "clickup",
    "get_time_entries",
    "GET",
    "/team/{team_id}/time_entries",
    "start_date? end_date?",
    query={"start_date": "start_date", "end_date": "end_date"},
)
op("github", "list_releases", "GET", "/repos/{owner}/{repository}/releases")
op(
    "github",
    "list_labels",
    "GET",
    "/repos/{owner}/{repository}/issues/{issue_number}/labels",
)
op(
    "github",
    "add_labels",
    "POST",
    "/repos/{owner}/{repository}/issues/{issue_number}/labels",
    "labels:list",
    body={"labels": "labels"},
)
op(
    "github",
    "remove_label",
    "DELETE",
    "/repos/{owner}/{repository}/issues/{issue_number}/labels/{name}",
)
op(
    "onedrive",
    "create_upload_session",
    "POST",
    "/drives/{drive_id}/items/{parent_id}:/{name}:/createUploadSession",
    "item:json?",
    body={"item": "item"},
    scope="Files.ReadWrite",
)
op(
    "sharepoint",
    "create_upload_session",
    "POST",
    "/drives/{drive_id}/items/{parent_id}:/{name}:/createUploadSession",
    "item:json?",
    body={"item": "item"},
    scope="Files.ReadWrite",
)
op(
    "box",
    "promote_version",
    "POST",
    "/files/{file_id}/versions/current",
    "version_id",
    transform="box_version",
)
op(
    "airtable",
    "delete_records",
    "DELETE",
    "/{base_id}/{table_id}",
    "records:list",
    query={"records[]": "records"},
)
op("notion", "archive_page", "PATCH", "/pages/{page_id}", transform="notion_archive")

for _mid, _path, _scope in [
    ("google_sheets", "/{spreadsheet_id}/values/{range}", G + "spreadsheets"),
    ("excel_online", "/tables/{table_id}/rows", "Files.ReadWrite"),
]:
    op(
        _mid,
        "find_rows",
        "GET",
        _path,
        "key_column key_value:any",
        transform="spreadsheet_find",
        scope=G + "spreadsheets.readonly" if _mid == "google_sheets" else _scope,
    )
    op(
        _mid,
        "upsert_row",
        "GET",
        _path,
        "key_column key_value:any record:json",
        transform="spreadsheet_upsert",
        scope=_scope,
    )
    OPERATIONS[_mid, "upsert_row"]["mutates"] = True

# HTTP's existing executor already supports auth, multipart, pagination and signed ingress.
module(
    "http",
    "HTTP API",
    "Webhooks and APIs",
    None,
    "",
    "https://developer.mozilla.org/en-US/docs/Web/HTTP",
    "webhook_received response_condition_matched",
)


def install(registry, inputs, action):
    from app.apps.power_apps.integrations.contracts import Manifest

    for id, info in MODULES.items():
        if id not in registry:
            registry[id] = Manifest(
                id=id,
                name=info["name"],
                category=info["category"],
                description=f"{info['name']} workflow triggers, reads and actions.",
                authentication=["basic", "bearer"] if id == "jira" else ["bearer"],
                documentation_url=info["docs"],
                setup=[
                    "Connect an authorized account in the encrypted vault.",
                    "Choose the operation and map its setup fields.",
                ],
            )
        manifest = registry[id]
        for (mid, aid), spec in list(OPERATIONS.items()):
            if mid != id:
                continue
            # Preserve published legacy contracts and handlers.
            if any(a.id == aid for a in manifest.actions):
                # Published legacy workflows keep their original schema. Expose the
                # expanded operation separately rather than silently changing it.
                advanced_id = aid + "_advanced"
                OPERATIONS[mid, advanced_id] = spec
                MODELS[mid, advanced_id] = MODELS[mid, aid]
                aid = advanced_id
            model = MODELS[mid, aid]
            manifest.actions.append(
                action(
                    aid,
                    aid.replace("_", " ").capitalize(),
                    model,
                    spec["mutates"],
                    [spec["scope"]] if spec["scope"] else [],
                )
            )
            inputs[mid, aid] = model
            INSTALLED.add((mid, aid))
        if (
            info["host"] == "graph.microsoft.com"
            and "oauth2" not in manifest.authentication
        ):
            manifest.authentication.insert(0, "oauth2")
        from app.apps.power_apps.integrations.native_specs import mode, SECRET_FIELDS
        for event in info["events"]:
            manifest.triggers.append(
                dict(
                    id=event,
                    name=event.replace("_", " ").capitalize(),
                    delivery=mode(id, {"event":event}),
                    provider_secret_fields=SECRET_FIELDS.get(id, {}),
                    setup_schema=trigger_schema(id),
                    description=(
                        "Worker polls the selected resource."
                        if id in {"telegram", "google_sheets", "excel_online"}
                        else "Power Apps manages native provider subscriptions and change cursors automatically."
                    ),
                )
            )


def trigger_schema(id):
    properties = {
        "connection_id": {"type": "integer", "minimum": 1},
        "event": {"type": "string", "enum": MODULES[id]["events"]},
    }
    required = ["connection_id", "event"]
    if id in {"google_sheets", "excel_online"}:
        properties.update(
            key_column={"type": "string", "title": "Unique row key column"},
            watched_columns={"type": "array", "items": {"type": "string"}},
            condition={
                "type": "object",
                "description": "Column/value equality conditions",
            },
            interval_seconds={
                "type": "integer",
                "minimum": 15,
                "maximum": 3600,
                "default": 30,
            },
            emit_initial={"type": "boolean", "default": False},
        )
        for key in (
            ["spreadsheet_id", "range"]
            if id == "google_sheets"
            else ["drive_id", "workbook_id", "table_id"]
        ):
            properties[key] = {"type": "string"}
            required.append(key)
        required.append("key_column")
    elif id == "telegram":
        properties.update(
            chat_id={"type": "string"},
            interval_seconds={
                "type": "integer",
                "minimum": 5,
                "maximum": 3600,
                "default": 5,
            },
        )
    else:
        properties.update(
            filters={"type": "object"},
            max_per_minute={
                "type": "integer",
                "minimum": 1,
                "maximum": 120,
                "default": 30,
            },
        )
    for token in EVENT_RESOURCE_FIELDS.get(id, "").split():
        key, _, kind = token.partition(":")
        field = {
            "type": {"bool": "boolean", "int": "integer", "list": "array"}.get(
                kind, "string"
            )
        }
        if kind == "list":
            field["items"] = {"type": "string"}
        if kind == "int":
            field.update(minimum=0, maximum=10080)
        properties[key] = field
    from app.apps.power_apps.integrations.native_specs import augment_schema
    return augment_schema(id, {"type":"object", "properties":properties, "required":required, "additionalProperties":False})


def execute(conn, action_id, parsed, transport, headers, secrets, operation_key):
    from app.apps.power_apps.integrations.adapters import decode, status_error

    info = MODULES[conn.connector_id]
    spec = OPERATIONS[conn.connector_id, action_id]
    data = parsed.model_dump(exclude_none=True)
    if spec["transform"] in {"spreadsheet_find", "spreadsheet_upsert"}:
        return _spreadsheet_action(
            conn, spec, data, transport, headers, secrets, operation_key
        )
    host = spec["host"] or info["host"] or conn.config.get("provider_host", "")
    if not host or not re.fullmatch(r"[A-Za-z0-9.-]+", host):
        raise IntegrationFailure(
            "configuration", "Configure the approved provider hostname"
        )
    route = info["base"] + spec["path"]
    if spec["path"].startswith("/upload/") or spec["transform"] == "telegram_download":
        route = spec["path"]
    for key in re.findall(r"\{(\w+)\}", route):
        value = (
            secrets.get("access_token", "")
            if key == "bot_token"
            else data.get(key, conn.config.get(key, ""))
        )
        if (
            value is None
            or str(value) in {"", ".", ".."}
            or any(c in str(value) for c in "\r\n")
        ):
            raise IntegrationFailure(
                "schema", f"Missing or unsafe resource identifier: {key}"
            )
        if key == "file_path" and any(
            s in {"", ".", ".."} or "\\" in s for s in str(value).split("/")
        ):
            raise IntegrationFailure(
                "schema", "File path must contain safe relative segments"
            )
        # Multi-segment paths are encoded segment by segment, never interpreted as URLs.
        route = route.replace(
            "{" + key + "}",
            (
                "/".join(quote(s, safe="") for s in str(value).split("/"))
                if key == "file_path"
                else quote(str(value), safe="")
            ),
        )
    if host == 'graph.microsoft.com':
        if data.get('mailbox') == 'me':
            route = route.replace('/users/me/', '/me/', 1)
        if conn.connector_id == 'microsoft_calendar' and data.get('calendar_id') == 'primary':
            route = route.replace('/calendars/primary/', '/calendar/', 1)
    query = {
        remote: data[local] for remote, local in spec["query"].items() if local in data
    }
    if conn.connector_id == "google_drive" and spec["id"] in {
        "search_files",
        "create_folder",
        "upload_file",
        "download_file",
        "update_metadata",
        "move_file",
        "copy_file",
        "share_file",
        "list_permissions",
        "update_content",
    }:
        query["supportsAllDrives"] = "true"
        if spec["id"] == "search_files":
            query["includeItemsFromAllDrives"] = "true"
    if conn.connector_id == "google_sheets" and action_id in {
        "update_values",
        "append_values",
    }:
        query.setdefault("valueInputOption", "RAW")
    if query:
        route += ("&" if "?" in route else "?") + urlencode(query, doseq=True)
    headers = {**headers, **info["headers"], "Accept": "application/json"}
    if conn.connector_id == "dropbox":
        if conn.config.get("team_member_id"):
            headers["Dropbox-API-Select-User"] = conn.config["team_member_id"]
        if conn.config.get("namespace_id"):
            headers["Dropbox-API-Path-Root"] = json.dumps(
                {".tag": "namespace_id", "namespace_id": conn.config["namespace_id"]}
            )
    if conn.connector_id == "telegram":
        headers.pop("Authorization", None)
    if conn.connector_id == "clickup" and "Authorization" in headers:
        headers["Authorization"] = headers["Authorization"].removeprefix("Bearer ")
    if conn.connector_id == "zoho_crm":
        headers["Authorization"] = "Zoho-oauthtoken " + secrets["access_token"]
    body = {
        remote: data[local] for remote, local in spec["body"].items() if local in data
    }
    t = spec["transform"]
    binary = t in {"binary", "drive_download", "telegram_download", "dropbox_download"}
    if t in {"fields", "message", "event", "member"}:
        body = data[t]
    elif isinstance(t, tuple) and t[0] == "gmail_labels":
        body = {"addLabelIds": t[1], "removeLabelIds": t[2]}
    elif t == "gmail":
        from email.message import EmailMessage

        message = EmailMessage()
        for key, header in [
            ("to", "To"),
            ("subject", "Subject"),
            ("cc", "Cc"),
            ("bcc", "Bcc"),
            ("reply_to", "Reply-To"),
            ("in_reply_to", "In-Reply-To"),
            ("references", "References"),
        ]:
            if data.get(key):
                message[header] = data[key]
        message.set_content(data["text"])
        if data.get("html"):
            message.add_alternative(data["html"], subtype="html")
        for attachment in data.get("attachments", []):
            main, sub = attachment.get("mime_type", "application/octet-stream").split(
                "/", 1
            )
            message.add_attachment(
                _bytes(attachment["content_base64"]),
                maintype=main,
                subtype=sub,
                filename=attachment["name"],
            )
        body = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
        if data.get("thread_id"):
            body["threadId"] = data["thread_id"]
        if spec["id"] == "create_draft":
            body = {"message": body}
    elif t == "drive_folder":
        body = {
            "name": data["name"],
            "mimeType": "application/vnd.google-apps.folder",
            **({"parents": [data["parent_id"]]} if data.get("parent_id") else {}),
        }
    elif t == "graph_folder":
        body = {
            "name": data["name"],
            "folder": {},
            "@microsoft.graph.conflictBehavior": data.get("conflict_behavior", "fail"),
        }
    elif t in {"box_folder", "box_update"}:
        body = {k: data[k] for k in ["name", "description"] if k in data}
        body.update(
            {"parent": {"id": data["parent_id"]}} if data.get("parent_id") else {}
        )
    elif t == "box_comment":
        body = {
            "item": {"type": "file", "id": data["file_id"]},
            "message": data["message"],
        }
    elif t == "sheet_create":
        body = {"properties": {"title": data["title"]}}
    elif t == "sheet_tab":
        body = {"requests": [{"addSheet": {"properties": {"title": data["title"]}}}]}
    elif t == "sheet_delete":
        if not 0 <= data["start_index"] < data["end_index"]:
            raise IntegrationFailure(
                "schema", "Row indexes must be an increasing zero-based interval"
            )
        body = {
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": data["sheet_id"],
                            "dimension": "ROWS",
                            "startIndex": data["start_index"],
                            "endIndex": data["end_index"],
                        }
                    }
                }
            ]
        }
    elif t == "sheet_format":
        body = {
            "requests": [
                {
                    "repeatCell": {
                        "range": data["grid_range"],
                        "cell": {"userEnteredFormat": data["format"]},
                        "fields": data["fields"],
                    }
                }
            ]
        }
    elif t == "jira_transition":
        body = {
            "transition": {"id": data["transition_id"]},
            **({"fields": data["fields"]} if "fields" in data else {}),
        }
    elif t == "whatsapp":
        body = {
            k: v for k, v in data.items() if k not in {"api_version", "phone_number_id"}
        }
        body["messaging_product"] = "whatsapp"
    elif t == "whatsapp_read":
        body = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": data["message_id"],
        }
    elif t == "zoho_note":
        body = {
            "data": [{"Note_Title": data["title"], "Note_Content": data["content"]}]
        }
    elif t == "zoho_record":
        body = {"data": [data["fields"]]}
    elif t == "zoho_owner":
        body = {"data": [{"Owner": {"id": data["owner_id"]}}]}
    elif t == "salesforce_query_job":
        body = {"operation": data.get("operation", "query"), "query": data["query"]}
    elif t == "salesforce_close_job":
        body = {"state": "UploadComplete"}
    elif t == "box_version":
        body = {"type": "file_version", "id": data["version_id"]}
    elif t == "notion_archive":
        body = {"archived": True}
    elif t == "drive_download":
        route += ("&" if "?" in route else "?") + "alt=media"
    content = None
    if t in {"upload", "dropbox_upload", "drive_update"}:
        content = _bytes(data["content_base64"])
        headers["Content-Type"] = data.get("mime_type", "application/octet-stream")
        if t == "drive_update":
            route += ("&" if "?" in route else "?") + "uploadType=media"
    elif t in {"jira_attachment", "zoho_attachment"}:
        filename = data["filename"]
        if any(c in filename for c in '\r\n"\\'):
            raise IntegrationFailure("schema", "Unsafe attachment filename")
        boundary = "power-" + operation_key[:32]
        content = (
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'
            ).encode()
            + _bytes(data["content_base64"])
            + f"\r\n--{boundary}--\r\n".encode()
        )
        headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
        if t == "jira_attachment":
            headers["X-Atlassian-Token"] = "no-check"
    elif t == "slack_upload":
        return _slack_upload(data, transport, headers, operation_key)
    elif t in {"drive_upload", "box_upload"}:
        metadata = {
            "name": data["name"],
            **({"parents": [data["parent_id"]]} if data.get("parent_id") else {}),
        }
        if t == "box_upload":
            metadata = {"name": data["name"], "parent": {"id": data["parent_id"]}}
        if t == "box_upload":
            # Box requires form-data with attributes and file parts.
            boundary = "power-" + operation_key[:32]
            content = (
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="attributes"\r\nContent-Type: application/json\r\n\r\n'
                    + json.dumps(metadata)
                    + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="upload"\r\nContent-Type: application/octet-stream\r\n\r\n'
                ).encode()
                + _bytes(data["content_base64"])
                + f"\r\n--{boundary}--\r\n".encode()
            )
            headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
        else:
            boundary = "power-" + operation_key[:32]
            mime = data["mime_type"]
            if "\r" in mime or "\n" in mime:
                raise IntegrationFailure("schema", "Invalid MIME type")
            content = (
                (
                    f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                    + json.dumps(metadata)
                    + f"\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n"
                ).encode()
                + _bytes(data["content_base64"])
                + f"\r\n--{boundary}--\r\n".encode()
            )
            headers["Content-Type"] = "multipart/related; boundary=" + boundary
            route += ("&" if "?" in route else "?") + "uploadType=multipart"
    if t in {"dropbox_upload", "dropbox_download"}:
        headers["Dropbox-API-Arg"] = json.dumps(
            {k: data[k] for k in ["path", "mode", "autorename"] if k in data}
        )
        if t == "dropbox_download":
            content = b""
    if content is None and spec["method"] not in {"GET", "HEAD"}:
        content = json.dumps(body, allow_nan=False).encode()
        headers["Content-Type"] = "application/json"
    started = time.monotonic()
    response = transport.request(
        spec["method"],
        "https://" + host + route,
        headers=headers,
        body=content,
        timeout=15,
        **({"return_redirect": True} if binary and spec["method"] == "GET" else {}),
    )
    if binary and response.status in {301, 302, 303, 307, 308}:
        from app.apps.power_apps.integrations.transport import (
            HttpTransport,
            EgressPolicy,
        )

        suffixes = {
            "onedrive": (".sharepoint.com", ".1drv.com"),
            "sharepoint": (".sharepoint.com",),
            "box": (".boxcloud.com",),
            "google_drive": (".googleusercontent.com",),
        }.get(conn.connector_id, ())
        previous = "https://" + host + route
        for _ in range(3):
            destination = urljoin(previous, response.headers.get("location", ""))
            target = urlsplit(destination)
            if (
                target.scheme != "https"
                or target.username
                or target.password
                or not target.hostname
                or not any(target.hostname.endswith(s) for s in suffixes)
            ):
                raise IntegrationFailure(
                    "redirect_denied",
                    "Download redirect is outside the provider's approved content hosts",
                )
            remaining = 15 - (time.monotonic() - started)
            if remaining <= 0:
                raise IntegrationFailure("timeout", "Download timed out")
            # Never forward the API bearer token or custom headers to content hosts.
            response = HttpTransport(EgressPolicy([target.hostname])).request(
                "GET",
                destination,
                headers={"Accept": "*/*"},
                timeout=remaining,
                return_redirect=True,
            )
            if response.status not in {301, 302, 303, 307, 308}:
                break
            previous = destination
    status_error(response, spec["mutates"])
    result = (
        {
            "content_base64": base64.b64encode(response.body).decode(),
            "mime_type": response.headers.get(
                "content-type", "application/octet-stream"
            ),
        }
        if binary
        else decode(response, list(secrets.values()))
    )
    if isinstance(result, dict) and result.get("ok") is False:
        raise IntegrationFailure(
            "remote", "Provider rejected the operation", uncertain=spec["mutates"]
        )
    return {
        "data": result,
        "http_status": response.status,
        "delivery": "accepted" if spec["mutates"] else "read",
    }


def _spreadsheet_action(conn, spec, data, transport, headers, secrets, operation_key):
    if (
        not isinstance(data.get("key_value"), (str, int, float, bool))
        or data.get("key_value") == ""
    ):
        raise IntegrationFailure("schema", "A row lookup key must be a nonempty scalar")

    def call(aid, value):
        model = MODELS[conn.connector_id, aid]
        return execute(
            conn,
            aid,
            model.model_validate(value),
            transport,
            headers,
            secrets,
            operation_key,
        )

    if conn.connector_id == "google_sheets":
        identifiers = {k: data[k] for k in ["spreadsheet_id", "range"]}
        value = call("get_values", identifiers)["data"]
        rows = value.get("values", [])
        if not rows:
            raise IntegrationFailure("schema", "Range must include a header row")
        columns, rows = rows[0], rows[1:]
    else:
        identifiers = {k: data[k] for k in ["drive_id", "workbook_id", "table_id"]}
        value = call("list_rows", identifiers)["data"]
        column_data = call("list_columns", identifiers)["data"]
        if value.get("@odata.nextLink") or column_data.get("@odata.nextLink"):
            raise IntegrationFailure(
                "pagination", "Find/upsert requires a complete bounded table"
            )
        columns = [
            c["name"]
            for c in sorted(column_data.get("value", []), key=lambda c: c["index"])
        ]
        rows = [r["values"][0] for r in value.get("value", [])]
    if (
        len(rows) > 1000
        or len(columns) != len(set(columns))
        or data["key_column"] not in columns
    ):
        raise IntegrationFailure(
            "schema", "Provide unique headers, a valid key column and at most 1000 rows"
        )
    index = columns.index(data["key_column"])
    matches = [
        i
        for i, row in enumerate(rows)
        if len(row) > index and str(row[index]) == str(data["key_value"])
    ]
    if spec["transform"] == "spreadsheet_find":
        return {
            "data": {
                "matches": [
                    {
                        "row_index": i,
                        "record": {
                            key: rows[i][j] if j < len(rows[i]) else ""
                            for j, key in enumerate(columns)
                        },
                    }
                    for i in matches
                ]
            },
            "http_status": 200,
            "delivery": "read",
        }
    if len(matches) > 1:
        raise IntegrationFailure("schema", "Upsert key matches multiple rows")
    if set(data["record"]) - set(columns):
        raise IntegrationFailure("schema", "Record contains unknown columns")
    if data["key_column"] in data["record"] and str(
        data["record"][data["key_column"]]
    ) != str(data["key_value"]):
        raise IntegrationFailure("schema", "Upsert record cannot change the lookup key")
    record = {
        key: rows[matches[0]][j] if matches and j < len(rows[matches[0]]) else ""
        for j, key in enumerate(columns)
    }
    record.update(data["record"])
    record[data["key_column"]] = data["key_value"]
    values = [[record[k] for k in columns]]
    if conn.connector_id == "excel_online":
        return (
            call(
                "update_row",
                {
                    **identifiers,
                    "row_index": str(value["value"][matches[0]]["index"]),
                    "values": values,
                },
            )
            if matches
            else call("add_rows", {**identifiers, "values": values})
        )
    # A bounded A1 range makes the header's physical row and column unambiguous.
    match = re.fullmatch(
        r"(.+)!([A-Za-z]+)([1-9][0-9]*):([A-Za-z]+)([1-9][0-9]*)", data["range"]
    )
    if not match:
        raise IntegrationFailure(
            "schema", "Upsert requires a bounded A1 range such as Sheet1!A1:Z1000"
        )
    if not matches:
        return call(
            "append_values",
            {**identifiers, "values": values, "insert_data_option": "INSERT_ROWS"},
        )
    sheet, start_col, start_row, _, _ = match.groups()
    number = 0
    for letter in start_col.upper():
        number = number * 26 + ord(letter) - 64
    number += len(columns) - 1
    end_col = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        end_col = chr(65 + remainder) + end_col
    row_number = int(start_row) + matches[0] + 1
    return call(
        "update_values",
        {
            "spreadsheet_id": data["spreadsheet_id"],
            "range": f"{sheet}!{start_col}{row_number}:{end_col}{row_number}",
            "values": values,
        },
    )


def _bytes(value):
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise IntegrationFailure(
            "schema", "File content must be valid base64"
        ) from None


def _slack_upload(data, transport, headers, operation_key):
    from app.apps.power_apps.integrations.transport import HttpTransport, EgressPolicy
    from app.apps.power_apps.integrations.adapters import decode, status_error

    content = _bytes(data["content_base64"])
    response = transport.request(
        "POST",
        "https://slack.com/api/files.getUploadURLExternal",
        body=urlencode({"filename": data["filename"], "length": len(content)}).encode(),
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=5,
    )
    status_error(response, True)
    result = decode(response, [])
    if not result.get("ok"):
        raise IntegrationFailure("remote", "Slack rejected the upload request")
    target = urlsplit(result.get("upload_url", ""))
    if (
        target.scheme != "https"
        or target.hostname != "files.slack.com"
        or target.username
        or target.password
    ):
        raise IntegrationFailure(
            "redirect_denied", "Slack returned an unexpected upload host"
        )
    response = HttpTransport(EgressPolicy(["files.slack.com"])).request(
        "POST",
        result["upload_url"],
        headers={"Content-Type": "application/octet-stream"},
        body=content,
        timeout=5,
    )
    status_error(response, True)
    body = {
        "files": [{"id": result["file_id"], "title": data["filename"]}],
        **{
            k: data[k]
            for k in ["channel_id", "initial_comment", "thread_ts"]
            if k in data
        },
    }
    response = transport.request(
        "POST",
        "https://slack.com/api/files.completeUploadExternal",
        headers={**headers, "Content-Type": "application/json"},
        body=json.dumps(body).encode(),
        timeout=5,
    )
    status_error(response, True)
    result = decode(response, [])
    if not result.get("ok"):
        raise IntegrationFailure(
            "remote", "Slack could not complete the upload", uncertain=True
        )
    return {"data": result, "http_status": response.status, "delivery": "accepted"}
