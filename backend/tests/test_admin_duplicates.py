from app.apps.crm.models import CRMLead
from admin_security_test_utils import auth_headers
from test_identity_utils import own_workflow_records
from app.models.company import Branch, Company


def test_duplicate_rule_scan_candidate_and_merge_log(client, db):
    headers = auth_headers(client, db)
    branch_id = int(headers["X-Suite-Branch"])
    leads = [CRMLead(organization_id=1, branch_id=branch_id, first_name="Asha", full_name="Asha Rao", email="dupe@example.com", company_name="Acme") for _ in range(2)]
    db.add_all(leads)
    own_workflow_records(db, *leads)
    db.commit()
    rule = client.post("/api/v1/admin/duplicate-rules", headers=headers, json={"module_name": "leads", "name": "Lead email", "match_fields_json": ["email"], "match_logic": "any"})
    assert rule.status_code == 201
    scan = client.post("/api/v1/admin/duplicates/scan", headers=headers, json={"module_name": "leads"})
    assert scan.status_code == 201
    assert scan.json()["total"] == 1
    assert {scan.json()["items"][0]["record_id"], scan.json()["items"][0]["duplicate_record_id"]} == {row.id for row in leads}
    candidate = scan.json()["items"][0]
    merge = client.post("/api/v1/admin/duplicates/merge", headers=headers, json={"module_name": "leads", "winner_record_id": candidate["record_id"], "loser_record_ids": [candidate["duplicate_record_id"]]})
    assert merge.status_code == 200
    assert merge.json()["detail_json"]["timeline_preserved"] is True


def test_duplicate_scan_excludes_other_branches_and_companies(client, db):
    headers = auth_headers(client, db)
    current = int(headers["X-Suite-Branch"])
    db.add(Company(id=2, name="Other duplicate tenant", is_active=True))
    db.flush()
    other_branch = Branch(company_id=1, name="Other branch", code="DUP-OTHER")
    foreign_branch = Branch(company_id=2, name="Foreign branch", code="DUP-FOREIGN")
    db.add_all([other_branch, foreign_branch]); db.flush()
    leads = []
    for company, branch in [(1, current), (1, other_branch.id), (2, foreign_branch.id)]:
        pair = [CRMLead(organization_id=company, branch_id=branch, first_name="Asha", full_name="Asha Rao", email="dupe@example.com") for _ in range(2)]
        db.add_all(pair)
        own_workflow_records(db, *pair, company_id=company)
        leads.extend(pair)
    db.commit()
    response = client.post("/api/v1/admin/duplicate-rules", headers=headers, json={"module_name": "leads", "name": "Scoped email duplicates", "match_fields_json": ["email"], "match_logic": "any"})
    assert response.status_code == 201, response.text
    response = client.post("/api/v1/admin/duplicates/scan", headers=headers, json={"module_name": "leads"})
    assert response.status_code == 201, response.text
    assert response.json()["total"] == 1
    candidate = response.json()["items"][0]
    assert {candidate["record_id"], candidate["duplicate_record_id"]} == {row.id for row in leads[:2]}
