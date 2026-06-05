from datetime import date, datetime, timezone

from app.apps.project_management.models import PMSProject, PMSTimeLog
from app.apps.srm.models import SRMEngagement, SRMInvoiceLine
from app.models.user import User
from tests.srm_test_utils import create_engagement_via_confirm


def test_srm_approved_timesheets_create_invoice_and_prevent_rebilling(client, db, superuser_headers):
    engagement, _order = create_engagement_via_confirm(client, superuser_headers)
    user = db.query(User).first()
    project = PMSProject(organization_id=1, project_key="TS-INV", name="Timesheet billing", status="Active")
    db.add(project)
    db.flush()
    db.query(SRMEngagement).filter(SRMEngagement.id == engagement["id"]).update({"pms_project_id": project.id})
    log = PMSTimeLog(
        user_id=user.id,
        project_id=project.id,
        log_date=date.today(),
        duration_minutes=180,
        description="Approved billable work",
        is_billable=True,
        approval_status="Approved",
        approved_by_user_id=user.id,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()

    invoice = client.post("/api/v1/srm/invoices/draft-from-timesheets", headers=superuser_headers, json={
        "engagement_id": engagement["id"],
        "time_log_ids": [log.id],
        "hourly_rate": 2000,
    })
    assert invoice.status_code == 201, invoice.text
    assert invoice.json()["total_amount"] == 6000.0
    assert db.query(SRMInvoiceLine).filter(SRMInvoiceLine.source_type == "pms_time_log", SRMInvoiceLine.source_id == log.id).count() == 1

    duplicate = client.post("/api/v1/srm/invoices/draft-from-timesheets", headers=superuser_headers, json={
        "engagement_id": engagement["id"],
        "time_log_ids": [log.id],
        "hourly_rate": 2000,
    })
    assert duplicate.status_code == 409


def test_srm_unapproved_timesheet_is_rejected(client, db, superuser_headers):
    engagement, _order = create_engagement_via_confirm(client, superuser_headers)
    user = db.query(User).first()
    project = PMSProject(organization_id=1, project_key="TS-PEND", name="Pending timesheet", status="Active")
    db.add(project)
    db.flush()
    log = PMSTimeLog(user_id=user.id, project_id=project.id, log_date=date.today(), duration_minutes=60, is_billable=True, approval_status="Pending")
    db.add(log)
    db.commit()

    response = client.post("/api/v1/srm/invoices/draft-from-timesheets", headers=superuser_headers, json={
        "engagement_id": engagement["id"],
        "time_log_ids": [log.id],
    })
    assert response.status_code == 400
