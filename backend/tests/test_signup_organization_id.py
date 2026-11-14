"""Organization references survive review and respect platform visibility."""
from tests.test_public_signup import platform_store, platform_headers, submit, approve, activate, login
from tests.test_platform_portal import call, staff_login
from app.platform_owner.models import PlatformTenant, PlatformSignupRequest
from app.platform_owner import service as s


def test_organization_reference_lifecycle(client, db, platform_headers):
    first = submit(client, db)
    second = submit(client, db, "individual-org@example.com", kind="individual")
    reference = first.organization_id
    assert reference.startswith("ORG-") and reference != second.organization_id
    listing = call(client, platform_headers, "get", f"/signups?search={reference}")
    assert [r["id"] for r in listing["items"]] == [first.id]
    assert listing["items"][0]["organization_id"] == reference
    assert reference in client.get("/api/v1/platform/signup-export", headers=platform_headers).text
    # Existing records require no migration or mutable identifier backfill.
    db._platform_db.expire_all()
    assert db._platform_db.get(PlatformSignupRequest, first.id).organization_id == reference
    approved = approve(client, db, platform_headers, first)
    assert approved["request"]["organization_id"] == reference
    tenant = db._platform_db.query(PlatformTenant).filter_by(signup_id=first.id).one()
    assert tenant.organization_id == reference
    assert call(client, platform_headers, "get", f"/customers/{tenant.id}")["organization_id"] == reference
    directory = call(client, platform_headers, "get", f"/client-directory?search={reference.lower()}")
    assert [r["id"] for r in directory["items"]] == [tenant.id]
    assert reference in client.get("/api/v1/platform/client-directory/export", headers=platform_headers).text
    found = call(client, platform_headers, "get", f"/search?q={reference}")
    assert found["signups"][0]["organization_id"] == found["customers"][0]["organization_id"] == reference
    _, restricted = staff_login(client, db._platform_db, "support", True)
    assert call(client, restricted, "get", f"/signups?search={reference}&status=all")["total"] == 0
    assert call(client, restricted, "get", f"/client-directory?search={reference}")["total"] == 0
    assert call(client, restricted, "get", f"/search?q={reference}") == {"signups": [], "customers": []}


def test_manual_signup_and_private_status_include_organization(client, db, platform_headers):
    row = call(client, platform_headers, "post", "/signups", {
        "applicant_type": "company", "name": "Organization Owner", "company_name": "Organization Test",
        "email": "manual-org@example.com", "phone": "+919876543210", "requested_modules": ["crm"],
        "consent": True, "consent_evidence": "Customer requested an application",
    }, status=201)
    signup = db._platform_db.get(PlatformSignupRequest, row["id"])
    assert row["organization_id"] == signup.organization_id
    link = call(client, platform_headers, "post", f"/signups/{signup.id}/tracking-link")
    token = link["url"].rsplit("/", 1)[-1]
    response = client.get(f"/api/v1/platform/public/{token}")
    assert response.status_code == 200, response.text
    assert response.json()["organization_id"] == signup.organization_id
    assert s.encode(signup)["organization_id"] == signup.organization_id


def test_signed_in_identity_matches_platform_and_handles_older_signups(client, db, platform_headers):
    from app.apps.saas.models import TenantSubscription
    row = submit(client, db, "profile-organization@example.com")
    activate(client, approve(client, db, platform_headers, row))
    headers = login(client, row.email)
    db._platform_db.refresh(row)
    for legacy in (False, True):
        if legacy:
            subscription = db.query(TenantSubscription).filter_by(company_id=row.company_id).one()
            subscription.config_json = {k: v for k, v in subscription.config_json.items() if k != "organization_id"}
            db.commit()
        response = client.get("/api/v1/access/me", headers=headers)
        assert response.status_code == 200, response.text
        access = response.json()
        assert access["organizationId"] == row.organization_id
        assert access["organizations"] == [{"id": row.company_id, "name": row.company_name, "organizationId": row.organization_id}]
    from app.access.models import AccessMembership
    second = submit(client, db, "other-profile-organization@example.com")
    approve(client, db, platform_headers, second)
    db._platform_db.refresh(second)
    # Another organization remains undiscoverable until membership is granted.
    assert client.get("/api/v1/access/me", headers={**headers, "X-Suite-Organization": str(second.company_id)}).status_code == 403
    db.add(AccessMembership(user_id=row.user_id, company_id=second.company_id, active=True))
    db.commit()
    switched = client.get("/api/v1/access/me", headers={**headers, "X-Suite-Organization": str(second.company_id)})
    assert switched.status_code == 200, switched.text
    assert switched.json()["organizationId"] == second.organization_id
    assert {org["organizationId"] for org in switched.json()["organizations"]} == {row.organization_id, second.organization_id}


def test_references_do_not_reuse_another_company_signup_receipt(db):
    from app.access.organization_identity import organization_references
    from app.models.company import Company
    from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
    first, second = Company(name="Existing organization"), Company(name="Other organization")
    db.add_all([first, second]); db.flush()
    plan = TenantSubscriptionPlan(code="platform-signup-42", name="Legacy trial", config_json={"platform_provisioning": {"company_id": first.id}})
    db.add(plan); db.flush()
    db.add_all([TenantSubscription(company_id=first.id, plan_id=plan.id), TenantSubscription(company_id=second.id, plan_id=plan.id)])
    db.flush()
    assert organization_references(db, [first.id, second.id]) == {first.id: "ORG-100000042", second.id: f"ORG-C-{second.id}"}
    assert organization_references(db, []) == {}
