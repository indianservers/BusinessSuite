import pytest

from app.apps.crm.models import CRMCompany
from app.apps.srm.models import SRMProduct
from app.branches.models import BranchOwnership
from app.models.company import Branch
from app.models.user import User
from app.shared.follow_ups import FollowUp


@pytest.fixture
def pos_headers(db, superuser_headers):
    from tests.tenant_test_utils import assign_company
    from app.apps.business_os.services.module_service import ensure_business_os_seed
    user = db.query(User).filter_by(email="testadmin@test.com").one()
    assign_company(db, user, 1)
    branch = Branch(company_id=1, name="POS customers", code="POSCUSTOMERS", is_active=True)
    db.add(branch)
    db.flush()
    ensure_business_os_seed(db, company_id=1)
    db.commit()
    return {**superuser_headers, "X-Suite-Branch": str(branch.id)}


def test_quick_customer_checkout_follow_up_and_branch_isolation(client, db, pos_headers):
    created = client.post("/api/v1/srm/business/customers", headers=pos_headers,
                          json={"name": "Customer One", "phone": "9876543210", "phone_country_code": "+91", "email": "customer@example.com"})
    assert created.status_code == 201, created.text
    customer = created.json()
    assert customer["phone"] == "9876543210"
    assert customer["phone_country_code"] == "+91"
    assert customer["email"] == "customer@example.com"
    row = db.get(CRMCompany, customer["id"])
    assert row.account_type == "Customer" and row.branch_id == int(pos_headers["X-Suite-Branch"])
    assert db.query(BranchOwnership).filter_by(resource_table="crm_companies", resource_key=str(row.id)).one().branch_id == row.branch_id
    directory = client.get("/api/v1/srm/business/customers", headers=pos_headers)
    assert directory.status_code == 200, directory.text
    assert directory.json()["items"][0]["phone"] == customer["phone"]
    product = SRMProduct(organization_id=1, sku="QUICK-CARE", item_name="Care service", product_type="service", track_inventory=False,
                         active=True, sales_rate=100, metadata_json={"follow_up": {"required": True, "reference": "completion", "interval_days": 7}})
    other = Branch(company_id=1, name="Other POS", code="OTHERPOS", is_active=True)
    db.add_all([product, other])
    db.commit()
    order = client.post("/api/v1/srm/sales-orders", headers=pos_headers, json={
        "order_number": "QUICK-CUSTOMER-SALE", "title": "Quick customer sale", "customer_id": row.id,
        "metadata_json": {"source": "pos", "pos_sale_id": "quick-sale"},
        "lines": [{"product_id": product.id, "description": "Care service", "service_type": "service", "quantity": 1, "unit_price": 100}]})
    assert order.status_code == 201, order.text
    follow_up = db.query(FollowUp).one()
    assert follow_up.customer_id == row.id and follow_up.order_id == order.json()["id"]
    hidden = client.get("/api/v1/srm/business/customers", headers={**pos_headers, "X-Suite-Branch": str(other.id)})
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["items"] == []


def test_quick_customer_validation_duplicate_and_read_only(client, db, pos_headers):
    path = "/api/v1/srm/business/customers"
    for payload in ({"name": " "}, {"name": "Customer", "email": "invalid"}, {"name": "Customer", "phone": "wrong"}):
        response = client.post(path, headers=pos_headers, json=payload)
        assert response.status_code == 422, response.text
    payload = {"name": "Customer", "phone": "9876543210", "email": "unique@example.com"}
    assert client.post(path, headers=pos_headers, json=payload).status_code == 201
    duplicate = client.post(path, headers=pos_headers, json={**payload, "phone": "9876543210", "phone_country_code": "+91", "email": "other@example.com"})
    assert duplicate.status_code == 409, duplicate.text
    branch = db.get(Branch, int(pos_headers["X-Suite-Branch"]))
    branch.is_active = False
    db.commit()
    readonly = client.post(path, headers=pos_headers, json={"name": "Cannot write"})
    assert readonly.status_code == 403, readonly.text


@pytest.mark.parametrize("reference", ["purchase", "completion"])
def test_regular_sale_and_service_completion_schedule_follow_ups(client, db, pos_headers, reference):
    buyer = client.post("/api/v1/srm/business/customers", headers=pos_headers, json={"name": "Service buyer"})
    assert buyer.status_code == 201, buyer.text
    product = SRMProduct(organization_id=1, sku=f"EVENT-{reference}", item_name="Customer service", product_type="service",
                         track_inventory=False, active=True, sales_rate=100,
                         metadata_json={"follow_up": {"required": True, "reference": reference, "interval_days": 7}})
    db.add(product)
    db.commit()
    order = client.post("/api/v1/srm/sales-orders", headers=pos_headers, json={
        "title": "Regular service sale", "customer_id": buyer.json()["id"],
        "lines": [{"product_id": product.id, "description": "Service", "quantity": 1, "unit_price": 100}]})
    assert order.status_code == 201, order.text
    ident = order.json()["id"]
    assert db.query(FollowUp).count() == 0
    approved = client.patch(f"/api/v1/srm/sales-orders/{ident}", headers=pos_headers, json={"status": "approved"})
    assert approved.status_code == 200, approved.text
    confirmed = client.post(f"/api/v1/srm/sales-orders/{ident}/confirm", headers=pos_headers)
    assert confirmed.status_code == 200, confirmed.text
    if reference == "completion":
        assert db.query(FollowUp).count() == 0
        engagement = confirmed.json()["engagement"]["id"]
        completed = client.post(f"/api/v1/srm/engagements/{engagement}/status/completed", headers=pos_headers)
        assert completed.status_code == 200, completed.text
        # Retrying the completion event must retain the original schedule.
        repeated = client.patch(f"/api/v1/srm/engagements/{engagement}", headers=pos_headers, json={"status": "completed"})
        assert repeated.status_code == 200, repeated.text
    assert db.query(FollowUp).count() == 1
    assert db.query(FollowUp).one().customer_id == buyer.json()["id"]
