"""Shared company identity, communication, and birthday behavior."""
from datetime import date
from app.apps.crm.models import CRMContact, CRMCompany
from app.shared.master_data_models import ContactBirthday
from tests.test_contact_directory import directory_identity

ROOT = "/api/v1/master-data"


def test_contact_assignment_options_use_login_identifiers(client, db, superuser_headers, directory_identity):
    from app.models.user import User
    response = client.get(ROOT + "/contact-assignment-options", headers=superuser_headers)
    assert response.status_code == 200, response.text
    actor = db.query(User).filter_by(email="testadmin@test.com").one()
    assert actor.id in {item["id"] for item in response.json()["items"]}
    assert all(item["id"] == item["userId"] for item in response.json()["items"])


def test_shared_vendor_edit_only_confirms_changed_contact_details(client, db, superuser_headers, directory_identity):
    company(client, superuser_headers, name="First vendor", phone="2025550101", phone_country_code="+1")
    shared = company(client, superuser_headers, name="Shared vendor", phone="2025550101", phone_country_code="+1", confirmShared=True)
    payload = {"name": shared["name"], "phone": shared["phone"], "phone_country_code": "+1", "version": shared["version"], "roles": ["Vendor"], "notes": "Reviewed payment terms"}
    endpoint = f"{ROOT}/companies/{shared['id']}"
    saved = client.patch(endpoint, headers=superuser_headers, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["notes"] == "Reviewed payment terms"
    company(client, superuser_headers, name="Another vendor", phone="2025550102", phone_country_code="+1")
    blocked = client.patch(endpoint, headers=superuser_headers, json={**payload, "version": saved.json()["version"], "phone": "2025550102"})
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "duplicate_contact"


def test_bulk_tag_normalizes_existing_whitespace(client, db, superuser_headers, directory_identity):
    row = company(client, superuser_headers, tags=["Office", "Preferred vendor"])
    for _ in range(2):
        response = client.post(ROOT + "/company-directory/bulk", headers=superuser_headers, json={"ids": [row["id"]], "action": "tag", "value": "Preferred vendor"})
        assert response.status_code == 200, response.text
    record = db.get(CRMCompany, row["id"])
    assert record.tags_text == "Office, Preferred vendor"


def company(client, headers, **values):
    result = client.post(ROOT + "/companies", headers=headers, json={"name": "Shared Company", **values})
    assert result.status_code == 201, result.text
    return result.json()


def test_company_roles_and_nested_contact(client, db, superuser_headers, directory_identity):
    row = company(client, superuser_headers, roles=["Customer", "Vendor", "Supplier"], newPrimaryContact={"name": "Primary person", "email": "person@example.com"})
    assert set(row["roles"]) == {"Customer", "Vendor", "Supplier"}
    for role in row["roles"]:
        response = client.get(ROOT + "/companies", headers=superuser_headers, params={"role": role})
        assert row["id"] in [x["id"] for x in response.json()["items"]]
    profile = client.get(f"{ROOT}/companies/{row['id']}", headers=superuser_headers).json()
    assert row["primaryContactId"] in [x["id"] for x in profile["contacts"]]
    assert not db.query(CRMContact).filter(CRMContact.email == "testadmin@test.com").first()
    duplicate = client.post(ROOT + "/companies", headers=superuser_headers, json={"name": row["name"]})
    assert duplicate.status_code == 409


def test_secondary_phone_country_and_optional_sharing_reason(client, db, superuser_headers, directory_identity):
    first = company(client, superuser_headers, name="First", phone="9876543210", phone_country_code="+91")
    endpoint = f"{ROOT}/company/{first['id']}/channels"
    channels = client.get(endpoint, headers=superuser_headers).json()
    values = [{"kind": "phone", "value": "9876543210", "countryCode": "+91", "primary": True}, {"kind": "phone", "value": "9123456780", "countryCode": "+91", "label": "Home"}, {"kind": "email", "value": "work@example.com", "primary": True}, {"kind": "email", "value": "home@example.com"}]
    saved = client.put(endpoint, headers=superuser_headers, json={"version": channels["version"], "items": values})
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["items"]) == 4
    attempt = client.post(ROOT + "/companies", headers=superuser_headers, json={"name": "Family", "phone": "+91 91234 56780", "phone_country_code": "+91"})
    assert attempt.status_code == 409, attempt.text
    shared = company(client, superuser_headers, name="Family", phone="9123456780", phone_country_code="+91", confirmShared=True)
    assert shared["id"] != first["id"]
    company(client, superuser_headers, name="Other country", phone="9123456780", phone_country_code="+1")
    stale = client.put(endpoint, headers=superuser_headers, json={"version": channels["version"], "items": []})
    assert stale.status_code == 409
    assert db.get(CRMCompany, first["id"]).email == "work@example.com"


def test_partial_birthday_consent_and_hr_boundary(client, db, superuser_headers, directory_identity):
    response = client.post("/api/v1/crm/contact-directory", headers=superuser_headers, json={"name": "Birthday person"})
    assert response.status_code == 200, response.text
    contact = response.json()
    endpoint = f"{ROOT}/contact/{contact['id']}/birthday"
    response = client.put(endpoint, headers=superuser_headers, json={"day": 29, "month": 2, "version": 0})
    assert response.status_code == 200, response.text
    assert response.json()["year"] is None and "age" not in response.json()
    assert db.get(CRMContact, contact["id"]).date_of_birth is None
    assert db.query(ContactBirthday).filter_by(contact_id=contact["id"]).one().birth_year is None
    denied = client.post(endpoint + "/prepare-greeting", headers=superuser_headers, json={"year": date.today().year, "channel": "email"})
    assert denied.status_code == 409
    invalid = client.put(endpoint, headers=superuser_headers, json={"day": 31, "month": 2, "version": 1})
    assert invalid.status_code == 422
    assert client.get(f"{ROOT}/employee/1/birthday", headers=superuser_headers).status_code == 403


def test_grid_bulk_export_and_source_identity(client, db, superuser_headers, directory_identity):
    import json
    row = company(client, superuser_headers, name="=Shared vendor", roles=["Customer"])
    result = client.post(ROOT + "/company-directory/bulk", headers=superuser_headers, json={"ids":[row["id"]], "action":"role", "value":"Vendor"}, params={"source":"srm"})
    assert result.status_code == 200, result.text
    result = client.get(ROOT + "/company-directory/query", headers=superuser_headers, params={"source":"srm","role":"Vendor","state":json.dumps({"search":"Shared vendor"})})
    assert result.status_code == 200, result.text
    assert [x["id"] for x in result.json()["rows"]] == [row["id"]]
    assert set(result.json()["rows"][0]["roles"]) >= {"Customer","Vendor"}
    output = client.post(ROOT + "/company-directory/export", headers=superuser_headers, json={"ids":[row["id"]],"columns":["name","roles"]}, params={"source":"srm"})
    assert output.status_code == 200, output.text
    assert "'=Shared vendor" in output.text
    response = client.get(ROOT + "/companies", headers=superuser_headers, params={"source":"project_management"})
    assert row["id"] in [x["id"] for x in response.json()["items"]]


def test_company_reader_cannot_create_or_access_hr(client, db, superuser_headers, directory_identity):
    from tests.test_crm_phase_1_core_foundation import _headers_for_permissions
    from app.models.user import User
    from app.branches.models import BranchGrant
    headers = _headers_for_permissions(client, db, "company-reader@example.com", ["crm_companies_view"])
    user = db.query(User).filter_by(email="company-reader@example.com").one()
    grant = db.query(BranchGrant).filter_by(company_id=1,user_id=user.id,branch_id=directory_identity.id).one()
    grant.can_write = False
    db.commit()
    response = client.get(ROOT + "/companies", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["canCreate"] is False
    assert client.post(ROOT + "/companies",headers=headers,json={"name":"Forbidden"}).status_code == 403
    assert client.get(ROOT + "/birthdays/upcoming",headers=headers,params={"source":"hrms"}).status_code == 403


def test_contact_form_channels_and_greeting_idempotence(client, db, superuser_headers, directory_identity):
    result = client.post("/api/v1/crm/contact-directory",headers=superuser_headers,json={"name":"Same contact","email":"same@example.com","communication_channels":[{"kind":"email","value":"same@example.com","primary":True},{"kind":"email","value":"second@example.com"}]})
    assert result.status_code == 200, result.text
    contact = result.json()
    channels = client.get(f"{ROOT}/contact/{contact['id']}/channels",headers=superuser_headers).json()
    assert len(channels["items"]) == 2
    endpoint=f"{ROOT}/contact/{contact['id']}/birthday"
    birthday=client.put(endpoint,headers=superuser_headers,json={"day":3,"month":11,"version":0,"emailOptIn":True})
    assert birthday.status_code == 200, birthday.text
    payload={"channel":"email","year":date.today().year}
    first=client.post(endpoint+"/prepare-greeting",headers=superuser_headers,json=payload)
    second=client.post(endpoint+"/prepare-greeting",headers=superuser_headers,json=payload)
    assert first.status_code == second.status_code == 200, first.text
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["alreadyPrepared"] and "mailto:" in second.json()["composeUrl"]


def test_postgresql_concurrent_phone_review(db):
    import pytest
    if db.bind.dialect.name != "postgresql":
        pytest.skip("Requires disposable PostgreSQL test database")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.orm import sessionmaker
    from fastapi import HTTPException
    from app.models.user import User
    from app.branches.boundary import install
    from app.branches.service import context
    from app.shared.master_data import write_company, CompanyInput
    from app.models.company import Branch
    factory=sessionmaker(bind=db.get_bind().engine,autoflush=False)
    with factory() as seed:
        actor=User(email="concurrent-master@example.com",hashed_password="unused",is_active=True,is_superuser=True)
        branch=Branch(company_id=1,name="Concurrent master capture",code="MCAP")
        seed.add_all([actor,branch]);seed.commit()
        branch_id=branch.id
    gate=Barrier(2)
    def capture(index):
        session=factory()
        actor=session.query(User).filter_by(email="concurrent-master@example.com").one()
        actor.organization_id = 1  # Request middleware normally supplies this context.
        cleanup=install(session,actor,context(session,actor,1,str(branch_id)))
        session.info["security_write_request"]=True
        try:
            gate.wait(timeout=15)
            write_company(session,actor,"crm",CompanyInput(name=f"Concurrent {index}",phone="9234567890",phone_country_code="+91"))
            session.commit()
            return 201
        except HTTPException as exc:
            session.rollback()
            return exc.status_code
        finally:
            cleanup();session.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(capture,[1,2]))
    assert sorted(results)==[201,409]


def test_relationship_edits_reject_stale_version(client, db, superuser_headers, directory_identity):
    row=company(client,superuser_headers,roles=["Customer","Vendor"])
    payload={"role":"Vendor","version":row["version"],"paymentTerms":"Net 30","creditLimit":"10000"}
    endpoint=f"{ROOT}/company/{row['id']}/relationship"
    first=client.put(endpoint,headers=superuser_headers,json=payload)
    assert first.status_code==200,first.text
    stale=client.put(endpoint,headers=superuser_headers,json=payload)
    assert stale.status_code==409,stale.text

def test_customer_location_grouping_uses_saved_primary_address(client, db, superuser_headers, directory_identity):
    import json
    rows = [company(client, superuser_headers, name=f"Location customer {index}", roles=["Customer"],
                    addresses=[{"type": "Billing", "state": state, "city": city, "postalCode": pin}])
            for index, (state, city, pin) in enumerate([
                ("Telangana", "Hyderabad", "500001"), ("Maharashtra", "Pune", "411001"),
                ("Telangana", "Hyderabad", "500001"), ("", "", "")])]
    for field, expected in [("state", {"Telangana": 2, "Maharashtra": 1, "Not set": 1}),
                            ("city", {"Hyderabad": 2, "Pune": 1, "Not set": 1}),
                            ("pincode", {"500001": 2, "411001": 1, "Not set": 1})]:
        result = client.get(ROOT + "/company-directory/query", headers=superuser_headers,
                            params={"role": "Customer", "state": json.dumps({"search": "Location customer", "grouping": [field]})})
        assert result.status_code == 200, result.text
        groups = result.json()["groups"]
        assert {group["label"]: group["count"] for group in groups} == expected
        for group in groups:
            expanded = client.get(ROOT + "/company-directory/query", headers=superuser_headers,
                params={"role": "Customer", "state": json.dumps({"search": "Location customer", "grouping": [field], "path": group["path"]})})
            assert expanded.status_code == 200, expanded.text
            records = expanded.json()["rows"]
            assert len(records) == group["count"]
            assert all(record[field] == group["value"] for record in records)


def test_customer_services_and_market_types(client, db, superuser_headers, directory_identity):
    row = company(client, superuser_headers, name="Service customer", roles=["Customer"], services_offered="Accounting, Consulting", business_types=["B2B", "B2C"])
    assert row["services_offered"] == ["Accounting", "Consulting"]
    assert row["business_types"] == ["B2B", "B2C"]
    endpoint = f"{ROOT}/companies/{row['id']}"
    saved = client.patch(endpoint, headers=superuser_headers, json={"name": row["name"], "version": row["version"], "services_offered": ["Training"], "business_types": ["B2G"]})
    assert saved.status_code == 200, saved.text
    profile = client.get(endpoint, headers=superuser_headers).json()
    assert profile["services_offered"] == ["Training"]
    assert profile["business_types"] == ["B2G"]
    # An older client omitting these fields must preserve the profile.
    preserved = client.patch(endpoint, headers=superuser_headers, json={"name": row["name"], "version": profile["version"]})
    assert preserved.status_code == 200, preserved.text
    assert preserved.json()["services_offered"] == ["Training"]
    invalid = client.patch(endpoint, headers=superuser_headers, json={"name": row["name"], "version": preserved.json()["version"], "business_types": ["B2X"]})
    assert invalid.status_code == 422
