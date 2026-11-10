from datetime import datetime, timezone
from tests.test_communication_engagement import customer_thread
from app.models.company import Branch
from app.branches.models import BranchOwnership
from app.apps.communication.customer_models import CustomerDelivery


def test_delivery_issue_summary_does_not_count_other_branches_or_duplicate_whatsapp(client, db, customer_thread):
    headers, actor, branch, record, contact, messages, recipient, reply = customer_thread
    other = Branch(company_id=1, name="Other summary branch", is_active=True)
    db.add(other)
    db.flush()
    for key, branch_id, channel in [("visible-failure", branch.id, "email"), ("hidden-failure", other.id, "email"), ("whatsapp-not-email", branch.id, "whatsapp")]:
        db.add(CustomerDelivery(organization_id=1, branch_id=branch_id, recipient_id=recipient.id, event_key=key, source_type="contact", source_id=record.id, channel=channel, purpose="transactional", subject="Isolated test", body="No transport", status="failed", due_at=datetime.now(timezone.utc), created_by=actor.id))
    db.flush()
    for delivery in db.query(CustomerDelivery).filter(CustomerDelivery.event_key.in_(["visible-failure","hidden-failure","whatsapp-not-email"])):
        db.add(BranchOwnership(resource_table=delivery.__tablename__,resource_key=str(delivery.id),company_id=1,branch_id=delivery.branch_id,source="test"))
    db.commit()
    response = client.get("/api/v1/communication/engagement/health-summary", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["deliveryIssues"] == 1, response.json()
