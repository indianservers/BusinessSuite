from datetime import datetime, timedelta, timezone, date
from pathlib import Path
import pytest
from fastapi import HTTPException
from app.services.hrms_report_schedules import next_run


def test_recurring_report_time_is_ist_and_validated():
    now = datetime(2026, 10, 28, 4, 0, tzinfo=timezone.utc)
    assert next_run("0 9 * * *", now) == datetime(2026, 10, 29, 3, 30, tzinfo=timezone.utc)
    assert next_run("0 9 * * 1", now) == datetime(2026, 11, 2, 3, 30, tzinfo=timezone.utc)
    assert next_run("0 9 1 * *", now) == datetime(2026, 11, 1, 3, 30, tzinfo=timezone.utc)
    for expression in ["bad", "0 25 * * *", "* * * * *"]:
        with pytest.raises(HTTPException):
            next_run(expression, now)


def test_report_export_writes_csv_applies_filters_and_escapes_cells(client, db, superuser_headers):
    from app.models.employee import Employee
    from app.models.platform import ReportRun
    from app.core.config import settings
    db.add_all([Employee(employee_id="REPORT-A", first_name="=UNTRUSTED()", last_name="Active", status="Active", date_of_joining=date.today()), Employee(employee_id="REPORT-B", first_name="Other", last_name="Inactive", status="Inactive", date_of_joining=date.today())])
    db.commit()
    definition = client.post("/api/v1/reports/definitions", headers=superuser_headers, json={"name": "Filtered report", "code": "FILTERED-REPORT", "module": "employees", "selected_fields_json": ["first_name", "status"], "filters_json": {"status": "Active"}})
    assert definition.status_code == 201, definition.text
    generated = client.post(f"/api/v1/reports/definitions/{definition.json()['id']}/run", headers=superuser_headers)
    assert generated.status_code == 201, generated.text
    run = db.get(ReportRun, generated.json()["id"])
    body = (Path(settings.UPLOAD_DIR) / run.file_url.removeprefix("/uploads/")).read_text(encoding="utf-8-sig")
    assert "'=UNTRUSTED()" in body
    assert "Inactive" not in body
    assert generated.json()["row_count"] == 1


def test_scheduled_report_materializes_once_and_queues_authorized_delivery(db, monkeypatch):
    from tests.test_shared_email import schedule_owner
    from app.models.platform import ReportDefinition, ReportSchedule, ReportRun
    from app.models.security_boundary import SecurityResourceOwnership
    from app.models.email_outbox import EmailOutbox
    from app.services.email_schedules import prepare_scheduled_email
    from app.core.config import settings
    owner = schedule_owner(db)
    monkeypatch.setattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", True)
    definition = ReportDefinition(name="People report", code="HRMS-SCHEDULED", module="employees", selected_fields_json=["employee_code", "first_name"], created_by=owner.id)
    db.add(definition); db.flush()
    schedule = ReportSchedule(report_definition_id=definition.id, name="Daily people report", cron_expression="0 9 * * *", recipients_json=[owner.email], status="Active", next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1), created_by=owner.id)
    db.add(schedule); db.flush()
    for table, identity in [("report_definitions", definition.id), ("report_schedules", schedule.id)]:
        if not db.get(SecurityResourceOwnership, (table, identity)):
            db.add(SecurityResourceOwnership(resource_table=table, resource_id=identity, company_id=1))
    db.commit()
    assert prepare_scheduled_email(db) == 1
    assert db.query(ReportRun).filter(ReportRun.report_definition_id == definition.id).count() == 1
    assert db.query(EmailOutbox).filter(EmailOutbox.event_key.startswith("hrms-report:")).count() == 1
    assert prepare_scheduled_email(db) == 0
