from app.apps.project_management.models import PMSProject
from app.apps.srm.models import SRMSalesOrder

from tests.test_srm_crm_won_handoff import create_won_deal_with_quote


def test_srm_crm_handoff_is_idempotent(client, db, superuser_headers):
    deal, _quote = create_won_deal_with_quote(db, "Idempotent Deal")

    first = client.post(f"/api/v1/srm/from-crm/deals/{deal.id}/create-sales-order", headers=superuser_headers)
    assert first.status_code == 201, first.text
    second = client.post(f"/api/v1/srm/from-crm/deals/{deal.id}/create-sales-order", headers=superuser_headers)
    assert second.status_code == 201, second.text
    assert second.json()["idempotent"] is True
    assert second.json()["sales_order"]["id"] == first.json()["sales_order"]["id"]
    assert db.query(SRMSalesOrder).filter(SRMSalesOrder.crm_deal_id == deal.id).count() == 1


def test_srm_pms_project_creation_is_idempotent(client, db, superuser_headers):
    deal, _quote = create_won_deal_with_quote(db, "PMS Idempotent Deal")
    handoff = client.post(f"/api/v1/srm/from-crm/deals/{deal.id}/create-sales-order", headers=superuser_headers).json()
    order_id = handoff["sales_order"]["id"]
    client.post(f"/api/v1/srm/sales-orders/{order_id}/submit", headers=superuser_headers)
    client.post(f"/api/v1/srm/sales-orders/{order_id}/confirm", headers=superuser_headers)

    first = client.post(f"/api/v1/srm/engagements/{handoff['engagement']['id']}/create-pms-project", headers=superuser_headers)
    assert first.status_code == 200, first.text
    second = client.post(f"/api/v1/srm/engagements/{handoff['engagement']['id']}/create-pms-project", headers=superuser_headers)
    assert second.status_code == 200, second.text
    assert second.json()["idempotent"] is True
    assert second.json()["project"]["id"] == first.json()["project"]["id"]
    assert db.query(PMSProject).filter(PMSProject.id == first.json()["project"]["id"]).count() == 1
