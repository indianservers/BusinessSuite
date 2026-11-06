import pytest
from sqlalchemy import select
from app.models.company import Company, Branch
from app.models.leave import LeaveType
from app.models.payroll import SalaryComponent
from app.models.security_boundary import SecurityResourceOwnership
from app.apps.crm.models import CRMPipeline
from app.shared.starter_values import populate, lead_sources, LEAD_SOURCES
from tests.test_settings_hub import actor, BASE


def owned(db, model, company):
    return db.connection().execute(select(model.__table__).where(model.id.in_(select(SecurityResourceOwnership.resource_id).where(
        SecurityResourceOwnership.resource_table == model.__tablename__, SecurityResourceOwnership.company_id == company)))).mappings().all()


def test_starters_are_owned_repeatable_and_preserve_customization(db):
    db.add_all([Company(id=1, name="First"), Company(id=2, name="Second")])
    db.flush()
    branches = [Branch(name="Main", company_id=company) for company in [1, 2]]
    db.add_all(branches); db.flush()
    for company, branch in zip([1, 2], branches):
        result = populate(db, company, branch.id, {"hrms", "crm", "fam"})
        assert result["leave_types"] == 3
        assert len(owned(db, LeaveType, company)) == 3
        assert len(owned(db, SalaryComponent, company)) == 4
        assert all(row["amount"] == 0 for row in owned(db, SalaryComponent, company))
        assert lead_sources(db, company) == LEAD_SOURCES
        assert populate(db, company, branch.id, {"hrms", "crm", "fam"}) == {}
    row = owned(db, LeaveType, 1)[0]
    db.connection().execute(LeaveType.__table__.update().where(LeaveType.id == row["id"]).values(name="Our custom leave", days_allowed=23, is_active=False))
    assert populate(db, 1, branches[0].id, {"hrms"}) == {}
    updated = db.connection().execute(select(LeaveType.__table__).where(LeaveType.id == row["id"])).mappings().one()
    assert updated["name"] == "Our custom leave" and updated["days_allowed"] == 23 and not updated["is_active"]
    with pytest.raises(ValueError):
        populate(db, 1, branches[1].id, {"hrms"})


def test_starter_endpoint_permissions_and_enabled_modules(client, db):
    employee, _ = actor(db)
    assert client.get(BASE + "/starter-values/catalog", headers=employee).status_code == 403
    assert client.post(BASE + "/starter-values/apply", headers=employee, json={"modules": ["hrms"]}).status_code == 403
    admin, _ = actor(db, superuser=True, role="starter_admin")
    branch = Branch(name="Main", company_id=1); db.add(branch); db.commit()
    response = client.post(BASE + "/starter-values/apply", headers=admin, json={"modules": ["hrms", "crm", "fam"]})
    assert response.status_code == 200, response.text
    assert response.json()["total"] > 0
    scoped = {**admin, "X-Suite-Branch": str(branch.id)}
    for endpoint, expected in [("/leave/types", "Casual Leave"), ("/payroll/components", "Basic Salary")]:
        listed = client.get("/api/v1" + endpoint, headers=scoped)
        assert listed.status_code == 200, listed.text
        assert expected in listed.text
    assert client.post(BASE + "/starter-values/apply", headers=admin, json={"modules": ["hrms", "crm", "fam"]}).json()["total"] == 0
    assert client.post(BASE + "/starter-values/apply", headers=admin, json={"modules": ["unknown"]}).status_code == 422


def test_custom_lead_sources_feed_defaults_and_do_not_overwrite_workflows(client, db):
    admin, user = actor(db, superuser=True)
    from app.apps.crm.lead_models import CRMLeadManagementConfig
    config = CRMLeadManagementConfig(organization_id=1, settings_json={"slaHours": 48})
    db.add(config); db.commit()
    endpoint = BASE + "/crm-lead-sources/options"
    result = client.put(endpoint, headers=admin, json={"sources": ["Website", "Trade Show"]})
    assert result.status_code == 200, result.text
    assert result.json()["sources"] == ["Website", "Trade Show", "Other"]
    db.refresh(config)
    assert config.settings_json["slaHours"] == 48
    assert client.get(BASE + "/defaults/effective", headers=admin).json()["leadSources"] == result.json()["sources"]
    fields = client.get(BASE + "/defaults/configuration", headers=admin).json()["fields"]
    assert next(field for field in fields if field["key"] == "lead_source")["options"][1]["value"] == "Trade Show"
    saved = client.put(BASE + "/defaults/configuration", headers=admin, json={"version": 0, "values": {"lead_source": "Trade Show"}})
    assert saved.status_code == 200, saved.text
    workflow = client.get("/api/v1/crm/lead-management/settings", headers=admin)
    assert workflow.status_code == 200, workflow.text
    saved_workflow = client.put("/api/v1/crm/lead-management/settings", headers=admin, json=workflow.json()["settings"])
    assert saved_workflow.status_code == 200, saved_workflow.text
    assert lead_sources(db, 1) == ["Website", "Trade Show", "Other"]
    for values in [[], ["Website", "website"], [" "], ["x" * 81]]:
        assert client.put(endpoint, headers=admin, json={"sources": values}).status_code == 422
    db.add(Company(id=2, name="Other company")); db.commit()
    assert lead_sources(db, 2) == LEAD_SOURCES


def test_existing_sales_pipeline_is_preserved(db):
    db.add(Company(id=1, name="Existing")); db.flush()
    branch = Branch(name="Main", company_id=1); db.add(branch); db.flush()
    db.add(CRMPipeline(organization_id=1, name="Custom disabled pipeline", active=False)); db.flush()
    populate(db, 1, branch.id, {"crm"})
    assert db.query(CRMPipeline).count() == 1
