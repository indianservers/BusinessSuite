"""Provider contract/transport tests use controlled fixtures, not customer accounts."""

import json
from types import SimpleNamespace as NS
import pytest
from app.apps.power_apps.integrations.providers import PROFILES, MODELS, execute
from app.apps.power_apps.integrations.registry import REGISTRY
from app.apps.power_apps.integrations.transport import Response
from app.apps.power_apps.integrations.contracts import IntegrationFailure

ACTIONS = [(pid, a) for pid, p in PROFILES.items() for a in p["actions"]]


def sample(action):
    data = {key: "fixture_value" for key in action["fields"]}
    data.update(
        {
            key: "fixture@example.test"
            for key in action["fields"]
            if key in {"to", "email", "from_email"}
        }
    )
    if "fields_json" in data:
        data["fields_json"] = '{"Name":"Fixture"}'
    if "starts_at" in data:
        data.update(
            starts_at="2026-11-01T09:00:00+00:00", ends_at="2026-11-01T10:00:00+00:00"
        )
    return data


@pytest.mark.parametrize(
    "pid,action", ACTIONS, ids=[pid + "-" + a["id"] for pid, a in ACTIONS]
)
def test_every_provider_action_builds_fixed_origin_valid_request(pid, action):
    calls = []

    class Transport:
        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            assert url.startswith("https://" + PROFILES[pid]["host"] + "/")
            assert method == action["method"]
            if kwargs.get("body") and action["transform"] != "stripe":
                assert isinstance(json.loads(kwargs["body"]), dict)
            return Response(200, {}, b'{"id":"fixture-result","ok":true}', 1)

    data = sample(action)
    parsed = MODELS[pid, action["id"]].model_validate(data)
    out = execute(
        NS(connector_id=pid),
        action["id"],
        parsed,
        Transport(),
        {"Authorization": "Bearer fixture-credential"},
        {"access_token": "fixture-credential"},
        "fixed-operation",
    )
    assert (
        len(calls) == 1
        and out["http_status"] == 200
        and out["data"]["id"] == "fixture-result"
    )
    if action["transform"] in {"chat", "anthropic"}:
        body = json.loads(calls[0][2]["body"])
        assert (
            body["max_tokens"] == 800
            and body["messages"][0]["content"] == data["prompt"]
        )


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
@pytest.mark.parametrize("pid", list(PROFILES))
def test_every_provider_handles_remote_failure(pid, status):
    action = PROFILES[pid]["actions"][0]

    class Transport:
        def request(self, *args, **kwargs):
            return Response(status, {"retry-after": "3"}, b'{"error":"fixture"}', 1)

    with pytest.raises(IntegrationFailure) as exc:
        execute(
            NS(connector_id=pid),
            action["id"],
            sample(action),
            Transport(),
            {},
            {"access_token": "fixture-credential"},
            "fixed-operation",
        )
    assert exc.value.http_status == status


def test_catalog_has_forty_real_implementations_not_candidate_placeholders():
    assert len(REGISTRY) >= 40
    for pid in PROFILES:
        assert REGISTRY[pid].actions
        assert all((pid, a["id"]) in MODELS for a in PROFILES[pid]["actions"])


def test_provider_application_failure_does_not_report_success():
    class Transport:
        def request(self, *args, **kwargs):
            return Response(200, {}, b'{"ok":false,"error":"not_in_channel"}', 1)

    with pytest.raises(IntegrationFailure):
        execute(
            NS(connector_id="slack"),
            "send_message",
            {"channel": "C123", "text": "fixture"},
            Transport(),
            {},
            {"access_token": "fixture"},
            "key",
        )


def test_shared_transport_over_real_tls_fixture(tmp_path):
    import ssl, socket, threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from app.apps.power_apps.integrations.transport import (
        EgressPolicy,
        HttpTransport,
        PinnedHTTPS,
        Target,
    )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "provider.fixture.example")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("provider.fixture.example")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    certfile = tmp_path / "fixture.pem"
    keyfile = tmp_path / "fixture-key.pem"
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(
                json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            )
            body = b'{"accepted":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(certfile), str(keyfile))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def resolver(host, port, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("8.8.8.8" if host == "provider.fixture.example" else "1.1.1.1", port),
            )
        ]

    class FixtureSocket(PinnedHTTPS):
        def __init__(self, target, timeout):
            assert (
                target.address == "8.8.8.8"
                and target.host == "provider.fixture.example"
            )
            # Test-only injection directs the validated fixture name to its local TLS server.
            super().__init__(
                Target(target.host, server.server_port, "127.0.0.1", target.url),
                timeout,
            )
            self._context = ssl.create_default_context(cafile=str(certfile))

    try:
        transport = HttpTransport(
            EgressPolicy(["provider.fixture.example"], resolver=resolver),
            connection_factory=FixtureSocket,
        )
        result = transport.request(
            "POST",
            "https://provider.fixture.example/events",
            headers={"Content-Type": "application/json"},
            body=b'{"message":"actual TLS fixture"}',
        )
        assert result.status == 200 and received == [{"message": "actual TLS fixture"}]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


LEGACY_ACTIONS = [
    (pid, a.id)
    for pid in ("github", "google_sheets", "google_drive", "outlook")
    for a in REGISTRY[pid].actions
]


@pytest.mark.parametrize("pid,action", LEGACY_ACTIONS)
def test_existing_provider_actions_have_valid_requests(pid, action):
    from app.apps.power_apps.integrations.adapters import provider_action
    from app.apps.power_apps.integrations.contracts import ProviderInput
    from app.apps.power_apps.integrations.vault import PROVIDER_HOSTS

    calls = []

    class Transport:
        def request(self, method, url, headers=None, body=None, **kwargs):
            calls.append((method, url, headers, body))
            assert any(
                url.startswith("https://" + host + "/") for host in PROVIDER_HOSTS[pid]
            )
            if body and "json" in headers.get("Content-Type", ""):
                assert isinstance(json.loads(body), dict)
            return Response(
                202 if pid == "outlook" and action == "send_mail" else 200,
                {},
                b'{"id":"fixture-resource","updates":{"updatedRows":1},"files":[],"value":[]}',
                1,
            )

    data = ProviderInput(
        owner="fixture-owner",
        repository="fixture-repo",
        title="Fixture issue",
        text="Fixture text",
        spreadsheet_id="fixture_sheet_123",
        values=[["fixture", 1]],
        file_id="fixture_file_123",
        name="Fixture file",
        content="Fixture body",
        recipient="recipient@example.com",
        subject="Fixture mail",
    )
    output = provider_action(
        NS(connector_id=pid, config={}),
        action,
        data,
        Transport(),
        {"Authorization": "Bearer fixture-secret"},
        {"access_token": "fixture-secret"},
        "fixture-operation",
    )
    assert len(calls) == 1
    if pid == "outlook" and action == "send_mail":
        assert output["accepted"] is True and output["delivery_confirmed"] is False
