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
    from app.apps.crm.models import CRMCompany
    buyer = db.get(CRMCompany, 701)
    if not buyer:
        buyer = CRMCompany(id=701, organization_id=1, name='Customer 360 buyer')
        db.add(buyer)
    from test_identity_utils import own_workflow_records
    db.flush()
    rows = [buyer, order, contract, project, engagement]
    for model in (SRMBillingPlan, SRMInvoice, SRMReceipt, SRMCustomerAging, SRMCollectionReminder, SRMProfitabilitySnapshot, SRMAuditLog):
        rows.extend(db.query(model).all())
    own_workflow_records(db, *rows)
    db.commit()
    return order, engagement


def test_srm_customer_360_returns_linked_commercial_delivery_collection_data(client, db, superuser_headers):
    from app.models.user import User
    from tests.tenant_test_utils import assign_company
    from test_identity_utils import attach_workflow_branch
    actor = db.query(User).filter_by(email='testadmin@test.com').one()
    assign_company(db, actor, 1)
    attach_workflow_branch(db, actor)
    db.commit()
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


import pytest
from tests.test_import_workspace import import_headers
from tests.rich_text_test_utils import organization_context

@pytest.mark.parametrize('kind',['order','engagement','contract','invoice'])
@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
def test_audit_customer_reference_search_is_literal(client,db,import_headers,kind,needle):
    from app.apps.crm.models import CRMCompany
    from test_identity_utils import own_workflow_records
    customers=[CRMCompany(organization_id=1,name=name,account_type='Customer') for name in ['Ordinary buyer','Literal buyer']]
    db.add_all(customers);db.flush()
    rows=[]
    for name,customer in zip(['QAplainLiteral','QA'+needle+'Literal'],customers):
        values={'organization_id':1,'customer_id':customer.id}
        if kind=='order':row=SRMSalesOrder(order_number=name,title=name,**values)
        elif kind=='engagement':row=SRMEngagement(engagement_number=name,name=name,**values)
        elif kind=='contract':row=SRMContract(contract_number=name,title=name,**values)
        else:row=SRMInvoice(invoice_number=name,**values)
        db.add(row);rows.append(row)
    own_workflow_records(db,*customers,*rows);db.commit()
    response=client.get('/api/v1/srm/customer-360',headers=import_headers,params={'q':needle})
    assert response.status_code==200,response.text
    assert response.json()['customer_id']==customers[1].id
    ordinary=client.get('/api/v1/srm/customer-360',headers=import_headers,params={'q':'qaplain'})
    assert ordinary.status_code==200,ordinary.text
    assert ordinary.json()['customer_id']==customers[0].id
