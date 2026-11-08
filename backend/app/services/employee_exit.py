"""Shared exit creation for the existing exit page and employee workbench."""
from fastapi import HTTPException
from app.models.employee import Employee, EmployeeLifecycleEvent
from app.models.exit import ExitRecord, ExitChecklistItem
from app.services.metrics.queries import employee_records

DEFAULT_EXIT_CHECKLIST = [
    ("Transfer open tasks and project ownership", "Manager"),
    ("Revoke login access and active sessions", "IT"),
    ("Return company assets and confirm condition", "IT"),
    ("Complete exit documents and certificates", "HR"),
    ("Review final settlement and outstanding recoveries", "Finance"),
]


def scoped_exit(db, user, ident):
    row = db.query(ExitRecord).filter(ExitRecord.id == ident,
        ExitRecord.employee_id.in_(employee_records(db, user, include_archived=True).with_entities(Employee.id))).populate_existing().with_for_update().first()
    if not row: raise HTTPException(404, "Exit record not found in your permitted scope")
    return row


def create_exit(db, user, values):
    person = employee_records(db, user, include_archived=True).filter(Employee.id == values["employee_id"]).with_for_update().first()
    if not person: raise HTTPException(404, "Employee not found in your permitted scope")
    existing = db.query(ExitRecord).filter_by(employee_id=person.id).order_by(ExitRecord.id.desc()).first()
    if existing:
        rehire = db.query(EmployeeLifecycleEvent).filter_by(employee_id=person.id, event_type="Employment reactivated").filter(EmployeeLifecycleEvent.created_at > existing.created_at).first()
        if existing.status not in {"Completed", "Cancelled"} or not rehire:
            raise HTTPException(409, "An exit case already exists for this employment period; open its existing checklist")
    if values.get("status", "Initiated") != "Initiated":
        raise HTTPException(422, "New exit records must start as Initiated")
    if values.get("last_working_date") and values["last_working_date"] < person.date_of_joining:
        raise HTTPException(422, "Last working date cannot precede the joining date")
    row = ExitRecord(**values)
    db.add(row); db.flush()
    for name, role in DEFAULT_EXIT_CHECKLIST:
        db.add(ExitChecklistItem(exit_record_id=row.id, task_name=name, assigned_to_role=role))
    return row
