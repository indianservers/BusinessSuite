"""Explicit organization boundary for legacy HR reports, including Super Admin.

Global administration privilege does not silently make an organization KPI global.
Other module/ownership restrictions already installed on the session still apply.
"""
from fastapi import Depends
from sqlalchemy import event,select,or_
from sqlalchemy.orm import with_loader_criteria
from app.core.deps import get_db,get_current_user
from app.db.base_class import Base
from app.models.employee import Employee
from app.models.company import Branch,Department,Company
from app.models.recruitment import Job,Candidate
from .queries import company_id,employee_records


def reporting_scope(db=Depends(get_db),user=Depends(get_current_user)):
    company=company_id(user)
    predicate=employee_records(db,user).whereclause
    employee_ids=select(Employee.__table__.c.id).where(predicate)
    branches=select(Branch.__table__.c.id).where(Branch.__table__.c.company_id==company)
    job_predicate=or_(Job.branch_id.in_(branches),(Job.branch_id.is_(None)) & (company==1))
    jobs=select(Job.__table__.c.id).where(job_predicate)
    criteria=[with_loader_criteria(Employee,predicate,include_aliases=True),with_loader_criteria(Branch,Branch.company_id==company,include_aliases=True),with_loader_criteria(Company,Company.id==company,include_aliases=True),with_loader_criteria(Department,Department.branch_id.in_(branches),include_aliases=True),with_loader_criteria(Job,job_predicate,include_aliases=True),with_loader_criteria(Candidate,Candidate.job_id.in_(jobs),include_aliases=True)]
    for mapper in Base.registry.mappers:
        model=mapper.class_
        if model is not Employee and "employee_id" in mapper.columns and model.__table__.c.employee_id.foreign_keys and any(f.column.table.name=="employees" for f in model.__table__.c.employee_id.foreign_keys):
            criteria.append(with_loader_criteria(model,model.employee_id.in_(employee_ids),include_aliases=True))
    def restrict(execution):
        if execution.is_select:execution.statement=execution.statement.options(*criteria)
    event.listen(db,"do_orm_execute",restrict)
    try:yield
    finally:event.remove(db,"do_orm_execute",restrict)
