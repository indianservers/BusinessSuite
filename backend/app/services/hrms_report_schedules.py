"""Real CSV materialization and permission-checked recurring HRMS reports."""
import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.core.config import settings
from app.core.storage import persist_file
from app.models.platform import ReportRun, ReportDefinition
from app.models.user import User


def next_run(expression, after=None):
    """Numeric or wildcard cron fields, interpreted in the company's India timezone."""
    values = expression.split()
    if len(values) != 5:
        raise HTTPException(422, "Choose a daily, weekly or monthly report schedule")
    limits = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    parsed = []
    for value, (low, high) in zip(values, limits):
        if value != "*" and (not value.isdigit() or not low <= int(value) <= high):
            raise HTTPException(422, "Schedule fields must be numeric or *")
        parsed.append(None if value == "*" else int(value))
    if parsed[0] is None or parsed[1] is None:
        raise HTTPException(422, "Reports require a specific hour and minute")
    now = (after or datetime.now(timezone.utc)).astimezone(ZoneInfo("Asia/Kolkata"))
    for days in range(367):
        candidate = (now + timedelta(days=days)).replace(hour=parsed[1], minute=parsed[0], second=0, microsecond=0)
        if candidate <= now or (parsed[2] is not None and candidate.day != parsed[2]) or (parsed[3] is not None and candidate.month != parsed[3]) or (parsed[4] is not None and (candidate.weekday() + 1) % 7 != parsed[4]):
            continue
        return candidate.astimezone(timezone.utc)
    raise HTTPException(422, "No report date occurs within the next year")


def materialize(db, definition, actor_id):
    from app.api.v1.reports import _run_report_rows
    columns, rows = _run_report_rows(db, definition)
    run = ReportRun(report_definition_id=definition.id, status="Completed", row_count=len(rows), requested_by=actor_id)
    db.add(run); db.flush()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    def cell(value):
        text = str(value if value is not None else "")
        return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text
    for row in rows:
        writer.writerow([cell(row.get(key)) for key in columns])
    target = Path(settings.UPLOAD_DIR) / "reports" / f"report-run-{run.id}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output.getvalue(), encoding="utf-8-sig")
    persist_file(str(target))
    run.file_url = f"/uploads/reports/{target.name}"
    from app.models.audit import AuditLog
    db.add(AuditLog(user_id=actor_id, method="SYSTEM", endpoint="/reports/exports", status_code=200, action="report_export_generated", module="reports", entity_type="report_run", entity_id=run.id, description=f"Generated {len(rows)} rows for report {definition.id}"))
    return run


def run_scheduled_report(db, schedule, now):
    from app.services.email_schedules import schedule_scope, permitted
    from app.services.email_dispatch import queue_email, user_can_receive
    from app.models.audit import AuditLog
    with schedule_scope(db, "report_schedules", schedule, "reports_manage") as (owner, company):
        definition = db.query(ReportDefinition).filter(ReportDefinition.id == schedule.report_definition_id, ReportDefinition.is_active.is_(True)).first()
        if not definition or not permitted(owner, "reports_view") or (definition.module == "payroll" and not permitted(owner, "payroll_view")):
            raise ValueError("Report owner no longer has access to this report")
        run = materialize(db, definition, owner.id)
        allowed_roles = {r.strip().lower() for r in (definition.visible_to_roles or "").split(",") if r.strip()}
        for address in schedule.recipients_json or [owner.email]:
            recipient = db.query(User).filter(User.email == address, User.is_active.is_(True)).first()
            role = recipient.role.name.lower() if recipient and recipient.role else ""
            if not recipient or not user_can_receive(db, recipient.id, recipient.email, company) or not permitted(recipient, "reports_view") or (definition.module == "payroll" and not permitted(recipient, "payroll_view")) or (allowed_roles and role not in allowed_roles and not recipient.is_superuser):
                db.add(AuditLog(user_id=owner.id, method="SYSTEM", endpoint="/reports/schedules", status_code=403, action="report_recipient_skipped", module="reports", entity_type="report_schedule", entity_id=schedule.id, description="Recipient no longer authorized for scheduled report"))
                continue
            queue_email(db, recipient=recipient.email, user_id=recipient.id, organization_id=company, module="hrms_reports",
                        subject=f"Scheduled report ready: {definition.name}",
                        body=f"Your scheduled report has completed ({run.row_count} rows). Sign in to view the authorized report:\n{settings.FRONTEND_PUBLIC_URL.rstrip('/')}/hrms/reports?report_id={definition.id}",
                        event_key=f"hrms-report:{schedule.id}:{run.id}:{recipient.id}")
        schedule.last_run_at = now
        schedule.next_run_at = next_run(schedule.cron_expression, now)
        db.commit()
