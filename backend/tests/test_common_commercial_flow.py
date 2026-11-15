"""One real HTTP lifecycle behind the Sales and CRM shared commercial pages."""
from datetime import date, timedelta
from decimal import Decimal
import json
import pytest

from tests.rich_text_test_utils import organization_context
from tests.srm_test_utils import seed_invoice_parties
from app.apps.crm.models import CRMDeal, CRMPipeline, CRMPipelineStage
from app.apps.srm.models import SRMSalesOrder, SRMInvoice


def seed_commercial_deal(db):
    seed_invoice_parties(db)
    pipeline = CRMPipeline(organization_id=1, name="Shared commercial pipeline", is_default=True)
    db.add(pipeline)
    db.flush()
    stage = CRMPipelineStage(organization_id=1, pipeline_id=pipeline.id, name="Won", probability=100, is_won=True)
    db.add(stage)
    db.flush()
    deal = CRMDeal(organization_id=1, pipeline_id=pipeline.id, stage_id=stage.id, name="Shared commercial implementation", company_id=101, amount=1800, currency="INR", status="Won")
    db.add(deal)
    db.commit()
    return deal


def test_quote_order_invoice_preserves_money_and_identity(client, db, superuser_headers):
    deal = seed_commercial_deal(db)
    created = client.post("/api/v1/crm/quotes", headers=superuser_headers, json={
        "quote_number": "COMMON-E2E", "company_id": 101, "deal_id": deal.id,
        "currency": "INR", "issue_date": str(date.today()), "expiry_date": str(date.today()+timedelta(days=30)),
    })
    assert created.status_code == 201, created.text
    quote_id = created.json()["id"]
    path = f"/api/v1/crm/quotes/{quote_id}"
    line = client.post(path+"/lines", headers=superuser_headers, json={"name":"Shared implementation", "item_type":"service", "quantity":2, "unit_price":1000, "discount_type":"percentage", "discount_value":10, "tax_rate":18})
    assert line.status_code == 201, line.text
    for action in ["calculate", "submit", "approve", "send", "accept"]:
        result = client.post(path+"/"+action, headers=superuser_headers, json={})
        assert result.status_code == 200, (action, result.text)
    quote = result.json()
    order_id = quote["srmConversion"]["conversionLog"]["srm_sales_order_id"]
    order = client.get(f"/api/v1/srm/sales-orders/{order_id}", headers=superuser_headers)
    assert order.status_code == 200, order.text
    assert order.json()["customer_id"] == 101
    assert order.json()["crm_quote_id"] == quote_id
    assert Decimal(str(order.json()["total_amount"])) == Decimal("2124")
    draft = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order_id}", headers=superuser_headers)
    assert draft.status_code == 201, draft.text
    invoice = draft.json()
    assert Decimal(str(invoice["total_amount"])) == Decimal("2124")
    assert Decimal(str(invoice["tax_amount"])) == Decimal("324")
    assert invoice["customer_id"] == 101 and invoice["sales_order_id"] == order_id
    approved = client.post(f"/api/v1/srm/invoices/{invoice['id']}/approve", headers=superuser_headers)
    assert approved.status_code == 200, approved.text
    assert client.get(f"/api/v1/srm/invoices/{invoice['id']}/pdf", headers=superuser_headers).status_code == 200
    assert client.post(path+"/convert-to-srm", headers=superuser_headers).json()["idempotent"] is True
    assert client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order_id}", headers=superuser_headers).status_code == 409
    assert db.query(SRMSalesOrder).filter_by(crm_quote_id=quote_id).count() == 1
    assert db.query(SRMInvoice).filter_by(sales_order_id=order_id).count() == 1


@pytest.mark.parametrize("module", ["crm", "srm"])
def test_shared_commercial_managers_real_browser(client, db, superuser_headers, monkeypatch, module):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'COMMUNICATION_EMAIL_PROVIDER', 'stub')
    from tests.test_control_browser import test_control_center_real_browser
    from app.models.user import User
    deal = seed_commercial_deal(db)
    actor = db.query(User).filter_by(email="testadmin@test.com").one()
    from test_identity_utils import attach_workflow_branch
    branch = attach_workflow_branch(db, actor)
    db.commit()
    monkeypatch.setenv("CONTROL_BROWSER_SCRIPT", "common-commercial-live.cjs")
    monkeypatch.setenv("SUITE_QA_AUTH", json.dumps({"token":superuser_headers["Authorization"].split(" ",1)[1], "user_id":actor.id, "branch":str(branch.id), "deal_id":deal.id, "module":module}))
    test_control_center_real_browser(client, db, None, superuser_headers)
