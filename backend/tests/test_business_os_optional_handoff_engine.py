from app.apps.business_os.models import BOSEnabledModule, BOSEntityLink, BOSLifecycleEvent
from app.apps.crm.models import CRMDeal, CRMPipeline, CRMPipelineStage
from app.apps.srm.models import SRMEngagement, SRMSalesOrder
from app.main import app


def _set_modules(client, headers, modules):
    response = client.put("/api/v1/business-os/modules", headers=headers, json={"enabled_modules": modules})
    assert response.status_code == 200
    return response.json()


def _crm_deal(db, user_id=1):
    pipeline = CRMPipeline(organization_id=1, name="Business OS Handoff Pipeline", is_default=True, active=True)
    db.add(pipeline)
    db.flush()
    stage = CRMPipelineStage(organization_id=1, pipeline_id=pipeline.id, name="Closed Won", probability=100, stage_type="won", is_won=True)
    db.add(stage)
    db.flush()
    deal = CRMDeal(organization_id=1, owner_user_id=user_id, pipeline_id=pipeline.id, stage_id=stage.id, name="Business OS Won Deal", amount=125000, currency="INR", status="Closed Won")
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def _srm_engagement(db, user_id=1):
    order = SRMSalesOrder(organization_id=1, order_number="BOS-SO-001", status="confirmed", title="Business OS Delivery", total_amount=50000, assigned_user_id=user_id, created_by=user_id)
    db.add(order)
    db.flush()
    engagement = SRMEngagement(organization_id=1, engagement_number="BOS-ENG-001", sales_order_id=order.id, assigned_user_id=user_id, project_manager_user_id=user_id, name="Business OS Delivery", status="created", budget_amount=50000, created_by=user_id)
    db.add(engagement)
    db.commit()
    db.refresh(engagement)
    return engagement


def test_business_os_optional_handoff_combinations(client, db, superuser_headers):
    app.state.business_os_session_factory = lambda: db
    app.state.business_os_close_session = False
    try:
        db.query(BOSLifecycleEvent).delete()
        db.query(BOSEntityLink).delete()
        db.query(BOSEnabledModule).delete()
        db.commit()
        _set_modules(client, superuser_headers, ["crm"])
        skipped = client.post("/api/v1/business-os/handoffs/crm/deals/9001/won", headers=superuser_headers)
        assert skipped.status_code == 200
        assert skipped.json()["status"] == "skipped"
        assert skipped.json()["message"] == "SRM not enabled"

        _set_modules(client, superuser_headers, ["crm", "srm"])
        deal = _crm_deal(db, 1)
        created = client.post(f"/api/v1/business-os/handoffs/crm/deals/{deal.id}/won", headers=superuser_headers)
        assert created.status_code == 200
        assert created.json()["status"] == "created"
        assert created.json()["sales_order"]["crm_deal_id"] == deal.id
        repeat = client.post(f"/api/v1/business-os/handoffs/crm/deals/{deal.id}/won", headers=superuser_headers)
        assert repeat.status_code == 200
        assert repeat.json()["status"] == "idempotent"
        assert db.query(BOSEntityLink).filter(BOSEntityLink.source_module == "crm", BOSEntityLink.target_module == "srm", BOSEntityLink.source_entity_id == str(deal.id)).count() >= 1

        _set_modules(client, superuser_headers, ["srm", "project_management"])
        engagement = _srm_engagement(db, 1)
        pms = client.post(f"/api/v1/business-os/handoffs/srm/engagements/{engagement.id}/pms-project", headers=superuser_headers)
        assert pms.status_code == 200
        assert pms.json()["status"] in {"created", "idempotent"}
        assert pms.json()["project"]["id"]

        _set_modules(client, superuser_headers, ["project_management"])
        no_billing = client.post("/api/v1/business-os/handoffs/pms/timesheet/77/invoice-draft", headers=superuser_headers)
        assert no_billing.status_code == 200
        assert no_billing.json()["status"] == "skipped"
        assert no_billing.json()["message"] == "Billing module not enabled"

        _set_modules(client, superuser_headers, ["project_management", "fam"])
        billing_ready = client.post("/api/v1/business-os/handoffs/pms/timesheet/77/invoice-draft", headers=superuser_headers)
        assert billing_ready.status_code == 200
        assert billing_ready.json()["status"] == "ready"

        _set_modules(client, superuser_headers, ["srm"])
        inventory_only = client.post("/api/v1/business-os/handoffs/inventory/grn/501/post-accounting", headers=superuser_headers)
        assert inventory_only.status_code == 200
        assert inventory_only.json()["status"] == "skipped"
        assert inventory_only.json()["message"] == "Accounting posting skipped because FAM is not enabled"

        _set_modules(client, superuser_headers, ["srm", "fam"])
        inventory_fam = client.post("/api/v1/business-os/handoffs/inventory/grn/501/post-accounting", headers=superuser_headers)
        assert inventory_fam.status_code == 200
        assert inventory_fam.json()["status"] == "ready"

        full = _set_modules(client, superuser_headers, ["fam", "crm", "srm", "project_management", "hrms", "ai", "portals", "communication"])
        assert "inventory" not in set(full["enabled_modules"])
        assert set(full["enabled_modules"]).issuperset({"fam", "crm", "srm", "project_management"})
        assert db.query(BOSLifecycleEvent).filter(BOSLifecycleEvent.event_name.in_(["crm_deal_won_handoff", "srm_inventory_to_fam_accounting", "pms_invoice_handoff_skipped"])).count() >= 3
    finally:
        delattr(app.state, "business_os_session_factory")
        delattr(app.state, "business_os_close_session")
