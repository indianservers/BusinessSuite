from ai_test_utils import auth_headers
from app.apps.ai_copilot.models import AIAgentAction


def test_ai_agent_action_preview_and_confirm_recheck_permissions(client, db):
    headers, _ = auth_headers(client, db)
    preview = client.post("/api/v1/ai/agent-action/preview", headers=headers, json={"action_type": "draft_email", "module_name": "crm", "record_type": "lead", "input_json": {"subject": "Follow up"}})
    assert preview.status_code == 200, preview.text
    action_id = preview.json()["action"]["id"]
    confirm = client.post("/api/v1/ai/agent-action/confirm", headers=headers, json={"action_id": action_id, "confirmation_note": "Reviewed"})
    assert confirm.status_code == 200, confirm.text
    assert db.query(AIAgentAction).filter(AIAgentAction.id == action_id).first().status == "confirmed"



def test_action_drafts_and_feedback_are_company_owned(client, db):
    from app.apps.ai_copilot.models import AIUserFeedback
    first, _ = auth_headers(client, db, email="first-company@example.com")
    second, _ = auth_headers(client, db, email="second-company@example.com", company_id=2)
    preview = client.post("/api/v1/ai/agent-action/preview", headers=first, json={"action_type":"draft_email","module_name":"crm","record_type":"lead","input_json":{"subject":"Follow up"}})
    assert preview.status_code == 200, preview.text
    action_id = preview.json()["action"]["id"]
    assert db.get(AIAgentAction, action_id).organization_id == 1
    denied = client.post("/api/v1/ai/agent-action/confirm", headers=second, json={"action_id":action_id})
    assert denied.status_code == 404, denied.text
    feedback = client.post("/api/v1/ai/feedback", headers=first, json={"rating":"helpful"})
    assert feedback.status_code == 201, feedback.text
    assert db.get(AIUserFeedback, feedback.json()["id"]).organization_id == 1


def test_unattributed_historical_action_is_not_assigned_to_company_one(client, db):
    headers, user = auth_headers(client, db)
    orphan = AIAgentAction(action_type="draft_email", module_name="crm", record_type="lead", preview_json={}, created_by=user.id)
    db.add(orphan)
    db.commit()
    response = client.post("/api/v1/ai/agent-action/confirm", headers=headers, json={"action_id":orphan.id})
    assert response.status_code == 404, response.text
