from app.access.catalog import permission_objects
from fastapi import Depends, HTTPException
from sqlalchemy import or_, and_, func, cast, select, exists
from app.core.deps import get_current_user
from app.models.employee import Employee
from app.models.company import Branch
from app.apps.srm.services.commercial import tenant
from .management_models import InternBatch, InternBatchMembership

HR_ROLES={"admin","super_admin","hr","hr_admin","hr_manager","hr_company_admin"}
MANAGER_ROLES={"manager","department_head","team_lead","pms_project_manager","pms_org_admin"}


def require_admin(user=Depends(get_current_user)):
    if not user or not user.is_active: raise HTTPException(403,"Active manager account required")
    role=user.role.name.lower() if user.role else ""
    perms={p.name for p in permission_objects(user)}
    if role=="intern" or user.employee and (user.employee.employment_type or "").lower()=="intern":
        raise HTTPException(403,"Interns cannot access administration")
    if user.is_superuser: return user
    if role not in HR_ROLES|MANAGER_ROLES or not perms.intersection({"employee_view","employee_update","intern_management_view","intern_management_manage","pms_manage_tasks","pms_manage_projects","pms_admin"}):
        raise HTTPException(403,"Intern Management requires an authorized HRMS manager or administrator")
    if user.employee and (user.employee.employment_type or "").lower()=="intern":
        raise HTTPException(403,"Interns cannot access administration")
    return user


def organization_admin(user):
    role=user.role.name.lower() if user.role else ""
    return user.is_superuser or role in HR_ROLES-{"hr_manager"}


def batch_query(db,user):
    q=db.query(InternBatch).filter(InternBatch.organization_id==tenant(user))
    if not organization_admin(user):
        e=user.employee
        if db.get_bind().dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB
            backup = cast(InternBatch.additional_mentors, JSONB).contains([user.id])
        else:
            mentors = func.json_each(InternBatch.additional_mentors).table_valued("value").alias("batch_backup_mentors")
            backup = exists(select(1).select_from(mentors).where(mentors.c.value == user.id))
        scope = [InternBatch.manager_user_id == user.id, InternBatch.mentor_user_id == user.id,
                 InternBatch.coordinator_user_id == user.id, backup]
        if e and e.department_id and user.role.name.lower() in {"hr_manager", "department_head"}:
            scope.append(InternBatch.department_id == e.department_id)
        q=q.filter(or_(*scope))
    return q


def employee_query(db,user,include_employees=False):
    q=db.query(Employee).outerjoin(Branch,Employee.branch_id==Branch.id).filter(Employee.deleted_at.is_(None))
    if not include_employees:q=q.filter(func.lower(Employee.employment_type)=="intern")
    q=q.filter(or_(Branch.company_id==tenant(user),and_(Employee.branch_id.is_(None),tenant(user)==1)))
    if not organization_admin(user):
        e=user.employee
        batches=batch_query(db,user).with_entities(InternBatch.id)
        members=db.query(InternBatchMembership.employee_id).filter(InternBatchMembership.batch_id.in_(batches),InternBatchMembership.status=="Active")
        scope=[Employee.id.in_(members)]
        if e:
            scope.append(Employee.reporting_manager_id==e.id)
            if user.role.name.lower() in {"hr_manager","department_head"} and e.department_id: scope.append(Employee.department_id==e.department_id)
        q=q.filter(or_(*scope))
    return q


def get_batch(db,user,batch_id):
    batch=batch_query(db,user).filter(InternBatch.id==batch_id).first()
    if not batch: raise HTTPException(404,"Authorized batch not found")
    return batch


def get_employee(db,user,employee_id):
    row=employee_query(db,user,include_employees=True).filter(Employee.id==employee_id).first()
    if not row: raise HTTPException(404,"Authorized intern not found")
    return row
