"""Request-local tenant restrictions for the legacy HRMS employee router."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy import event, or_
from sqlalchemy.orm import with_loader_criteria
from app.core.reporting_managers import eligible_reporting_manager
from app.core.deps import get_current_user, get_db
from app.models.employee import Employee, EmployeeDocument, EmployeeEducation, EmployeeExperience, EmployeeSkill, EmployeeLifecycleEvent, EmployeeChangeRequest
from app.models.company import Branch, Department, Designation
from app.models.document import EmployeeCertificate, GeneratedDocument, CertificateImportExportBatch, CompanyPolicy, CompanyPolicyVersion, DocumentTemplate
from app.apps.srm.services.commercial import tenant


def validate_employee_links(db, user, values, employee=None):
    """Reject write payloads that would move a record across tenant boundaries."""
    company_id = tenant(user)
    branch_id = values.get('branch_id', employee.branch_id if employee else None)
    if branch_id is None:
        if company_id != 1 and not user.is_superuser:
            raise HTTPException(422, 'A company branch is required')
    elif not db.query(Branch.id).filter(Branch.id == branch_id, *([] if user.is_superuser else [Branch.company_id == company_id])).first():
        raise HTTPException(404, 'Authorized branch not found')
    department_id = values.get('department_id', employee.department_id if employee else None)
    if (employee is None or {'branch_id','department_id'}.intersection(values)) and department_id is not None and not db.query(Department.id).filter(Department.id == department_id, Department.branch_id == branch_id).first():
        raise HTTPException(422, 'Department must belong to the selected branch')
    designation_id = values.get('designation_id', employee.designation_id if employee else None)
    if (employee is None or {'branch_id','department_id','designation_id'}.intersection(values)) and designation_id is not None and not db.query(Designation.id).filter(Designation.id == designation_id, Designation.department_id == department_id).first():
        raise HTTPException(422, 'Designation must belong to the selected department')
    manager_id = values.get('reporting_manager_id')
    if manager_id is not None:
        manager = db.query(Employee).filter(Employee.id == manager_id, Employee.deleted_at.is_(None)).first()
        if manager is None:
            raise HTTPException(404, 'Authorized manager not found')
        if employee is not None and manager.id == employee.id:
            raise HTTPException(422, 'An employee cannot report to themselves')
        if (manager.employment_type or '').strip().lower() == 'intern':
            raise HTTPException(422, 'Interns cannot be reporting managers')
        if not eligible_reporting_manager(manager):
            raise HTTPException(422, 'Choose a Super Admin, CEO, HR or Project Manager as reporting manager')


def employee_tenant_scope(request: Request, db=Depends(get_db), user=Depends(get_current_user)):
    if user.is_superuser:
        yield
        return
    company_id = tenant(user)
    allowed = or_(Employee.branch.has(Branch.company_id == company_id),
                  (Employee.branch_id.is_(None)) & (company_id == 1))
    employee_ids = db.query(Employee.id).filter(allowed).subquery()
    criteria = [with_loader_criteria(Employee, allowed, include_aliases=True)]
    criteria.extend([with_loader_criteria(CompanyPolicy,CompanyPolicy.organization_id==company_id,include_aliases=True),with_loader_criteria(DocumentTemplate,DocumentTemplate.organization_id==company_id,include_aliases=True)])
    policies=db.query(CompanyPolicy.id).filter(CompanyPolicy.organization_id==company_id).subquery()
    criteria.append(with_loader_criteria(CompanyPolicyVersion,CompanyPolicyVersion.policy_id.in_(policies.select()),include_aliases=True))
    for model in (EmployeeDocument, EmployeeEducation, EmployeeExperience, EmployeeSkill, EmployeeLifecycleEvent, EmployeeChangeRequest, EmployeeCertificate, GeneratedDocument, CertificateImportExportBatch):
        criteria.append(with_loader_criteria(model, model.employee_id.in_(employee_ids.select()), include_aliases=True))

    def restrict(execution):
        if execution.is_select or execution.is_update or execution.is_delete:
            execution.statement = execution.statement.options(*criteria)

    event.listen(db, 'do_orm_execute', restrict)
    try:
        employee_id = request.path_params.get('employee_id')
        if employee_id is not None:
            try: employee_id = int(employee_id)
            except (ValueError, TypeError): raise HTTPException(404, 'Employee not found')
            if not 0 < employee_id <= 2147483647: raise HTTPException(404, 'Employee not found')
        if employee_id is not None and not db.query(Employee.id).filter(Employee.id == employee_id).first():
            raise HTTPException(404, 'Employee not found')
        yield
    finally:
        event.remove(db, 'do_orm_execute', restrict)
