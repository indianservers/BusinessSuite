"""Bounded, pinned HTTPS adapters. No provider credentials or public sharing URLs leave the server."""
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote, urlsplit, parse_qsl
from uuid import uuid4
from pathlib import Path
from fastapi import HTTPException
from app.core.config import settings
from app.apps.power_apps.integrations.transport import EgressPolicy, HttpTransport
from app.apps.power_apps.integrations.vault import CredentialVault

PROVIDERS = {
    "google_drive": {"label": "Google Drive", "family": "GOOGLE", "authorize": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token", "scopes": ["https://www.googleapis.com/auth/drive.file"], "root": "root"},
    "onedrive": {"label": "OneDrive", "family": "MICROSOFT", "authorize": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize", "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token", "scopes": ["Files.ReadWrite", "offline_access", "User.Read"], "root": "root"},
    "box": {"label": "Box", "family": "BOX", "authorize": "https://account.box.com/api/oauth2/authorize", "token": "https://api.box.com/oauth2/token", "scopes": [], "root": "0"},
    "dropbox": {"label": "Dropbox", "family": "DROPBOX", "authorize": "https://www.dropbox.com/oauth2/authorize", "token": "https://api.dropboxapi.com/oauth2/token", "scopes": ["account_info.read", "files.metadata.read", "files.content.read", "files.content.write"], "root": "root"},
}
HOSTS = {"www.googleapis.com", "oauth2.googleapis.com", "graph.microsoft.com", "login.microsoftonline.com", "api.box.com", "upload.box.com", "api.dropboxapi.com", "content.dropboxapi.com"}
LIMIT = 32 * 1024 * 1024


def now(): return datetime.now(timezone.utc)
def utc(value): return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def app_config(provider):
    if provider not in PROVIDERS: raise HTTPException(422, "Choose Google Drive, OneDrive, Box or Dropbox")
    info = PROVIDERS[provider]
    family = info["family"]
    key = getattr(settings, f"FILES_{family}_CLIENT_ID", "") or getattr(settings, f"POWER_{family}_CLIENT_ID", "")
    secret = getattr(settings, f"FILES_{family}_CLIENT_SECRET", "") or getattr(settings, f"POWER_{family}_CLIENT_SECRET", "")
    if provider == "google_drive" and settings.FILES_GOOGLE_CLIENT_JSON:
        try:
            path = Path(settings.FILES_GOOGLE_CLIENT_JSON)
            if path.stat().st_size > 32768: raise ValueError()
            web = json.loads(path.read_text(encoding="utf-8"))["web"]
            key, secret = web["client_id"], web["client_secret"]
            if not isinstance(key, str) or not isinstance(secret, str): raise ValueError()
        except (OSError, ValueError, KeyError, TypeError):
            key, secret = "", ""
    redirect = settings.BACKEND_PUBLIC_URL.rstrip("/") + "/api/v1/files-storage/oauth/callback"
    parsed = urlsplit(redirect)
    secure = parsed.scheme == "https" or (settings.ENVIRONMENT != "production" and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"})
    return {**info, "client_id": key, "client_secret": secret, "redirect_uri": redirect, "ready": bool(key and secret and secure)}


def request(method, url, headers=None, body=None, *, media=False, redirect=False):
    host = urlsplit(url).hostname
    if host not in HOSTS: raise HTTPException(502, "Unsupported storage provider host")
    response = HttpTransport(EgressPolicy([host])).request(method, url, headers, body, timeout=15,
        return_redirect=redirect, max_response_bytes=LIMIT if media else 262144)
    if response.status not in ({200, 201, 202, 204, 302, 303, 307} if redirect else {200, 201, 202, 204}):
        if response.status == 507: raise HTTPException(409, "Cloud storage quota is full. Free space or increase the connected account's storage, then try again. Your original file is retained.")
        if response.status in {401, 403}: raise HTTPException(409, "Storage access expired or folder access was denied. Reconnect the account.")
        if response.status == 404: raise HTTPException(404, "The cloud file or folder is no longer available")
        raise HTTPException(502, "Storage provider request failed. Your original file is retained.")
    return response


def tokens(provider, fields):
    cfg = app_config(provider)
    if not cfg["ready"]: raise HTTPException(503, "The server OAuth application needs configuration before sign-in")
    response = request("POST", cfg["token"], {"Content-Type": "application/x-www-form-urlencoded"},
        urlencode({"client_id": cfg["client_id"], "client_secret": cfg["client_secret"], **fields}).encode())
    data = json.loads(response.body)
    if not isinstance(data.get("access_token"), str) or not data["access_token"] or data.get("token_type", "bearer").lower() != "bearer":
        raise HTTPException(502, "Provider returned an invalid authorization response")
    if not 30 <= int(data.get("expires_in", 3600)) <= 604800: raise HTTPException(502, "Invalid token expiry")
    return data


def authorization(db, connection):
    if not connection.connected or not connection.encrypted_value:
        raise HTTPException(409, "Connect this storage account before using it")
    value = CredentialVault.decrypt(connection)
    if not connection.expires_at or utc(connection.expires_at) < now() + timedelta(seconds=90):
        if not value.get("refresh_token"): raise HTTPException(409, "Reconnect this storage account")
        data = tokens(connection.provider, {"grant_type": "refresh_token", "refresh_token": value["refresh_token"]})
        value = {**value, "access_token": data["access_token"], "refresh_token": data.get("refresh_token") or value["refresh_token"]}
        connection.encrypted_value = CredentialVault.encrypt(value)
        connection.expires_at = now() + timedelta(seconds=int(data.get("expires_in", 3600)))
        db.flush()
    return {"Authorization": "Bearer " + value["access_token"]}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_!.-]{1,250}", value) or value in {".", ".."}:
        raise HTTPException(422, "Invalid provider folder or file identifier")
    return quote(value, safe="")


def json_request(db, conn, method, url, data=None):
    headers = authorization(db, conn)
    headers["Content-Type"] = "application/json"
    response = request(method, url, headers, json.dumps(data).encode() if data is not None else None)
    return json.loads(response.body) if response.body else {}


def account_info(db, conn):
    if conn.provider == "dropbox":
        user = dropbox_rpc(db, conn, "users/get_current_account")
        return user.get("email") or user["account_id"]
    if conn.provider == "google_drive":
        user = json_request(db, conn, "GET", "https://www.googleapis.com/drive/v3/about?fields=user")["user"]
        return user.get("emailAddress") or user.get("displayName") or "Google Drive"
    if conn.provider == "onedrive":
        user = json_request(db, conn, "GET", "https://graph.microsoft.com/v1.0/me?$select=displayName,mail,userPrincipalName")
        return user.get("mail") or user.get("userPrincipalName") or user.get("displayName") or "OneDrive"
    user = json_request(db, conn, "GET", "https://api.box.com/2.0/users/me")
    return user.get("login") or user.get("name") or "Box"


def folder_info(db, conn, folder):
    if conn.provider == "google_drive" and folder == "root":
        # drive.file can upload into My Drive without permission to read its
        # root folder metadata. Validate the token with the permitted list API.
        json_request(db, conn, "GET", "https://www.googleapis.com/drive/v3/files?pageSize=1&fields=files(id)")
        return {"id": "root", "name": "My Drive"}
    if conn.provider == "dropbox":
        if folder == "root":
            dropbox_rpc(db, conn, "files/list_folder", {"path": "", "limit": 1})
            return {"id": "root", "name": "Dropbox app folder"}
        data = dropbox_rpc(db, conn, "files/get_metadata", {"path": dropbox_identifier(folder)})
        if data.get(".tag") != "folder": raise HTTPException(422, "Choose an accessible folder")
        return {"id": data["id"], "name": data["name"]}
    item = identifier(folder)
    if conn.provider == "google_drive":
        data = json_request(db, conn, "GET", f"https://www.googleapis.com/drive/v3/files/{item}?fields=id,name,mimeType,trashed&supportsAllDrives=true")
        valid = data.get("mimeType") == "application/vnd.google-apps.folder" and not data.get("trashed")
    elif conn.provider == "onedrive":
        data = json_request(db, conn, "GET", "https://graph.microsoft.com/v1.0/me/drive/" + ("root" if folder == "root" else f"items/{item}"))
        valid = "folder" in data and not data.get("deleted")
    else:
        data = json_request(db, conn, "GET", f"https://api.box.com/2.0/folders/{item}")
        valid = data.get("type") == "folder" and data.get("item_status", "active") == "active"
    if not valid: raise HTTPException(422, "Choose an accessible folder")
    return {"id": str(data["id"]), "name": data.get("name", folder)}


def folders(db, conn, parent=None, cursor=None):
    parent = parent or PROVIDERS[conn.provider]["root"]
    if cursor and (len(cursor) > 2000 or "\n" in cursor): raise HTTPException(422, "Invalid folder cursor")
    if conn.provider == "dropbox":
        data = dropbox_rpc(db, conn, "files/list_folder/continue" if cursor else "files/list_folder",
            {"cursor": cursor} if cursor else {"path": "" if parent == "root" else dropbox_identifier(parent), "limit": 100})
        return {"items": [{"id": f["id"], "name": f["name"]} for f in data.get("entries", []) if f.get(".tag") == "folder"], "cursor": data.get("cursor") if data.get("has_more") else None}
    item = identifier(parent)
    if conn.provider == "google_drive":
        params = {"q": f"'{parent}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false", "fields": "nextPageToken,files(id,name)", "pageSize": 100, "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if cursor: params["pageToken"] = cursor
        data = json_request(db, conn, "GET", "https://www.googleapis.com/drive/v3/files?" + urlencode(params))
        return {"items": data.get("files", []), "cursor": data.get("nextPageToken")}
    if conn.provider == "onedrive":
        params = {"$top": 100, "$select": "id,name,folder"}
        if cursor: params["$skiptoken"] = cursor
        url = "https://graph.microsoft.com/v1.0/me/drive/" + ("root" if parent == "root" else f"items/{item}") + "/children?" + urlencode(params)
        data = json_request(db, conn, "GET", url)
        next_values = dict(parse_qsl(urlsplit(data.get("@odata.nextLink", "")).query))
        return {"items": [{"id": f["id"], "name": f["name"]} for f in data.get("value", []) if "folder" in f], "cursor": next_values.get("$skiptoken")}
    offset = int(cursor or "0") if (cursor or "0").isdigit() else 0
    data = json_request(db, conn, "GET", f"https://api.box.com/2.0/folders/{item}/items?limit=100&offset={offset}")
    return {"items": [{"id": f["id"], "name": f["name"]} for f in data.get("entries", []) if f.get("type") == "folder"], "cursor": str(offset+100) if offset+100 < data.get("total_count", 0) else None}


def create_folder(db, conn, parent, name):
    if not name.strip() or len(name) > 120 or any(c in name for c in '/\\\r\n'): raise HTTPException(422, "Choose a valid folder name")
    if name.strip() in {".", ".."}: raise HTTPException(422, "Choose a valid folder name")
    if conn.provider == "dropbox":
        data = dropbox_rpc(db, conn, "files/create_folder_v2", {"path": dropbox_child_path(db, conn, parent, name.strip()), "autorename": False})["metadata"]
        return {"id": data["id"], "name": data["name"]}
    item = identifier(parent)
    if conn.provider == "google_drive":
        data = json_request(db, conn, "POST", "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true", {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]})
    elif conn.provider == "onedrive":
        url = "https://graph.microsoft.com/v1.0/me/drive/" + ("root" if parent == "root" else f"items/{item}") + "/children"
        data = json_request(db, conn, "POST", url, {"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"})
    else:
        data = json_request(db, conn, "POST", "https://api.box.com/2.0/folders", {"name": name, "parent": {"id": parent}})
    return {"id": str(data["id"]), "name": data["name"]}


def upload(db, conn, folder, name, content, mime):
    if not content or len(content) > LIMIT: raise HTTPException(413, "Cloud attachment must be between 1 byte and 32 MB")
    headers = authorization(db, conn)
    # Unique provider filenames prevent overwriting an unrelated file with the same display name.
    safe_name = uuid4().hex[:12] + "-" + re.sub(r"[^\w. -]", "_", name)[:180]
    if conn.provider == "dropbox":
        headers.update({"Content-Type": "application/octet-stream", "Dropbox-API-Arg": json.dumps({"path": dropbox_child_path(db, conn, folder, safe_name), "mode": "add", "autorename": False, "mute": True, "strict_conflict": True})})
        return str(json.loads(request("POST", "https://content.dropboxapi.com/2/files/upload", headers, content).body)["id"])
    item = identifier(folder)
    if conn.provider in {"google_drive", "box"}:
        boundary = uuid4().hex
        if conn.provider == "google_drive":
            metadata = {"name": safe_name, "parents": [folder]}
            body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + json.dumps(metadata).encode() + f"\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n".encode() + content + f"\r\n--{boundary}--\r\n".encode())
            headers["Content-Type"] = f"multipart/related; boundary={boundary}"
            url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id&supportsAllDrives=true"
        else:
            metadata = {"name": safe_name, "parent": {"id": folder}}
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="attributes"\r\n\r\n'.encode() + json.dumps(metadata).encode() + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{safe_name}"\r\nContent-Type: {mime}\r\n\r\n'.encode() + content + f"\r\n--{boundary}--\r\n".encode())
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            url = "https://upload.box.com/api/2.0/files/content"
    else:
        headers["Content-Type"] = mime
        base = "https://graph.microsoft.com/v1.0/me/drive/" + ("root" if folder == "root" else f"items/{item}")
        url, body = base + ":/" + quote(safe_name, safe="") + ":/content", content
    data = json.loads(request("PUT" if conn.provider == "onedrive" else "POST", url, headers, body).body)
    return str(data["entries"][0]["id"] if conn.provider == "box" else data["id"])


def download(db, conn, remote_id):
    if conn.provider == "dropbox":
        headers = authorization(db, conn)
        headers["Dropbox-API-Arg"] = json.dumps({"path": dropbox_identifier(remote_id)})
        return request("POST", "https://content.dropboxapi.com/2/files/download", headers, media=True).body
    item = identifier(remote_id)
    urls = {"google_drive": f"https://www.googleapis.com/drive/v3/files/{item}?alt=media&supportsAllDrives=true", "onedrive": f"https://graph.microsoft.com/v1.0/me/drive/items/{item}/content", "box": f"https://api.box.com/2.0/files/{item}/content"}
    response = request("GET", urls[conn.provider], authorization(db, conn), media=True, redirect=True)
    if response.status in {302, 303, 307}:
        location = response.headers.get("location", "")
        host = (urlsplit(location).hostname or "").lower()
        suffixes = {"box": (".boxcloud.com",), "onedrive": (".files.1drv.com", ".sharepoint.com", ".onedrive.com", ".storage.live.com"), "google_drive": (".googleusercontent.com",)}
        if not any(host.endswith(s) for s in suffixes[conn.provider]): raise HTTPException(502, "Storage download redirected to an unsupported host")
        # Never forward the OAuth bearer to the provider's signed download host.
        policy = EgressPolicy([host], safe_query_keys={k for k, _ in parse_qsl(urlsplit(location).query)})
        response = HttpTransport(policy).request("GET", location, timeout=15, max_response_bytes=LIMIT)
        if response.status != 200: raise HTTPException(502, "Cloud file could not be downloaded")
    return response.body


def dropbox_identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"id:[A-Za-z0-9_-]{1,240}", value):
        raise HTTPException(422, "Invalid Dropbox file or folder identifier")
    return value


def dropbox_rpc(db, conn, route, data=None):
    headers = authorization(db, conn)
    headers["Content-Type"] = "application/json"
    return json.loads(request("POST", "https://api.dropboxapi.com/2/" + route, headers, json.dumps(data).encode()).body)


def dropbox_child_path(db, conn, parent, name):
    if parent == "root": return "/" + name
    data = dropbox_rpc(db, conn, "files/get_metadata", {"path": dropbox_identifier(parent)})
    prefix = data.get("path_lower")
    if data.get(".tag") != "folder" or not isinstance(prefix, str) or not prefix.startswith("/"):
        raise HTTPException(422, "Choose an accessible Dropbox folder")
    return prefix.rstrip("/") + "/" + name
