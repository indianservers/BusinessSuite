import pytest
from app.apps.crm.models import CRMDealContact
from app.models.company import Company, Branch


@pytest.mark.parametrize("endpoint", ["deal_edit", "contact_replace"])
def test_replace_contacts_uses_branch_validated_record_writes(client, db, superuser_headers, endpoint):
    if not db.get(Company, 1):
        db.add(Company(id=1, name="Contact replacement tenant", country="India", email="contact-test@example.test"))
        db.commit()
    company = db.get(Company, 1)
    company.country = "India"
    company.email = "contact-test@example.test"
    db.add(Branch(company_id=1, name="Contact replacement branch", code="CONTACT-REPLACEMENT", is_active=True))
    db.commit()
    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Contact replacement"})
    assert pipeline.status_code == 201, pipeline.text
    stage = client.post(f"/api/v1/crm/pipelines/{pipeline.json()['id']}/stages", headers=superuser_headers, json={"name": "Discovery", "probability": 20})
    assert stage.status_code == 201, stage.text
    payload = {"name": "Contact replacement deal", "pipeline_id": pipeline.json()["id"], "stage_id": stage.json()["id"]}
    identifiers = []
    for name in ("Original contact", "Replacement contact"):
        contact = client.post("/api/v1/crm/contacts", headers=superuser_headers, json={"first_name": name, "full_name": name})
        assert contact.status_code == 201, contact.text
        identifiers.append(contact.json()["id"])
    payload["dealContacts"] = [{"contactId": identifiers[0], "role": "Primary", "isPrimary": True}]
    created = client.post("/api/v1/crm/deals", headers=superuser_headers, json=payload)
    assert created.status_code == 201, created.text
    deal = created.json()
    replacement = [{"contactId": identifiers[1], "role": "Primary", "isPrimary": True}]
    if endpoint == "deal_edit":
        response = client.patch(f"/api/v1/crm/deals/{deal['id']}", headers=superuser_headers,
                                json={"name": "Edited deal", "expected_version": deal["version"], "dealContacts": replacement})
    else:
        response = client.put(f"/api/v1/crm/deals/{deal['id']}/contacts", headers=superuser_headers, json={"contacts": replacement})
    assert response.status_code == 200, response.text
    db.expire_all()
    links = db.query(CRMDealContact).filter(CRMDealContact.deal_id == deal["id"]).all()
    assert [link.contact_id for link in links] == [identifiers[1]]
