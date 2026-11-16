"""Security-store retries never retry business work or ambiguously committed charges."""

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from app.core import request_limits


class DriverFailure(Exception):
    def __init__(self, code, *, legacy=False):
        super().__init__("driver detail contains credential-sentinel")
        if legacy:
            self.pgcode = code
        else:
            self.sqlstate = code


def database_failure(code, *, legacy=False):
    return OperationalError(
        "SQL containing credential-sentinel",
        {"password": "credential-sentinel"},
        DriverFailure(code, legacy=legacy),
    )


class Session:
    def __init__(self, store):
        self.store = store
        self.info = {}
        self.pending = 0
        self.reservation = False
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, error_type, error, traceback):
        if error_type or self.pending:
            self.rollback()
        self.closed = True

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def execute(self, *args, **kwargs):
        # Session-level timeout setup may execute SQL before the callback.
        return SimpleNamespace(scalar_one_or_none=lambda: None)

    def in_transaction(self):
        return False

    def commit(self):
        if self.reservation and self.store.commit_error is not None:
            error = self.store.commit_error
            self.store.commit_error = None
            if self.store.commit_error_after_accept:
                self.store.accepted += self.pending
                self.pending = 0
            raise error
        self.store.accepted += self.pending
        self.pending = 0
        self.commits += 1

    def rollback(self):
        self.pending = 0
        self.rollbacks += 1


@pytest.fixture
def store(monkeypatch):
    state = SimpleNamespace(sessions=[], accepted=0, commit_error=None, commit_error_after_accept=False, sleeps=[], request=SimpleNamespace(state=SimpleNamespace(request_id="security-store-test"), url=SimpleNamespace(path="/api/v1/test")), cleanup_helper=request_limits._cleanup_after_commit)

    def create_session():
        session = Session(state)
        state.sessions.append(session)
        return session

    monkeypatch.setattr(request_limits, "factory", lambda request: create_session)
    monkeypatch.setattr(request_limits, "time", SimpleNamespace(time=request_limits.time.time, monotonic=request_limits.time.monotonic, sleep=state.sleeps.append))
    monkeypatch.setattr(request_limits, "cleanup_expired", lambda db: None)
    monkeypatch.setattr(request_limits, "_cleanup_after_commit", lambda request: None)
    return state


def reserve_once(db):
    assert db.info.get("security_store_timeout") is True
    db.reservation = True
    db.pending += 1
    return "reserved"


@pytest.mark.parametrize("code", ["55P03", "40P01", "40001"])
@pytest.mark.parametrize("legacy", [False, True])
def test_rolled_back_contention_retries_in_a_new_session_once(store, caplog, code, legacy):
    operations = []

    def operation(db):
        operations.append(db)
        reserve_once(db)
        if len(operations) == 1:
            raise database_failure(code, legacy=legacy)
        return "reserved"

    assert request_limits.security_transaction(store.request, operation) == "reserved"
    assert len(operations) == 2
    assert operations[0] is not operations[1]
    assert operations[0].rollbacks >= 1
    assert operations[0].commits == 0
    assert operations[1].commits == 1
    assert store.accepted == 1, "A rolled-back attempt must not consume a second budget"
    assert all(session.closed for session in operations)
    assert "credential-sentinel" not in caplog.text


def test_continuous_contention_stops_after_three_attempts_and_does_not_accept(store):
    operations = []

    def operation(db):
        operations.append(db)
        reserve_once(db)
        raise database_failure("55P03")

    with pytest.raises(OperationalError):
        request_limits.security_transaction(store.request, operation)
    assert len(operations) == 3
    assert store.accepted == 0
    assert all(session.rollbacks >= 1 and session.closed for session in operations)


def test_unknown_connection_failure_during_commit_is_never_retried(store, caplog):
    operations = []
    store.commit_error = database_failure("08006")
    store.commit_error_after_accept = True

    def operation(db):
        operations.append(db)
        return reserve_once(db)

    with pytest.raises(OperationalError):
        request_limits.security_transaction(store.request, operation)
    assert len(operations) == 1, "An ambiguous commit must never be charged again"
    assert store.accepted == 1, "Simulate the first charge committing before the connection is lost"
    assert not store.sleeps
    assert "credential-sentinel" not in caplog.text


def test_programming_failure_is_not_retried(store):
    calls = []

    def operation(db):
        calls.append(db)
        raise ValueError("Invalid security specification")

    with pytest.raises(ValueError):
        request_limits.security_transaction(store.request, operation)
    assert len(calls) == 1
    assert not store.sleeps
    assert store.accepted == 0


def test_known_aborted_commit_can_retry_without_a_second_charge(store):
    calls = []
    store.commit_error = database_failure("40001")

    def operation(db):
        calls.append(db)
        return reserve_once(db)

    assert request_limits.security_transaction(store.request, operation) == "reserved"
    assert len(calls) == 2
    assert calls[0].rollbacks >= 1
    assert calls[0].commits == 0
    assert calls[1].commits == 1
    assert store.accepted == 1


def test_throttled_result_is_committed_once_without_retry(store):
    calls = []

    def operation(db):
        calls.append(db)
        reserve_once(db)
        return 17

    assert request_limits.security_transaction(store.request, operation) == 17
    assert len(calls) == 1
    assert calls[0].commits == 1
    assert not store.sleeps


def test_cleanup_failure_cannot_reject_an_already_committed_reservation(store, monkeypatch, caplog):
    operations, cleanup = [], []

    def operation(db):
        operations.append(db)
        return reserve_once(db)

    def fail_cleanup(db):
        cleanup.append(db)
        raise database_failure("55P03")

    monkeypatch.setattr(request_limits, "cleanup_expired", fail_cleanup)
    monkeypatch.setattr(request_limits, "_cleanup_after_commit", store.cleanup_helper)
    monkeypatch.setattr(request_limits, "_next_cleanup_at", 0.0)
    assert request_limits.security_transaction(store.request, operation) == "reserved"
    assert len(operations) == 1
    assert len(cleanup) == 1
    assert cleanup[0] is not operations[0], "Cleanup must not hold the active budget's row locks"
    assert operations[0].commits == 1
    assert store.accepted == 1
    assert cleanup[0].rollbacks >= 1
    assert "credential-sentinel" not in caplog.text


def test_retry_deadline_stops_new_attempts_even_when_attempt_budget_remains(store, monkeypatch):
    # The first failed transaction consumes more than the whole bounded retry window.
    times = iter([100.0, 110.0, 110.0, 110.0])
    monkeypatch.setattr(request_limits.time, "monotonic", lambda: next(times, 110.0))
    calls = []

    def operation(db):
        calls.append(db)
        raise database_failure("55P03")

    with pytest.raises(OperationalError):
        request_limits.security_transaction(store.request, operation)
    assert len(calls) == 1
    assert not store.sleeps


def test_backoff_crossing_deadline_does_not_start_a_new_transaction(store, monkeypatch):
    clock = SimpleNamespace(value=100.0)
    monkeypatch.setattr(request_limits.time, "monotonic", lambda: clock.value)

    def sleep(delay):
        store.sleeps.append(delay)
        clock.value = 104.05

    monkeypatch.setattr(request_limits.time, "sleep", sleep)
    calls = []

    def operation(db):
        calls.append(db)
        clock.value = 103.99
        raise database_failure("55P03")

    with pytest.raises(OperationalError):
        request_limits.security_transaction(store.request, operation)
    assert len(calls) == 1


@pytest.mark.parametrize("security_store", [False, True])
def test_tenant_timeout_flag_precedes_identity_query(monkeypatch, security_store):
    from app.db import tenant

    route = SimpleNamespace(tenant_uuid="tenant-fixture", company_id=41, database_name="fixture_test")
    observed = []
    session = SimpleNamespace(info={})

    def execute(statement):
        observed.append(session.info.get("security_store_timeout", False))
        return SimpleNamespace(one=lambda: (route.tenant_uuid, route.company_id, route.database_name))

    session.execute = execute
    monkeypatch.setattr(tenant, "tenant_engine", lambda selected: object())
    monkeypatch.setattr(tenant, "sessionmaker", lambda **kwargs: lambda: session)
    assert tenant.tenant_session(route, security_store=security_store) is session
    assert observed == [security_store], "after_begin must see the flag on the identity query's transaction"
    assert session.info["tenant_company_id"] == 41


def test_tenant_control_factory_requests_security_timeouts(monkeypatch):
    from app.db import session as sessions, tenant

    route = SimpleNamespace(tenant_uuid="tenant-fixture")
    selected = []
    sentinel = object()

    def create(selected_route, *, security_store=False):
        selected.append((selected_route, security_store))
        return sentinel

    monkeypatch.setattr(tenant, "tenant_session", create)
    token = tenant.current_tenant.set(route)
    try:
        assert sessions.ControlSessionLocal() is sentinel
    finally:
        tenant.current_tenant.reset(token)
    assert selected == [(route, True)], "Security counters must stay in the tenant DB with a bounded transaction"


def test_tenant_security_identity_failure_retains_retryable_driver_state(monkeypatch):
    from app.db import tenant

    route = SimpleNamespace(tenant_uuid="tenant-fixture")
    failure = database_failure("55P03")
    session = SimpleNamespace(info={}, closed=False)

    def execute(statement):
        raise failure

    def close():
        session.closed = True

    session.execute = execute
    session.close = close
    monkeypatch.setattr(tenant, "tenant_engine", lambda selected: object())
    monkeypatch.setattr(tenant, "sessionmaker", lambda **kwargs: lambda: session)
    with pytest.raises(OperationalError) as error:
        tenant.tenant_session(route, security_store=True)
    assert error.value is failure
    assert session.closed
