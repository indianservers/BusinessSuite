"""Shared server-side employee filters and sorting for listing and CSV export."""
from datetime import date
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from app.models.employee import Employee, EmployeeEducation


class EmployeeDirectoryFilters(BaseModel):
    search: str | None = None
    status: str | None = None
    branch_id: int | None = Field(default=None, gt=0)
    department_id: int | None = Field(default=None, gt=0)
    designation_id: int | None = Field(default=None, gt=0)
    employment_type: str | None = None
    city: str | None = None
    state: str | None = None
    passout_year: int | None = Field(default=None, ge=1970, le=2200)
    college: str | None = None
    degree: str | None = None
    specialization: str | None = None
    gender: str | None = None
    work_location: str | None = None
    worker_type: str | None = None
    reporting_manager_id: int | None = Field(default=None, gt=0)
    joined_from: date | None = None
    joined_to: date | None = None
    account_status: Literal["active", "inactive", "unlinked"] | None = None
    sort_by: Literal["name", "employee_id", "date_of_joining", "city", "status", "employment_type", "passout_year"] = "name"
    sort_order: Literal["asc", "desc"] = "asc"


def apply_employee_directory_filters(query, values):
    if values.get("joined_from") and values.get("joined_to") and values["joined_from"] > values["joined_to"]:
        raise HTTPException(422, "Joining date From must be on or before To")
    for key in ("branch_id", "department_id", "designation_id", "status", "employment_type", "gender", "work_location", "worker_type", "reporting_manager_id"):
        if values.get(key):
            query = query.filter(getattr(Employee, key) == values[key])
    for key, column in (("city", Employee.present_city), ("state", Employee.present_state)):
        if values.get(key):
            query = query.filter(func.lower(func.trim(column)) == values[key].strip().lower())
    if values.get("search"):
        term = "%" + values["search"].strip() + "%"
        query = query.filter(or_(*[column.ilike(term) for column in (
            Employee.first_name, Employee.last_name, Employee.employee_id,
            Employee.personal_email, Employee.work_email, Employee.phone_number,
            Employee.first_name + " " + Employee.last_name,
        )]))
    education = []
    for key, column in (("passout_year", EmployeeEducation.pass_year), ("college", EmployeeEducation.institution),
                        ("degree", EmployeeEducation.degree), ("specialization", EmployeeEducation.specialization)):
        if values.get(key):
            education.append(column == values[key] if key == "passout_year" else func.lower(func.trim(column)) == values[key].strip().lower())
    if education:
        query = query.filter(Employee.educations.any(and_(*education)))
    if values.get("joined_from"):
        query = query.filter(Employee.date_of_joining >= values["joined_from"])
    if values.get("joined_to"):
        query = query.filter(Employee.date_of_joining <= values["joined_to"])
    account = values.get("account_status")
    if account == "unlinked":
        query = query.filter(Employee.user_id.is_(None))
    elif account:
        from app.models.user import User
        query = query.filter(Employee.user.has(User.is_active.is_(account == "active")))
    return query


def order_employee_directory(query, sort_by="name", sort_order="asc"):
    passout_year = select(func.max(EmployeeEducation.pass_year)).where(EmployeeEducation.employee_id == Employee.id).correlate(Employee).scalar_subquery()
    columns = {"name": func.lower(Employee.first_name), "employee_id": Employee.employee_id,
               "date_of_joining": Employee.date_of_joining, "city": func.lower(Employee.present_city),
               "status": Employee.status, "employment_type": Employee.employment_type, "passout_year": passout_year}
    column = columns.get(sort_by, columns["name"])
    ordered = column.desc() if sort_order == "desc" else column.asc()
    return query.order_by(ordered.nullslast(), func.lower(Employee.last_name), Employee.id)
