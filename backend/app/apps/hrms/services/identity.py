from sqlalchemy.orm import Session

from app.common.models import CommonPerson
from app.common.services.identity import SharedIdentityService
from app.models.employee import Employee


class HrmsIdentityService:
    @staticmethod
    def sync_employee_identity(db: Session, employee: Employee) -> CommonPerson | None:
        return SharedIdentityService.sync_from_employee(db, employee)

    @staticmethod
    def person_for_employee(db: Session, employee: Employee) -> CommonPerson | None:
        if employee.user_id:
            return SharedIdentityService.ensure_person_for_user(
                db,
                employee.user,
                display_name=" ".join(part for part in [employee.first_name, employee.last_name] if part).strip(),
                phone_number=employee.phone_number,
                source_module="hrms",
                source_record_type="employee",
                source_record_id=employee.id,
            )
        return None
