"""Provision synthetic local payroll inputs; performs no payout or delivery."""
from serve_verified_1582 import SessionLocal
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary,EmployeeStatutoryProfile,PayrollPayGroup,PayrollPeriod,SalaryComponent
from app.branches.models import BranchOwnership
from sqlalchemy import cast,String
from tests.payroll_test_utils import ensure_payroll_ready
from test_identity_utils import own_workflow_records
with SessionLocal() as db:
    employees=db.query(Employee).join(BranchOwnership,(BranchOwnership.resource_table=='employees') & (BranchOwnership.resource_key==cast(Employee.id,String))).filter(BranchOwnership.company_id==1,Employee.deleted_at.is_(None)).all()
    period=ensure_payroll_ready(db,11,2026,employees=employees)
    ids=[e.id for e in employees]
    rows=[period,db.get(PayrollPayGroup,period.pay_group_id)]
    rows+=db.query(EmployeeSalary).filter(EmployeeSalary.employee_id.in_(ids)).all()
    rows+=db.query(EmployeeStatutoryProfile).filter(EmployeeStatutoryProfile.employee_id.in_(ids)).all()
    component=db.query(SalaryComponent).filter_by(code='UI-ACCEPTANCE').first()
    if not component:
        component=SalaryComponent(name='UI acceptance allowance',code='UI-ACCEPTANCE',component_type='Earning',amount=0,is_active=True);db.add(component)
    own_workflow_records(db,*rows,component,company_id=1);db.commit()
    print({'synthetic_employees':len(ids),'period_id':period.id})
