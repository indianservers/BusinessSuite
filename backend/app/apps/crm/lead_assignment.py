"""Employee-aware lead ownership; stored identifiers always remain users.id."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import joinedload, load_only

from app.apps.crm.models import CRMActivity, CRMTask, CRMTimelineEvent
from app.apps.crm.services.identity import CrmIdentityService
from app.models.employee import Employee
from app.models.notification import Notification
from app.models.user import Role, User
from app.module_registry import is_app_enabled

LEAD_ACCESS = {
    "crm_view",
    "crm_manage",
    "crm_admin",
    "crm_leads_view",
    "crm_leads_manage",
}
ACTIVE_EMPLOYMENT = {"active", "probation"}


def employee_directory_query(db):
    # Assignment needs business identity, not the rest of the HRMS profile.
    return db.query(Employee).options(
        load_only(
            Employee.id,
            Employee.employee_id,
            Employee.user_id,
            Employee.first_name,
            Employee.middle_name,
            Employee.last_name,
            Employee.status,
            Employee.deleted_at,
            Employee.branch_id,
        ),
        joinedload(Employee.branch),
    )


def tenant(user):
    from app.apps.srm.services.commercial import tenant as organization

    return organization(user)


def ineligible_reason(candidate, organization_id, employee=None):
    if not candidate or not candidate.is_active:
        return "Needs an active login account"
    if tenant(candidate) != organization_id:
        return "Needs a login account in this organization"
    if employee is not None:
        if (
            employee.deleted_at
            or (employee.status or "").casefold() not in ACTIVE_EMPLOYMENT
        ):
            return "Employee is not active or on probation"
        if employee.branch and employee.branch.company_id != organization_id:
            return "Employee belongs to another organization"
    if (
        candidate.person
        and (candidate.person.status or "active").casefold() != "active"
    ):
        return "Employee identity is inactive"
    permissions = {
        p.name for p in (candidate.role.permissions if candidate.role else [])
    }
    if not candidate.is_superuser and not permissions.intersection(LEAD_ACCESS):
        return "Needs CRM lead access on the linked account"
    return None


def employee_for_user(db, candidate):
    if not candidate or not is_app_enabled("hrms"):
        return None
    return employee_directory_query(db).filter(Employee.user_id == candidate.id).first()


def validate_assignee(db, candidate, organization_id):
    reason = ineligible_reason(
        candidate, organization_id, employee_for_user(db, candidate)
    )
    if reason:
        raise HTTPException(422, reason)
    return candidate


def assignee_summary(db, candidate, employee=None):
    if employee:
        display_name = " ".join(
            filter(
                None, [employee.first_name, employee.middle_name, employee.last_name]
            )
        )
    else:
        summary = CrmIdentityService.owner_summary(db, candidate.id)
        display_name = summary.display_name if summary else candidate.email
    code = employee.employee_id if employee else None
    return {
        "id": candidate.id,
        "userId": candidate.id,
        "name": f"{display_name} ({code})" if code else display_name,
        "displayName": display_name,
        "email": candidate.email,
        "employeeId": employee.id if employee else None,
        "employeeCode": code,
        "kind": "employee" if employee else "crm_user",
    }


def directory(db, actor, can_assign):
    organization_id = tenant(actor)
    users = (
        db.query(User)
        .options(
            joinedload(User.person), joinedload(User.role).joinedload(Role.permissions)
        )
        .all()
        if can_assign
        else [actor]
    )
    employees_query = employee_directory_query(db)
    if not can_assign:
        employees_query = employees_query.filter(Employee.user_id == actor.id)
    employees = employees_query.all() if is_app_enabled("hrms") else []
    employee_map = {e.user_id: e for e in employees if e.user_id is not None}
    available = [
        assignee_summary(db, candidate, employee_map.get(candidate.id))
        for candidate in users
        if not ineligible_reason(
            candidate, organization_id, employee_map.get(candidate.id)
        )
    ]
    unavailable = []
    if can_assign:
        users_by_id = {candidate.id: candidate for candidate in users}
        for employee in employees:
            linked_user = users_by_id.get(employee.user_id)
            employee_org = (
                employee.branch.company_id
                if employee.branch
                else tenant(linked_user) if linked_user else 1
            )
            if (
                employee_org != organization_id
                or employee.deleted_at
                or (employee.status or "").casefold() not in ACTIVE_EMPLOYMENT
            ):
                continue
            reason = ineligible_reason(linked_user, organization_id, employee)
            if reason:
                unavailable.append(
                    {
                        "employeeId": employee.id,
                        "employeeCode": employee.employee_id,
                        "name": " ".join(
                            filter(None, [employee.first_name, employee.last_name])
                        ),
                        "reason": reason,
                    }
                )
    return sorted(available, key=lambda item: item["name"].casefold()), unavailable


def assignment_changed(db, lead, actor, previous_owner):
    if lead.owner_user_id == previous_owner:
        return
    candidate = db.get(User, lead.owner_user_id) if lead.owner_user_id else None
    if candidate:
        validate_assignee(db, candidate, lead.organization_id)
    label = (
        assignee_summary(db, candidate, employee_for_user(db, candidate))["name"]
        if candidate
        else "Unassigned"
    )
    for model in (CRMActivity, CRMTask):
        db.query(model).filter(
            model.organization_id == lead.organization_id,
            model.lead_id == lead.id,
            model.owner_user_id == previous_owner,
            model.status.in_(["Pending", "To Do", "Open"]),
        ).update({model.owner_user_id: lead.owner_user_id}, synchronize_session="fetch")
    db.add(
        CRMTimelineEvent(
            organization_id=lead.organization_id,
            record_type="lead",
            record_id=lead.id,
            event_type="assignment",
            title=f"Assigned to {label}",
            actor_user_id=actor.id,
            occurred_at=datetime.now(timezone.utc),
            metadata_json={
                "previousOwnerId": previous_owner,
                "ownerId": lead.owner_user_id,
            },
        )
    )
    if candidate and candidate.id != actor.id:
        db.add(
            Notification(
                company_id=lead.organization_id,
                user_id=candidate.id,
                module="crm",
                event_type="lead_assignment",
                title="Lead assigned to you",
                message=f"{lead.full_name} has been assigned to you.",
                related_entity_type="lead",
                related_entity_id=lead.id,
                action_url=f"/crm/leads?lead={lead.id}",
            )
        )
