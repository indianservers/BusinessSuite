"""CRM relationship pages use one canonical master, including Sales customers."""
import json
import pytest
from app.apps.crm.models import CRMCompany, CRMLead, CRMContact
from tests.test_master_data import company, ROOT
from tests.test_contact_directory import directory_identity


def grid(client, headers, **params):
    response = client.get(ROOT + "/company-directory/query", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()["rows"]


def test_separate_customer_company_vendor_views_share_sales_identity(client, db, superuser_headers, directory_identity):
    person = company(client, superuser_headers, name="Individual buyer", entityKind="Individual", roles=["Customer"])
    business = company(client, superuser_headers, name="Business buyer and vendor", entityKind="Company", roles=["Customer", "Vendor"])
    prospect = company(client, superuser_headers, name="Prospect company", roles=["Prospect"])
    assert person["entityKind"] == "Individual"
    assert {x["id"] for x in grid(client, superuser_headers, entity_kind="companies")} == {business["id"], prospect["id"]}
    assert {x["id"] for x in grid(client, superuser_headers, role="Customer")} == {person["id"], business["id"]}
    assert {x["id"] for x in grid(client, superuser_headers, role="Vendor", source="srm")} == {business["id"]}
    sales = client.get("/api/v1/srm/business/customers", headers=superuser_headers)
    assert sales.status_code == 200, sales.text
    assert {x["id"] for x in sales.json()["items"]} == {person["id"], business["id"]}
    assert db.query(CRMCompany).count() == 3
    response = client.get(ROOT + "/companies", headers=superuser_headers, params={"entity_kind":"individuals"})
    assert [x["id"] for x in response.json()["items"]] == [person["id"]]
    export = client.post(ROOT + "/company-directory/export", headers=superuser_headers, params={"entity_kind":"companies"}, json={"columns":["name"], "state":json.dumps({})})
    assert export.status_code == 200, export.text
    assert person["name"] not in export.text and business["name"] in export.text


def test_sales_created_customer_uses_same_master_and_classification(client, db, superuser_headers, directory_identity):
    response = client.post("/api/v1/srm/business/customers", headers=superuser_headers, json={"name":"Sales individual"})
    assert response.status_code == 201, response.text
    ident = response.json()["id"]
    assert [x["id"] for x in grid(client, superuser_headers, role="Customer")] == [ident]
    assert not grid(client, superuser_headers, entity_kind="companies")
    assert db.query(CRMCompany).count() == 1


@pytest.mark.parametrize("customer_type", ["Individual", "Business"])
def test_lead_conversion_becomes_same_sales_customer(client, db, superuser_headers, directory_identity, customer_type):
    from app.branches.migration import backfill
    lead = CRMLead(organization_id=1, branch_id=directory_identity.id, first_name="Converted", full_name="Converted buyer", company_name="Converted business" if customer_type == "Business" else None, status="Qualified")
    db.add(lead); db.commit()
    backfill(db.connection(), 1); db.commit()
    response = client.post("/api/v1/crm/contact-directory/convert", headers=superuser_headers, json={"leadId":lead.id, "customerType":customer_type})
    assert response.status_code == 200, response.text
    db.expire_all()
    ident = db.get(CRMLead, lead.id).converted_company_id
    assert ident
    assert db.query(CRMContact).filter(CRMContact.full_name == "Converted buyer").count() == 1
    assert [x["id"] for x in grid(client, superuser_headers, role="Customer")] == [ident]
    assert bool(grid(client, superuser_headers, entity_kind="companies")) == (customer_type == "Business")
    sales = client.get("/api/v1/srm/business/customers", headers=superuser_headers)
    assert ident in {x["id"] for x in sales.json()["items"]}

    corrected = client.post(f"/api/v1/crm/contact-directory/leads/{lead.id}/correct-conversion", headers=superuser_headers, json={"reason":"Review and reconvert the same identity"})
    assert corrected.status_code == 200, corrected.text
    assert not grid(client, superuser_headers, role="Customer")
    repeated = client.post("/api/v1/crm/contact-directory/convert", headers=superuser_headers, json={"leadId":lead.id, "customerType":customer_type})
    assert repeated.status_code == 200, repeated.text
    db.expire_all()
    assert db.get(CRMLead, lead.id).converted_company_id == ident
    assert db.query(CRMCompany).count() == 1
