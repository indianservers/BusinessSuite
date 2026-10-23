import pytest


@pytest.fixture(autouse=True)
def module_access_uses_test_database(client, db, monkeypatch):
    from app.core.middleware.audit import AuditLogMiddleware
    # Request logging opens a separate production connection; domain audit
    # records still run through the isolated test session in the handlers.
    monkeypatch.setattr(AuditLogMiddleware, "_should_skip", lambda self, request: True)
    # Module gating uses app state rather than FastAPI's get_db override.
    state = client.app.state
    previous_factory = getattr(state, "business_os_session_factory", None)
    previous_close = getattr(state, "business_os_close_session", None)
    state.business_os_session_factory = lambda: db
    state.business_os_close_session = False
    yield
    for name, previous in [("business_os_session_factory", previous_factory), ("business_os_close_session", previous_close)]:
        if previous is None:
            delattr(state, name)
        else:
            setattr(state, name, previous)


@pytest.mark.parametrize("resource,payload,start_field,end_field", [
    ("sales-orders", {"title": "Scheduled delivery"}, "expected_start_date", "expected_end_date"),
    ("contracts", {"title": "Scheduled contract"}, "effective_date", "expiry_date"),
    ("engagements", {"name": "Scheduled engagement"}, "planned_start_date", "planned_end_date"),
])
def test_schedule_dates_persist_validate_and_clear(client, superuser_headers, resource, payload, start_field, end_field):
    created = client.post(f"/api/v1/srm/{resource}", headers=superuser_headers, json=payload)
    assert created.status_code == 201, created.text
    url = f"/api/v1/srm/{resource}/{created.json()['id']}"
    dates = {start_field: "2026-10-20", end_field: "2026-11-12"}
    updated = client.patch(url, headers=superuser_headers, json=dates)
    assert updated.status_code == 200, updated.text
    record = client.get(url, headers=superuser_headers).json()
    assert {key: record[key] for key in dates} == dates
    # Validate against the saved start even when only the end is patched.
    invalid = client.patch(url, headers=superuser_headers, json={end_field: "2026-10-01"})
    assert invalid.status_code == 422, invalid.text
    assert client.get(url, headers=superuser_headers).json()[end_field] == dates[end_field]
    cleared = client.patch(url, headers=superuser_headers, json={start_field: None, end_field: None})
    assert cleared.status_code == 200, cleared.text
    record = client.get(url, headers=superuser_headers).json()
    assert record[start_field] is None and record[end_field] is None
