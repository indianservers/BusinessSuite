from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import account, middleware_database, BASE
from tests.fam_test_utils import fam_admin_headers, party_payload


def test_linked_note_save_keeps_branch_checks_and_optimistic_version(client, db):
    _, headers = account(db, "crud-note-owner@example.test", True)
    wid = client.post(BASE + "/workspaces", headers=headers, json={"name": "Notes regression"}).json()["id"]
    project = client.post(BASE + "/projects", headers=headers, json={"name":"Linked notes", "project_key":"NREG", "workspace_id":wid}).json()
    created = client.post(BASE + "/notes", headers=headers, json={"title":"Before", "content":"Private", "project_id":project["id"]})
    assert created.status_code == 201, created.text
    note = created.json()
    payload = {"title":"After", "content":"Saved content", "project_id":project["id"], "version":note["version"]}
    saved = client.put(BASE + f"/notes/{note['id']}", headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["project_id"] == project["id"]
    assert saved.json()["title"] == "After"
    assert client.put(BASE + f"/notes/{note['id']}", headers=headers, json=payload).status_code == 409
    _, outsider = account(db, "crud-note-outsider@example.test", True)
    assert client.get(BASE + f"/notes/{note['id']}", headers=outsider).status_code == 404
    assert client.put(BASE + f"/notes/{note['id']}", headers=outsider, json=payload).status_code == 404


def test_finance_party_contact_replacement_uses_authorized_record_writes(client, db):
    headers = fam_admin_headers(client, db)
    original = party_payload("customer", "CR-REG", "Before")
    created = client.post("/api/v1/fam/parties", headers=headers, json=original)
    assert created.status_code == 201, created.text
    ident = created.json()["id"]
    updated = {**original, "legal_name":"After", "contacts":[{"name":"New accounts contact", "email":"new@example.com"}]}
    response = client.put(f"/api/v1/fam/parties/{ident}", headers=headers, json=updated)
    assert response.status_code == 200, response.text
    data = client.get(f"/api/v1/fam/parties/{ident}", headers=headers).json()
    assert data["legal_name"] == "After"
    assert len(data["contacts"]) == 1
    assert data["contacts"][0]["email"] == "new@example.com"


def test_company_reference_paths_accept_both_slash_forms(client, db, superuser_headers):
    headers = superuser_headers
    for name in ["branches", "departments", "designations"]:
        canonical = client.get("/api/v1/company/"+name+"/", headers=headers)
        alias = client.get("/api/v1/company/"+name, headers=headers)
        assert canonical.status_code == 200, canonical.text
        assert alias.status_code == 200, alias.text
        assert alias.json() == canonical.json()
        assert client.get("/api/v1/company/"+name).status_code in [401,403]
