from uuid import uuid4

from app.apps.project_management.models import PMSMilestone, PMSProject, PMSTask
from app.apps.srm.models import SRMInvoice, SRMInvoiceLine, SRMProduct

from tests.srm_test_utils import create_engagement_via_confirm, create_sales_order


def test_mobile_sales_order_create_replays_without_duplicate(client, db, superuser_headers):
    from app.shared.offline_operations import receipts

    receipts.create(db.get_bind(), checkfirst=True)
    path = "/api/v1/srm/sales-orders"
    headers = {**superuser_headers, "X-Offline-Operation": str(uuid4())}
    body = {"title": "Offline sales order", "lines": [{"description": "Consulting", "quantity": 2, "unit_price": 100}]}
    first = client.post(path, headers=headers, json=body)
    replay = client.post(path, headers=headers, json=body)
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert client.post(path, headers=headers, json={**body, "title": "Different order"}).status_code == 409
    matches = client.get(path, headers=superuser_headers, params={"summary_only": True, "search": body["title"]})
    assert matches.status_code == 200
    assert [row["id"] for row in matches.json()] == [first.json()["id"]]


def test_sales_order_summary_preserves_header_and_skips_lines(client, superuser_headers):
    order = create_sales_order(client, superuser_headers)
    path = "/api/v1/srm/sales-orders"
    full = client.get(path, headers=superuser_headers)
    summary = client.get(path, headers=superuser_headers, params={"summary_only": True})
    assert full.status_code == summary.status_code == 200
    assert [row["id"] for row in full.json()] == [row["id"] for row in summary.json()]
    header = next(row for row in summary.json() if row["id"] == order["id"])
    detailed = next(row for row in full.json() if row["id"] == order["id"])
    assert detailed["lines"]
    assert header == {key: detailed[key] for key in header}
    assert "lines" not in header
    found = client.get(path, headers=superuser_headers, params={
        "summary_only": True, "search": order["order_number"].lower(),
    })
    assert found.status_code == 200
    assert header in found.json()
    no_match = client.get(path, headers=superuser_headers, params={"search": "%%"})
    assert no_match.status_code == 200
    assert no_match.json() == []


def test_inventory_summary_preserves_search_and_pagination(client, db, superuser_headers):
    db.add_all([
        SRMProduct(organization_id=1, sku="SUMMARY-A", item_name="Summary product A", description="Full details"),
        SRMProduct(organization_id=1, sku="SUMMARY-B", item_name="Summary product B",
                   barcode="7845112345", category_name="Test accessories",
                   hsn_code="8471", sales_rate=125.50, gst_rate=18),
    ])
    db.commit()
    path = "/api/v1/srm/inventory/items"
    params = {"search": "SUMMARY-", "page": 2, "per_page": 1}
    full = client.get(path, headers=superuser_headers, params=params)
    slim = client.get(path, headers=superuser_headers, params={**params, "summary_only": True})
    assert full.status_code == slim.status_code == 200
    assert full.json()["total"] == slim.json()["total"] == 2
    assert slim.json()["page"] == 2
    item = slim.json()["items"][0]
    assert item["sku"] == "SUMMARY-B"
    assert item == {key: full.json()["items"][0][key] for key in item}
    assert "description" not in item
    assert (item["hsn_code"], item["sales_rate"], item["gst_rate"]) == ("8471", 125.50, 18)
    for search in ("7845112345", "Test accessories"):
        result = client.get(path, headers=superuser_headers, params={"summary_only": True, "search": search})
        assert result.status_code == 200
        assert [row["sku"] for row in result.json()["items"]] == ["SUMMARY-B"]


def test_srm_engagement_creates_pms_project(client, db, superuser_headers):
    engagement, _order = create_engagement_via_confirm(client, superuser_headers)
    response = client.post(f"/api/v1/srm/engagements/{engagement['id']}/create-pms-project", headers=superuser_headers)
    assert response.status_code == 200, response.text
    project = response.json()["project"]
    assert project["project_key"].startswith("SRM")
    assert db.query(PMSProject).filter(PMSProject.id == project["id"]).first() is not None
    assert db.query(PMSMilestone).filter(PMSMilestone.project_id == project["id"]).count() >= 2
    assert db.query(PMSTask).filter(PMSTask.project_id == project["id"]).count() >= 1


def test_invoice_summary_keeps_lifecycle_status_without_lines(client, db, superuser_headers):
    invoice = SRMInvoice(
        organization_id=1, invoice_number="SUMMARY-QA", total_amount=100,
        paid_amount=20, balance_amount=80,
        lines=[SRMInvoiceLine(description="Invoice line")],
    )
    db.add(invoice)
    db.commit()
    path = "/api/v1/srm/invoices"
    full = client.get(path, headers=superuser_headers)
    summary = client.get(path, headers=superuser_headers, params={"summary_only": True})
    assert full.status_code == summary.status_code == 200
    assert [row["id"] for row in full.json()] == [row["id"] for row in summary.json()]
    header = next(row for row in summary.json() if row["id"] == invoice.id)
    detailed = next(row for row in full.json() if row["id"] == invoice.id)
    assert detailed["lines"]
    assert header == {field: detailed[field] for field in header}
    assert "lines" not in header
    assert header["payment_status"] == "partially_paid"


def test_srm_engagement_rejects_pms_project_before_sales_order_confirmed(client, db, superuser_headers):
    order = client.post("/api/v1/srm/sales-orders", headers=superuser_headers, json={"title": "Unconfirmed order"}).json()
    engagement = client.post("/api/v1/srm/engagements", headers=superuser_headers, json={
        "name": "Unconfirmed engagement",
        "sales_order_id": order["id"],
    }).json()
    response = client.post(f"/api/v1/srm/engagements/{engagement['id']}/create-pms-project", headers=superuser_headers)
    assert response.status_code == 400
