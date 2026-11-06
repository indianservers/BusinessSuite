from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
from app.access.models import AccessMembership, AccessPolicy
from app.platform_owner.models import PlatformSignupRequest as SignupRequest
from app.models.user import User, Permission
from app.models.company import Company, Branch
from app.models.email_outbox import EmailOutbox
from app.apps.saas.models import TenantSubscription
from app.shared.starter_values import lead_sources, LEAD_SOURCES

ROOT = "/api/v1/auth"
PASSWORD = "TrialPassword@12345"


def test_approved_signup_includes_starter_sales_setup(client, db, platform_headers):
    from app.apps.crm.models import CRMPipeline, CRMPipelineStage
    row = submit(client, db, email="starter-signup@example.com")
    approved = approve(client, db, platform_headers, row)
    company_id = db._platform_db.get(SignupRequest, row.id).company_id
    pipeline = db.query(CRMPipeline).filter_by(organization_id=company_id).one()
    assert pipeline.active and pipeline.is_default
    stages = db.query(CRMPipelineStage).filter_by(pipeline_id=pipeline.id).order_by(CRMPipelineStage.position).all()
    assert [stage.name for stage in stages] == ["Qualification", "Proposal", "Negotiation", "Won", "Lost"]
    assert lead_sources(db, company_id) == LEAD_SOURCES
    # Retrying provisioning uses its receipt rather than duplicating starters.
    from app.access.signup import provision_signup
    recovered = provision_signup(row, None, db)
    assert recovered["company_id"] == company_id
    assert db.query(CRMPipeline).filter_by(organization_id=company_id).count() == 1


import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.config import settings
from app.core.security import get_password_hash
from app.platform_owner.models import PlatformBase, PlatformAdmin, PlatformRecord
from app.platform_owner.session import get_platform_db


@pytest.fixture(autouse=True)
def platform_store(db, monkeypatch):
    monkeypatch.setattr(settings, "TENANT_DATABASES_ENABLED", False)
    monkeypatch.setattr(settings, "PLATFORM_SECRET_KEY", "isolated-platform-tests-secret-key-0123456789")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    PlatformBase.metadata.create_all(engine)
    with Session(engine) as store:
        db._platform_db = store
        app.dependency_overrides[get_platform_db] = lambda: store
        store.add(PlatformAdmin(email="owner@indianservers.com", hashed_password=get_password_hash(PASSWORD)))
        store.add(PlatformRecord(kind="settings",title="Test settings",data={"require_checklist":False}))
        store.commit()
        yield store
    app.dependency_overrides.pop(get_platform_db, None)
    engine.dispose()


@pytest.fixture
def platform_headers(client, platform_store):
    response = client.post(ROOT + "/platform/login", json={"email": "owner@indianservers.com", "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def submit(client, db, email="prospect@example.com", kind="company"):
    response = client.post(ROOT + "/signup", json={"applicant_type": kind, "name": "Trial Owner", "company_name": "Trial Company" if kind == "company" else None, "email": email, "phone": "+919876543210", "requested_modules": ["crm"], "consent": True})
    assert response.status_code == 202, response.text
    row = db._platform_db.query(SignupRequest).filter_by(email=email).one()
    return row


def approve(client, db, headers, row):
    if not db.query(Permission).filter_by(name="crm_view").first():
        db.add_all([Permission(name="crm_view", module="crm"), Permission(name="crm_manage", module="crm"), Permission(name="crm_admin", module="crm")])
        db.commit()
    response = client.post(ROOT + f"/signup-requests/{row.id}/review", headers=headers, json={"decision": "approve", "reason": "Trial approved after review", "trial_days": 14, "modules": ["crm"]})
    assert response.status_code == 200, response.text
    return response.json()


def activate(client, approved):
    token = parse_qs(urlparse(approved["invitation_url"]).query)["token"][0]
    response = client.post(ROOT + "/reset-password", json={"token": token, "new_password": PASSWORD})
    assert response.status_code == 200, response.text
    return token


def login(client, email):
    response = client.post(ROOT + "/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    assert response.json()["is_superuser"] is False
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_company_sample_import_is_explicit_approved_and_reversible(client, db, platform_headers):
    from app.shared.import_models import ImportBatch
    from app.apps.saas.models import TenantSubscriptionPlan
    row = submit(client, db)
    assert not (row.workflow or {}).get("sample_data_requested")
    assert client.post("/api/v1/imports/sample-data/import", json={"confirmation":"import"}).status_code in {401,403}
    approved = approve(client, db, platform_headers, row)
    assert not db.query(ImportBatch).filter_by(source="company_sample").first()
    activate(client, approved)
    headers = login(client, row.email)
    initial = client.get("/api/v1/imports/sample-data/status", headers=headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()["batch"] is None
    assert client.post("/api/v1/imports/sample-data/import", headers=headers, json={"confirmation":"yes"}).status_code == 422
    imported = client.post("/api/v1/imports/sample-data/import", headers=headers, json={"confirmation":"import"})
    assert imported.status_code == 200, imported.text
    pack = imported.json()["batch"]
    assert pack["total"] >= 300
    repeated = client.post("/api/v1/imports/sample-data/import", headers=headers, json={"confirmation":"import"})
    assert repeated.status_code == 200 and repeated.json()["batch"]["id"] == pack["id"]
    assert db.query(TenantSubscriptionPlan).filter_by(code=f"platform-signup-{row.id}").one().config_json["sample_data_requested"]
    deleted = client.post("/api/v1/imports/sample-data/delete", headers=headers, json={"confirmation":"delete","batch_id":pack["id"]})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["batch"] is None


def test_sample_preference_only_remembered_for_company_opt_in(client, db):
    payload = {"applicant_type":"company", "name":"Sample Owner", "company_name":"Sample Co", "email":"samples@example.com",
               "phone":"+919876543210", "requested_modules":["crm"], "consent":True, "sample_data_requested":True}
    assert client.post(ROOT+"/signup", json=payload).status_code == 202
    assert db._platform_db.query(SignupRequest).filter_by(email="samples@example.com").one().workflow["sample_data_requested"]
    assert client.post(ROOT+"/signup", json={**payload,"applicant_type":"individual","email":"person@example.com"}).status_code == 422


def test_public_signup_is_pending_and_cannot_choose_authority(client, db):
    assert client.get(ROOT + "/signup/options").status_code == 200
    row = submit(client, db)
    assert row.status == "pending" and row.user_id is None and row.company_id is None
    assert not db.query(User).filter_by(email=row.email).first()
    assert client.post(ROOT + "/login", json={"email": row.email, "password": PASSWORD}).status_code in {400, 401, 403}
    response = client.post(ROOT + "/signup", json={"applicant_type": "individual", "name": "Owner", "email": "inject@example.com", "phone": "9999999999", "requested_modules": ["crm"], "consent": True, "is_superuser": True, "company_id": 1})
    assert response.status_code == 422
    assert client.get(ROOT + "/signup-requests").status_code in {401, 403}
    assert client.post(ROOT + f"/signup-requests/{row.id}/review", json={"decision": "approve", "reason": "Unauthorized", "modules": ["crm"]}).status_code in {401, 403}
    submit(client, db)
    assert db._platform_db.query(SignupRequest).count() == 1


def test_approval_activation_and_duplicate_review(client, db, platform_headers):
    existing = Company(name="Existing customer", is_active=True)
    db.add(existing); db.commit()
    existing_id = existing.id
    row = submit(client, db)
    approved = approve(client, db, platform_headers, row)
    db._platform_db.refresh(row)
    user = db.get(User, row.user_id)
    assert not user.is_superuser and not user.is_active
    assert row.company_id != existing_id
    assert db.query(AccessMembership).filter_by(user_id=user.id, company_id=row.company_id, is_admin=True).one()
    policy = db.query(AccessPolicy).filter_by(user_id=user.id).one()
    assert policy.status == "invited" and set(policy.grants) == {"crm"}
    assert policy.grants["crm"]["scope"] == "organization"
    mail = db.query(EmailOutbox).filter_by(event_key=f"signup-approved:{row.id}").one()
    assert mail.status == "held_local" and approved["invitation_url"] in mail.body
    # No active login until the holder of the invitation sets a password.
    assert client.post(ROOT + "/login", json={"email": row.email, "password": PASSWORD}).status_code != 200
    token = activate(client, approved)
    assert client.post(ROOT + "/reset-password", json={"token": token, "new_password": PASSWORD}).status_code == 400
    login(client, row.email)
    repeated = client.post(ROOT + f"/signup-requests/{row.id}/review", headers=platform_headers, json={"decision": "approve", "reason": "Review twice", "modules": ["crm"]})
    assert repeated.status_code == 409


def test_trial_workspace_isolation_and_expiry(client, db, platform_headers):
    first = submit(client, db, "first@example.com")
    second = submit(client, db, "second@example.com", "individual")
    a = approve(client, db, platform_headers, first)
    b = approve(client, db, platform_headers, second)
    activate(client, a); activate(client, b)
    ha, hb = login(client, first.email), login(client, second.email)
    db._platform_db.refresh(first); db._platform_db.refresh(second)
    own = client.post("/api/v1/crm/lead-management/leads", headers=ha, json={"values": {"full_name": "Private first workspace lead", "email": "private-first@example.com"}})
    assert own.status_code == 201, own.text
    ident = own.json()["id"]
    other_list = client.get("/api/v1/crm/lead-management/leads", headers=hb)
    assert other_list.status_code == 200, other_list.text
    assert ident not in {item["id"] for item in other_list.json()["items"]}
    assert client.get(f"/api/v1/crm/lead-management/leads/{ident}", headers=hb).status_code == 404
    assert client.patch(f"/api/v1/crm/lead-management/leads/{ident}", headers=hb, json={"values": {"notes": "stolen"}}).status_code == 404
    assert client.get("/api/v1/crm/lead-management/leads", headers={**hb, "X-Suite-Organization": str(first.company_id)}).status_code == 403
    foreign_branch = db.query(Branch).filter_by(company_id=first.company_id).one()
    assert client.get("/api/v1/crm/lead-management/leads", headers={**hb, "X-Suite-Branch": str(foreign_branch.id)}).status_code == 403
    exported = client.get("/api/v1/crm/lead-management/excel/export", headers=hb)
    assert exported.status_code == 200, exported.text
    import io
    from openpyxl import load_workbook
    assert "private-first@example.com" not in str(list(load_workbook(io.BytesIO(exported.content)).active.values))
    assert client.get(ROOT + "/users", headers=ha).status_code == 403
    assert client.put("/api/v1/access/enterprise/subscription", headers=ha, json={"companyId": first.company_id, "planId": 1, "reason": "Self extend trial"}).status_code == 403
    assert client.get(ROOT + "/signup-requests", headers=ha).status_code == 401
    assert client.post(ROOT + f"/signup-requests/{second.id}/review", headers=ha, json={"decision": "reject", "reason": "Unauthorized"}).status_code == 401
    assert client.get("/api/v1/fam/dashboard", headers=ha).status_code == 403
    sub = db.query(TenantSubscription).filter_by(company_id=first.company_id).one()
    sub.config_json = {**sub.config_json, "grace_until": (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}
    db.commit()
    assert client.get("/api/v1/crm/lead-management/leads", headers=ha).status_code == 403


def test_rejection_never_creates_workspace(client, db, platform_headers):
    row = submit(client, db, kind="individual")
    result = client.post(ROOT + f"/signup-requests/{row.id}/review", headers=platform_headers, json={"decision": "reject", "reason": "Not eligible for trial"})
    assert result.status_code == 200, result.text
    db._platform_db.refresh(row)
    assert row.status == "rejected" and row.company_id is None and row.user_id is None
    assert not db.query(User).filter_by(email=row.email).first()


def test_signup_throttle_and_invalid_requests(client, db):
    base = {"applicant_type": "company", "name": "Trial Owner", "email": "invalid@example.com", "phone": "9999999999", "requested_modules": ["crm"], "consent": True}
    assert client.post(ROOT + "/signup", json=base).status_code == 422
    assert client.post(ROOT + "/signup", json={**base, "company_name": "Valid", "requested_modules": ["security"]}).status_code == 422
    for i in range(10):
        r = client.post(ROOT + "/signup", json={**base, "company_name": "Valid", "email": f"limited{i}@example.com"})
        assert r.status_code == 202, r.text
    assert client.post(ROOT + "/signup", json={**base, "company_name": "Valid"}).status_code == 429


def test_invalid_approval_and_existing_email_cannot_create_or_join_a_tenant(client, db, platform_headers):
    row = submit(client, db)
    count = db.query(Company).count()
    invalid = client.post(ROOT + f"/signup-requests/{row.id}/review", headers=platform_headers, json={"decision": "approve", "reason": "Invalid module request", "modules": ["security"]})
    assert invalid.status_code == 422
    assert db.query(Company).count() == count
    db._platform_db.refresh(row)
    assert row.status == "pending" and row.reviewed_by is None
    # A user created after the public request must never be silently attached.
    from app.core.security import get_password_hash
    db.add(User(email=row.email, hashed_password=get_password_hash(PASSWORD), is_active=True))
    db.commit()
    blocked = client.post(ROOT + f"/signup-requests/{row.id}/review", headers=platform_headers, json={"decision": "approve", "reason": "Email collision", "modules": ["crm"]})
    assert blocked.status_code == 409
    assert db.query(Company).count() == count


def test_signup_migration_round_trip():
    from sqlalchemy import create_engine, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.services.signup_schema import upgrade, downgrade
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE companies (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        operations = Operations(MigrationContext.configure(connection))
        upgrade(operations)
        assert inspect(connection).has_table("suite_signup_requests")
        indexes = inspect(connection).get_indexes("suite_signup_requests")
        assert any(index["unique"] and index["column_names"] == ["email"] for index in indexes)
        downgrade(operations)
        assert not inspect(connection).has_table("suite_signup_requests")
    engine.dispose()


def test_platform_identity_is_separate_from_business_superuser(client, db, superuser_headers, platform_headers):
    row = submit(client, db, "owner-only@example.com")
    assert client.get(ROOT + "/signup-requests", headers=superuser_headers).status_code == 401
    assert client.post(ROOT + f"/signup-requests/{row.id}/review", headers=superuser_headers,
                       json={"decision": "reject", "reason": "Business superuser cannot review"}).status_code == 401
    assert client.get(ROOT + "/signup-requests", headers=platform_headers).json()["total"] == 1
    assert client.get(ROOT + "/me", headers=platform_headers).status_code == 401
    from app.access.models import SignupRequest as LegacySignup
    assert db.query(LegacySignup).count() == 0
    platform_store = db._platform_db
    admin = platform_store.query(PlatformAdmin).one()
    admin.token_version += 1
    platform_store.commit()
    assert client.get(ROOT + "/signup-requests", headers=platform_headers).status_code == 401


def test_owner_commit_failure_recovers_without_duplicate_workspace(client, db, platform_headers, monkeypatch):
    row = submit(client, db, "recover@example.com")
    if not db.query(Permission).filter_by(name="crm_view").first():
        db.add(Permission(name="crm_view", module="crm")); db.commit()
    store = db._platform_db
    real_commit = store.commit
    def fail_owner_commit():
        raise RuntimeError("Simulated platform DB commit failure")
    monkeypatch.setattr(store, "commit", fail_owner_commit)
    payload = {"decision": "approve", "reason": "Recover approval", "modules": ["crm"]}
    with pytest.raises(RuntimeError, match="Simulated platform"):
        client.post(ROOT + f"/signup-requests/{row.id}/review", headers=platform_headers, json=payload)
    store.rollback()
    monkeypatch.setattr(store, "commit", real_commit)
    count = db.query(Company).count()
    assert client.post(ROOT + f"/signup-requests/{row.id}/review", headers=platform_headers,
                       json={"decision": "reject", "reason": "Cannot reject provisioned workspace"}).status_code == 409
    response = client.post(ROOT + f"/signup-requests/{row.id}/review", headers=platform_headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["request"]["status"] == "approved"
    assert db.query(Company).count() == count
    assert db.query(User).filter_by(email=row.email).count() == 1
    from app.platform_owner.models import PlatformAudit
    assert store.query(PlatformAudit).filter_by(signup_id=row.id).count() == 1
