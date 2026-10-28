from datetime import date, timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from unittest.mock import Mock

import pytest

from app.core import email
from app.core.config import settings
from app.models.email_outbox import EmailOutbox
from app.models.employee import Employee
from app.models.expense import ExpenseClaim
from app.models.notification import Notification, NotificationDeliveryLog
from app.models.user import User
from app.services.email_dispatch import queue_email, drain_outbox, drain_notifications
from app.services.email_events import EVENTS
from app.services.email_reminders import enqueue_due_reminders


@pytest.fixture
def ses(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "ses")
    monkeypatch.setattr(settings, "SES_FROM", "suite@example.com")
    monkeypatch.setattr(settings, "SES_REGION", "ap-south-1")
    monkeypatch.setattr(settings, "SES_SMTP_SERVER", "")
    monkeypatch.setattr(settings, "INTERN_HUB_SES_SMTP_SERVER", "")
    client = Mock()
    client.send_raw_email.return_value = {"MessageId": "ses-accepted"}
    monkeypatch.setattr("boto3.client", Mock(return_value=client))
    return client


def test_shared_ses_preserves_mime_and_hides_bcc(ses, monkeypatch):
    monkeypatch.setattr(settings, "SES_CONFIGURATION_SET", "suite-events")
    message = EmailMessage()
    message["To"], message["Cc"], message["Bcc"] = "to@example.com", "cc@example.com", "hidden@example.com"
    message["Subject"] = "Invoice"
    message.set_content("Invoice notification")
    message.add_alternative("<p>Invoice notification</p>", subtype="html")
    message.add_attachment(b"test-pdf", maintype="application", subtype="pdf", filename="invoice.pdf")
    assert email.send_message(message) == "ses-accepted"
    payload = ses.send_raw_email.call_args.kwargs
    assert set(payload["Destinations"]) == {"to@example.com", "cc@example.com", "hidden@example.com"}
    assert payload["ConfigurationSetName"] == "suite-events"
    parsed = BytesParser(policy=policy.default).parsebytes(payload["RawMessage"]["Data"])
    assert parsed["Bcc"] is None
    assert list(parsed.iter_attachments())[0].get_payload(decode=True) == b"test-pdf"


@pytest.mark.parametrize("fails", [False, True])
def test_outbox_claims_before_send_and_never_blindly_retries(db, monkeypatch, fails):
    monkeypatch.setattr(email, "email_configured", lambda: True)
    row = queue_email(db, recipient="recipient@example.com", subject="Test", body="Body", module="hrms", event_key="once")
    assert queue_email(db, recipient="recipient@example.com", subject="Test", body="Body", module="hrms", event_key="once") is None
    db.commit()

    def deliver(*args):
        assert db.get(EmailOutbox, row.id).status == "reconciliation_required"
        assert drain_outbox(db)["processed"] == 0
        if fails:
            raise TimeoutError("unknown provider outcome")
        return "accepted-id"

    sender = Mock(side_effect=deliver)
    monkeypatch.setattr(email, "send_email", sender)
    assert drain_outbox(db)["processed"] == 1
    assert drain_outbox(db)["processed"] == 0
    sender.assert_called_once()
    assert row.status == ("reconciliation_required" if fails else "accepted")


def test_unconfigured_provider_keeps_outbox_queued(db, monkeypatch):
    monkeypatch.setattr(email, "email_configured", lambda: False)
    row = queue_email(db, recipient="recipient@example.com", subject="Test", body="Body", module="crm")
    db.commit()
    assert drain_outbox(db)["status"] == "unconfigured"
    assert row.status == "queued"


def test_expense_events_follow_commit_rollback_and_real_status_changes(db, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", True)
    employee = Employee(employee_id="EMAIL-EMP", first_name="Test", last_name="Employee", personal_email="employee@example.com", date_of_joining=date.today())
    db.add(employee); db.commit()
    claim = ExpenseClaim(employee_id=employee.id, claim_number="EMAIL-CLAIM", claim_type="Travel", expense_date=date.today(), amount=100, status="submitted")
    point = db.begin_nested()
    db.add(claim); db.flush()
    db.flush()  # Persist the outbox entries staged by after_flush_postexec.
    assert db.query(EmailOutbox).filter_by(module="hrms").count() == 1
    point.rollback()
    assert db.query(EmailOutbox).filter_by(module="hrms").count() == 0
    claim = ExpenseClaim(employee_id=employee.id, claim_number="EMAIL-CLAIM2", claim_type="Travel", expense_date=date.today(), amount=100, status="submitted")
    db.add(claim); db.commit()
    assert db.query(EmailOutbox).count() == 1
    claim.status = "approved"; db.commit()
    assert db.query(EmailOutbox).count() == 2
    claim.status = "approved"; db.commit()
    assert db.query(EmailOutbox).count() == 2
    assert all("100" not in row.body for row in db.query(EmailOutbox))


def test_draft_offer_does_not_send_but_sent_offer_does(db, monkeypatch):
    from app.models.recruitment import Job, Candidate, OfferLetter
    monkeypatch.setattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", True)
    job = Job(title="Test internship"); db.add(job); db.flush()
    candidate = Candidate(job_id=job.id, first_name="Test", last_name="Candidate", email="candidate@example.com")
    db.add(candidate); db.commit()
    initial = db.query(EmailOutbox).count()
    offer = OfferLetter(candidate_id=candidate.id)
    db.add(offer); db.commit()
    assert db.query(EmailOutbox).count() == initial
    offer.status = "Sent"; db.commit()
    assert db.query(EmailOutbox).count() == initial + 1


def test_legacy_notification_queue_is_delivered_once(db, monkeypatch):
    monkeypatch.setattr(email, "email_configured", lambda: True)
    sender = Mock(return_value="ses-id")
    monkeypatch.setattr(email, "send_email", sender)
    user = User(email="notify@example.com", hashed_password="unused", is_active=True)
    db.add(user); db.flush()
    notification = Notification(user_id=user.id, title="Private HR details", message="Confidential", channels=["in_app", "email"], module="hrms")
    db.add(notification); db.flush()
    log = NotificationDeliveryLog(notification_id=notification.id, channel="email", status="queued")
    db.add(log); db.commit()
    assert drain_notifications(db) == 1
    assert drain_notifications(db) == 0
    assert log.status == "accepted"
    assert "Confidential" not in sender.call_args.args[2]


def test_inactive_recipient_is_suppressed(db, monkeypatch):
    monkeypatch.setattr(email, "email_configured", lambda: True)
    sender = Mock(); monkeypatch.setattr(email, "send_email", sender)
    user = User(email="inactive@example.com", hashed_password="unused", is_active=False)
    db.add(user); db.flush()
    row = queue_email(db, recipient=user.email, user_id=user.id, subject="Private", body="Body", module="hrms")
    db.commit(); drain_outbox(db)
    assert row.status == "suppressed"
    sender.assert_not_called()


def test_module_rules_reference_real_schema():
    from app.db.base import Base
    for table, spec in EVENTS.items():
        assert table in Base.metadata.tables, table
        columns = Base.metadata.tables[table].c
        for field in ([spec[2]] if spec[2] else []) + list(spec[3]) + list(spec[4]):
            assert field in columns, (table, field)


def test_due_reminders_are_daily_and_skip_completed_work(db, monkeypatch):
    from app.models.onboarding import EmployeeOnboarding, EmployeeOnboardingTask
    monkeypatch.setattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", True)
    user = User(email="task@example.com", hashed_password="unused", is_active=True)
    employee = Employee(employee_id="REMINDER-EMP", first_name="Test", last_name="Employee", date_of_joining=date.today())
    db.add_all([user, employee]); db.flush()
    onboarding = EmployeeOnboarding(employee_id=employee.id); db.add(onboarding); db.flush()
    task = EmployeeOnboardingTask(employee_onboarding_id=onboarding.id, task_name="Upload documents", assigned_to_user_id=user.id, due_date=date.today(), status="pending")
    db.add(task); db.commit()
    assert enqueue_due_reminders(db, run_date=date.today()) == 1
    assert enqueue_due_reminders(db, run_date=date.today()) == 0
    task.status = "completed"; db.commit()
    assert enqueue_due_reminders(db, run_date=date.today() + timedelta(days=1)) == 0


def test_email_cron_requires_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "CRON_SECRET", "synthetic-cron-secret")
    assert client.get("/api/v1/internal/email-dispatch").status_code == 401


def schedule_owner(db):
    from app.models.company import Company
    from app.common.models import CommonPerson
    company = db.get(Company, 1)
    if not company:
        db.add(Company(id=1, name="Email test company", is_active=True))
    user = User(email="schedule-owner@example.com", hashed_password="unused", is_active=True, is_superuser=True)
    db.add(user); db.flush()
    db.add(CommonPerson(user_id=user.id, organization_id=1, display_name="Email owner"))
    db.commit()
    return user


@pytest.mark.parametrize("optout", [False, True])
def test_scheduled_campaigns_use_outbox_and_recheck_optouts(db, monkeypatch, optout):
    from datetime import datetime, timezone
    from app.apps.communication.models import CommunicationCampaign, CommunicationEmailTemplate, CommunicationOptOut
    from app.apps.crm.models import CRMLead
    from app.models.security_boundary import SecurityResourceOwnership
    from app.services.email_schedules import prepare_scheduled_email
    owner = schedule_owner(db)
    lead = CRMLead(organization_id=1, first_name="Lead", full_name="Lead", email="campaign@example.com")
    template = CommunicationEmailTemplate(organization_id=1, name="Campaign template", subject="Hello", body_text="Welcome", module_name="crm", active=True)
    db.add_all([lead, template]); db.flush()
    campaign = CommunicationCampaign(name="Due campaign", type="email", template_id=template.id, status="scheduled",
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1), segment_json={"source": "lead"}, created_by=owner.id)
    db.add(campaign); db.flush()
    if not db.get(SecurityResourceOwnership, ("communication_campaigns", campaign.id)):
        db.add(SecurityResourceOwnership(resource_table="communication_campaigns", resource_id=campaign.id, company_id=1))
    db.commit()
    assert prepare_scheduled_email(db) == 1
    db.refresh(campaign)
    assert campaign.status == "queued"
    assert prepare_scheduled_email(db) == 0
    if optout:
        db.add(CommunicationOptOut(email=lead.email, channel="email")); db.commit()
    monkeypatch.setattr(email, "email_configured", lambda: True)
    sender = Mock(return_value="campaign-id"); monkeypatch.setattr(email, "send_email", sender)
    drain_outbox(db)
    assert campaign.status == "completed"
    assert campaign.sent_count == (0 if optout else 1)
    assert campaign.blocked_count == (1 if optout else 0)
    assert sender.call_count == (0 if optout else 1)


def test_scheduled_reports_run_in_one_company_and_notify_recipients(db):
    from datetime import datetime, timezone
    from app.apps.analytics.models import AnalyticsReport, AnalyticsScheduledReport, AnalyticsReportRun
    from app.apps.crm.models import CRMLead
    from app.models.company import Company
    from app.models.security_boundary import SecurityResourceOwnership
    from app.services.email_schedules import prepare_scheduled_email
    owner = schedule_owner(db)
    db.add(Company(id=2, name="Other company", is_active=True)); db.flush()
    db.add_all([CRMLead(organization_id=1, first_name="Allowed", full_name="Allowed", email="allowed@example.com"),
                CRMLead(organization_id=2, first_name="Other", full_name="Other", email="other@example.com")])
    report = AnalyticsReport(name="Lead report", module_name="crm_leads", owner_id=owner.id, visibility="private", fields_json=["id", "email"])
    db.add(report); db.flush()
    schedule = AnalyticsScheduledReport(report_id=report.id, name="Daily report", frequency="daily", active=1,
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1), recipients_json=[owner.email], created_by=owner.id)
    db.add(schedule); db.flush()
    for table, identity in (("analytics_reports", report.id), ("analytics_scheduled_reports", schedule.id)):
        if not db.get(SecurityResourceOwnership, (table, identity)):
            db.add(SecurityResourceOwnership(resource_table=table, resource_id=identity, company_id=1))
    db.commit()
    assert prepare_scheduled_email(db) == 1
    run = db.query(AnalyticsReportRun).one()
    assert run.row_count == 1
    assert "other@example.com" not in str(run.result_preview_json)
    assert db.query(EmailOutbox).filter(EmailOutbox.event_key.startswith("report-schedule:")).count() == 1
    assert prepare_scheduled_email(db) == 0


def test_published_announcements_respect_department_and_do_not_repeat(db):
    from app.models.company import Branch, Department
    from app.models.engagement import Announcement
    from app.models.security_boundary import SecurityResourceOwnership
    from app.services.email_schedules import prepare_engagement_email
    owner = schedule_owner(db)
    branch = Branch(company_id=1, name="Email branch"); db.add(branch); db.flush()
    department = Department(branch_id=branch.id, name="Email department"); db.add(department); db.flush()
    db.add_all([
        Employee(employee_id="ANN-IN", first_name="In", last_name="Audience", branch_id=branch.id,
            department_id=department.id, personal_email="audience@example.com", status="Active", date_of_joining=date.today()),
        Employee(employee_id="ANN-OUT", first_name="Outside", last_name="Audience", branch_id=branch.id,
            personal_email="outside@example.com", status="Active", date_of_joining=date.today()),
    ])
    source = Announcement(title="Published notice", body="Private announcement", audience="Department",
        target_department_id=department.id, is_published=True, created_by=owner.id)
    db.add(source); db.flush()
    if not db.get(SecurityResourceOwnership, ("announcements", source.id)):
        db.add(SecurityResourceOwnership(resource_table="announcements", resource_id=source.id, company_id=1))
    db.commit()
    assert prepare_engagement_email(db) == 1
    assert prepare_engagement_email(db) == 0
    messages = db.query(EmailOutbox).filter(EmailOutbox.event_key.startswith("engagement:")).all()
    assert [row.recipient for row in messages] == ["audience@example.com"]
    assert "Private announcement" not in messages[0].body


def test_shared_task_assignments_and_reviews_send_one_decision_email(db):
    from app.apps.project_management.models import PMSProject, PMSTask, PMSTaskAssignee, PMSWorkSubmission, PMSWorkReview
    owner = schedule_owner(db)
    project = PMSProject(name="Assignment email project", project_key="EMAIL", organization_id=1, manager_user_id=owner.id)
    db.add(project); db.flush()
    task = PMSTask(project_id=project.id, title="Shared task", task_key="EMAIL-1", status="To Do", due_date=date.today())
    db.add(task); db.flush()
    assignment = PMSTaskAssignee(task_id=task.id, user_id=owner.id, execution_status="To Do")
    db.add(assignment); db.commit()
    assert db.query(EmailOutbox).filter_by(module="pms").count() == 1
    assert enqueue_due_reminders(db, run_date=date.today()) == 1
    submission = PMSWorkSubmission(task_id=task.id, user_id=owner.id, version=1, notes="Private evidence", status="Pending Review")
    db.add(submission); db.commit()
    initial = db.query(EmailOutbox).count()
    review = PMSWorkReview(submission_id=submission.id, reviewer_user_id=owner.id, decision="Approved", score=100, maximum_score=100, feedback="Private feedback")
    db.add(review)
    assignment.execution_status = "Done"
    submission.status = "Approved"
    db.commit()
    assert db.query(EmailOutbox).count() == initial + 1
    assert "Private feedback" not in db.query(EmailOutbox).order_by(EmailOutbox.id.desc()).first().body


def test_automation_email_action_queues_tenant_template(db):
    from app.apps.automation.models import AutomationAction
    from app.apps.automation.services.engine import _action_result
    from app.apps.communication.models import CommunicationEmailTemplate
    owner = schedule_owner(db)
    owner.organization_id = 1
    template = CommunicationEmailTemplate(organization_id=1, name="Automation template", subject="Hello {{name}}", body_text="Welcome {{name}}", module_name="crm", active=True)
    db.add(template); db.commit()
    action = AutomationAction(action_json={"type": "send_email", "template_id": template.id})
    result = _action_result(db, action, {"module_name": "crm", "record": {"name": "Test"}}, owner)
    db.commit()
    assert result["status"] == "email_queued"
    assert db.query(EmailOutbox).filter_by(subject="Hello Test", organization_id=1).count() == 1


def test_revoked_invitation_is_not_emailed(db, monkeypatch):
    from datetime import datetime, timezone
    from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceInvitation
    schedule_owner(db)
    workspace = PMSWorkspace(name="Revoked invite", organization_id=1)
    db.add(workspace); db.flush()
    invitation = PMSWorkspaceInvitation(workspace_id=workspace.id, email="invitee@example.com", role="Member",
        token_hash="synthetic-invite-hash", status="revoked", expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    db.add(invitation)
    row = queue_email(db, recipient=invitation.email, subject="Invitation", body="Private invitation", module="pms",
        event_key="workspace-invite:synthetic-invite-hash")
    db.commit()
    monkeypatch.setattr(email, "email_configured", lambda: True)
    sender = Mock(); monkeypatch.setattr(email, "send_email", sender)
    drain_outbox(db)
    assert row.status == "suppressed"
    sender.assert_not_called()


def test_failed_automation_does_not_send_earlier_queued_email(db):
    from app.apps.automation.models import AutomationAction, AutomationWorkflow
    from app.apps.automation.services.engine import execute_workflow
    from app.apps.communication.models import CommunicationEmailTemplate
    owner = schedule_owner(db)
    owner.organization_id = 1
    template = CommunicationEmailTemplate(organization_id=1, name="Atomic template", subject="Do not send", body_text="Body", module_name="crm", active=True)
    workflow = AutomationWorkflow(organization_id=1, name="Atomic email", module_name="crm", record_type="lead", trigger_type="created", created_by=owner.id)
    db.add_all([template, workflow]); db.flush()
    db.add_all([
        AutomationAction(workflow_id=workflow.id, action_type="send_email", action_json={"type": "send_email", "template_id": template.id}, order_index=1),
        AutomationAction(workflow_id=workflow.id, action_type="call_webhook", action_json={"type": "call_webhook", "webhook_endpoint_id": 1}, order_index=2),
    ])
    db.commit()
    result = execute_workflow(db, workflow, {"module_name": "crm", "record_type": "lead", "record_id": 1}, owner)
    db.commit()
    assert result.status == "failed"
    assert db.query(EmailOutbox).filter_by(subject="Do not send").count() == 0
