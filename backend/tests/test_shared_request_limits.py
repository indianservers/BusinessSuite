import asyncio
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request
from app.main import app
from app.core.config import settings
from app.core.middleware.audit import client_addresses
from app.core.middleware.request_boundary import RequestBoundaryMiddleware
from app.core.request_limits import consume, acquire
from app.models.security_boundary import SecurityRateBucket, SecurityWorkLease


@pytest.fixture
def shared_store(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "limits.sqlite"),
        connect_args={"check_same_thread": False},
    )
    for table in [SecurityRateBucket.__table__, SecurityWorkLease.__table__]:
        table.create(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture
def limited(client, shared_store, monkeypatch):
    monkeypatch.setattr(app.state, "security_enforce_tests", True, raising=False)
    monkeypatch.setattr(
        app.state, "security_session_factory", shared_store, raising=False
    )
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1000)
    return client


def test_counters_are_shared_between_sessions_and_reset_after_window(shared_store):
    for _ in range(3):
        with shared_store() as db:
            assert consume(db, [("same-account", 3, 60)], now=120) == 0
            db.commit()
    with shared_store() as db:
        assert consume(db, [("same-account", 3, 60)], now=121) == 59
        db.commit()
    with shared_store() as db:
        assert consume(db, [("same-account", 3, 60)], now=180) == 0
        assert "same-account" not in db.query(SecurityRateBucket.key).first()[0]
        db.commit()


def test_expired_work_lease_cannot_be_released_by_old_request(shared_store):
    with shared_store() as db:
        first = acquire(db, "expensive-company", 1, 10, now=100)
        assert first
        assert acquire(db, "expensive-company", 1, 10, now=101) is None
        second = acquire(db, "expensive-company", 1, 10, now=111)
        assert second and second[2] != first[2]
        db.execute(
            delete(SecurityWorkLease).where(
                SecurityWorkLease.key == first[0],
                SecurityWorkLease.slot == first[1],
                SecurityWorkLease.token == first[2],
            )
        )
        assert db.query(SecurityWorkLease).one().token == second[2]


def test_expired_counter_cleanup_is_bounded_and_uses_one_delete(shared_store):
    from sqlalchemy import event
    with shared_store() as db:
        db.add_all([SecurityRateBucket(key=f"{i:064x}", window=1, count=1, expires=99) for i in range(150)])
        db.add(SecurityRateBucket(key="f" * 64, window=2, count=1, expires=2000))
        db.commit()
        statements = []
        engine = db.get_bind()
        def record(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("DELETE FROM SECURITY_RATE_BUCKETS"):
                statements.append(statement)
        event.listen(engine, "before_cursor_execute", record)
        try:
            assert consume(db, [("new-active-request", 10, 60)], now=1000) == 0
            db.commit()
        finally:
            event.remove(engine, "before_cursor_execute", record)
        assert len(statements) == 1
        assert db.query(SecurityRateBucket).filter(SecurityRateBucket.expires < 1000).count() == 50
        assert db.query(SecurityRateBucket).filter(SecurityRateBucket.key == "f" * 64).count() == 1


def test_login_throttle_cannot_be_bypassed_with_forwarded_header(limited):
    for index in range(8):
        response = limited.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": "bad"},
            headers={"X-Forwarded-For": f"203.0.113.{index + 1}"},
        )
        assert response.status_code == 401, response.text
    response = limited.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "bad"},
        headers={"X-Forwarded-For": "192.0.2.99"},
    )
    assert response.status_code == 429, response.text
    assert 1 <= int(response.headers["Retry-After"]) <= 60


def test_reset_has_shared_account_and_ip_throttle(limited):
    for _ in range(8):
        response = limited.post(
            "/api/v1/auth/forgot-password", json={"email": "absent@example.com"}
        )
        assert response.status_code == 200
    assert (
        limited.post(
            "/api/v1/auth/forgot-password", json={"email": "absent@example.com"}
        ).status_code
        == 429
    )


def test_only_configured_proxy_networks_can_supply_client_ip(monkeypatch):
    monkeypatch.delenv("AUDIT_TRUSTED_PROXY_CIDRS", raising=False)

    def request(peer, forwarded):
        return Request(
            {
                "type": "http",
                "client": (peer, 123),
                "headers": [(b"x-forwarded-for", forwarded.encode())],
            }
        )

    monkeypatch.setattr(settings, "SECURITY_TRUSTED_PROXY_CIDRS", "")
    assert client_addresses(request("198.51.100.7", "203.0.113.9"))[0] == "198.51.100.7"
    monkeypatch.setattr(settings, "SECURITY_TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    assert (
        client_addresses(request("10.1.1.1", "203.0.113.9, 198.51.100.7, 10.2.2.2"))[0]
        == "198.51.100.7"
    )


@pytest.mark.parametrize(
    "query",
    [
        "limit=501",
        "page_size=1000000",
        "offset=100001",
        "skip=-1",
        "limit=1e10",
        "q=" + "x" * 513,
    ],
)
def test_pagination_and_search_are_bounded(client, query):
    response = client.get("/api/v1/crm/leads?" + query)
    assert response.status_code == 422


def test_body_and_json_complexity_are_bounded(client, monkeypatch):
    monkeypatch.setattr(settings, "SECURITY_MAX_BODY_BYTES", 100)
    response = client.post(
        "/api/v1/auth/login",
        content=b"x" * 101,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    monkeypatch.setattr(settings, "SECURITY_MAX_BODY_BYTES", 10000)
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "a@example.com", "password": "x", "user_ids": [1] * 201},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "a@example.com", "password": "x", "is_superuser": True},
        ).status_code
        == 422
    )


def test_chunked_body_limit_cannot_be_bypassed(monkeypatch):
    monkeypatch.setattr(settings, "SECURITY_MAX_BODY_BYTES", 10)
    called = []

    async def inner(scope, receive, send):
        called.append(True)

    messages = iter(
        [
            {"type": "http.request", "body": b"123456", "more_body": True},
            {"type": "http.request", "body": b"789012", "more_body": False},
        ]
    )

    async def receive():
        return next(messages)

    sent = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 80),
        "app": SimpleNamespace(state=SimpleNamespace()),
    }
    asyncio.run(RequestBoundaryMiddleware(inner)(scope, receive, send))
    assert not called
    assert sent[0]["status"] == 413


def test_security_store_failure_fails_closed(limited, monkeypatch):
    def unavailable():
        raise RuntimeError("Synthetic credential that must not appear")

    monkeypatch.setattr(app.state, "security_session_factory", unavailable)
    response = limited.get("/api/v1/auth/firebase/config")
    assert response.status_code == 503
    assert "Synthetic" not in response.text
    assert response.headers["Retry-After"] == "5"


def test_http_timeout_keeps_worker_scope_until_it_finishes(monkeypatch):
    monkeypatch.setattr(settings, "SECURITY_REQUEST_TIMEOUT_SECONDS", 1)
    finished = []
    statuses = []

    async def inner(scope, receive, send):
        await asyncio.sleep(1.1)
        finished.append(True)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"late"})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/private",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 80),
        "app": SimpleNamespace(state=SimpleNamespace()),
    }
    asyncio.run(RequestBoundaryMiddleware(inner)(scope, receive, send))
    assert finished == [True]
    assert statuses == [504]


def test_early_throttle_retains_cors_and_security_headers(limited, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(
        settings, "BACKEND_CORS_ORIGINS", ["https://portal.example.com"]
    )
    headers = {"Origin": "https://portal.example.com"}
    response = None
    for _ in range(11):
        response = limited.get("/api/v1/auth/firebase/config", headers=headers)
    assert response.status_code == 429
    assert response.headers["Access-Control-Allow-Origin"] == headers["Origin"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Retry-After" in response.headers


def test_postgresql_atomic_counter_has_no_concurrent_overshoot(db_engine):
    if db_engine.dialect.name != "postgresql":
        pytest.skip(
            "PostgreSQL concurrency proof runs in the isolated PostgreSQL rehearsal"
        )
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4
    from app.core.request_limits import digest

    key = "concurrent-proof:" + str(uuid4())
    factory = sessionmaker(bind=db_engine)

    def request(_):
        with factory() as db:
            retry = consume(db, [(key, 5, 60)])
            db.commit()
            return retry == 0

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes = list(executor.map(request, range(12)))
        assert sum(outcomes) == 5
    finally:
        with factory() as db:
            db.execute(
                delete(SecurityRateBucket).where(SecurityRateBucket.key == digest(key))
            )
            db.commit()
