"""Create isolated action-limited actors for the local 1582 UI acceptance suite."""
import os,json
os.environ.setdefault('PRESERVED_QA_UPLOADS','C:/Users/SAISAT~1/AppData/Local/Temp/suite-navigation-qa-t5op8r7a/uploads')
from serve_verified_1582 import SessionLocal,User,Role,Permission,CommonPerson,AccessMembership,AccessPolicy,Branch,BranchGrant,BranchPolicy,get_password_hash,MODULE_PERMISSIONS,PMSProject,PMSProjectMember,PMSWorkspace,PMSWorkspaceMember
from app.models.employee import Employee
from datetime import date
from test_identity_utils import own_workflow_records
profiles={'operator':['view','create','edit','delete','approve','configure','assign','export','manage_users'],'user_manager':['view','configure','manage_users'],'user_manager_only':['view','manage_users'],'delegator':['view','approve','assign'],'creator':['view','create'],'editor':['view','edit'],'approver':['view','approve'],'configurer':['view','configure'],'deleter':['view','delete'],'assigner':['view','assign']}
with SessionLocal() as db:
    admin=db.query(User).filter_by(email='admin@suiteqa.example.com').one()
    # Native PMS permissions are declared in init_db rather than RequirePermission routes.
    # The preserved QA copy may predate that seed; expose the real permission catalogue.
    for permission_name in ('pms_view','pms_manage_projects','pms_manage_tasks','pms_time_manage','pms_client_portal','pms_admin'):
        if not db.query(Permission).filter_by(name=permission_name).first():db.add(Permission(name=permission_name,module='project_management',description='Native PMS acceptance permission'))
    db.flush()
    permissions=db.query(Permission).all();names=sorted({p.name for p in permissions})
    branch=db.query(Branch).filter_by(company_id=1).first()
    for name,actions in profiles.items():
        email=f'conditional-{name}@suiteqa.example.com'
        actor=db.query(User).filter_by(email=email).first()
        if not actor:
            role=Role(name=f'conditional_{name}',description='Isolated UI permission acceptance role',permissions=permissions)
            actor=User(email=email,hashed_password=get_password_hash('ConditionalQA@12345'),role=role,is_active=True,is_superuser=False,person=CommonPerson(organization_id=1,primary_email=email,display_name=f'Conditional {name}'))
            db.add(actor);db.flush();db.add(AccessMembership(user_id=actor.id,company_id=1,active=True,is_admin=False));db.add(BranchGrant(user_id=actor.id,company_id=1,branch_id=branch.id,can_write=True));db.add(BranchPolicy(user_id=actor.id,company_id=1,all_branches=True,use_home_branch=False))
        grants={module:{'enabled':True,'role':'editor','scope':'organization','permissions':names,'actions':actions} for module in {*MODULE_PERMISSIONS,'project_management'}}
        policy=db.query(AccessPolicy).filter_by(user_id=actor.id,company_id=1).first()
        if policy:policy.grants=grants
        else:db.add(AccessPolicy(user_id=actor.id,company_id=1,status='active',grants=grants))
        if not db.query(Employee).filter_by(user_id=actor.id).first():
            employee=Employee(employee_id=f'COND-{actor.id}',first_name='Conditional',last_name=name,work_email=email,date_of_joining=date.today(),user_id=actor.id,status='Active');db.add(employee);own_workflow_records(db,employee,company_id=1)
        for workspace in db.query(PMSWorkspace).filter_by(organization_id=1):
            if not db.query(PMSWorkspaceMember).filter_by(workspace_id=workspace.id,user_id=actor.id).first():db.add(PMSWorkspaceMember(workspace_id=workspace.id,user_id=actor.id,role='Admin'))
        for project in db.query(PMSProject).filter_by(organization_id=1):
            if not db.query(PMSProjectMember).filter_by(project_id=project.id,user_id=actor.id).first():db.add(PMSProjectMember(project_id=project.id,user_id=actor.id,role='Project Manager'))
        db.flush()  # Stamp newly added memberships too; this session disables autoflush.
        own_workflow_records(db,actor,*db.query(PMSWorkspaceMember).filter_by(user_id=actor.id).all(),*db.query(PMSProjectMember).filter_by(user_id=actor.id).all(),company_id=1)
    db.commit()
print(json.dumps({'profiles':list(profiles),'organization':1}))
