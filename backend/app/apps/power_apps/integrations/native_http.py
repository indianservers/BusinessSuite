"""Fixed-origin native management and event reads through the pinned transport."""

import json
import time
from urllib.parse import quote, urlencode, urlsplit
from app.apps.power_apps.integrations.contracts import IntegrationFailure
from app.apps.power_apps.integrations import adapters, vault, oauth
from app.apps.power_apps.integrations.transport import EgressPolicy
from app.apps.power_apps.integrations.automation_catalog import MODULES


def segment(value):
    value = str(value)
    if value in {"", ".", ".."} or any(c in value for c in "\r\n\\"):
        raise IntegrationFailure("schema", "Invalid native resource identifier")
    return quote(value, safe="")


class NativeClient:
    def __init__(self, db, actor, conn):
        credential, values = vault.credential_values(db, actor, conn)
        values = oauth.access_values(db, conn, credential, values)
        self.conn = vault.connection(db, actor, conn.environment, conn.id)
        self.deadline = time.monotonic() + 20
        if not self.conn.enabled:
            raise IntegrationFailure("disabled", "Native connection was disabled")
        vault.credential_values(db, actor, self.conn)
        self.headers = vault.authentication(credential.auth_type, values, conn.config)
        self.host = MODULES[conn.connector_id]["host"] or conn.config.get(
            "provider_host", ""
        )
        self.hosts = {self.host}
        if conn.connector_id in {"gmail", "google_forms"}:
            self.hosts.update({"pubsub.googleapis.com", "oauth2.googleapis.com"})
        if conn.connector_id == "clickup" and "Authorization" in self.headers:
            self.headers["Authorization"] = self.headers["Authorization"].removeprefix(
                "Bearer "
            )
        if conn.connector_id == "zoho_crm":
            self.headers["Authorization"] = "Zoho-oauthtoken " + values["access_token"]
        if conn.connector_id == "notion":
            self.headers["Notion-Version"] = "2025-09-03"
        if conn.connector_id == "dropbox":
            if conn.config.get("team_member_id"):
                self.headers["Dropbox-API-Select-User"] = conn.config["team_member_id"]
            if conn.config.get("namespace_id"):
                self.headers["Dropbox-API-Path-Root"] = json.dumps(
                    {
                        ".tag": "namespace_id",
                        "namespace_id": conn.config["namespace_id"],
                    }
                )

    def request(
        self,
        method,
        path,
        body=None,
        *,
        query=None,
        host=None,
        bearer=None,
        allow=(),
        timeout=10
    ):
        host = host or self.host
        if host != self.host and bearer is None:
            raise IntegrationFailure("credential","A native infrastructure request requires its own credential")
        if host not in self.hosts or not path.startswith("/") or path.startswith("//"):
            raise IntegrationFailure("egress", "Native request origin is not approved")
        url = "https://" + host + path
        if query:
            url += ("&" if "?" in path else "?") + urlencode(query, doseq=True)
        headers = {**self.headers, "Accept": "application/json"}
        if bearer is not None:
            headers["Authorization"] = "Bearer " + bearer
        content = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            content = json.dumps(body, allow_nan=False).encode()
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise IntegrationFailure(
                "timeout", "Native provider work exceeded its IO budget"
            )
        policy = EgressPolicy(
            self.hosts,
            safe_query_keys={
                "pageToken",
                "nextPageToken",
                "syncToken",
                "$skiptoken",
                "$deltatoken",
                "page_token",
                "cursor",
            },
        )
        response = adapters.HTTP_FACTORY(policy).request(
            method, url, headers=headers, body=content, timeout=min(timeout, remaining)
        )
        if response.status in allow:
            return {"_status": response.status}
        adapters.status_error(response, method not in {"GET", "HEAD"})
        try:
            value = json.loads(response.body) if response.body else {}
        except (ValueError, UnicodeDecodeError):
            raise IntegrationFailure(
                "response", "Native API returned invalid JSON"
            ) from None
        if isinstance(value, dict) and (
            value.get("ok") is False or value.get("success") is False
        ):
            raise IntegrationFailure("remote", "Provider rejected native setup")
        return value

    def follow(self, url, prefix):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != self.host
            or not parsed.path.startswith(prefix)
        ):
            raise IntegrationFailure(
                "pagination", "Native continuation changed resource or origin"
            )
        return self.request(
            "GET", parsed.path + ("?" + parsed.query if parsed.query else "")
        )

    def collection(
        self, path, key="value", *, query=None, method="GET", body=None, max_items=1000
    ):
        rows = []
        value = self.request(method, path, body, query=query)
        for _ in range(20):
            batch = value.get(key, [])
            if not isinstance(batch, list) or len(rows) + len(batch) > max_items:
                raise IntegrationFailure(
                    "snapshot", "Native watch exceeds the complete-snapshot limit"
                )
            rows.extend(batch)
            if value.get("@odata.nextLink"):
                value = self.follow(value["@odata.nextLink"], path.split("?")[0])
            elif value.get("nextPageToken"):
                value = self.request(
                    method,
                    path,
                    body,
                    query={**(query or {}), "pageToken": value["nextPageToken"]},
                )
            elif value.get("has_more"):
                value = self.request(
                    method,
                    path,
                    {**(body or {}), "start_cursor": value["next_cursor"]},
                    query=query,
                )
            elif value.get("paging", {}).get("next", {}).get("after"):
                value = self.request(
                    method,
                    path,
                    body,
                    query={**(query or {}), "after": value["paging"]["next"]["after"]},
                )
            else:
                return rows, value
        raise IntegrationFailure("pagination", "Native watch has too many pages")
