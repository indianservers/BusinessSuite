from app.apps.crm.models import CRMLead
from admin_security_test_utils import auth_headers


def test_duplicate_rule_scan_candidate_and_merge_log(client, db):
    headers = auth_headers(client, db)
    db.add_all([
        CRMLead(first_name="Asha", full_name="Asha Rao", email="dupe@example.com", company_name="Acme"),
        CRMLead(first_name="Asha", full_name="Asha Rao", email="dupe@example.com", company_name="Acme"),
    ])
    db.commit()
    rule = client.post("/api/v1/admin/duplicate-rules", headers=headers, json={"module_name": "leads", "name": "Lead email", "match_fields_json": ["email"], "match_logic": "any"})
    assert rule.status_code == 201
    scan = client.post("/api/v1/admin/duplicates/scan", headers=headers, json={"module_name": "leads"})
    assert scan.status_code == 201
    assert scan.json()["total"] >= 1
    candidate = scan.json()["items"][0]
    merge = client.post("/api/v1/admin/duplicates/merge", headers=headers, json={"module_name": "leads", "winner_record_id": candidate["record_id"], "loser_record_ids": [candidate["duplicate_record_id"]]})
    assert merge.status_code == 200
    assert merge.json()["detail_json"]["timeline_preserved"] is True
