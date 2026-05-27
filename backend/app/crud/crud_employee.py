from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from app.apps.hrms.services.identity import HrmsIdentityService
from app.crud.base import CRUDBase
from app.models.employee import (
    Employee,
    EmployeeDocument,
    EmployeeEducation,
    EmployeeExperience,
    EmployeeLifecycleEvent,
    EmployeeSkill,
)
from app.models.user import User
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.core.security import get_password_hash


class CRUDEmployee(CRUDBase[Employee, EmployeeCreate, EmployeeUpdate]):

    def generate_employee_id(self, db: Session) -> str:
        last = db.query(Employee).order_by(Employee.id.desc()).first()
        next_num = (last.id + 1) if last else 1
        return f"EMP{next_num:05d}"

    def get_by_employee_id(self, db: Session, employee_id: str) -> Optional[Employee]:
        return db.query(Employee).filter(
            Employee.employee_id == employee_id,
            Employee.deleted_at.is_(None),
        ).first()

    def get_with_details(self, db: Session, id: int) -> Optional[Employee]:
        return (
            db.query(Employee)
            .options(
                joinedload(Employee.educations),
                joinedload(Employee.experiences),
                joinedload(Employee.skills),
                joinedload(Employee.documents),
                joinedload(Employee.lifecycle_events),
            )
            .filter(Employee.id == id, Employee.deleted_at.is_(None))
            .first()
        )

    def search(
        self,
        db: Session,
        *,
        search: Optional[str] = None,
        department_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        designation_id: Optional[int] = None,
        status: Optional[str] = None,
        employment_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Employee], int]:
        query = db.query(Employee).filter(Employee.deleted_at.is_(None))

        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(term),
                    Employee.last_name.ilike(term),
                    Employee.employee_id.ilike(term),
                    Employee.personal_email.ilike(term),
                    Employee.phone_number.ilike(term),
                )
            )
        if department_id:
            query = query.filter(Employee.department_id == department_id)
        if branch_id:
            query = query.filter(Employee.branch_id == branch_id)
        if designation_id:
            query = query.filter(Employee.designation_id == designation_id)
        if status:
            query = query.filter(Employee.status == status)
        if employment_type:
            query = query.filter(Employee.employment_type == employment_type)

        total = query.count()
        items = query.order_by(Employee.first_name).offset(skip).limit(limit).all()
        return items, total

    def create_with_user(self, db: Session, *, obj_in: EmployeeCreate, created_by: int | None = None) -> Employee:
        emp_id = obj_in.employee_id or self.generate_employee_id(db)

        user = None
        if obj_in.create_user_account and obj_in.user_email:
            user = User(
                email=obj_in.user_email,
                hashed_password=get_password_hash(obj_in.user_password or "Welcome@123"),
                is_active=True,
            )
            db.add(user)
            db.flush()

        emp_data = obj_in.model_dump(
            exclude={"create_user_account", "user_email", "user_password", "employee_id"}
        )
        db_emp = Employee(**emp_data, employee_id=emp_id, user_id=user.id if user else None)
        db.add(db_emp)
        db.flush()
        if user:
            db_emp.user = user
            HrmsIdentityService.sync_employee_identity(db, db_emp)
        from app.crud.crud_onboarding import auto_start_onboarding_for_employee

        auto_start_onboarding_for_employee(db, db_emp, created_by=created_by)
        db.commit()
        db.refresh(db_emp)
        return db_emp

    def add_education(self, db: Session, employee_id: int, data: dict) -> EmployeeEducation:
        edu = EmployeeEducation(employee_id=employee_id, **data)
        db.add(edu)
        db.commit()
        db.refresh(edu)
        return edu

    def add_experience(self, db: Session, employee_id: int, data: dict) -> EmployeeExperience:
        exp = EmployeeExperience(employee_id=employee_id, **data)
        db.add(exp)
        db.commit()
        db.refresh(exp)
        return exp

    def add_skill(self, db: Session, employee_id: int, data: dict) -> EmployeeSkill:
        skill = EmployeeSkill(employee_id=employee_id, **data)
        db.add(skill)
        db.commit()
        db.refresh(skill)
        return skill

    def add_document(self, db: Session, employee_id: int, data: dict) -> EmployeeDocument:
        doc = EmployeeDocument(employee_id=employee_id, **data)
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    def list_lifecycle_events(self, db: Session, employee_id: int) -> List[EmployeeLifecycleEvent]:
        return (
            db.query(EmployeeLifecycleEvent)
            .filter(EmployeeLifecycleEvent.employee_id == employee_id)
            .order_by(EmployeeLifecycleEvent.event_date.desc(), EmployeeLifecycleEvent.id.desc())
            .all()
        )

    def add_lifecycle_event(
        self,
        db: Session,
        *,
        employee: Employee,
        data: dict,
        created_by: Optional[int] = None,
    ) -> EmployeeLifecycleEvent:
        apply_to_employee = data.pop("apply_to_employee", False)
        event = EmployeeLifecycleEvent(
            employee_id=employee.id,
            created_by=created_by,
            from_status=employee.status,
            from_branch_id=employee.branch_id,
            from_department_id=employee.department_id,
            from_designation_id=employee.designation_id,
            from_manager_id=employee.reporting_manager_id,
            **data,
        )

        if apply_to_employee:
            if data.get("to_status") is not None:
                employee.status = data["to_status"]
            if data.get("to_branch_id") is not None:
                employee.branch_id = data["to_branch_id"]
            if data.get("to_department_id") is not None:
                employee.department_id = data["to_department_id"]
            if data.get("to_designation_id") is not None:
                employee.designation_id = data["to_designation_id"]
            if data.get("to_manager_id") is not None:
                employee.reporting_manager_id = data["to_manager_id"]

        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def get_headcount_stats(self, db: Session) -> dict:
        active_query = db.query(func.count(Employee.id)).filter(Employee.deleted_at.is_(None))
        total = active_query.scalar()
        active = active_query.filter(Employee.status == "Active").scalar()
        on_leave = active_query.filter(Employee.status == "On Leave").scalar()
        resigned = active_query.filter(Employee.status == "Resigned").scalar()
        return {"total": total, "active": active, "on_leave": on_leave, "resigned": resigned}


crud_employee = CRUDEmployee(Employee)
