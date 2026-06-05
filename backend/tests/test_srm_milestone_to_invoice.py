from datetime import datetime, timezone

from app.apps.project_management.models import PMSMilestone, PMSProject
from app.apps.srm.models import SRMBillingMilestone, SRMEngagement
from tests.srm_test_utils import create_engagement_via_confirm


def test_srm_billing_milestone_creates_invoice_once(client, db, superuser_headers):
    engagement, _order = create_engagement_via_confirm(client, superuser_headers)
    milestone = db.query(SRMBillingMilestone).first()
    milestone.status = "approved"
    db.commit()

    response = client.post(f"/api/v1/srm/invoices/draft-from-billing-milestone/{milestone.id}", headers=superuser_headers)
    assert response.status_code == 201, response.text
    assert response.json()["engagement_id"] == engagement["id"]
    db.refresh(milestone)
    assert milestone.invoice_draft_id is not None

    duplicate = client.post(f"/api/v1/srm/invoices/draft-from-billing-milestone/{milestone.id}", headers=superuser_headers)
    assert duplicate.status_code == 409


def test_srm_client_approved_pms_milestone_creates_invoice(client, db, superuser_headers):
    engagement, _order = create_engagement_via_confirm(client, superuser_headers)
    project = PMSProject(organization_id=1, project_key="MS-INV", name="Milestone billing", status="Active")
    db.add(project)
    db.flush()
    db.query(SRMEngagement).filter(SRMEngagement.id == engagement["id"]).update({"pms_project_id": project.id})
    milestone = PMSMilestone(
        project_id=project.id,
        name="Client accepted milestone",
        status="Done",
        client_approval_status="Approved",
        client_approved_at=datetime.now(timezone.utc),
    )
    db.add(milestone)
    db.commit()

    response = client.post(f"/api/v1/srm/invoices/draft-from-pms-milestone/{milestone.id}", headers=superuser_headers)
    assert response.status_code == 201, response.text
    assert response.json()["source_type"] == "pms_milestone"

    duplicate = client.post(f"/api/v1/srm/invoices/draft-from-pms-milestone/{milestone.id}", headers=superuser_headers)
    assert duplicate.status_code == 409
