from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.apps.srm.models import SRMSalesOrder, SRMInvoice, SRMReceipt
from app.models.user import User
from app.shared.payment_models import PaymentRequest
from app.shared import payment_requests as payments
from app.shared.payment_gateway import RazorpayGateway, verified_link, provider_reference
from tests.test_contact_directory import directory_identity

ROOT = "/api/v1/payment-requests"


@pytest.fixture
def order(db, directory_identity):
    actor = db.query(User).filter_by(email="testadmin@test.com").one()
    row = SRMSalesOrder(organization_id=1, order_number="PAYMENT-ORDER", title="Pending order", status="draft",
        currency="INR", total_amount=Decimal("100.00"), created_by=actor.id, assigned_user_id=actor.id)
    from test_identity_utils import own_workflow_records
    db.add(row); db.flush(); own_workflow_records(db, row); db.commit(); return row


@pytest.fixture(autouse=True)
def disconnected(monkeypatch):
    # No test may inherit a real deployment payment account.
    monkeypatch.setattr(payments, "gateway_for", lambda organization: None)


def payload(order, **changes):
    return {"source_type":"srm_order", "source_id":order.id, "amount":"40.25", "instructions":"Use our agreed bank transfer details", "request_id":str(uuid4()), **changes}


def test_saved_request_is_idempotent_and_does_not_record_money(client, db, order, superuser_headers):
    data = payload(order)
    first = client.post(ROOT, json=data, headers=superuser_headers)
    assert first.status_code == 201, first.text
    repeat = client.post(ROOT, json=data, headers=superuser_headers)
    assert repeat.status_code == 201 and repeat.json()["id"] == first.json()["id"]
    assert db.query(PaymentRequest).count() == 1
    assert db.query(SRMReceipt).count() == 0
    db.refresh(order); assert order.status == "draft"
    conflict = client.post(ROOT, json={**data,"amount":"20.00"}, headers=superuser_headers)
    assert conflict.status_code == 409
    saved = first.json()
    assert saved["status"] == "awaiting_gateway" and saved["payment_url"] is None
    no_gateway = client.post(f"{ROOT}/{saved['id']}/link", headers=superuser_headers)
    assert no_gateway.status_code == 409
    assert db.get(PaymentRequest, saved["id"]).status == "awaiting_gateway"


def test_reservation_amount_checks_cancel_and_forbidden_fields(client, db, order, superuser_headers):
    first = client.post(ROOT, json=payload(order,amount="75.00"), headers=superuser_headers)
    assert first.status_code == 201, first.text
    assert client.post(ROOT, json=payload(order,amount="25.01"), headers=superuser_headers).status_code == 422
    ctx = client.get(ROOT+"/context", params={"source_type":"srm_order","source_id":order.id}, headers=superuser_headers)
    assert ctx.status_code == 200, ctx.text
    assert Decimal(ctx.json()["available_amount"]) == Decimal("25")
    assert ctx.json()["gateway"]["connected"] is False
    for amount in ["0", "-1", "NaN", "Infinity", "0.001", "1000000000000"]:
        assert client.post(ROOT,json=payload(order,amount=amount),headers=superuser_headers).status_code == 422
    assert client.post(ROOT,json=payload(order,currency="USD"),headers=superuser_headers).status_code == 422
    cancelled = client.post(f"{ROOT}/{first.json()['id']}/cancel",headers=superuser_headers)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert client.post(ROOT,json=payload(order,amount="100.00"),headers=superuser_headers).status_code == 201


def test_tenant_boundary_and_cancelled_source(client, db, order, superuser_headers):
    order.organization_id=2; db.commit()
    assert client.post(ROOT,json=payload(order),headers=superuser_headers).status_code == 404
    order.organization_id=1; order.status="cancelled"; db.commit()
    assert client.post(ROOT,json=payload(order),headers=superuser_headers).status_code == 422


def test_completed_cash_pos_order_cannot_request_money_again(client, db, order, superuser_headers):
    order.metadata_json={"source":"pos","payment_mode":"Cash"};db.commit()
    assert client.post(ROOT,json=payload(order),headers=superuser_headers).status_code == 422
    order.metadata_json={"source":"pos","payment_mode":"Payment request","payment_status":"awaiting_payment"};db.commit()
    pending=client.post(ROOT,json=payload(order),headers=superuser_headers)
    assert pending.status_code == 201,pending.text


def provider_result(row, **changes):
    return {"id":"plink_Original", "reference_id":provider_reference(row),"amount":int(row.amount*100),"currency":"INR",
        "short_url":"https://rzp.io/i/original","status":"created","amount_paid":0, **changes}


def test_uncertain_provider_create_reconciles_without_duplicate(client, db, order, superuser_headers, monkeypatch):
    calls=[]
    class Gateway:
        name="razorpay"; account="test-account"; test_mode=True
        def create(self,row):
            calls.append(row.request_id);raise HTTPException(502,"Timeout")
        def find(self,reference):
            row = db.query(PaymentRequest).one()
            assert reference == provider_reference(row)
            return provider_result(row)
    gateway=Gateway();monkeypatch.setattr(payments,"gateway_for",lambda organization:gateway)
    saved=client.post(ROOT,json=payload(order),headers=superuser_headers).json()
    assert client.post(f"{ROOT}/{saved['id']}/link",headers=superuser_headers).status_code == 502
    assert db.get(PaymentRequest,saved["id"]).status == "reconciliation_required"
    reconciled=client.post(f"{ROOT}/{saved['id']}/link",headers=superuser_headers)
    assert reconciled.status_code == 200,reconciled.text
    assert reconciled.json()["status"] == "link_ready"
    assert len(calls) == 1
    assert client.post(f"{ROOT}/{saved['id']}/link",headers=superuser_headers).json()["id"] == saved["id"]
    assert len(calls) == 1


def test_provider_identity_amount_and_paid_status_are_verified():
    row=PaymentRequest(request_id=str(uuid4()),amount=Decimal("25"),currency="INR")
    for changes in [{"amount":1},{"currency":"USD"},{"reference_id":"another"},{"short_url":"https://evil.test/pay"},{"status":"paid","amount_paid":0}]:
        with pytest.raises(HTTPException):verified_link(row,provider_result(row,**changes))
    verified_link(row,provider_result(row,status="paid",amount_paid=2500))
    assert row.status == "gateway_paid" and row.amount_paid == 25


def test_provider_payload_does_not_send_unsolicited_messages(monkeypatch):
    captured={}
    gateway=RazorpayGateway("rzp_test_example","secret")
    def send(method,path,**args):captured.update(args["body"]);return {}
    monkeypatch.setattr(gateway,"request",send)
    gateway.create(PaymentRequest(request_id=str(uuid4()),amount=Decimal("1.23"),currency="INR",reference="ORDER-1"))
    assert captured["amount"] == 123
    assert captured["notify"] == {"sms":False,"email":False}
    assert captured["reminder_enable"] is False and captured["accept_partial"] is False


def test_invoice_handover_reserves_request_until_actual_receipt_is_matched(client, db, order, superuser_headers):
    from app.apps.srm.models import SRMReceiptAllocation
    from app.apps.srm.commercial_models import ReceiptContext
    from test_identity_utils import own_workflow_records
    saved = client.post(ROOT, json=payload(order, amount="40.00"), headers=superuser_headers).json()
    assert client.post(f"{ROOT}/{saved['id']}/reconcile-receipt",headers=superuser_headers).status_code == 409
    invoice=SRMInvoice(organization_id=1,invoice_number="PAY-INV",sales_order_id=order.id,status="partially_paid",
        currency="INR",total_amount=100,paid_amount=40,balance_amount=60)
    receipt=SRMReceipt(organization_id=1,receipt_number="PAY-RCT",reference_number=saved["request_id"],status="allocated",
        currency="INR",amount=40,unallocated_amount=0)
    db.add_all([invoice,receipt]);db.flush();own_workflow_records(db,invoice,receipt)
    allocation=SRMReceiptAllocation(receipt_id=receipt.id,invoice_id=invoice.id,amount=40)
    receipt_context=ReceiptContext(receipt_id=receipt.id,seller_id=1,invoice_id=invoice.id,request_id=str(uuid4()))
    db.add_all([allocation,receipt_context]);db.flush();own_workflow_records(db,allocation,receipt_context);db.commit()
    ctx=client.get(ROOT+"/context",headers=superuser_headers,params={"source_type":"srm_invoice","source_id":invoice.id})
    assert ctx.status_code == 200,ctx.text
    assert Decimal(ctx.json()["available_amount"]) == 20  # old order request still reserves 40
    matched=client.post(f"{ROOT}/{saved['id']}/reconcile-receipt",headers=superuser_headers)
    assert matched.status_code == 200,matched.text
    assert matched.json()["status"] == "receipt_recorded" and matched.json()["receipt_id"] == receipt.id
    again=client.post(f"{ROOT}/{saved['id']}/reconcile-receipt",headers=superuser_headers)
    assert again.json()["receipt_id"] == receipt.id
    ctx=client.get(ROOT+"/context",headers=superuser_headers,params={"source_type":"srm_invoice","source_id":invoice.id})
    assert Decimal(ctx.json()["available_amount"]) == 60
    assert db.query(SRMReceipt).count() == 1
    db.refresh(invoice);assert invoice.paid_amount == 40 and invoice.balance_amount == 60


def test_gateway_account_is_explicitly_tenant_bound(monkeypatch):
    from app.shared import payment_gateway
    monkeypatch.setattr(payment_gateway.settings,"PAYMENT_GATEWAY_PROVIDER","razorpay")
    monkeypatch.setattr(payment_gateway.settings,"PAYMENT_GATEWAY_ORGANIZATION_ID",1)
    monkeypatch.setattr(payment_gateway.settings,"RAZORPAY_KEY_ID","rzp_test_sample")
    monkeypatch.setattr(payment_gateway.settings,"RAZORPAY_KEY_SECRET","not-real")
    assert payment_gateway.gateway_for(1).test_mode is True
    assert payment_gateway.gateway_for(2) is None
    key=str(uuid4())
    first=PaymentRequest(request_id=key,organization_id=1)
    second=PaymentRequest(request_id=key,organization_id=2)
    assert provider_reference(first) != provider_reference(second)
    assert len(provider_reference(first)) <= 40


def test_disabled_module_and_unauthenticated_requests_are_denied(client, db):
    from types import SimpleNamespace
    actor=SimpleNamespace(is_superuser=False,_suite_grants={"srm":{"enabled":False}})
    with pytest.raises(HTTPException) as denied:payments.source_context(db,actor,"srm_order",1)
    assert denied.value.status_code == 403
    assert client.get(ROOT,params={"source_type":"srm_order","source_id":1}).status_code in {401,403}


def test_additive_schema_matches_models_and_is_idempotent():
    from sqlalchemy import create_engine, MetaData, Table, Column, Integer, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.shared import payment_schema
    engine=create_engine("sqlite://")
    metadata=MetaData()
    for name in ["companies","users","crm_deals","crm_quotations","srm_sales_orders","srm_invoices","srm_receipts"]:
        Table(name,metadata,Column("id",Integer,primary_key=True))
    metadata.create_all(engine)
    with engine.begin() as connection:
        ops=Operations(MigrationContext.configure(connection))
        payment_schema.upgrade(ops);payment_schema.upgrade(ops)
        actual={row["name"] for row in inspect(connection).get_columns("suite_payment_requests")}
        assert actual == set(PaymentRequest.__table__.columns.keys())
        assert len(inspect(connection).get_foreign_keys("suite_payment_requests")) == 7
        assert len(inspect(connection).get_check_constraints("suite_payment_requests")) == 2
        payment_schema.downgrade(ops)
        assert not inspect(connection).has_table("suite_payment_requests")
