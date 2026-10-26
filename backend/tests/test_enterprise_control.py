import pytest
import json
from datetime import datetime, timezone
from app.apps.crm.models import CRMLead
from app.apps.saas.models import TenantSubscriptionPlan, TenantSubscription
from app.apps.business_os.models import BOSFeatureFlag
from app.access.models import AccessMembership, AccessPolicy
from app.models.user import User
from app.models.audit import AuditLog
from app.models.company import Company
from app.shared.models import ServicePolicy
from app.enterprise.controls import evaluate_flag
from tests.test_shared_services import shared_setup, access_account
from tests.test_suite_access import login

ROOT = "/api/v1/access/enterprise"


def plan_body(**updates):
    return dict(
        companyId=1,
        version=0,
        reason="Configure verified subscription",
        code="enterprise-test",
        name="Enterprise test",
        modules=["crm"],
        seats=100,
        storageMb=100,
        aiRequests=100,
        automationRuns=100,
        apiRequests=10000,
        **updates,
    )


def test_real_catalog_health_and_masked_errors(client, db, shared_setup):
    headers, user, lead = shared_setup
    db.add(
        AuditLog(
            organization_id=1,
            user_id=user.id,
            method="GET",
            endpoint="/api/v1/test/{id}",
            module="crm",
            status_code=500,
            duration_ms=25,
            error_type="ControlledTestError",
            description="password=secret-do-not-expose",
        )
    )
    db.add(
        AuditLog(
            organization_id=999,
            user_id=user.id,
            method="GET",
            endpoint="/foreign/private",
            module="hrms",
            status_code=500,
            error_type="ForeignError",
        )
    )
    db.commit()
    catalog = client.get(ROOT + "/catalog", headers=headers)
    assert catalog.status_code == 200, catalog.text
    assert any(m["key"] == "crm" for m in catalog.json()["modules"])
    health = client.get(ROOT + "/health", headers=headers)
    assert health.status_code == 200, health.text
    assert health.json()["database"]["status"] == "healthy"
    assert health.json()["frontend"]["status"] == "unknown"
    assert health.json()["api"]["errors"] == 1
    errors = client.get(ROOT + "/errors", headers=headers)
    assert errors.status_code == 200, errors.text
    assert (
        "secret-do-not-expose" not in errors.text and "ForeignError" not in errors.text
    )
    assert errors.json()["items"][0]["type"] == "ControlledTestError"


def test_licensing_reuses_plans_and_enforces_native_api(client, db, shared_setup):
    headers, user, lead = shared_setup
    response = client.post(ROOT + "/plans", headers=headers, json=plan_body())
    assert response.status_code == 200, response.text
    plan = response.json()
    assert (
        db.query(TenantSubscriptionPlan).filter_by(code="enterprise-test").count() == 1
    )
    response = client.put(
        ROOT + "/subscription",
        headers=headers,
        json={
            "companyId": 1,
            "version": 0,
            "planId": plan["id"],
            "reason": "Enable explicit company entitlements",
        },
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/crm/leads", headers=headers).status_code == 200
    assert (
        client.get("/api/v1/project-management/projects", headers=headers).status_code
        == 403
    )
    assert (
        client.get(ROOT + "/subscription", headers=headers).json()["subscription"][
            "planId"
        ]
        == plan["id"]
    )
    assert (
        client.put(
            ROOT + "/subscription",
            headers=headers,
            json={
                "companyId": 1,
                "version": 0,
                "planId": plan["id"],
                "reason": "Stale update must fail",
            },
        ).status_code
        == 409
    )


def test_scoped_analytics_cannot_aggregate_another_company_or_owner(
    client, db, shared_setup
):
    headers, user, lead = shared_setup
    other = Company(name="Analytics foreign company")
    db.add(other)
    db.flush()
    db.add_all(
        [
            CRMLead(
                organization_id=other.id,
                owner_user_id=user.id,
                first_name="Foreign",
                full_name="Foreign",
                status="New",
            ),
            CRMLead(
                organization_id=1,
                owner_user_id=db.query(User).filter(User.id != user.id).first().id,
                first_name="Unrelated",
                full_name="Unrelated",
                status="New",
            ),
        ]
    )
    membership = AccessMembership(
        company_id=1, user_id=user.id, is_admin=True, active=True
    )
    db.add(membership)
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=user.id).one()
    policy.grants = {
        **policy.grants,
        "crm": {**policy.grants["crm"], "scope": "own"},
        "hrms": {**policy.grants.get("hrms", {}), "enabled": False},
    }
    db.commit()
    user_headers = login(client, user.email)
    response = client.get(
        ROOT + "/analytics",
        headers=user_headers,
        params={"companyId": 1, "source": "crm_leads"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["count"] == 1, response.text
    assert (
        client.get(
            ROOT + "/analytics",
            headers=user_headers,
            params={"companyId": other.id, "source": "crm_leads"},
        ).status_code
        == 403
    )
    assert (
        client.get(
            ROOT + "/analytics",
            headers=user_headers,
            params={"companyId": 1, "source": "employees"},
        ).status_code
        == 403
    )


def test_flag_targeting_is_stable_and_cannot_override_disabled_access(
    client, db, shared_setup, monkeypatch
):
    headers, user, lead = shared_setup
    from app.core.config import settings

    body = {
        "companyId": 1,
        "version": 0,
        "reason": "Enable controlled rollout",
        "module": "crm",
        "key": "crm.beta",
        "name": "CRM beta",
        "ownerId": user.id,
        "enabled": True,
        "environment": settings.ENVIRONMENT,
        "percentage": 37,
        "users": [user.id],
    }
    response = client.put(ROOT + "/flags", headers=headers, json=body)
    assert response.status_code == 200, response.text
    a = evaluate_flag(db, user, 1, "crm", "crm.beta")
    b = evaluate_flag(db, user, 1, "crm", "crm.beta")
    assert a == b
    assert db.query(BOSFeatureFlag).filter_by(flag_key="crm.beta").count() == 1
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=user.id).one()
    policy.grants = {**policy.grants, "crm": {**policy.grants["crm"], "enabled": False}}
    db.commit()
    db.info.pop("suite_access_policies", None)
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        evaluate_flag(db, user, 1, "crm", "crm.beta")


def test_brand_contrast_governance_and_optimistic_versions(client, db, shared_setup):
    headers, user, lead = shared_setup
    body = {
        "companyId": 1,
        "version": 0,
        "reason": "Configure accessible company theme",
        "kind": "branding",
        "key": "theme",
        "values": {
            "appName": "Central workspace",
            "text": "#eeeeee",
            "surface": "#ffffff",
        },
    }
    assert client.put(ROOT + "/policies", headers=headers, json=body).status_code == 422
    body["values"]["text"] = "#171717"
    body["values"]["primary"] = "#ffffff"
    assert client.put(ROOT + "/policies", headers=headers, json=body).status_code == 422
    body["values"]["primary"] = "#6d28d9"
    response = client.put(ROOT + "/policies", headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert (
        client.get(ROOT + "/branding", headers=headers).json()["values"]["appName"]
        == "Central workspace"
    )
    assert client.put(ROOT + "/policies", headers=headers, json=body).status_code == 409
    restricted = {
        "companyId": 1,
        "version": 0,
        "reason": "Protect sensitive source data",
        "kind": "governance",
        "key": "crm:lead",
        "values": {
            "module": "crm",
            "entity": "lead",
            "classification": "restricted",
            "allowedRoles": [],
            "legalHold": True,
        },
    }
    assert (
        client.put(ROOT + "/policies", headers=headers, json=restricted).status_code
        == 200
    )
    from app.shared.gateway import ModuleServices
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        ModuleServices(db, user, 1, "crm").read("lead", lead.id)


def test_support_tenant_boundaries_comments_and_diagnostics(client, db, shared_setup):
    headers, user, lead = shared_setup
    body = {
        "companyId": 1,
        "version": 0,
        "reason": "Record controlled incident",
        "subject": "Controlled failed workflow",
        "description": "Actual failed workflow requires investigation",
        "module": "crm",
        "kind": "incident",
        "priority": "High",
        "assignedTo": user.id,
    }
    response = client.post(ROOT + "/tickets", headers=headers, json=body)
    assert response.status_code == 201, response.text
    ticket = response.json()
    response = client.put(
        ROOT + f"/tickets/{ticket['id']}",
        headers=headers,
        json={
            "companyId": 1,
            "version": ticket["version"],
            "reason": "Triage observed incident",
            "status": "In Progress",
            "assignedTo": user.id,
            "comment": "Investigating observed execution failure",
        },
    )
    assert response.status_code == 200, response.text
    comments = client.get(ROOT + f"/tickets/{ticket['id']}/comments", headers=headers)
    assert len(comments.json()) == 1
    bundle = client.get(ROOT + "/diagnostics", headers=headers)
    assert bundle.status_code == 200, bundle.text
    assert "hashed_password" not in bundle.text and "secret_ref" not in bundle.text
    assert (
        client.post(
            ROOT + "/tickets", headers=headers, json={**body, "assignedTo": 999999}
        ).status_code
        == 422
    )


def test_user_cannot_access_enterprise_controls(client, shared_setup):
    headers, user, lead = shared_setup
    user_headers = login(client, user.email)
    for path in ("/plans", "/health", "/errors", "/tickets", "/backups", "/catalog"):
        assert client.get(ROOT + path, headers=user_headers).status_code == 403, path


def test_existing_backup_roundtrip_to_offline_sqlite(tmp_path, monkeypatch):
    import sqlite3
    from sqlalchemy import create_engine, text
    from app.core.config import settings
    from app.services.data_backups import (
        create_archive,
        verify_archive,
        extract_archive,
    )

    source = create_engine("sqlite:///" + str(tmp_path / "source.sqlite3"))
    with source.begin() as conn:
        conn.execute(
            text("CREATE TABLE recovery_probe (id INTEGER PRIMARY KEY, value TEXT)")
        )
        conn.execute(
            text("INSERT INTO recovery_probe VALUES (1, 'verified original data')")
        )
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "probe.txt").write_text("actual file bytes")
    monkeypatch.setenv("BUSINESSSUITE_BACKUP_DIR", str(tmp_path / "archives"))
    monkeypatch.setattr(settings, "SERVERLESS", False)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(uploads))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    row = create_archive(engine=source)
    path = tmp_path / "archives" / (row["id"] + ".zip")
    manifest = verify_archive(path)
    assert manifest["database"] == "sqlite"
    restored = extract_archive(path, tmp_path / "offline-restore")
    with sqlite3.connect(restored / "database.sqlite3") as connection:
        assert (
            connection.execute(
                "SELECT value FROM recovery_probe WHERE id=1"
            ).fetchone()[0]
            == "verified original data"
        )
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert (restored / "uploads" / "probe.txt").read_text() == "actual file bytes"
    with pytest.raises(FileExistsError):
        extract_archive(path, restored)
    source.dispose()


def test_dashboard_ownership_sharing_and_alert_dedup(client, db, shared_setup):
    headers, user, lead = shared_setup
    from app.models.user import User

    admin_id = db.query(User.id).filter(User.is_superuser.is_(True)).first()[0]
    body = {
        "companyId": 1,
        "version": 0,
        "reason": "Persist authorized dashboard layout",
        "kind": "dashboard",
        "key": f"user:{admin_id}:test",
        "values": {
            "name": "Verified dashboard",
            "widgets": [
                {
                    "source": "crm_leads",
                    "type": "line",
                    "width": 2,
                    "title": "Lead creation",
                }
            ],
            "sharedRoles": [],
        },
    }
    response = client.put(ROOT + "/policies", headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert (
        client.get(
            ROOT + "/policies",
            headers=headers,
            params={"companyId": 1, "kind": "dashboard"},
        ).json()[0]["values_json"]["name"]
        == "Verified dashboard"
    )
    assert (
        client.put(
            ROOT + "/policies",
            headers=headers,
            json={**body, "key": f"user:{user.id}:test"},
        ).status_code
        == 403
    )
    now = datetime.now(timezone.utc)
    for i in range(5):
        db.add(
            AuditLog(
                organization_id=1,
                user_id=user.id,
                method="GET",
                endpoint="/controlled/{id}",
                module="crm",
                status_code=500,
                error_type="ControlledError",
                created_at=now,
            )
        )
    db.commit()
    command = {"companyId": 1, "reason": "Evaluate observed operational errors"}
    first = client.post(ROOT + "/alerts/evaluate", headers=headers, json=command)
    second = client.post(ROOT + "/alerts/evaluate", headers=headers, json=command)
    assert first.status_code == 200, first.text
    assert first.json()["created"] >= 1
    assert second.json()["created"] == 0


def test_internal_legacy_config_cannot_bypass_central_governance(
    client, db, shared_setup
):
    headers, user, lead = shared_setup
    from app.models.user import Permission

    permission = db.query(Permission).filter_by(name="tenant_admin").first()
    if not permission:
        permission = Permission(name="tenant_admin", module="saas")
        db.add(permission)
    user.role.permissions.append(permission)
    db.commit()
    user_headers = login(client, user.email)
    for path in ["/api/v1/admin/subscription", "/api/v1/admin/feature-flags"]:
        response = client.get(path, headers=user_headers)
        assert response.status_code in {403, 404}, response.text


def test_postgres_backup_and_restore_into_disposable_database(
    db, tmp_path, monkeypatch
):
    if db.get_bind().dialect.name != "postgresql":
        pytest.skip("PostgreSQL recovery profile")
    import subprocess, time
    from sqlalchemy import create_engine, text
    from app.core.config import settings
    from app.services.data_backups import create_archive, extract_archive, postgres_args

    source = db.get_bind().engine
    url = source.url
    assert url.database.startswith("business_suite_") and url.database.endswith("_test")
    target_name = "business_suite_phase3_restore_test"
    assert target_name != url.database
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "recovery.txt").write_text("postgres recovery file evidence")
    monkeypatch.setenv("BUSINESSSUITE_BACKUP_DIR", str(tmp_path / "archives"))
    monkeypatch.setattr(settings, "SERVERLESS", False)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(uploads))
    with source.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE enterprise_restore_probe (id INTEGER PRIMARY KEY, value TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO enterprise_restore_probe VALUES (1,'verified PostgreSQL recovery')"
            )
        )
    started = time.perf_counter()
    row = create_archive(engine=source)
    directory = extract_archive(
        tmp_path / "archives" / (row["id"] + ".zip"), tmp_path / "offline"
    )
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    target = None
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(
                'DROP DATABASE IF EXISTS "business_suite_phase3_restore_test" WITH (FORCE)'
            )
            connection.exec_driver_sql(
                'CREATE DATABASE "business_suite_phase3_restore_test"'
            )
        helper, env = postgres_args(url.set(database=target_name))
        subprocess.run(
            [
                helper.postgres_tool("pg_restore"),
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                "--single-transaction",
                "--dbname",
                target_name,
                str(directory / "database.dump"),
            ],
            env=env,
            check=True,
            capture_output=True,
            timeout=180,
        )
        target = create_engine(url.set(database=target_name))
        with target.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT value FROM enterprise_restore_probe WHERE id=1")
                ).scalar()
                == "verified PostgreSQL recovery"
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM alembic_version")
                ).scalar()
                == 1
            )
        assert (
            directory / "uploads" / "recovery.txt"
        ).read_text() == "postgres recovery file evidence"
        from pathlib import Path

        Path("../docs/qa/suite-access/phase3-recovery.json").write_text(
            json.dumps(
                {
                    "database": "isolated disposable PostgreSQL database",
                    "restored": True,
                    "probeData": "verified",
                    "schemaMigrationHead": "verified present",
                    "fileBytes": "verified",
                    "elapsedSeconds": round(time.perf_counter() - started, 2),
                    "productionRtoMeasured": False,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        if target:
            target.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql(
                'DROP DATABASE IF EXISTS "business_suite_phase3_restore_test" WITH (FORCE)'
            )
        admin.dispose()
        with source.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS enterprise_restore_probe"))


def test_governance_blocks_native_bypass_and_recovery_self_approval(
    client, db, shared_setup
):
    headers, user, lead = shared_setup
    body = {
        "companyId": 1,
        "version": 0,
        "reason": "Protect native records consistently",
        "kind": "governance",
        "key": "crm:lead",
        "values": {
            "module": "crm",
            "entity": "lead",
            "classification": "restricted",
            "allowedRoles": [],
            "legalHold": True,
        },
    }
    response = client.put(ROOT + "/policies", headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert (
        client.get("/api/v1/crm/leads", headers=login(client, user.email)).status_code
        == 403
    )
    recovery = {
        "companyId": 1,
        "version": 0,
        "reason": "Request isolated recovery review",
        "kind": "recovery_request",
        "key": "test-recovery",
        "values": {
            "backupId": "a" * 32,
            "environment": "non-production",
            "procedure": "Use verified offline restoration into an empty isolated database",
            "status": "requested",
        },
    }
    response = client.put(ROOT + "/policies", headers=headers, json=recovery)
    assert response.status_code == 200, response.text
    recovery["version"] = response.json()["version"]
    recovery["values"]["status"] = "approved"
    assert (
        client.put(ROOT + "/policies", headers=headers, json=recovery).status_code
        == 403
    )
    recovery["values"]["environment"] = "production"
    assert (
        client.put(ROOT + "/policies", headers=headers, json=recovery).status_code
        == 422
    )


def test_subscription_seats_and_shared_quota_enforcement(client, db, shared_setup):
    headers, user, lead = shared_setup
    body = plan_body()
    body.update(seats=2, aiRequests=0, automationRuns=0, storageMb=1)
    response = client.post(ROOT + "/plans", headers=headers, json=body)
    assert response.status_code == 200, response.text
    plan = response.json()
    response = client.put(
        ROOT + "/subscription",
        headers=headers,
        json={
            "companyId": 1,
            "version": 0,
            "planId": plan["id"],
            "reason": "Apply actual shared consumption limits",
        },
    )
    assert response.status_code == 200, response.text
    from app.enterprise.controls import quota
    from fastapi import HTTPException

    for metric, amount in [
        ("seats", 1),
        ("ai_requests", 1),
        ("automation_runs", 1),
        ("storage_mb", 2 * 1024 * 1024),
    ]:
        with pytest.raises(HTTPException) as blocked:
            quota(db, 1, metric, amount)
        assert blocked.value.status_code == 429
    response = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"email": "over-limit@example.com", "password": "Valid@123456"},
    )
    assert response.status_code == 429, response.text


def test_business_api_quota_and_flag_rollback_are_real(client, db, shared_setup):
    headers, user, lead = shared_setup
    body = plan_body()
    body["apiRequests"] = 1
    plan = client.post(ROOT + "/plans", headers=headers, json=body).json()
    response = client.put(
        ROOT + "/subscription",
        headers=headers,
        json={
            "companyId": 1,
            "version": 0,
            "planId": plan["id"],
            "reason": "Apply one observed API request allowance",
        },
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/crm/leads", headers=headers).status_code == 200
    assert client.get("/api/v1/crm/leads", headers=headers).status_code == 429
    # The administration plane stays available to repair entitlement settings.
    assert client.get(ROOT + "/subscription", headers=headers).status_code == 200
    from app.core.config import settings

    flag = {
        "companyId": 1,
        "version": 0,
        "reason": "Create controlled feature snapshot",
        "module": "crm",
        "key": "rollback.beta",
        "name": "Rollback beta",
        "ownerId": user.id,
        "enabled": True,
        "environment": settings.ENVIRONMENT,
    }
    first = client.put(ROOT + "/flags", headers=headers, json=flag)
    assert first.status_code == 200, first.text
    flag.update(version=1, enabled=False)
    assert client.put(ROOT + "/flags", headers=headers, json=flag).status_code == 200
    rollback = client.post(
        ROOT + f"/flags/{first.json()['id']}/rollback",
        headers=headers,
        json={
            "companyId": 1,
            "version": 2,
            "reason": "Restore prior controlled rollout",
        },
    )
    assert rollback.status_code == 200, rollback.text
    assert rollback.json()["enabled"] is True
    assert rollback.json()["value_json"]["version"] == 3


def test_new_error_occurrence_reopens_resolved_group(client, db, shared_setup):
    from datetime import timedelta

    headers, user, lead = shared_setup
    now = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            organization_id=1,
            user_id=user.id,
            method="GET",
            endpoint="/error-reopen",
            module="crm",
            status_code=500,
            error_type="ReopenError",
            created_at=now,
        )
    )
    db.commit()
    group = client.get(ROOT + "/errors", headers=headers).json()["items"][0]
    response = client.put(
        ROOT + "/policies",
        headers=headers,
        json={
            "companyId": 1,
            "version": 0,
            "reason": "Mark controlled failure resolved",
            "kind": "error_resolution",
            "key": group["key"],
            "values": {"status": "resolved", "notes": "Controlled verification"},
        },
    )
    assert response.status_code == 200, response.text
    db.add(
        AuditLog(
            organization_id=1,
            user_id=user.id,
            method="GET",
            endpoint="/error-reopen",
            module="crm",
            status_code=500,
            error_type="ReopenError",
            created_at=now + timedelta(minutes=1),
        )
    )
    db.commit()
    response = client.get(ROOT + "/errors", headers=headers)
    assert response.json()["items"][0]["status"] == "open", response.text
