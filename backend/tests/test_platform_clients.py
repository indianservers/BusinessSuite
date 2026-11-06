"""Client intelligence must remain scoped to the independent owner identity."""
from datetime import timedelta
from tests.test_platform_portal import call, customer, staff_login
from tests.test_public_signup import platform_store, platform_headers, submit, approve
from app.platform_owner.models import PlatformTenant, PlatformRecord
from app.platform_owner import service as s


def test_directory_scope_filters_summary_and_export(client, db, platform_headers, superuser_headers):
    _, _, tenant = customer(client, db, platform_headers)
    tenant.name = "=SUM(1,2)"
    tenant.usage = {"seats": 4, "active_30d": 2, "activated": True, "recorded_at": s.now().isoformat()}
    tenant.config = {**tenant.config, "account_profile": {"priority": "high", "tags": ["priority-account"]}}
    db._platform_db.commit()
    result = call(client, platform_headers, "get", "/client-directory?priority=high&search=priority-account&attention=seat_capacity")
    assert result["total"] == 1 and result["summary"]["seats"] == 4
    assert call(client, platform_headers, "get", "/client-directory?module=project_management")["total"] == 0
    response = client.get("/api/v1/platform/client-directory/export", headers=platform_headers)
    assert response.status_code == 200 and "'=SUM" in response.text
    _, restricted = staff_login(client, db._platform_db, "support", True)
    assert call(client, restricted, "get", "/client-directory")["summary"]["total"] == 0
    call(client, restricted, "get", f"/clients/{tenant.id}/statistics", status=404)
    for path in ["/client-directory", "/client-directory/export", f"/clients/{tenant.id}/statistics"]:
        assert client.get("/api/v1/platform"+path, headers=superuser_headers).status_code == 401


def test_account_profile_versioned_and_owner_only(client, db, platform_headers):
    _, _, tenant = customer(client, db, platform_headers)
    payload = {"version": 0, "priority": "critical", "stage": "at_risk", "tags": [" demo ", "demo"],
        "next_review_at": s.now().isoformat(), "reason": "Client needs onboarding assistance"}
    saved = call(client, platform_headers, "patch", f"/clients/{tenant.id}/profile", payload)
    assert saved["version"] == 1 and saved["tags"] == ["demo"]
    call(client, platform_headers, "patch", f"/clients/{tenant.id}/profile", payload, 409)
    _, support = staff_login(client, db._platform_db, "support")
    call(client, support, "patch", f"/clients/{tenant.id}/profile", {**payload, "version": 1}, 403)
    assert "review_due" in call(client, platform_headers, "get", "/client-directory")["items"][0]["flags"]
    assert call(client, platform_headers, "get", f"/customers/{tenant.id}")["history"][0]["action"] == "tenant.profile_updated"


def test_usage_batch_partial_failure_and_bounded_snapshots(client, db, platform_headers, monkeypatch):
    _, _, first = customer(client, db, platform_headers)
    row = submit(client, db, "second-client@example.com"); approve(client, db, platform_headers, row)
    second = db._platform_db.query(PlatformTenant).filter_by(signup_id=row.id).one()
    from app.platform_owner import bridge
    def usage(_, tenant):
        if tenant.id == second.id: raise RuntimeError("private connection details must not escape")
        return {"seats": 1, "activated": True, "recorded_at": s.now().isoformat()}
    monkeypatch.setattr(bridge, "usage", usage)
    result = call(client, platform_headers, "post", "/client-usage-refresh", {"ids": [first.id, second.id]})
    assert result["items"][0]["ok"] and not result["items"][1]["ok"]
    assert "private connection" not in str(result)
    stats = call(client, platform_headers, "get", f"/clients/{first.id}/statistics")
    assert len(stats["snapshots"]) == 1 and stats["usage"]["seats"] == 1
    call(client, platform_headers, "post", "/client-usage-refresh", {"ids": [first.id]*11}, 422)
    from app.platform_owner.clients import save_usage
    for index in range(35): save_usage(db._platform_db, first, {"seats": index})
    db._platform_db.commit()
    assert db._platform_db.query(PlatformRecord).filter_by(kind="usage_snapshot", tenant_id=first.id).count() == 30


def test_usage_sync_aggregates_exclude_other_company_activity(client, db, platform_headers):
    _, _, tenant = customer(client, db, platform_headers)
    from app.models.audit import AuditLog
    db.add_all([AuditLog(organization_id=tenant.company_id, method="GET", endpoint="/crm/leads", status_code=200),
                AuditLog(organization_id=tenant.company_id+999, method="GET", endpoint="/private", status_code=500)])
    db.commit()
    result = call(client, platform_headers, "post", f"/customers/{tenant.id}/action", {"action": "sync_usage", "reason": "Verify scoped aggregate metrics"})
    usage = result["customer"]["usage"]
    assert usage["requests_30d"] == 1 and usage["server_errors_30d"] == 0
    assert "pms_projects" not in usage["record_counts"]
    assert "endpoint" not in usage and "email" not in usage
    from app.apps.project_management.models import PMSProject, PMSTask
    own = PMSProject(name="Own aggregate project", project_key="OWN", organization_id=tenant.company_id)
    foreign = PMSProject(name="Foreign aggregate project", project_key="FOREIGN", organization_id=tenant.company_id+999)
    db.add_all([own, foreign]); db.flush()
    db.add_all([PMSTask(project_id=own.id, title="Own task", task_key="OWN-1"),
                PMSTask(project_id=foreign.id, title="Foreign task", task_key="FOREIGN-1")])
    db.commit()
    tenant.config = {**tenant.config, "modules": ["crm", "project_management"]}; db._platform_db.commit()
    result = call(client, platform_headers, "post", f"/customers/{tenant.id}/action", {"action": "sync_usage", "reason": "Verify project-scoped task aggregates"})
    assert result["customer"]["usage"]["record_counts"]["pms_tasks"] == 1
    assert result["customer"]["usage"]["record_counts"]["pms_projects"] == 1


def test_trial_and_currency_summary_are_precise(client, db, platform_headers):
    _, _, tenant = customer(client, db, platform_headers)
    tenant.config = {**tenant.config, "trial_ends_at": (s.now()-timedelta(days=1)).isoformat(), "monthly_price_minor": 1000}
    db._platform_db.commit()
    result = call(client, platform_headers, "get", "/client-directory?attention=trial_expired")
    assert result["total"] == 1 and result["summary"]["mrr_by_currency"] == {}
    tenant.status = "active"; tenant.config = {**tenant.config, "currency": "INR"}; db._platform_db.commit()
    assert call(client, platform_headers, "get", "/client-directory")["summary"]["mrr_by_currency"] == {"INR": 1000}


def test_paid_cancellation_resumes_paid_and_offboarding_cannot_be_bypassed(client, db, platform_headers):
    from tests.test_platform_portal import plan
    _, _, tenant = customer(client, db, platform_headers)
    catalogue = plan(client, platform_headers)
    def action(command, values=None, status=200):
        return call(client, platform_headers, "post", f"/customers/{tenant.id}/action", {"action": command, "reason": "Lifecycle regression test", "values": values or {}}, status)
    action("convert_paid", {"plan_id": catalogue["id"]})
    action("cancel"); action("resume")
    assert tenant.status == "active"
    action("cancel"); action("suspend", status=409)
    action("offboard")
    for command in ["cancel", "resume", "suspend", "convert_paid", "resend_invitation", "admin_transfer"]:
        action(command, status=409)
    assert tenant.status == "offboarded"
