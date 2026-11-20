import httpx
import pytest
from pydantic import ValidationError

from app.apps.project_management.schemas import PMSProjectCreateRequest
from app.apps.crm.api import router as crm_router
from app.core.request_limits import expensive


@pytest.mark.parametrize(("field", "value"), [
    ("status", "Invalid"),
    ("billing_status", "Billed"),
    ("actual_cost", 25),
    ("progress_percent", 25),
    ("is_client_visible", True),
])
def test_project_create_request_rejects_invalid_initial_state(field, value):
    with pytest.raises(ValidationError) as error:
        PMSProjectCreateRequest(name="Project", project_key="PRJ", **{field: value})
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize("path", [
    "/api/v1/attendance/biometric/reconcile",
    "/api/v1/attendance/team",
    "/api/v1/crm/dashboard",
    "/api/v1/crm/dashboard/records",
    "/api/v1/crm/statistics/records",
    "/api/v1/fam/dashboard",
    "/api/v1/fam/inventory",
    "/api/v1/fam/inventory/accounting",
    "/api/v1/fam/inventory/dashboard",
    "/api/v1/fam/payables/dashboard",
    "/api/v1/hrms/probation/dashboard",
    "/api/v1/srm/dashboard",
    "/api/v1/srm/profitability",
])
def test_aggregate_dashboards_use_expensive_request_limit(path):
    assert expensive(path)


@pytest.mark.parametrize(("method", "path"), [
    ("GET", "/api/v1/attendance/team"),
    ("GET", "/api/v1/attendance/reports/missing-punches"),
    ("POST", "/api/v1/attendance/biometric/reconcile"),
])
def test_attendance_matrix_requires_a_bounded_date_range(client, superuser_headers, method, path):
    period = {"from_date": "2026-01-01", "to_date": "2026-02-01"}
    request_args = {"json": period} if method == "POST" else {"params": period}
    response = client.request(method, path, headers=superuser_headers, **request_args)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "Choose at most 31 days"


def test_crm_webhook_pins_address_and_bounds_preview(monkeypatch):
    requests = []
    client_class = httpx.Client

    def response_for(request):
        requests.append(request)
        return httpx.Response(202, stream=httpx.ByteStream(b"x" * 5000))

    monkeypatch.setattr(crm_router.settings, "CRM_WEBHOOK_BLOCK_PRIVATE_URLS", True)
    monkeypatch.setattr(crm_router.socket, "getaddrinfo",
                        lambda *args, **kwargs: [(None, None, None, "", ("8.8.8.8", 443))])
    monkeypatch.setattr(crm_router.httpx, "Client",
                        lambda **kwargs: client_class(transport=httpx.MockTransport(response_for), **kwargs))
    status, preview = crm_router._send_webhook("https://hooks.example.test/events?key=value", "{}", {})

    assert status == 202
    assert preview == "x" * 4000
    assert str(requests[0].url) == "https://8.8.8.8/events?key=value"
    assert requests[0].headers["Host"] == "hooks.example.test"
    assert requests[0].extensions["sni_hostname"] == "hooks.example.test"
