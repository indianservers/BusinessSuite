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

