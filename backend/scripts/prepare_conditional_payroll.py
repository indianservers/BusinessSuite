import os,json,time
from datetime import date,datetime,timezone
os.environ.setdefault('PRESERVED_QA_UPLOADS','C:/Users/SAISAT~1/AppData/Local/Temp/suite-navigation-qa-t5op8r7a/uploads')
from serve_verified_1582 import SessionLocal,ROOT
from app.models.employee import Employee
from app.models.company import Department,Branch
from app.models.payroll import PayrollPayGroup,PayrollPeriod,PayrollRun,PayrollRecord,PayrollAttendanceInput,EmployeeSalary
from test_identity_utils import own_workflow_records
with SessionLocal() as db:
 tag=str(int(time.time()))
 branch=db.query(Branch).filter_by(company_id=1).first()
 department=Department(name='Conditional payroll '+tag,branch_id=branch.id);db.add(department);own_workflow_records(db,department,company_id=1)
 group=PayrollPayGroup(name='Conditional payroll '+tag,code='CP'+tag,branch_id=branch.id);db.add(group);own_workflow_records(db,group,company_id=1)
 employee=Employee(employee_id='PAY-COND-'+tag,first_name='Conditional',last_name='Payroll',date_of_joining=date(2026,1,1),branch_id=branch.id,department_id=department.id,status='Active',account_number='987654321001',ifsc_code='HDFC0001234',pan_number='ABCDE1234F');db.add(employee);own_workflow_records(db,employee,company_id=1)
 salary=EmployeeSalary(employee_id=employee.id,ctc=12000,basic=1000,effective_from=date(2026,1,1),is_active=True);db.add(salary);own_workflow_records(db,salary,company_id=1)
 period=PayrollPeriod(pay_group_id=group.id,month=2,year=2027,financial_year='2026-27',period_start=date(2027,2,1),period_end=date(2027,2,28),payroll_date=date(2027,2,28),status='Locked',locked_at=datetime.now(timezone.utc));db.add(period);own_workflow_records(db,period,company_id=1)
 run=PayrollRun(company_id=1,branch_id=branch.id,department_id=department.id,pay_group_id=group.id,month=2,year=2027,pay_period_start=date(2027,2,1),pay_period_end=date(2027,2,28),status='calculated',total_gross=1000,total_net=1000,total_deductions=0);db.add(run);own_workflow_records(db,run,company_id=1)
 record=PayrollRecord(payroll_run_id=run.id,employee_id=employee.id,gross_salary=1000,net_salary=1000,total_deductions=0,salary_currency='INR');db.add(record);own_workflow_records(db,record,company_id=1)
 attendance=PayrollAttendanceInput(period_id=period.id,employee_id=employee.id,working_days=20,payable_days=20,present_days=20,source_status='Locked',locked_at=datetime.now(timezone.utc));db.add(attendance);own_workflow_records(db,attendance,company_id=1)
 db.commit();result={'run':run.id,'employee':employee.id,'period':period.id,'group':group.id};(ROOT/'outputs/conditional-121/payroll-fixture.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
