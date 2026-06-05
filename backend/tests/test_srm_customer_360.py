from datetime import date
from decimal import Decimal

from app.apps.project_management.models import PMSProject
from app.apps.srm.models import (
    SRMAuditLog,
    SRMBillingPlan,
    SRMCollectionReminder,
    SRMContract,
    SRMCustomerAging,
    SRMEngagement,
    SRMInvoice,
    SRMProfitabilitySnapshot,
    SRMReceipt,
    SRMSalesOrder,
)
from tests.srm_test_utils import auth_headers_for


def seed_customer_360(db):
    order = SRMSalesOrder(order_number="SO-360-001", title="Customer 360 order", status="confirmed", customer_id=701, crm_deal_id=9001, crm_quote_id=8001, crm_company_id=7001, crm_contact_id=6001, total_amount=Decimal("180000"))
    db.add(order)
    db.flush()
    contract = SRMContract(contract_number="CTR-360-001", title="Customer 360 contract", status="active", customer_id=701, sales_order_id=order.id, contract_value=Decimal("180000"))
    project = PMSProject(project_key="P360", name="Customer 360 PMS project", status="Active", budget_amount=Decimal("180000"))
    db.add_all([contract, project])
    db.flush()
    engagement = SRMEngagement(engagement_number="ENG-360-001", name="Customer 360 engagement", status="project_created", customer_id=701, crm_deal_id=9001, sales_order_id=order.id, contract_id=contract.id, pms_project_id=project.id, budget_amount=Decimal("180000"))
    db.add(engagement)
    db.flush()
    db.add_all([
        SRMBillingPlan(engagement_id=engagement.id, name="Customer 360 billing", status="active", total_amount=Decimal("180000")),
        SRMInvoice(invoice_number="INV-360-001", sales_order_id=order.id, engagement_id=engagement.id, customer_id=701, status="sent", issue_date=date.today(), due_date=date.today(), total_amount=Decimal("180000"), paid_amount=Decimal("60000"), balance_amount=Decimal("120000")),
        SRMReceipt(receipt_number="RCT-360-001", customer_id=701, status="allocated", amount=Decimal("60000"), unallocated_amount=Decimal("0")),
        SRMCustomerAging(customer_id=701, current_amount=Decimal("120000"), total_outstanding=Decimal("120000")),
        SRMCollectionReminder(customer_id=701, status="sent", reminder_type="email", message="Follow up"),
        SRMProfitabilitySnapshot(engagement_id=engagement.id, customer_id=701, invoiced_amount=Decimal("180000"), collected_amount=Decimal("60000"), outstanding_amount=Decimal("120000"), gross_margin_amount=Decimal("50000"), cash_margin_amount=Decimal("10000")),
        SRMAuditLog(entity_type="sales_order", entity_id=order.id, action="crm_won_handoff", after_json={"crm_deal_id": 9001}),
        SRMAuditLog(entity_type="engagement", entity_id=engagement.id, action="pms_project_created", after_json={"pms_project_id": project.id}),
    ])
    db.commit()
    return order, engagement


def test_srm_customer_360_returns_linked_commercial_delivery_collection_data(client, db, superuser_headers):
    order, engagement = seed_customer_360(db)

    response = client.get("/api/v1/srm/customer-360", headers=superuser_headers, params={"customer_id": 701})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["matched"] is True
    assert body["customer_id"] == 701
    assert body["crm_references"]["crm_deal_ids"] == [9001]
    assert body["sales_orders"][0]["order_number"] == "SO-360-001"
    assert body["contracts"][0]["contract_number"] == "CTR-360-001"
    assert body["engagements"][0]["engagement_number"] == "ENG-360-001"
    assert body["billing_plans"][0]["name"] == "Customer 360 billing"
    assert body["invoices"][0]["invoice_number"] == "INV-360-001"
    assert body["receipts"][0]["receipt_number"] == "RCT-360-001"
    assert body["outstanding_amount"] == 120000.0
    assert body["aging"]["total_outstanding"] == 120000.0
    assert body["collection_reminders"][0]["reminder_type"] == "email"
    assert body["profitability"][0]["gross_margin"] == 50000.0
    assert body["pms_projects"][0]["project_key"] == "P360"
    assert any(item.get("action") == "crm_won_handoff" for item in body["audit_trail"])

    by_order = client.get("/api/v1/srm/customer-360", headers=superuser_headers, params={"sales_order_id": order.id})
    assert by_order.status_code == 200
    assert by_order.json()["customer_id"] == 701

    by_engagement = client.get("/api/v1/srm/customer-360", headers=superuser_headers, params={"engagement_id": engagement.id})
    assert by_engagement.status_code == 200
    assert by_engagement.json()["customer_id"] == 701

    by_crm_deal = client.get("/api/v1/srm/customer-360", headers=superuser_headers, params={"crm_deal_id": 9001})
    assert by_crm_deal.status_code == 200
    assert by_crm_deal.json()["customer_id"] == 701

    by_search = client.get("/api/v1/srm/customer-360", headers=superuser_headers, params={"q": "SO-360-001"})
    assert by_search.status_code == 200
    assert by_search.json()["customer_id"] == 701


def test_srm_customer_360_empty_search_and_rbac(client, db):
    blocked_headers = auth_headers_for(client, db, "customer360-blocked@example.com", "srm_viewer", permissions=[])
    response = client.get("/api/v1/srm/customer-360", headers=blocked_headers, params={"q": "missing"})
    assert response.status_code == 403

    allowed_headers = auth_headers_for(client, db, "customer360-viewer@example.com", "srm_viewer", permissions=["srm_view"])
    response = client.get("/api/v1/srm/customer-360", headers=allowed_headers, params={"q": "missing"})
    assert response.status_code == 200
    assert response.json()["matched"] is False
    assert response.json()["sales_orders"] == []
