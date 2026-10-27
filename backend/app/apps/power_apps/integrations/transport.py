"""Pinned-address HTTPS transport. The validated IP is the actual socket target.

No proxy environment, arbitrary ports, credentials in URLs, or cross-origin
redirects. TLS still verifies the original hostname and uses it for SNI.
"""

import base64
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit, urlencode, urljoin, parse_qsl, quote
from app.apps.power_apps.integrations.contracts import IntegrationFailure, HTTPInput

DENIED_NAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "kubernetes.default.svc",
}
SENSITIVE = re.compile(
    r"(?i)(authorization|cookie|password|secret|token|api.?key|private.?key|signature|credential)"
)


@dataclass(frozen=True)
class Target:
    host: str
    port: int
    address: str
    url: str


class EgressPolicy:
    def __init__(self, allowed_hosts, approved=None, resolver=None):
        self.allowed_hosts = {h.lower().rstrip(".") for h in allowed_hosts}
        self.approved = approved or {}
        self.resolver = resolver or socket.getaddrinfo

    def resolve(self, url, *, database=False, port=None):
        try:
            parsed = urlsplit(url)
            host = (parsed.hostname or "").encode("idna").decode().lower().rstrip(".")
            if (
                not host
                or parsed.username
                or parsed.password
                or parsed.fragment
                or "%" in host
                or "\\" in url
            ):
                raise ValueError()
            if database:
                if parsed.scheme != "postgresql":
                    raise ValueError()
                selected_port = port or parsed.port or 5432
            else:
                if parsed.scheme != "https" or (parsed.port or 443) != 443:
                    raise ValueError()
                selected_port = 443
            from app.core.config import settings

            protected = {
                urlsplit(settings.BACKEND_PUBLIC_URL).hostname,
                urlsplit(settings.FRONTEND_PUBLIC_URL).hostname,
            }
            if host in protected:
                raise ValueError()
            if any(SENSITIVE.search(k) for k, v in parse_qsl(parsed.query)):
                raise ValueError()
            if (
                host not in self.allowed_hosts
                or host in DENIED_NAMES
                or host.endswith((".localhost", ".local", ".internal", ".svc"))
            ):
                raise ValueError()
            answers = self.resolver(host, selected_port, type=socket.SOCK_STREAM)
            addresses = sorted({answer[4][0] for answer in answers})
            if not addresses:
                raise ValueError()
            protected_addresses = set()
            for app_host in protected:
                if not app_host:
                    continue
                try:
                    protected_addresses.update(
                        a[4][0]
                        for a in self.resolver(app_host, 443, type=socket.SOCK_STREAM)
                    )
                except OSError:
                    raise ValueError() from None
            if set(addresses) & protected_addresses:
                raise ValueError()
            approved = set(self.approved.get((host, selected_port), []))
            if database and selected_port != 5432 and not approved:
                raise ValueError()
            for raw in addresses:
                ip = ipaddress.ip_address(raw)
                if getattr(ip, "ipv4_mapped", None):
                    ip = ip.ipv4_mapped
                if str(ip) in {"100.100.100.200", "fd00:ec2::254"}:
                    raise ValueError()
                if (
                    ip.is_loopback
                    or ip.is_link_local
                    or ip.is_multicast
                    or ip.is_unspecified
                    or ip.is_reserved
                ):
                    raise ValueError()
                if not ip.is_global and raw not in approved:
                    raise ValueError()
            path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
            if any(ord(ch) < 32 or ord(ch) == 127 for ch in url):
                raise ValueError()
            return Target(
                host,
                selected_port,
                addresses[0],
                urlunsplit(
                    (
                        "https" if not database else "postgresql",
                        ("[" + host + "]" if ":" in host else host)
                        + (":" + str(selected_port) if selected_port != 443 else ""),
                        path,
                        parsed.query,
                        "",
                    )
                ),
            )
        except (ValueError, UnicodeError, OSError):
            raise IntegrationFailure(
                "egress_denied", "Destination is outside the approved egress policy"
            ) from None


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, target, timeout):
        super().__init__(
            target.host,
            port=target.port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        self.target = target

    def connect(self):
        raw = socket.create_connection(
            (self.target.address, self.target.port), self.timeout
        )
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.target.host)
        except BaseException:
            raw.close()
            raise


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes
    duration_ms: int


def scrub(value, secrets=()):
    from app.apps.power_apps.authoring import redact_debug

    if isinstance(value, dict):
        return {
            str(k): scrub(v, secrets)
            for k, v in value.items()
            if not SENSITIVE.search(str(k))
            and not str(k).startswith("__")
            and str(k) not in {"constructor", "prototype"}
        }
    if isinstance(value, list):
        return [scrub(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in sorted({str(s) for s in secrets if s}, key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        return redact_debug(value)
    return value


class HttpTransport:
    def __init__(self, policy, connection_factory=PinnedHTTPS):
        self.policy = policy
        self.connection_factory = connection_factory

    def request(self, method, url, headers=None, body=None, timeout=10, redirects=0):
        headers = dict(headers or {})
        started = time.monotonic()
        original = None
        for redirect in range(redirects + 1):
            target = self.policy.resolve(url)
            origin = (target.host, target.port)
            if original and original != origin:
                raise IntegrationFailure(
                    "redirect_denied", "Cross-origin redirects are not permitted"
                )
            original = origin
            parsed = urlsplit(target.url)
            conn = self.connection_factory(target, min(timeout, 15))
            sent = False
            try:
                conn.connect()  # Connect failures are known to precede request dispatch.
                sent = True
                conn.request(
                    method,
                    (parsed.path or "/") + ("?" + parsed.query if parsed.query else ""),
                    body=body,
                    headers=headers,
                )
                response = conn.getresponse()
                data = response.read(262145)
                if len(data) > 262144:
                    raise IntegrationFailure(
                        "response_size",
                        "Response exceeds 256 KB",
                        uncertain=method not in {"GET", "HEAD"},
                    )
                result = Response(
                    response.status,
                    {k.lower(): v for k, v in response.getheaders()},
                    data,
                    int((time.monotonic() - started) * 1000),
                )
            except IntegrationFailure:
                raise
            except (
                OSError,
                ssl.SSLError,
                http.client.HTTPException,
                ValueError,
                UnicodeError,
            ):
                raise IntegrationFailure(
                    "network",
                    "Remote request could not be completed",
                    retryable=method in {"GET", "HEAD"} or not sent,
                    uncertain=sent and method not in {"GET", "HEAD"},
                ) from None
            finally:
                conn.close()
            if result.status in {301, 302, 303, 307, 308}:
                if redirect >= redirects:
                    raise IntegrationFailure(
                        "redirect_denied",
                        "Redirect was not followed",
                        uncertain=method not in {"GET", "HEAD"},
                    )
                if method not in {"GET", "HEAD"}:
                    raise IntegrationFailure(
                        "redirect_denied",
                        "Mutating requests cannot redirect",
                        uncertain=True,
                    )
                url = urljoin(target.url, result.headers.get("location", ""))
                continue
            return result
        raise IntegrationFailure("redirect_denied", "Redirect limit exceeded")


def encode_request(data):
    data = HTTPInput.model_validate(data)
    headers = {}
    for name, value in data.headers.items():
        if (
            not re.fullmatch(r"[A-Za-z0-9-]{1,80}", name)
            or SENSITIVE.search(name)
            or name.lower()
            in {
                "host",
                "connection",
                "content-length",
                "transfer-encoding",
                "proxy-authorization",
            }
            or "\r" in value
            or "\n" in value
        ):
            raise IntegrationFailure(
                "headers",
                "Use a credential reference for authentication and safe custom headers",
            )
        headers[name] = value
    body = None
    if data.body is not None:
        body = json.dumps(data.body, allow_nan=False).encode()
        headers["Content-Type"] = "application/json"
    elif data.form is not None:
        body = urlencode(data.form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif data.files:
        import secrets

        boundary = "power_" + secrets.token_hex(16)
        chunks = []
        for file in data.files:
            if set(file) - {"name", "filename", "content_base64", "content_type"}:
                raise ValueError("Unknown multipart field")
            name = file.get("name", "file")
            filename = file.get("filename", "upload.bin")
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name) or not re.fullmatch(
                r"[A-Za-z0-9_.-]{1,100}", filename
            ):
                raise ValueError("Unsafe multipart name")
            content = base64.b64decode(file.get("content_base64", ""), validate=True)
            if len(content) > 65536:
                raise ValueError("File exceeds 64 KB")
            content_type = file.get("content_type", "application/octet-stream")
            if not re.fullmatch(r"[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+", content_type):
                raise ValueError("Invalid content type")
            chunks.extend(
                [
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode(),
                    content,
                    b"\r\n",
                ]
            )
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
    if body and len(body) > 196608:
        raise ValueError("Request body exceeds 192 KB")
    return data, headers, body
