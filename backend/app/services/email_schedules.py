"""Prepare due campaigns and reports under their owner's current company scope."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from sqlalchemy import func
from app.access.catalog import permission_objects
from app.core.config import settings
from app.core.tenant_boundary import company_ids, install
from app.models.security_boundary import SecurityResourceOwnership
from app.models.user import User
from app.models.email_outbox import EmailOutbox
from app.services.email_dispatch import queue_email, user_can_receive


def permitted(user, permission):
    return bool(user and user.is_active and (user.is_superuser or permission in {p.name for p in permission_objects(user)}))


@contextmanager
def schedule_scope(db, table, row, permission):
    user = db.get(User, row.created_by)
    if not permitted(user, permission):
        raise ValueError("Schedule owner no longer has permission")
    ownership = db.get(SecurityResourceOwnership, (table, row.id))
    companies = company_ids(db, user)
    company = ownership.company_id if ownership else next(iter(companies)) if len(companies) == 1 else None
    if not company or (not user.is_superuser and company not in companies):
        raise ValueError("Schedule company cannot be verified")
    # A scheduled run is company-scoped even when its owner is a global admin.
    from types import SimpleNamespace
    scoped_user = SimpleNamespace(id=user.id, is_superuser=False) if user.is_superuser else user
    cleanup = install(db, scoped_user, company, verified_portal=user.is_superuser)
    try:
        yield user, company
    finally:
        cleanup()


def _campaign(db, campaign):
    from app.apps.communication.api.router import _recipient_records
    from app.apps.communication.models import CommunicationEmailTemplate
    from app.apps.communication.services.delivery import merge_template
    from app.apps.crm.models import CRMLead, CRMContact
    with schedule_scope(db, "communication_campaigns", campaign, "communication_campaigns_send") as (user, company):
        template = db.query(CommunicationEmailTemplate).filter_by(id=campaign.template_id, active=True).first()
        if not template or template.organization_id != company:
            raise ValueError("Campaign template is unavailable in its company")
        for recipient in _recipient_records(db, campaign.segment_json):
            # Super admins bypass ORM tenant filters, so still bind each recipient explicitly.
            model = CRMContact if recipient["record_type"] == "contact" else CRMLead
            source = db.query(model).filter(model.id == recipient["record_id"], func.coalesce(model.organization_id, 1) == company).first()
            if not source:
                continue
            address_hash = sha256(recipient["email"].casefold().encode()).hexdigest()
            queue_email(db, recipient=recipient["email"], organization_id=company, module="campaign",
                event_key=f"campaign:{campaign.id}:{address_hash}",
                subject=merge_template(template.subject, recipient), body=merge_template(template.body_html or template.body_text, recipient),
                is_html=bool(template.body_html))
        campaign.status = "queued"
        db.commit()


def _report(db, schedule, now):
    from app.apps.analytics.models import AnalyticsReport, AnalyticsReportRun
    from app.apps.analytics.api.router import _financial_allowed
    from app.apps.analytics.services.engine import run_report
    with schedule_scope(db, "analytics_scheduled_reports", schedule, "analytics_schedule") as (user, company):
        report = db.query(AnalyticsReport).filter_by(id=schedule.report_id).first()
        ownership = db.get(SecurityResourceOwnership, ("analytics_reports", schedule.report_id))
        if not report or (ownership and ownership.company_id != company):
            raise ValueError("Scheduled report is unavailable")
        payload = run_report(db, report, _financial_allowed(user), 1, 50, None)
        run = AnalyticsReportRun(report_id=report.id, status="completed", row_count=payload["total"],
            run_by=user.id, parameters_json={"schedule_id": schedule.id}, result_preview_json={"items": payload["items"][:10]})
        db.add(run)
        db.flush()
        for address in schedule.recipients_json or [user.email]:
            recipient = db.query(User).filter(func.lower(User.email) == address.casefold(), User.is_active.is_(True)).first()
            if not recipient or not user_can_receive(db, recipient.id, recipient.email, company):
                continue
            if report.visibility == "private" and recipient.id != report.owner_id:
                continue
            queue_email(db, recipient=recipient.email, user_id=recipient.id, organization_id=company, module="analytics",
                subject="Your scheduled report is ready",
                body="Your scheduled report has completed. Sign in to review the report:\n"
                    + settings.FRONTEND_PUBLIC_URL.rstrip("/") + "/analytics",
                event_key=f"report-schedule:{schedule.id}:{run.id}:{recipient.id}")
        if schedule.frequency == "monthly":
            import calendar
            month = now.month % 12 + 1
            year = now.year + (now.month == 12)
            schedule.next_run_at = now.replace(year=year, month=month, day=min(now.day, calendar.monthrange(year, month)[1]))
        else:
            schedule.next_run_at = now + timedelta(days={"daily": 1, "weekly": 7}[schedule.frequency])
        db.commit()


def prepare_scheduled_email(db, limit=5):
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return 0
    from app.apps.analytics.models import AnalyticsScheduledReport
    from app.apps.communication.models import CommunicationCampaign
    from app.models.platform import ReportSchedule
    from app.services.hrms_report_schedules import run_scheduled_report
    now = datetime.now(timezone.utc)
    processed = 0
    for model, query, handler in (
        (CommunicationCampaign, lambda: db.query(CommunicationCampaign).filter(CommunicationCampaign.status == "scheduled", CommunicationCampaign.scheduled_at <= now), _campaign),
        (AnalyticsScheduledReport, lambda: db.query(AnalyticsScheduledReport).filter(AnalyticsScheduledReport.active == 1, AnalyticsScheduledReport.next_run_at <= now), lambda db, row: _report(db, row, now)),
        (ReportSchedule, lambda: db.query(ReportSchedule).filter(ReportSchedule.status == "Active", ReportSchedule.next_run_at <= now), lambda db, row: run_scheduled_report(db, row, now)),
    ):
        for _ in range(limit - processed):
            row = query().order_by(model.id).with_for_update(skip_locked=True).first()
            if not row:
                break
            identity = row.id
            try:
                handler(db, row)
            except Exception:
                import logging
                logging.getLogger(__name__).warning("scheduled_email_preparation_failed table=%s id=%s", model.__tablename__, identity)
                db.rollback()
                row = db.get(model, identity)
                if model is CommunicationCampaign:
                    row.status = "blocked"
                else:
                    row.next_run_at = now + timedelta(hours=1)
                db.commit()
            processed += 1
    return processed


def prepare_engagement_email(db, limit=25):
    """Fan out published surveys and announcements without unbounded request work."""
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return 0
    from sqlalchemy import exists, select, cast, String, literal
    from app.models.engagement import Announcement, EngagementSurvey
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.services.email_events import _employee
    now = datetime.now(timezone.utc)
    count = 0
    for model, permission in ((Announcement, "notification_manage"), (EngagementSurvey, "performance_manage")):
        marker_key = literal("broadcast:" + model.__tablename__ + ":") + cast(model.id, String)
        query = db.query(model).filter(exists(select(EmailOutbox.id).where(
            EmailOutbox.event_key == marker_key, EmailOutbox.status == "broadcast")))
        if model is Announcement:
            query = query.filter(model.is_published.is_(True), (model.expires_at.is_(None) | (model.expires_at > now)))
        else:
            query = query.filter(model.status.in_(["Active", "Published", "Open"]),
                (model.start_date.is_(None) | (model.start_date <= now.date())),
                (model.end_date.is_(None) | (model.end_date >= now.date())))
        for source in query.order_by(model.id).limit(50).all():
            if count >= limit:
                return count
            try:
                with schedule_scope(db, model.__tablename__, source, permission) as (owner, company):
                    prefix = f"engagement:{model.__tablename__}:{source.id}:"
                    event_key = literal(prefix) + cast(Employee.id, String)
                    employees = db.query(Employee).join(Branch, Employee.branch_id == Branch.id).filter(
                        Branch.company_id == company, Employee.deleted_at.is_(None), Employee.status.in_(["Active", "Probation"]),
                        ~exists(select(EmailOutbox.id).where(EmailOutbox.event_key == event_key)))
                    employees = employees.outerjoin(User, User.id == Employee.user_id).filter(
                        User.is_active.is_(True) | ((Employee.user_id.is_(None)) &
                            (Employee.work_email.is_not(None) | Employee.personal_email.is_not(None))))
                    if model is Announcement:
                        if source.target_department_id:
                            employees = employees.filter(Employee.department_id == source.target_department_id)
                        if source.target_location_id:
                            employees = employees.filter(Employee.location_id == source.target_location_id)
                        if source.audience.casefold() not in {"all", "employees", "department", "location"}:
                            continue  # Unknown audience must never broaden into an all-staff email.
                    for employee in employees.order_by(Employee.id).limit(limit - count):
                        contact = _employee(db, employee.id, company)
                        if not contact:
                            continue
                        address, user_id, org = contact
                        queue_email(db, recipient=address, user_id=user_id, organization_id=org, module="hrms",
                            event_key=prefix + str(employee.id), subject="New employee announcement" if model is Announcement else "You are invited to an employee survey",
                            body="Sign in to review the published announcement or survey:\n"
                                + settings.FRONTEND_PUBLIC_URL.rstrip("/") + "/hrms/engagement")
                        count += 1
                    db.commit()
                    if not employees.first():
                        marker = db.query(EmailOutbox).filter_by(event_key=f"broadcast:{model.__tablename__}:{source.id}").first()
                        if marker:
                            marker.status = "expanded"
                            db.commit()
            except Exception:
                db.rollback()
    return count


def campaign_allowed(db, outbox):
    from app.apps.communication.models import CommunicationCampaign
    from app.apps.communication.services.delivery import is_opted_out
    campaign_id = int(outbox.event_key.split(":")[1])
    campaign = db.get(CommunicationCampaign, campaign_id)
    owner = db.get(User, campaign.created_by) if campaign else None
    return bool(campaign and campaign.status in {"queued", "running"}
        and permitted(owner, "communication_campaigns_send")
        and (owner.is_superuser or outbox.organization_id in company_ids(db, owner))
        and not is_opted_out(db, outbox.recipient))


def update_campaign_result(db, outbox):
    from app.apps.communication.models import CommunicationCampaign
    campaign_id = int(outbox.event_key.split(":")[1])
    campaign = db.get(CommunicationCampaign, campaign_id)
    if not campaign:
        return
    db.flush()
    counts = dict(db.query(EmailOutbox.status, func.count(EmailOutbox.id)).filter(
        EmailOutbox.event_key.startswith(f"campaign:{campaign_id}:")).group_by(EmailOutbox.status))
    campaign.sent_count = counts.get("accepted", 0)
    campaign.blocked_count = counts.get("suppressed", 0)
    campaign.failed_count = counts.get("reconciliation_required", 0) + counts.get("failed", 0)
    if not counts.get("queued") and campaign.status != "cancelled":
        campaign.status = "completed"
