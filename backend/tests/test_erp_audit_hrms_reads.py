"""Read-only reproduction checks for DEF-012 against an isolated organization."""
import pytest
from tests.test_import_workspace import import_headers


@pytest.mark.parametrize("path", [
    "/expenses/employees", "/benefits/enrollments", "/assets/",
    "/assets/insights", "/assets/summary", "/reports/dashboard",
    "/reports/attendance-trend", "/reports/headcount-by-department",
    "/reports/payroll-summary", "/company/departments/", "/attendance/register",
    "/statutory/compliance-summary", "/background-verification/register",
    "/reports/analytics/metric-definitions",
])
def test_audit_hrms_page_reads_do_not_fail(client, db, import_headers, path):
    response = client.get("/api/v1" + path, headers=import_headers, params={"date":"2026-11-13"} if path=="/attendance/register" else {})
    assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"
