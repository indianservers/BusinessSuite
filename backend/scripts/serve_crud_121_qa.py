"""Disposable loopback CRUD/RBAC acceptance fixture. No production database or delivery."""
import os
import serve_project_portfolio_qa as fixture
from app.access.catalog import MODULE_PERMISSIONS
from app.models.user import User,Role,Permission
from app.common.models import CommonPerson
from app.access.models import AccessPolicy,AccessMembership
from app.models.company import Branch
from app.branches.models import BranchGrant,BranchPolicy
from app.apps.business_os.models import BOSEnabledModule
from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember,PMSProject,PMSProjectMember
from app.core.security import get_password_hash

with fixture.qa.SessionLocal() as db:
    all_names=set().union(*MODULE_PERMISSIONS.values())
    all_names.update({'portal_manage','tenant_admin','crm_view','crm_manage','analytics_view','analytics_manage','analytics_export','analytics_report_builder','analytics_schedule','analytics_financial_view','analytics_profitability_view','customization_view','customization_manage','power_apps_view','power_apps_create','power_apps_edit','power_apps_delete'})
    for suffix,company,readonly in [('reader',1,True),('outsider',2,False)]:
        names={n for n in all_names if n.endswith(('_view','_read')) or n=='report_view'} if readonly else all_names
        role=Role(name=f'crud_{suffix}',description='Synthetic 121-page acceptance role')
        db.add(role);db.flush()
        for name in names:
            permission=db.query(Permission).filter_by(name=name).first()
            if not permission:
                permission=Permission(name=name,module='acceptance');db.add(permission);db.flush()
            role.permissions.append(permission)
        email=f'{suffix}@crudqa.example.com'
        actor=User(email=email,hashed_password=get_password_hash('CrudQA@12345'),role=role,is_active=True,is_superuser=False,person=CommonPerson(organization_id=company,primary_email=email,display_name=f'CRUD {suffix}'))
        db.add(actor);db.flush()
        db.add(AccessMembership(user_id=actor.id,company_id=company,active=True,is_admin=False))
        grants={module:{'enabled':True,'role':'viewer' if readonly else 'admin','scope':'organization','permissions':sorted(names),'actions':['view','export'] if readonly else ['view','create','edit','delete','approve','configure','export']} for module in MODULE_PERMISSIONS}
        db.add(AccessPolicy(user_id=actor.id,company_id=company,status='active',grants=grants))
        branch=db.query(Branch).filter_by(company_id=company).first()
        db.add(BranchGrant(user_id=actor.id,company_id=company,branch_id=branch.id,can_write=not readonly))
        db.add(BranchPolicy(user_id=actor.id,company_id=company,all_branches=True,use_home_branch=False))
        if readonly:
            for workspace in db.query(PMSWorkspace).filter_by(organization_id=1):db.add(PMSWorkspaceMember(workspace_id=workspace.id,user_id=actor.id,role='Guest'))
            for project in db.query(PMSProject).filter_by(organization_id=1):db.add(PMSProjectMember(project_id=project.id,user_id=actor.id,role='Viewer'))
    from datetime import date
    from app.models.employee import Employee
    from test_identity_utils import own_workflow_records, complete_workflow_company
    for company in [1,2]:complete_workflow_company(db,company)
    for email in ['admin@suiteqa.example.com','reader@crudqa.example.com','outsider@crudqa.example.com']:
        actor=db.query(User).filter_by(email=email).one()
        company=2 if email.startswith('outsider') else 1
        employee=Employee(employee_id=f"CRUD-{actor.id}",first_name='Acceptance',last_name=email.split('@')[0],work_email=email,date_of_joining=date.today(),user_id=actor.id,status='Active')
        db.add(employee);own_workflow_records(db,employee,company_id=company)
    from app.models.leave import LeaveType, LeaveBalance
    leave_type=LeaveType(name='Acceptance annual leave',code='QA-ANNUAL',days_allowed=20,accrual_frequency='annual',is_active=True)
    db.add(leave_type);own_workflow_records(db,leave_type,company_id=1);db.flush()
    for employee in db.query(Employee).filter(Employee.employee_id.like('CRUD-%')).all():
        db.add(LeaveBalance(employee_id=employee.id,leave_type_id=leave_type.id,year=date.today().year,allocated=20,used=0,pending=0))
    from tests.srm_test_utils import seed_invoice_parties
    seed_invoice_parties(db)
    from app.apps.power_apps.models import PowerEnvironment
    for company in [1,2]:db.add(PowerEnvironment(organization_id=company,key='development',enabled=True))
    for enabled in db.query(BOSEnabledModule).all():enabled.enabled=True
    db.commit()

if __name__=='__main__':
    import uvicorn
    try:uvicorn.run(fixture.qa.app,host='127.0.0.1',port=int(os.environ.get('CRUD_QA_PORT','1592')),log_level='warning')
    finally:fixture.qa.engine.dispose();fixture.qa.temporary.cleanup()
