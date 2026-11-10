"""Opt-in document reminders dispatched by the existing authenticated cron."""

from datetime import date, timedelta
from fastapi import HTTPException
from app.shared.models import ServicePolicy
from app.models.user import User
from app.models.document import EmployeeCertificate
from app.models.employee import Employee
from app.access.service import background_scope
from app.branches.service import access
from app.services.metrics.queries import business_day


def run_document_reminders(db, limit=50):
    from app.api.v1.document_vault import (
        policies,
        missing_for,
        records,
        employees,
        applies,
        remind,
        Reminder,
    )

    sources = (
        db.query(ServicePolicy)
        .filter(
            ServicePolicy.module_key == "hrms",
            ServicePolicy.kind.in_(["document_requirement", "certificate_metadata"]),
        )
        .all()
    )
    actors = {
        (row.organization_id, row.updated_by)
        for row in sources
        if row.values_json.get("reminders_enabled")
        or row.kind == "certificate_metadata"
        and row.values_json.get("reminder_date")
    }
    queued = 0
    for company, actor_id in sorted(actors):
        actor = db.get(User, actor_id)
        if not actor or not actor.is_active:
            continue
        previous = getattr(actor, "organization_id", None)
        actor.organization_id = company
        try:
            for branch in sorted(access(db, actor, company)[0]):
                with background_scope(
                    db, actor, "hrms", action="edit", branch_id=branch
                ):
                    today = business_day(db, actor)
                    rules = [
                        p.values_json
                        for p in policies(db, actor).all()
                        if p.values_json.get("active", True)
                        and p.values_json.get("reminders_enabled")
                    ]
                    wanted = {}
                    for identity, missing in missing_for(db, actor).items():
                        if any(rule in rules for rule in missing):
                            wanted[identity] = (
                                "Please review and complete your mandatory employee documents."
                            )
                    for certificate in records(db, actor).all():
                        if certificate.expiry_date and any(
                            applies(rule, certificate.employee)
                            and rule["certificate_type"].casefold()
                            == certificate.certificate_type.casefold()
                            and certificate.expiry_date
                            <= today + timedelta(days=rule.get("reminder_days", 30))
                            for rule in rules
                        ):
                            wanted[certificate.employee_id] = (
                                "An employee document is expired or nearing renewal. Please review your document vault."
                            )
                    for saved in sources:
                        if (
                            saved.organization_id != company
                            or saved.kind != "certificate_metadata"
                        ):
                            continue
                        reminder = saved.values_json.get("reminder_date")
                        if not reminder:
                            continue
                        try:
                            due = date.fromisoformat(reminder) <= today
                        except ValueError:
                            continue
                        if due:
                            identity = int(saved.scope_key.rsplit(":", 1)[-1])
                            cert = (
                                records(db, actor)
                                .filter(EmployeeCertificate.id == identity)
                                .first()
                            )
                            if cert:
                                wanted[cert.employee_id] = (
                                    "Your configured employee document reminder is due. Please review your document vault."
                                )
                    for identity, message in wanted.items():
                        person = (
                            employees(db, actor).filter(Employee.id == identity).first()
                        )
                        if not person or not person.user_id:
                            continue
                        result = remind(
                            Reminder(employee_id=identity, message=message), db, actor
                        )
                        if not result.get("duplicate"):
                            queued += 1
                        if queued >= limit:
                            return queued
        except HTTPException:
            db.rollback()  # A revoked policy owner cannot send background notices.
        finally:
            actor.organization_id = previous
    return queued
