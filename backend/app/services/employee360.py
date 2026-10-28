"""Employee-scoped, permission-filtered operational overview."""
from datetime import date
from sqlalchemy.orm import joinedload
from app.access.catalog import permission_objects
from app.models.asset import AssetAssignment
from app.models.employee import EmployeeChangeRequest
from app.models.expense import ExpenseClaim
from app.models.payroll import EmployeeSalary, SalaryRevisionRequest


def build_employee360(db, employee, user):
    permissions = {p.name for p in permission_objects(user)}
    allowed = lambda name: user.is_superuser or name in permissions
    own = bool(user.employee and user.employee.id == employee.id)
    manager = bool(user.employee and employee.reporting_manager_id == user.employee.id)
    role = (user.role.name if user.role else "").lower().replace(" ", "_")
    finance = allowed("payroll_run") or allowed("payroll_approve")
    hr = finance or allowed("hr_admin") or role in {"hr", "hr_admin", "hr_manager", "super_admin"}
    access = {
        "payroll": allowed("payroll_view"),
        "assets": own or allowed("asset_view"),
        "expenses": own or manager or hr,
        "profile_changes": own or allowed("employee_update"),
    }
    result = {"employee_id": employee.id, "as_of": date.today(), "currency": employee.salary_currency or "INR",
              "access": access, "salary": None, "salary_history": [], "increments": [],
              "assets": [], "expenses": [], "pending_actions": []}

    def action(key, title, section, owner):
        result["pending_actions"].append({"id": key, "title": title, "section": section, "owner": owner})

    if access["payroll"]:
        salaries = db.query(EmployeeSalary).filter(EmployeeSalary.employee_id == employee.id).order_by(
            EmployeeSalary.effective_from.desc(), EmployeeSalary.id.desc()).all()
        for row in salaries:
            item = {"id": row.id, "ctc": str(row.ctc), "effective_from": row.effective_from,
                    "effective_to": row.effective_to, "payroll_type": row.payroll_type}
            result["salary_history"].append(item)
            if result["salary"] is None and row.effective_from <= date.today() and (
                row.effective_to is None or row.effective_to >= date.today()
            ):
                result["salary"] = item
        if result["salary"] is None:
            action("salary-missing", "Set up a currently effective salary", "salary", "Payroll team")
        revisions = db.query(SalaryRevisionRequest).filter(SalaryRevisionRequest.employee_id == employee.id).order_by(
            SalaryRevisionRequest.effective_from.desc(), SalaryRevisionRequest.id.desc()).all()
        for row in revisions:
            result["increments"].append({"id": row.id, "current_ctc": str(row.current_ctc or 0),
                "proposed_ctc": str(row.proposed_ctc), "effective_from": row.effective_from,
                "reason": row.reason, "status": row.status})
            if row.status.lower() == "pending":
                action(f"revision-{row.id}", f"Salary revision #{row.id} awaiting review", "increments", "Payroll approver")
    if access["assets"]:
        assignments = db.query(AssetAssignment).options(joinedload(AssetAssignment.asset)).filter(
            AssetAssignment.employee_id == employee.id, AssetAssignment.is_active.is_(True)
        ).order_by(AssetAssignment.assigned_date.desc(), AssetAssignment.id.desc()).all()
        for row in assignments:
            result["assets"].append({"id": row.id, "name": row.asset.name, "asset_tag": row.asset.asset_tag,
                "serial_number": row.asset.serial_number, "assigned_date": row.assigned_date,
                "condition": row.condition_at_assignment, "acknowledged": row.acknowledgement_signed})
            if not row.acknowledgement_signed:
                action(f"asset-{row.id}", f"Acknowledge {row.asset.name} ({row.asset.asset_tag})", "assets", "Employee")
    if access["expenses"]:
        claims = db.query(ExpenseClaim).filter(ExpenseClaim.employee_id == employee.id).order_by(
            ExpenseClaim.expense_date.desc(), ExpenseClaim.id.desc()).all()
        for row in claims:
            result["expenses"].append({"id": row.id, "claim_number": row.claim_number,
                "claim_type": row.claim_type, "expense_date": row.expense_date, "amount": str(row.amount),
                "approved_amount": str(row.approved_amount or 0), "currency": row.currency,
                "status": row.status, "reimbursed_at": row.reimbursed_at,
                "payment_reference": row.reimbursement_reference, "payroll_run_id": row.payroll_run_id})
            owner = {"submitted": "Manager", "manager_approved": "Finance team", "finance_approved": "Payroll / finance team"}.get(row.status.lower())
            if owner and not row.reimbursed_at:
                action(f"expense-{row.id}", f"{row.claim_number}: {row.status.replace('_', ' ')}", "expenses", owner)
    if access["profile_changes"]:
        requests = db.query(EmployeeChangeRequest).filter(EmployeeChangeRequest.employee_id == employee.id,
            EmployeeChangeRequest.status == "Pending").order_by(EmployeeChangeRequest.id.desc()).all()
        for row in requests:
            action(f"profile-{row.id}", f"Profile change #{row.id} awaiting review", "profile", "HR team")
    return result
