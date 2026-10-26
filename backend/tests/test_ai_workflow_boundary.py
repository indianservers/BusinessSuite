"""AI-origin events cannot borrow a workflow service account or fan out writes."""

import pytest
from tests.test_shared_services import shared_setup, create_workflow, graph
from tests.test_suite_access import access_account
from app.shared.gateway import ModuleServices
from app.shared import runtime
from app.ai_agents.security import seal
from app.models.user import User
from app.models.notification import Notification
from app.apps.automation.models import AutomationScheduledJob
from app.apps.crm.models import CRMTask


def test_ai_event_cannot_borrow_workflow_identity(client, db, shared_setup):
    headers, user, lead = shared_setup
    create_workflow(
        client,
        headers,
        user,
        graph(
            {
                "id": "notice",
                "type": "notification",
                "config": {
                    "recipientId": user.id,
                    "title": "Forbidden deputy",
                    "message": "blocked",
                },
            }
        ),
    )
    origin = db.query(User).filter_by(is_superuser=True).first()
    event = ModuleServices(db, origin, 1, "crm").emit(
        "test.event", "lead", lead.id, "ai-deputy-event-001"
    )
    event.payload_json = {**event.payload_json, "ai_origin": seal(db, origin)}
    db.commit()
    runtime.process_batch(db, 10)
    assert db.query(Notification).filter_by(title="Forbidden deputy").count() == 0
    job = db.query(AutomationScheduledJob).filter_by(job_type="shared_workflow").one()
    assert job.status != "completed"
    assert "identity" in (job.last_error or "").lower()


@pytest.mark.parametrize("kind", ["create_record", "update_record", "assignment"])
def test_ai_event_cannot_fan_out_unconfirmed_mutations(client, db, shared_setup, kind):
    headers, user, lead = shared_setup
    create_workflow(
        client,
        headers,
        user,
        graph(
            {
                "id": "write",
                "type": kind,
                "config": {
                    "tool": "crm.create_task",
                    "payload": {
                        "title": "Unconfirmed AI workflow side effect",
                        "related_entity_type": "lead",
                        "related_entity_id": lead.id,
                    },
                },
            }
        ),
    )
    event = ModuleServices(db, user, 1, "crm").emit(
        "test.event", "lead", lead.id, "ai-fanout-event-001"
    )
    event.payload_json = {**event.payload_json, "ai_origin": seal(db, user)}
    db.commit()
    runtime.process_batch(db, 10)
    assert (
        db.query(CRMTask).filter_by(title="Unconfirmed AI workflow side effect").count()
        == 0
    )
    job = db.query(AutomationScheduledJob).filter_by(job_type="shared_workflow").one()
    assert job.status != "completed"
    assert "confirmation" in (job.last_error or "").lower()
