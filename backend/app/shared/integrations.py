"""Tenant-scoped connectors. HTTPS is pinned to a validated public address."""

import hashlib
import hmac
import http.client
import ipaddress
import json
import socket
import ssl
import time
from urllib.parse import urlsplit
from fastapi import HTTPException
from app.core.mfa import _fernet
from app.models.platform import IntegrationCredential, IntegrationEvent
from app.shared.contracts import authorize


def protect(value):
    return "enc:" + _fernet().encrypt(value.encode()).decode()


def reveal(value):
    if not value or not value.startswith("enc:"):
        raise HTTPException(503, "Connection requires secure credential migration")
    try:
        return _fernet().decrypt(value[4:].encode()).decode()
    except Exception:
        raise HTTPException(
            503, "Credential is unavailable; reconnect securely"
        ) from None


def destination(url):
    if (
        not isinstance(url, str)
        or not 1 <= len(url) <= 2000
        or any(c.isspace() for c in url)
    ):
        raise HTTPException(422, "Invalid integration destination")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise HTTPException(422, "Invalid integration destination") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or port not in {None, 443}
    ):
        raise HTTPException(
            422, "Use an HTTPS origin/path without credentials, query or redirects"
        )
    try:
        addresses = sorted(
            {
                r[4][0]
                for r in socket.getaddrinfo(
                    parsed.hostname, 443, type=socket.SOCK_STREAM
                )
            }
        )
    except OSError:
        raise HTTPException(422, "Destination cannot be resolved") from None
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise HTTPException(
            422, "Private, loopback and reserved destinations are forbidden"
        )
    return parsed, addresses[0]


def send(url, secret, payload):
    parsed, address = destination(url)

    class PinnedHTTPS(http.client.HTTPSConnection):
        def connect(self):
            self.sock = ssl.create_default_context().wrap_socket(
                socket.create_connection((address, 443), timeout=10),
                server_hostname=parsed.hostname,
            )

    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if len(raw) > 256000:
        raise HTTPException(422, "Integration payload is too large")
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    connection = PinnedHTTPS(parsed.hostname, timeout=10)
    try:
        connection.request(
            "POST",
            parsed.path or "/",
            raw,
            {
                "Content-Type": "application/json",
                "X-Suite-Timestamp": timestamp,
                "X-Suite-Signature": signature,
            },
        )
        response = connection.getresponse()
        response.read(
            4096
        )  # Bounded diagnostics; never persist external response bodies/secrets.
        if not 200 <= response.status < 300:
            raise HTTPException(
                502, f"Connector rejected request (HTTP {response.status})"
            )
        return {
            "status": "accepted",
            "httpStatus": response.status,
            "confirmedDelivery": False,
        }
    finally:
        connection.close()


def invoke(db, actor, company, module, connection_id, operation, payload):
    authorize(db, actor, company, module, "export")
    row = (
        db.query(IntegrationCredential)
        .filter_by(id=connection_id, organization_id=company, status="Active")
        .first()
    )
    if not row or module not in (row.module_keys or []):
        raise HTTPException(403, "Connection is not authorized for this company/module")
    operation_config = (row.config_json or {}).get("operations", {}).get(operation)
    if not operation_config:
        raise HTTPException(422, "Choose a registered connector operation")
    permitted = set(operation_config.get("fields", []))
    if not isinstance(payload, dict) or set(payload) - permitted:
        raise HTTPException(422, "Connector operation contains unsupported fields")
    log = IntegrationEvent(
        event_type=f"shared.{operation}",
        status="Queued",
        payload_json={
            "companyId": company,
            "module": module,
            "connectionId": row.id,
            "actorId": actor.id,
        },
        attempts=1,
    )
    db.add(log)
    db.flush()
    try:
        result = send(operation_config["url"], reveal(row.secret_ref), payload)
        log.status = "Accepted"
        return result
    except HTTPException:
        log.status = "Failed"
        log.last_error = "Connector failed; inspect provider status. Outcome may require reconciliation."
        raise
