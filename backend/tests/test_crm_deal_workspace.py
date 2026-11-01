from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import csv
import io
import pytest
from app.apps.crm.models import CRMDeal, CRMPipelineStage, CRMTask
from tests.test_crm_deal_catalog import seed

BASE = "/api/v1/crm/deal-workspace"


def create(client, db, headers, **extra):
    payload, _, _ = seed(client, db, headers)
    payload.update(extra)
    result = client.post("/api/v1/crm/deals", headers=headers, json=payload)
    assert result.status_code == 201, result.text
    return result.json()


def test_paginated_scoped_query_and_currency_separated_database_totals(client, db, superuser_headers):
    first = create(client, db, superuser_headers, amount=100, probability=50, currency="INR")
    stage = db.get(CRMPipelineStage, first["stage_id"])
    for i in range(104):
        db.add(CRMDeal(name=f"Revenue {i}", organization_id=1, pipeline_id=stage.pipeline_id, stage_id=stage.id, amount=10, probability=50, currency="USD", status="Open"))
    db.add(CRMDeal(name="Foreign secret", organization_id=999, pipeline_id=stage.pipeline_id, stage_id=stage.id, amount=999999, probability=100, currency="INR", status="Open"))
    db.commit()
    response = client.get(BASE + "/query", headers=superuser_headers, params={"page": 2, "per_page": 100})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 105
    assert len(response.json()["items"]) == 5
    assert all(item["organization_id"] == 1 for item in response.json()["items"])
    assert client.get(BASE + "/query", headers=superuser_headers, params={"per_page": 101}).status_code == 422
    totals = client.get(BASE + "/summary", headers=superuser_headers)
    assert totals.status_code == 200, totals.text
    assert totals.json()["counts"]["open"] == 105
    money = {item["currency"]: item for item in totals.json()["currencies"]}
    assert money["INR"]["pipeline"] == 100
    assert money["USD"]["pipeline"] == 1040
    assert money["USD"]["weighted"] == 520
    filtered = client.get(BASE + "/summary", headers=superuser_headers, params={"currency": "USD"})
    assert len(filtered.json()["currencies"]) == 1


def test_optimistic_version_duplicate_and_planning_roundtrip(client, db, superuser_headers):
    record = create(client, db, superuser_headers, priority="Critical", deal_type="Renewal", planning={"qualification": {"business_need": "Replace legacy platform", "budget_confirmed": True}, "financial": {"estimated_cost": "20"}, "dates": {"proposal_submission_date": "2026-11-02"}})
    assert record["version"] == 1
    update = client.patch(f"/api/v1/crm/deals/{record['id']}", headers=superuser_headers, json={"name": "Updated enterprise deal", "expected_version": 1})
    assert update.status_code == 200, update.text
    assert update.json()["version"] == 2
    stale = client.patch(f"/api/v1/crm/deals/{record['id']}", headers=superuser_headers, json={"amount": 999, "expected_version": 1})
    assert stale.status_code == 409, stale.text
    db.refresh(db.get(CRMDeal, record["id"]))
    assert db.get(CRMDeal, record["id"]).amount != Decimal("999")
    duplicate = client.get(BASE + "/duplicates", headers=superuser_headers, params={"name": "updated enterprise deal"})
    assert [item["id"] for item in duplicate.json()["items"]] == [record["id"]]
    detail = client.get(f"/api/v1/crm/deals/{record['id']}", headers=superuser_headers)
    assert detail.json()["planning"]["qualification"]["business_need"] == "Replace legacy platform"


@pytest.mark.parametrize("payload", [{"amount": -1}, {"probability": 101}, {"priority": "Urgent"}, {"currency": "INVALID"}, {"planning": {"financial": {"estimated_cost": -1}}}, {"planning": {"dates": {"proposal_submission_date": "tomorrow"}}}])
def test_deal_field_validation(client, db, superuser_headers, payload):
    base, _, _ = seed(client, db, superuser_headers)
    response = client.post("/api/v1/crm/deals", headers=superuser_headers, json={**base, **payload})
    assert response.status_code == 422, response.text


def test_stage_requirements_terminal_closure_and_onboarding_are_real(client, db, superuser_headers):
    record = create(client, db, superuser_headers, amount=250)
    won = CRMPipelineStage(name="Closed Won", organization_id=1, pipeline_id=record["pipeline_id"], stage_type="won", is_won=True, probability=100, active=True)
    db.add(won); db.commit()
    policy = client.put(BASE + f"/stage-policy/{won.id}", headers=superuser_headers, json={"required": ["expected_close_date"], "allowed_next_ids": [], "stagnation_days": 7, "approval_required": False})
    assert policy.status_code == 200, policy.text
    denied = client.patch(f"/api/v1/crm/deals/{record['id']}", headers=superuser_headers, json={"stage_id": won.id})
    assert denied.status_code == 422, denied.text
    patched = client.patch(f"/api/v1/crm/deals/{record['id']}", headers=superuser_headers, json={"expected_close_date": date.today().isoformat(), "expected_version": 1})
    assert patched.status_code == 200, patched.text
    response = client.post(BASE + f"/{record['id']}/close", headers=superuser_headers, json={"outcome": "Won", "expected_version": 2, "reason": "Customer signed the contract", "actual_close_date": date.today().isoformat(), "actual_value": 250, "currency": "INR", "onboarding": True})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Won"
    assert response.json()["stage_id"] == won.id
    assert db.query(CRMTask).filter_by(deal_id=record["id"], title="Customer onboarding").count() == 1
    repeated = client.post(BASE + f"/{record['id']}/close", headers=superuser_headers, json={"outcome": "Won", "expected_version": 2, "reason": "Customer signed again", "actual_close_date": date.today().isoformat(), "actual_value": 250, "currency": "INR", "onboarding": True})
    assert repeated.status_code == 409
    assert db.query(CRMTask).filter_by(deal_id=record["id"], title="Customer onboarding").count() == 1


def test_insights_and_exports_have_real_records_and_safe_currency(client, db, superuser_headers):
    record = create(client, db, superuser_headers, name="=HYPERLINK(unsafe)", amount=123.45)
    item = db.get(CRMDeal, record["id"])
    item.next_follow_up_at = datetime.now(timezone.utc) - timedelta(days=2)
    db.commit()
    response = client.get(BASE + f"/{item.id}/insights", headers=superuser_headers)
    assert response.status_code == 200, response.text
    assert "Follow-up overdue" in response.json()["reasons"]
    assert response.json()["score"] < 100
    csv_response = client.get(BASE + "/export", headers=superuser_headers, params={"format": "csv", "currency": "INR"})
    assert csv_response.status_code == 200, csv_response.text
    exported = list(csv.reader(io.StringIO(csv_response.content.decode("utf-8-sig"))))
    assert exported[1][1].startswith("'=HYPERLINK")
    assert exported[1][2] == "INR"
    excel = client.get(BASE + "/export", headers=superuser_headers, params={"format": "xlsx"})
    assert excel.status_code == 200, excel.text
    assert excel.content[:2] == b"PK"


def test_bulk_reports_partial_failure_and_keeps_stage_rules(client, db, superuser_headers):
    record = create(client, db, superuser_headers)
    stage = CRMPipelineStage(name="Requires company", organization_id=1, pipeline_id=record["pipeline_id"], policy_json={"required": ["company_id"]})
    db.add(stage); db.commit()
    result = client.post(BASE + "/bulk", headers=superuser_headers, json={"records": [{"id": record["id"], "version": 1}], "stage_id": stage.id})
    assert result.status_code == 200, result.text
    assert not result.json()["items"][0]["saved"]
    assert "company" in result.json()["items"][0]["message"]
    db.refresh(db.get(CRMDeal, record["id"]))
    assert db.get(CRMDeal, record["id"]).stage_id == record["stage_id"]


def test_collaborators_retain_access_checks_and_internal_notifications(client, db, superuser_headers):
    from app.models.user import User
    from app.models.notification import Notification
    from tests.tenant_test_utils import assign_company
    record = create(client, db, superuser_headers)
    colleague = User(email="dealwatcher@example.com", hashed_password="unused", is_active=True, is_superuser=True)
    db.add(colleague); db.flush(); assign_company(db, colleague, 1); db.commit()
    added = client.put(BASE + f"/{record['id']}/collaborators/{colleague.id}", headers=superuser_headers, json={"role": "Secondary Owner", "watching": True})
    assert added.status_code == 200, added.text
    people = client.get(BASE + f"/{record['id']}/collaborators", headers=superuser_headers)
    assert people.json()["items"][0]["role"] == "Secondary Owner"
    response = client.patch(f"/api/v1/crm/deals/{record['id']}", headers=superuser_headers, json={"name": "Watched update", "expected_version": 1})
    assert response.status_code == 200, response.text
    notification = db.query(Notification).filter_by(user_id=colleague.id, event_type="deal.updated").one()
    assert notification.channels == ["in_app"]
    assert notification.company_id == 1
    assert notification.related_entity_id == record["id"]
    client.patch(f"/api/v1/crm/deals/{record['id']}", headers=superuser_headers, json={"name": "Duplicated retry", "expected_version": 1})
    assert db.query(Notification).filter_by(user_id=colleague.id, event_type="deal.updated").count() == 1


def test_task_activity_updates_insights_and_event_pagination(client, db, superuser_headers):
    record = create(client, db, superuser_headers)
    for index in range(3):
        result = client.post("/api/v1/crm/tasks", headers=superuser_headers, json={"title": f"Follow up {index}", "deal_id": record["id"], "status": "To Do"})
        assert result.status_code == 201, result.text
    detail = client.get(f"/api/v1/crm/deals/{record['id']}", headers=superuser_headers)
    assert detail.json()["last_activity_at"]
    assert detail.json()["version"] == 4
    events = client.get(BASE + f"/{record['id']}/events", headers=superuser_headers, params={"per_page": 2})
    assert events.status_code == 200, events.text
    assert events.json()["total"] >= 3
    assert len(events.json()["items"]) == 2
    assert events.json()["pages"] >= 2
    assert client.get(BASE + f"/{record['id']}/events", headers=superuser_headers, params={"per_page": 101}).status_code == 422


def test_secure_upload_links_to_visible_deal_and_rejects_foreign_parent(client, db, superuser_headers, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.apps.crm.models import CRMFileAsset
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    record = create(client, db, superuser_headers)
    response = client.post("/api/v1/crm/file-workspace/upload", headers=superuser_headers, data={"deal_id": str(record["id"])}, files={"file": ("proposal.txt", b"Customer proposal details", "text/plain")})
    assert response.status_code == 201, response.text
    uploaded = db.get(CRMFileAsset, response.json()["id"])
    assert uploaded.deal_id == record["id"]
    bad = client.post("/api/v1/crm/file-workspace/upload", headers=superuser_headers, data={"deal_id": "999999"}, files={"file": ("secret.txt", b"Do not write this", "text/plain")})
    assert bad.status_code in {403, 404}, bad.text
    assert db.query(CRMFileAsset).count() == 1


def test_readonly_deal_access_does_not_expose_restricted_notes_or_allow_mutation(client, db, superuser_headers):
    from app.models.user import User
    from tests.test_crm_phase_1_core_foundation import _headers_for_permissions
    record = create(client, db, superuser_headers)
    note = client.post("/api/v1/crm/notes", headers=superuser_headers, json={"deal_id": record["id"], "body": "Restricted activity note"})
    assert note.status_code == 201, note.text
    headers = _headers_for_permissions(client, db, "dealreader@example.com", ["crm_deals_view"])
    reader = db.query(User).filter_by(email="dealreader@example.com").one()
    row = db.get(CRMDeal, record["id"]); row.owner_user_id = reader.id; db.commit()
    result = client.get(BASE + f"/{row.id}/record", headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["related"]["notes"] == []
    choices = client.get(BASE + "/pipelines", headers=headers)
    assert choices.status_code == 200, choices.text
    assert record["pipeline_id"] in [item["id"] for item in choices.json()["items"]]
    stages = client.get(BASE + "/pipeline-stages", headers=headers, params={"pipeline_id":record["pipeline_id"]})
    assert stages.status_code == 200, stages.text
    assert record["stage_id"] in [item["id"] for item in stages.json()["items"]]
    policy = client.put(BASE + f"/stage-policy/{record['stage_id']}", headers=headers, json={})
    assert policy.status_code == 403, policy.text
    forbidden = client.patch(f"/api/v1/crm/deals/{row.id}", headers=headers, json={"amount": 999})
    assert forbidden.status_code == 403, forbidden.text
    feed = client.get(BASE + f"/{row.id}/events", headers=headers)
    assert feed.status_code == 200, feed.text
    assert all(event["type"] != "notes" for event in feed.json()["items"])


def test_whatsapp_recording_is_internal_and_visible_in_unified_events(client, db, superuser_headers):
    record = create(client, db, superuser_headers)
    response = client.post("/api/v1/crm/productivity/interaction", headers=superuser_headers, json={"entity": "deals", "record_id": record["id"], "channel": "whatsapp", "outcome": "Connected", "notes": "Customer acknowledged the proposal", "no_next_reason": "Customer will return next quarter", "timezone": "Asia/Kolkata"})
    assert response.status_code == 200, response.text
    db.refresh(db.get(CRMDeal, record["id"]))
    assert db.get(CRMDeal, record["id"]).version == 2
    feed = client.get(BASE + f"/{record['id']}/events", headers=superuser_headers)
    assert feed.status_code == 200, feed.text
    assert any(event["type"] == "whatsapp" and "acknowledged" in event["record"]["description"] for event in feed.json()["items"])


def test_recorded_conversion_loss_analysis_and_drill_filters(client, db, superuser_headers):
    record = create(client, db, superuser_headers, amount=125)
    initial = db.get(CRMPipelineStage, record["stage_id"])
    next_stage = CRMPipelineStage(name="Proposal", organization_id=1, pipeline_id=record["pipeline_id"], position=(initial.position or 0)+1, probability=60, active=True)
    lost = CRMPipelineStage(name="Lost", organization_id=1, pipeline_id=record["pipeline_id"], position=10, stage_type="lost", is_lost=True, probability=0, active=True)
    db.add_all([next_stage, lost]); db.commit()
    moved = client.patch(f"/api/v1/crm/deals/{record['id']}", headers=superuser_headers, json={"stage_id":next_stage.id, "expected_version":1})
    assert moved.status_code == 200, moved.text
    report = client.get(BASE + "/conversion", headers=superuser_headers)
    assert report.status_code == 200, report.text
    discovery = next(row for row in report.json()["items"] if row["stage_id"] == initial.id)
    assert discovery["entries"] == discovery["progressed"] == 1
    assert discovery["conversion_rate"] == 100
    drill = client.get(BASE + "/query", headers=superuser_headers, params={"entered_stage_id":initial.id})
    assert [row["id"] for row in drill.json()["items"]] == [record["id"]]
    closed = client.post(BASE + f"/{record['id']}/close", headers=superuser_headers, json={"outcome":"Lost", "expected_version":2, "reason":"Price too high", "actual_close_date":date.today().isoformat(), "actual_value":125, "currency":"INR", "competitor":"Alternative supplier"})
    assert closed.status_code == 200, closed.text
    losses = client.get(BASE + "/loss-analysis", headers=superuser_headers)
    assert losses.status_code == 200, losses.text
    assert losses.json()["items"] == [{"name":"Price too high", "currency":"INR", "count":1, "amount":125}]
    assert losses.json()["competitors"][0]["name"] == "Alternative supplier"
    drill = client.get(BASE + "/query", headers=superuser_headers, params={"lost_reason":"Price too high"})
    assert drill.json()["total"] == 1
    totals = client.get(BASE + "/summary", headers=superuser_headers).json()
    assert totals["counts"]["lost_month"] == 1
    assert totals["analytics"][0]["lost_value"] == 125


def test_service_currency_is_persisted_and_deal_mismatch_rejected(client, db, superuser_headers):
    payload, _, service_id = seed(client, db, superuser_headers)
    updated = client.patch(f"/api/v1/crm/services/{service_id}", headers=superuser_headers, json={"currency":"USD"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["currency"] == "USD"
    payload.update(currency="INR", catalog_items=[{"kind":"service", "item_id":service_id, "quantity":1, "unit_price":50, "discount":0}])
    rejected = client.post("/api/v1/crm/deals", headers=superuser_headers, json=payload)
    assert rejected.status_code == 422, rejected.text
    payload["currency"] = "USD"
    saved = client.post("/api/v1/crm/deals", headers=superuser_headers, json=payload)
    assert saved.status_code == 201, saved.text
    assert saved.json()["amount"] == 50
