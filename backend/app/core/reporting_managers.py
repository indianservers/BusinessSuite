"""Shared eligibility policy for reporting managers and intern supervisors."""

REPORTING_MANAGER_ROLES = {
    "super_admin", "superadmin", "ceo", "hr", "hr_admin", "hr_manager",
    "project_manager", "pms_project_manager",
}


def eligible_manager_account(account):
    if account is None or not account.is_active:
        return False
    role = (account.role.name if account.role else "").strip().lower().replace("-", "_").replace(" ", "_")
    return role != "intern" and (account.is_superuser or role in REPORTING_MANAGER_ROLES)


def eligible_reporting_manager(employee):
    return bool(
        employee is not None
        and employee.deleted_at is None
        and employee.status in {"Active", "Probation"}
        and (employee.employment_type or "").strip().lower() != "intern"
        and eligible_manager_account(employee.user)
    )
