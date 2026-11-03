"""Canonical identity, access isolation, safe mutations and retained history."""
from datetime import date
import pytest
from fastapi import HTTPException
from app.apps.crm.models import CRMContact, CRMLead, CRMCompany, CRMNote
from app.apps.crm.contact_identity import ContactIdentityLink
from app.apps.crm.contact_directory import ContactEdit, apply_edit, labels, filtered
from app.models.user import User
from app.models.employee import Employee

ROOT = "/api/v1/crm/contact-directory"


@pytest.fixture(autouse=True)
def directory_identity(db, superuser_headers):
    from test_identity_utils import attach_test_identity
    from app.models.company import Branch
    from app.branches.migration import backfill
    user = db.query(User).filter(User.email == "testadmin@test.com").one()
    attach_test_identity(db, user)
    branch = Branch(company_id=1, name="Directory branch", code="DIR")
    db.add(branch); db.commit()
    backfill(db.connection(), 1); db.commit()
    return branch


def new_contact(client, headers, **values):
    result = client.post(ROOT, headers=headers, json={"name": "Ravi Kumar", "email": "ravi@example.com", "tags": ["Customer", "Vendor", "Partner"], **values})
    assert result.status_code == 200, result.text
    return result.json()


def test_multiple_relationships_counts_filters_and_conflicts(client, db, superuser_headers):
    row = new_contact(client, superuser_headers)
    assert set(row["tags"]) >= {"Customer", "Vendor", "Partner"}
    listing = client.get(ROOT, headers=superuser_headers, params={"relationship": "Vendor"})
    assert listing.status_code == 200, listing.text
    assert row["id"] in {x["id"] for x in listing.json()["items"]}
    assert listing.json()["stats"]["Customer"] >= 1
    edit = {"name": "Ravi edited", "email": "ravi@example.com", "tags": ["Customer", "Vendor"], "version": row["version"]}
    saved = client.patch(f"{ROOT}/{row['id']}", headers=superuser_headers, json=edit)
    assert saved.status_code == 200, saved.text
    stale = client.patch(f"{ROOT}/{row['id']}", headers=superuser_headers, json=edit)
    assert stale.status_code == 409
    forbidden = client.patch(f"{ROOT}/{row['id']}", headers=superuser_headers, json={**edit, "version": saved.json()["version"], "role_id": 1})
    assert forbidden.status_code == 422


def test_no_employee_or_account_publication_from_hr(client, db, superuser_headers):
    before = db.query(CRMContact).count()
    person = User(email="private.employee@example.test", hashed_password="unused", is_active=True)
    db.add(person); db.flush()
    employee = Employee(user_id=person.id, employee_id="PRIVATE-ONLY", first_name="Private", last_name="Employee", date_of_joining=date(2026, 1, 1))
    db.add(employee); db.commit()
    response = client.post(ROOT + "/backfill", headers=superuser_headers)
    assert response.status_code == 200, response.text
    assert db.query(ContactIdentityLink).filter(ContactIdentityLink.employee_id == employee.id).count() == 0
    assert db.query(CRMContact).filter(CRMContact.email == person.email).count() == 0
    result = client.get(ROOT, headers=superuser_headers, params={"relationship": "Employee"})
    assert result.status_code == 200 and not result.json()["items"]
    result = client.post(ROOT, headers=superuser_headers, json={"name": "Invalid role", "tags": ["Admin"]})
    assert result.status_code == 422


def test_trash_and_restore_do_not_delete_history(client, db, superuser_headers):
    row = new_contact(client, superuser_headers)
    note = CRMNote(organization_id=1, contact_id=row["id"], body="History remains")
    db.add(note); db.commit()
    from app.branches.migration import backfill
    backfill(db.connection(), 1); db.commit()
    response = client.post(ROOT + "/bulk", headers=superuser_headers, json={"ids": [row["id"]], "action": "trash"})
    assert response.status_code == 200, response.text
    assert client.get(f"{ROOT}/{row['id']}", headers=superuser_headers).status_code == 404
    assert db.get(CRMNote, note.id) is not None
    deleted = client.get(ROOT, headers=superuser_headers, params={"deleted": True}).json()
    assert row["id"] in {x["id"] for x in deleted["items"]}
    response = client.post(ROOT + "/bulk", headers=superuser_headers, json={"ids": [row["id"]], "action": "restore"})
    assert response.status_code == 200, response.text
    assert client.get(f"{ROOT}/{row['id']}", headers=superuser_headers).status_code == 200


def test_backfill_reuses_converted_identity_and_is_idempotent(client, db, superuser_headers):
    row = new_contact(client, superuser_headers)
    lead = CRMLead(organization_id=1, first_name="Ravi", full_name="Ravi Kumar", email="ravi@example.com", is_converted=True, converted_contact_id=row["id"], status="Converted")
    db.add(lead); db.commit()
    from app.branches.migration import backfill
    backfill(db.connection(), 1); db.commit()
    count = db.query(CRMContact).count()
    for _ in range(2):
        result = client.post(ROOT + "/backfill", headers=superuser_headers)
        assert result.status_code == 200, result.text
    assert db.query(CRMContact).count() == count
    link = db.query(ContactIdentityLink).filter(ContactIdentityLink.lead_id == lead.id).one()
    assert link.contact_id == row["id"]


def test_export_escapes_spreadsheet_formula_injection(client, superuser_headers):
    new_contact(client, superuser_headers, name="=HYPERLINK dangerous")
    result = client.get(ROOT + "/export", headers=superuser_headers)
    assert result.status_code == 200, result.text
    assert "'=HYPERLINK dangerous" in result.text


def test_directory_branch_scope_and_bulk_atomicity(db):
    from tests.test_branch_access import setup
    from app.branches.boundary import install
    from app.branches.service import context
    from app.apps.crm.contact_directory import base, bulk, Bulk
    actor, a, b, first, second, hidden = setup(db)
    actor.is_superuser = True
    db.flush()
    cleanup = install(db, actor, context(db, actor, 1, str(a.id)))
    try:
        visible = CRMContact(organization_id=1, branch_id=a.id, first_name="Visible", full_name="Visible")
        db.add(visible); db.flush()
        assert hidden.id not in {x.id for x in base(db, actor)}
        with pytest.raises(HTTPException):
            bulk(Bulk(ids=[visible.id, hidden.id], action="trash"), db, actor)
        assert visible.deleted_at is None
    finally:
        cleanup()


def test_conversion_reuses_identity_preserves_history_and_correction(client, db, superuser_headers, directory_identity):
    from app.branches.migration import backfill
    lead = CRMLead(organization_id=1, branch_id=directory_identity.id, first_name="Canonical", full_name="Canonical Customer", email="canonical@example.com", status="Qualified", notes="Lead history")
    db.add(lead); db.commit()
    backfill(db.connection(), 1); db.commit()
    result = client.post(ROOT + "/backfill", headers=superuser_headers)
    assert result.status_code == 200, result.text
    contact_id = db.query(ContactIdentityLink).filter(ContactIdentityLink.lead_id == lead.id).one().contact_id
    result = client.post(ROOT + "/convert", headers=superuser_headers, json={"leadId": lead.id, "existingContactId": contact_id, "customerType": "Individual"})
    assert result.status_code == 200, result.text
    assert result.json()["contact"]["id"] == contact_id
    db.expire_all()
    assert db.get(CRMLead, lead.id).notes == "Lead history"
    assert "Customer" in labels(db.get(CRMContact, contact_id))
    repeated = client.post(ROOT + "/convert", headers=superuser_headers, json={"leadId": lead.id, "existingContactId": contact_id})
    assert repeated.status_code == 409
    result = client.post(f"{ROOT}/leads/{lead.id}/correct-conversion", headers=superuser_headers, json={"reason": "Selected conversion in error"})
    assert result.status_code == 200, result.text
    db.expire_all()
    assert not db.get(CRMLead, lead.id).is_converted
    assert db.get(CRMLead, lead.id).converted_contact_id == contact_id
    assert db.get(CRMLead, lead.id).notes == "Lead history"


def test_merge_moves_identity_links_notes_and_blocks_restore(client, db, superuser_headers, directory_identity):
    from app.branches.migration import backfill
    first = new_contact(client, superuser_headers, name="Keep", email="keep@example.com")
    second = new_contact(client, superuser_headers, name="Merge", email="merge@example.com")
    lead = CRMLead(organization_id=1, branch_id=directory_identity.id, first_name="Merge", full_name="Merge", status="Qualified")
    db.add(lead); db.flush()
    db.add(ContactIdentityLink(organization_id=1, contact_id=second["id"], lead_id=lead.id))
    note = CRMNote(organization_id=1, contact_id=second["id"], body="Preserved source note")
    db.add(note); db.commit()
    backfill(db.connection(), 1); db.commit()
    result = client.post("/api/v1/crm/duplicates/merge", headers=superuser_headers, json={"entityType": "contacts", "winnerId": first["id"], "loserIds": [second["id"]], "allowUndetected": True})
    assert result.status_code == 200, result.text
    db.expire_all()
    assert db.get(CRMNote, note.id).contact_id == first["id"]
    assert db.query(ContactIdentityLink).filter(ContactIdentityLink.lead_id == lead.id).one().contact_id == first["id"]
    result = client.post(ROOT + "/bulk", headers=superuser_headers, json={"action": "restore", "ids": [second["id"]]})
    assert result.status_code == 409, result.text


def test_read_permission_does_not_grant_mutation_or_hr_access(client, db, superuser_headers, directory_identity):
    from tests.test_crm_phase_1_core_foundation import _headers_for_permissions
    from app.branches.models import BranchGrant
    row = new_contact(client, superuser_headers)
    reader = _headers_for_permissions(client, db, "contact-reader@example.com", ["crm_contacts_view"])
    user = db.query(User).filter(User.email == "contact-reader@example.com").one()
    db.add(BranchGrant(company_id=1, user_id=user.id, branch_id=directory_identity.id, can_write=False)); db.commit()
    listing = client.get(ROOT, headers=reader)
    assert listing.status_code == 200, listing.text
    assert not listing.json()["canManage"]
    assert client.post(ROOT, headers=reader, json={"name": "Forbidden"}).status_code == 403
    assert client.post(ROOT + "/bulk", headers=reader, json={"ids": [row["id"]], "action": "trash"}).status_code == 403
    assert client.post(ROOT + "/backfill", headers=reader).status_code == 403
    assert client.delete(f"{ROOT}/{row['id']}/permanent", headers=reader).status_code == 403
    no_contacts = _headers_for_permissions(client, db, "hr-only@example.com", ["employee_view", "employee_update"])
    assert client.get(ROOT, headers=no_contacts).status_code == 403


def test_writes_sync_business_identities_but_never_hr_identities(db, directory_identity):
    from app.branches.boundary import install
    from app.branches.service import context
    from app.common.models import CommonPerson
    actor = db.query(User).filter(User.email == "testadmin@test.com").one()
    cleanup = install(db, actor, context(db, actor, 1, str(directory_identity.id)))
    db.info["security_write_request"] = True
    try:
        employee_user = User(email="private-sync@example.com", hashed_password="unused", is_active=True)
        db.add(employee_user); db.flush()
        employee = Employee(user_id=employee_user.id, employee_id="NO-PUBLISH", first_name="Private", last_name="Identity", branch_id=directory_identity.id, date_of_joining=date(2026, 1, 1))
        person = CommonPerson(organization_id=1, user_id=employee_user.id, primary_email=employee_user.email, display_name="Private identity")
        lead = CRMLead(organization_id=1, first_name="Public", full_name="Public business lead", email="public@example.com", status="New")
        db.add_all([employee, person, lead]); db.flush()
        assert db.query(CRMContact).filter(CRMContact.email == employee_user.email).count() == 0
        link = db.query(ContactIdentityLink).filter(ContactIdentityLink.lead_id == lead.id).one()
        assert link.contact.email == lead.email
        lead.full_name = "Updated business lead"
        db.flush()
        assert link.contact.full_name == "Updated business lead"
    finally:
        db.info.pop("security_write_request", None)
        cleanup()


def test_advanced_boolean_filters_favorites_and_duplicate_capture(client, superuser_headers):
    import json
    alpha = new_contact(client, superuser_headers, name="Alpha Contact", email="alpha@example.com", tags=["Vendor"])
    beta = new_contact(client, superuser_headers, name="Beta Contact", email="beta@example.com", tags=["Customer"])
    conditions = json.dumps([{"field": "tag", "operator": "equals", "value": "Vendor"}, {"field": "name", "operator": "contains", "value": "Beta"}])
    assert client.get(ROOT, headers=superuser_headers, params={"filters": conditions, "match": "and"}).json()["total"] == 0
    result = client.get(ROOT, headers=superuser_headers, params={"filters": conditions, "match": "or"})
    assert {x["id"] for x in result.json()["items"]} == {alpha["id"], beta["id"]}
    result = client.get(ROOT, headers=superuser_headers, params={"ids": str(beta["id"])})
    assert [x["id"] for x in result.json()["items"]] == [beta["id"]]
    exported = client.get(ROOT + "/export", headers=superuser_headers, params={"ids": str(beta["id"])})
    assert "Beta Contact" in exported.text and "Alpha Contact" not in exported.text
    duplicate = client.post(ROOT, headers=superuser_headers, json={"name": "Duplicate", "email": " ALPHA@example.com "})
    assert duplicate.status_code == 409


def test_permanent_deletion_is_admin_only_and_protects_referenced_contacts(client, db, superuser_headers):
    free = new_contact(client, superuser_headers, email="unused@example.com")
    used = new_contact(client, superuser_headers, email="retained@example.com")
    db.add(CRMNote(organization_id=1, contact_id=used["id"], body="Retain this history")); db.commit()
    for row in [free, used]:
        assert client.post(ROOT + "/bulk", headers=superuser_headers, json={"ids": [row["id"]], "action": "trash"}).status_code == 200
    assert client.delete(f"{ROOT}/{used['id']}/permanent", headers=superuser_headers).status_code == 409
    result = client.delete(f"{ROOT}/{free['id']}/permanent", headers=superuser_headers)
    assert result.status_code == 200, result.text
    db.expire_all()
    assert db.get(CRMContact, free["id"]) is None
    assert db.get(CRMContact, used["id"]) is not None

def financial_details():
    return {"gstNumber": "27ABCDE1234F1Z5", "bankAccounts": [
        {"holderName": "Ravi Kumar", "bankName": "Example Bank", "accountNumber": "001234567890", "ifsc": "SBIN0001234", "micr": "400002001", "primary": True},
        {"holderName": "Ravi Kumar", "bankName": "Other Bank", "accountNumber": "009876543210", "ifsc": "HDFC0001234", "primary": False}],
        "upiIds": [{"upiId": "ravi@bank", "mobile": "+919876543210", "primary": True}, {"upiId": "business@bank", "mobile": "9876543210"}]}


def test_financial_profile_roundtrip_conflict_and_optional(client, superuser_headers):
    row = new_contact(client, superuser_headers, financialData=financial_details())
    endpoint = f"{ROOT}/{row['id']}/financial-data"
    saved = client.get(endpoint, headers=superuser_headers)
    assert saved.status_code == 200, saved.text
    data = saved.json()
    data.pop("canManage", None)
    data.pop("canVoid", None)
    assert data["bankAccounts"][0]["accountNumber"] == "001234567890"
    assert len(data["upiIds"]) == 2 and data["version"] == 1
    listing = client.get(ROOT, headers=superuser_headers).json()
    summary = next(x for x in listing["items"] if x["id"] == row["id"])
    assert summary["gstNumber"] == data["gstNumber"] and summary["bankAccountCount"] == 2 and summary["upiCount"] == 2
    data["gstNumber"] = ""
    assert client.put(endpoint, headers=superuser_headers, json=data).status_code == 200
    assert client.put(endpoint, headers=superuser_headers, json=data).status_code == 409
    for key, value in [("gstNumber", "INVALID"), ("bankAccounts", [{"accountNumber": "123", "ifsc": "BAD"}]), ("bankAccounts", [{"accountNumber": "123", "micr": "123"}]), ("upiIds", [{"upiId": "invalid"}])]:
        invalid = {**financial_details(), key: value, "version": 2}
        assert client.put(endpoint, headers=superuser_headers, json=invalid).status_code == 422
    blank = new_contact(client, superuser_headers, name="No financial data", email="optional@example.com")
    result = client.get(f"{ROOT}/{blank['id']}/financial-data", headers=superuser_headers)
    assert result.status_code == 200 and result.json()["bankAccounts"] == []


def test_financial_transactions_persist_and_validate(client, superuser_headers):
    row = new_contact(client, superuser_headers)
    endpoint = f"{ROOT}/{row['id']}/financial-transactions"
    body = {"requestId": "035a40dd-833f-431f-b29a-4c4c56f3e1ae", "direction": "received", "amount": "123.45", "currency": "INR", "transactionDate": "2026-11-03", "method": "UPI", "reference": "UTR-123", "notes": "Invoice payment"}
    saved = client.post(endpoint, headers=superuser_headers, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["amount"] == "123.45"
    repeated = client.post(endpoint, headers=superuser_headers, json=body)
    assert repeated.status_code == 200 and repeated.json()["id"] == saved.json()["id"]
    changed = client.post(endpoint, headers=superuser_headers, json={**body, "amount": "456.78"})
    assert changed.status_code == 409
    for amount in ["0", "-10", "1.234"]:
        assert client.post(endpoint, headers=superuser_headers, json={**body, "amount": amount}).status_code == 422
    listing = client.get(endpoint, headers=superuser_headers)
    assert listing.status_code == 200 and listing.json()["total"] == 1
    assert listing.json()["items"][0]["reference"] == "UTR-123"
    # Updating a bank profile never replaces transaction history.
    assert client.put(f"{ROOT}/{row['id']}/financial-data", headers=superuser_headers, json=financial_details()).status_code == 200
    assert client.get(endpoint, headers=superuser_headers).json()["total"] == 1


def test_financial_access_scope_and_read_only(client, db, superuser_headers, directory_identity):
    from tests.test_crm_phase_1_core_foundation import _headers_for_permissions
    from app.branches.models import BranchGrant
    row = new_contact(client, superuser_headers)
    reader = _headers_for_permissions(client, db, "financial-reader@example.com", ["crm_contacts_view"])
    actor = db.query(User).filter_by(email="financial-reader@example.com").one()
    db.add(BranchGrant(company_id=1, user_id=actor.id, branch_id=directory_identity.id, can_write=False)); db.commit()
    endpoint = f"{ROOT}/{row['id']}"
    # A contacts viewer still cannot see a record outside their visibility.
    assert client.get(endpoint + "/financial-data", headers=reader).status_code == 404
    contact = db.get(CRMContact, row["id"])
    contact.owner_user_id, contact.branch_id = actor.id, directory_identity.id
    db.commit()
    from app.branches.migration import backfill
    backfill(db.connection(), 1); db.commit()
    assert client.get(endpoint + "/financial-data", headers=reader).status_code == 200
    assert client.put(endpoint + "/financial-data", headers=reader, json=financial_details()).status_code == 403
    assert client.post(endpoint + "/financial-transactions", headers=reader, json={"direction":"paid", "amount":"1", "transactionDate":"2026-11-03", "method":"Cash"}).status_code == 403
    outsider = _headers_for_permissions(client, db, "financial-outsider@example.com", ["employee_view"])
    assert client.get(endpoint + "/financial-data", headers=outsider).status_code == 403
    assert client.get(endpoint + "/financial-transactions", headers=outsider).status_code == 403


def test_financial_data_in_legacy_contact_capture(client, superuser_headers):
    response = client.post("/api/v1/crm/contacts", headers=superuser_headers, json={"first_name": "Legacy", "full_name": "Legacy Financial", "email": "legacy-financial@example.com", "financialData": financial_details()})
    assert response.status_code == 201, response.text
    ident = response.json()["id"]
    data = client.get(f"{ROOT}/{ident}/financial-data", headers=superuser_headers).json()
    data.pop("canManage", None)
    data.pop("canVoid", None)
    assert data["gstNumber"] == "27ABCDE1234F1Z5"
    assert data["bankAccounts"][0]["accountNumber"] == "001234567890"
    data["bankAccounts"][0]["micr"] = "500002001"
    response = client.patch(f"/api/v1/crm/contacts/{ident}", headers=superuser_headers, json={"financialData": data})
    assert response.status_code == 200, response.text
    saved = client.get(f"{ROOT}/{ident}/financial-data", headers=superuser_headers).json()
    assert saved["bankAccounts"][0]["micr"] == "500002001"

def test_financial_history_survives_contact_merge(client, db, superuser_headers):
    first = new_contact(client, superuser_headers, name="Financial survivor", email="finance-keep@example.com")
    second = new_contact(client, superuser_headers, name="Financial source", email="finance-source@example.com", financialData=financial_details())
    endpoint = f"{ROOT}/{second['id']}/financial-transactions"
    result = client.post(endpoint, headers=superuser_headers, json={"direction": "paid", "amount": "500.00", "transactionDate": "2026-11-03", "method": "Bank transfer", "reference": "MERGE-UTR"})
    assert result.status_code == 200, result.text
    result = client.post("/api/v1/crm/duplicates/merge", headers=superuser_headers, json={"entityType": "contacts", "winnerId": first["id"], "loserIds": [second["id"]], "allowUndetected": True})
    assert result.status_code == 200, result.text
    profile = client.get(f"{ROOT}/{first['id']}/financial-data", headers=superuser_headers)
    assert profile.status_code == 200 and len(profile.json()["bankAccounts"]) == 2
    records = client.get(f"{ROOT}/{first['id']}/financial-transactions", headers=superuser_headers)
    assert records.status_code == 200 and records.json()["items"][0]["reference"] == "MERGE-UTR"


def test_financial_crud_corrections_voiding_and_clear(client, superuser_headers):
    row = new_contact(client, superuser_headers, financialData=financial_details())
    root = f"{ROOT}/{row['id']}"
    body = {"direction":"received", "amount":"10.00", "transactionDate":"2026-11-03", "method":"Cash"}
    created = client.post(root + "/financial-transactions", headers=superuser_headers, json=body)
    assert created.status_code == 200, created.text
    tx = created.json()
    endpoint = root + f"/financial-transactions/{tx['id']}"
    update = {**body, "amount":"20.25", "version":tx["version"], "reason":"Correct original amount"}
    corrected = client.patch(endpoint, headers=superuser_headers, json=update)
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["amount"] == "20.25"
    assert client.patch(endpoint, headers=superuser_headers, json=update).status_code == 409
    void = client.request("DELETE", endpoint, headers=superuser_headers, json={"version":corrected.json()["version"], "reason":"Duplicate cash entry"})
    assert void.status_code == 200 and void.json()["status"] == "void", void.text
    detail = client.get(endpoint, headers=superuser_headers)
    assert detail.status_code == 200 and detail.json()["status"] == "void"
    assert "no-store" in detail.headers["cache-control"]
    other = new_contact(client, superuser_headers, name="Other payer", email="other-payer@example.com")
    assert client.get(f"{ROOT}/{other['id']}/financial-transactions/{tx['id']}", headers=superuser_headers).status_code == 404
    assert client.patch(endpoint, headers=superuser_headers, json={**update, "version":void.json()["version"]}).status_code == 409
    clear = client.delete(root + "/financial-data", headers=superuser_headers, params={"version":1})
    assert clear.status_code == 200 and clear.json()["bankAccounts"] == []
    assert client.delete(root + "/financial-data", headers=superuser_headers, params={"version":1}).status_code == 409
    listing = client.get(root + "/financial-transactions", headers=superuser_headers).json()
    assert listing["total"] == 1 and listing["items"][0]["voidReason"] == "Duplicate cash entry"


def test_financial_columns_sort_export_and_duplicate_bank_identity(client, superuser_headers):
    details = financial_details()
    details["bankAccounts"][1]["accountNumber"] = details["bankAccounts"][0]["accountNumber"]
    row = new_contact(client, superuser_headers, financialData=details)
    for sort in ["gstNumber", "bankAccounts", "upi"]:
        result = client.get(ROOT, headers=superuser_headers, params={"sort":sort})
        assert result.status_code == 200, result.text
        assert row["id"] in [x["id"] for x in result.json()["items"]]
    export = client.get(ROOT + "/export", headers=superuser_headers)
    assert export.status_code == 200 and "Company GST number" in export.text and details["gstNumber"] in export.text


def test_crm_new_menu_customer_and_reminder_contracts(client, superuser_headers):
    created = client.post("/api/v1/master-data/companies", headers=superuser_headers, json={"name":"Quick customer", "roles":["Customer"], "entityKind":"Individual", "status":"Active"})
    assert created.status_code == 201 and "Customer" in created.json()["roles"], created.text
    due = "2026-12-01T04:30:00Z"
    reminder = client.post("/api/v1/crm/tasks", headers=superuser_headers, json={"title":"Call customer", "due_date":due, "reminder_at":due, "status":"To Do"})
    assert reminder.status_code == 201, reminder.text
    ident = reminder.json()["id"]
    saved = client.get(f"/api/v1/crm/tasks/{ident}", headers=superuser_headers)
    assert saved.status_code == 200 and saved.json()["reminder_at"] is not None


def test_shared_customer_vendor_financial_identity_and_columns(client, superuser_headers):
    company = client.post("/api/v1/master-data/companies", headers=superuser_headers, json={"name":"Financial shared customer", "roles":["Customer","Vendor"], "entityKind":"Individual"})
    assert company.status_code == 201, company.text
    ident = company.json()["id"]
    detail = client.get(f"/api/v1/master-data/companies/{ident}", headers=superuser_headers)
    assert detail.status_code == 200, detail.text
    contact = detail.json()["financialContactId"]
    assert client.put(f"{ROOT}/{contact}/financial-data", headers=superuser_headers, json=financial_details()).status_code == 200
    for role in ["Customer","Vendor"]:
        grid = client.get("/api/v1/master-data/company-directory/query", headers=superuser_headers, params={"source":"crm","role":role})
        assert grid.status_code == 200, grid.text
        saved = next(x for x in grid.json()["rows"] if x["id"] == ident)
        assert saved["financialContactId"] == contact and saved["bankAccountCount"] == 2 and saved["upiCount"] == 2
        assert saved["gstNumber"] == "27ABCDE1234F1Z5"

    exported = client.post("/api/v1/master-data/company-directory/export", headers=superuser_headers, params={"source":"crm","role":"Customer"}, json={"columns":["name","gstNumber","bankAccountCount","upiCount"]})
    assert exported.status_code == 200 and "27ABCDE1234F1Z5" in exported.text, exported.text
