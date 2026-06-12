from app.apps.business_os.models import BOSLifecycleEvent
from app.apps.business_os.services.module_service import enabled_module_keys, ensure_business_os_seed
from app.apps.crm.models import CRMLead
from app.main import app


def test_business_os_module_enable_disable_api_blocking_and_preservation(client, db, superuser_headers):
    app.state.business_os_session_factory = lambda: db
    app.state.business_os_close_session = False
    try:
        ensure_business_os_seed(db, company_id=1)
        preserved = CRMLead(organization_id=1, first_name="Preserved", last_name="Lead", full_name="Preserved Lead", company_name="Historical CRM", status="New", source="Manual")
        db.add(preserved)
        db.commit()

        response = client.put("/api/v1/business-os/modules", headers=superuser_headers, json={"enabled_modules": ["srm", "project_management"]})
        assert response.status_code == 200
        assert set(response.json()["enabled_modules"]) == {"srm", "project_management"}
        assert "crm" not in enabled_module_keys(db, 1)

        blocked = client.get("/api/v1/crm/leads", headers=superuser_headers)
        assert blocked.status_code == 403
        assert blocked.json()["historical_data_preserved"] is True

        assert db.query(CRMLead).filter(CRMLead.id == preserved.id).first() is not None
        assert db.query(BOSLifecycleEvent).filter(BOSLifecycleEvent.module_key == "crm", BOSLifecycleEvent.event_name == "module_disabled").count() == 1

        allowed = client.get("/api/v1/business-os/dependencies", headers=superuser_headers)
        assert allowed.status_code == 200
        dependency_pairs = {(item["module_key"], item["depends_on_module_key"], item["dependency_type"]) for item in allowed.json()}
        assert ("srm", "crm", "optional") in dependency_pairs
        assert ("project_management", "srm", "optional") in dependency_pairs

        response = client.put("/api/v1/business-os/modules", headers=superuser_headers, json={"enabled_modules": ["crm"]})
        assert response.status_code == 200
        assert response.json()["enabled_modules"] == ["crm"]

    finally:
        delattr(app.state, "business_os_session_factory")
        delattr(app.state, "business_os_close_session")


def test_business_os_supported_combinations_include_required_standalone_sets(client, db, superuser_headers):
    ensure_business_os_seed(db, company_id=1)
    response = client.get("/api/v1/business-os/modules", headers=superuser_headers)
    assert response.status_code == 200
    combos = {item["name"]: set(item["modules"]) for item in response.json()["supported_combinations"]}
    assert combos["Accounts only"] == {"fam"}
    assert combos["CRM only"] == {"crm"}
    assert combos["SRM only"] == {"srm"}
    assert combos["PMS only"] == {"project_management"}
    assert combos["Full Business OS"].issuperset({"fam", "inventory", "crm", "srm", "project_management", "hrms", "ai"})
