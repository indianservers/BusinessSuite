from tests.fam_test_utils import auth_headers_for, fam_admin_headers


def test_fam_role_without_permission_is_blocked(client, db):
    headers = auth_headers_for(client, db, "blocked@fam.example.com", "non_fam_employee")
    response = client.get("/api/v1/fam/module-info", headers=headers)
    assert response.status_code == 403


def test_fam_viewer_can_view_but_cannot_mutate_chart(client, db):
    headers = auth_headers_for(client, db, "viewer@fam.example.com", "fam_viewer", permissions=["fam_view", "fam_chart_view"])
    assert client.get("/api/v1/fam/module-info", headers=headers).status_code == 200
    response = client.post("/api/v1/fam/ledger-groups", headers=headers, json={
        "group_name": "Viewer Group",
        "group_code": "VIEW",
        "nature": "asset",
        "sequence_order": 1,
    })
    assert response.status_code == 403


def test_fam_admin_can_reach_all_foundation_apis(client, db):
    headers = fam_admin_headers(client, db)
    for path in [
        "/api/v1/fam/module-info",
        "/api/v1/fam/dashboard",
        "/api/v1/fam/settings",
        "/api/v1/fam/financial-years",
        "/api/v1/fam/ledger-groups",
        "/api/v1/fam/ledgers",
        "/api/v1/fam/opening-balances",
        "/api/v1/fam/cost-centers",
        "/api/v1/fam/branches",
        "/api/v1/fam/audit-logs",
        "/api/v1/fam/chart-of-accounts",
    ]:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, f"{path}: {response.text}"
