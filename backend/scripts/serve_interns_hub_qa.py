"""Loopback-only QA server with disposable SQLite data. Never uses the HRMS DB."""
import os
import sys
import secrets
from pathlib import Path
from datetime import timedelta, datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['ENVIRONMENT'] = 'test'
os.environ['SECRET_KEY']=secrets.token_urlsafe(48)
os.environ['REFRESH_SECRET_KEY']=secrets.token_urlsafe(48)
os.environ['SECRET_KEY_PREVIOUS']=''
os.environ['REFRESH_SECRET_KEY_PREVIOUS']=''
os.environ['STORAGE_BACKEND']='local'
for credential in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','GEMINI_API_KEY','S3_ACCESS_KEY_ID','S3_SECRET_ACCESS_KEY','BLOB_READ_WRITE_TOKEN','RECAPTCHA_SECRET_KEY','FORMS_TURNSTILE_SECRET_KEY'):
    os.environ[credential]=''
from tempfile import TemporaryDirectory
qa_directory = TemporaryDirectory(prefix='intern-hub-qa-')
os.environ['UPLOAD_DIR'] = str(Path(qa_directory.name)/'uploads')
os.environ['DATABASE_URL']='sqlite:///'+str(Path(qa_directory.name)/'qa.db')
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tempfile import TemporaryDirectory
from app.db.base import Base
from app.core.deps import get_db
from app.core.security import get_password_hash, pwd_context
from app.models.user import User, Role
from app.models.company import Company, Branch, Department, Designation
from app.models.employee import Employee, EmployeeEducation, EmployeeSkill
from app.models.attendance import Attendance
from app.apps.interns_hub.models import InternTask, InternSubmission, InternReport, InternCourse, InternCertificate
from app.apps.interns_hub.router import router, today
from app.api.v1.auth import router as auth_router
from app.api.v1.company import router as company_router
from app.api.v1.employees import router as employees_router
from app.apps.project_management.api.router import router as pms_router
from app.apps.project_management.models import PMSProject
from app.apps.interns_hub.management_models import InternBatch, InternBatchMembership
from app.apps.interns_hub.legacy_import import import_history

engine = create_engine('sqlite:///' + str(Path(qa_directory.name) / 'qa.db'), connect_args={'check_same_thread': False, 'timeout': 30})
with engine.connect() as connection:
    connection.exec_driver_sql('PRAGMA journal_mode=WAL')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
pwd_context.update(bcrypt__rounds=4)
with Session() as db:
    role = Role(name='employee')
    admin_role = Role(name='super_admin')
    db.add_all([role, admin_role])
    db.flush()
    user = User(email='intern@example.com', hashed_password=get_password_hash('InternHub@123'), role_id=role.id, is_active=True)
    admin_user = User(email='admin@example.com', hashed_password=get_password_hash('AdminHub@123'), role_id=admin_role.id, is_active=True, is_superuser=True)
    db.add_all([user, admin_user])
    company = Company(name='QA Company')
    db.add(company)
    db.flush()
    branch = Branch(name='Head Office', company_id=company.id)
    db.add(branch)
    db.flush()
    dept = Department(name='Marketing', branch_id=branch.id)
    db.add(dept)
    db.flush()
    for name in ["Software Testing","Web Development","AI / ML","Mobile Development","Data Analytics"]:
        department=Department(name=name,branch_id=branch.id);db.add(department);db.flush();db.add(Designation(name=name+" Intern",department_id=department.id));db.add(Designation(name=name+" Employee",department_id=department.id))
    designation = Designation(name='Marketing Intern', department_id=dept.id)
    manager = Employee(employee_id='QA-MGR', first_name='Aarav', last_name='Mehta', date_of_joining=today())
    db.add_all([designation, manager])
    db.flush()
    employee = Employee(employee_id='QA-INT-001', user_id=user.id, first_name='Riya', last_name='Sharma', employment_type='Intern', date_of_joining=today()-timedelta(days=60), department_id=dept.id, designation_id=designation.id, reporting_manager_id=manager.id, branch_id=branch.id, personal_email=user.email, phone_number='+91 98765 43210', present_city='New Delhi', bio='Passionate about learning and creating real impact.', interests='Marketing, design and research')
    db.add(employee)
    db.flush()
    db.add(EmployeeEducation(employee_id=employee.id, degree='B.Tech (Computer Science)', institution='Delhi Technological University', board_university='DTU', percentage_cgpa=8.5, pass_year=2027))
    db.add(EmployeeSkill(employee_id=employee.id, skill_name='Digital Marketing'))
    titles = [('Create a social media post (Design + Caption)', 'Marketing', 'High', 10), ('Research on competitor analysis', 'Research', 'Medium', 15), ("Write a blog on Benefits of Internship", 'Content', 'Medium', 20), ('Prepare a presentation on market trends', 'Presentation', 'High', 15), ('Summarize a training video', 'Learning', 'Low', 10), ('Participate in community discussion', 'Community', 'Low', 5), ('Analyze social media performance', 'Analytics', 'Medium', 15), ('Final project submission', 'Project', 'High', 25)]
    for i, (title, category, priority, points) in enumerate(titles):
        task = InternTask(employee_id=employee.id,title=title,description='Design a creative post for our upcoming campaign.',category=category,priority=priority,points=points,due_date=today()+timedelta(days=i),status='Completed' if i in [1,2,5] else 'In Progress' if i in [0,4] else 'Pending',objectives='Create clear, engaging work that follows the campaign brief.',instructions='1. Read the brief.\n2. Follow brand guidelines.\n3. Prepare original work.\n4. Include supporting resources.',deliverables='Completed design and a short explanation.')
        db.add(task)
        db.flush()
        if task.status == 'Completed':
            db.add(InternSubmission(task_id=task.id,employee_id=employee.id,notes='Completed campaign work.',links=[],files=[],status='Approved',score=[85,78,92][i%3],feedback='Great creativity and clear communication. Keep maintaining this quality.',strengths='Clear design and original thinking.',improvements='Try adding more insights next time.',reviewed_at=datetime.now(timezone.utc)))
    for i in range(5):
        day = today()-timedelta(days=i)
        db.add(InternReport(employee_id=employee.id,report_date=day,work='Campaign planning and creative work',learning='Brand communication and research',status='Submitted',mood='Great',minutes=380))
        db.add(Attendance(employee_id=employee.id,attendance_date=day,check_in=datetime.now(timezone.utc)-timedelta(hours=3),status='Present',source='Interns Hub'))
    for title in ['Communication Skills','Excel Basics','Digital Marketing','Web Development','Corporate Etiquette','Report Writing']:
        db.add(InternCourse(title=title,description='Build practical skills and apply them in your internship.',lessons=[{'title':'Getting started','url':'https://example.com/lesson'}],questions=[{'prompt':'What makes a strong submission?','options':['Original work with a clear explanation','Copied work without notes'],'answer':0}]))
    db.add(InternCertificate(employee_id=employee.id,title='Communication Skills',certificate_type='Module Completion',issued_by=admin_user.id))
    db.commit()
    project=PMSProject(organization_id=1,name='Internship Delivery',project_key='INT',manager_user_id=admin_user.id,department_id=dept.id,branch_id=branch.id)
    db.add(project);db.commit()
    import_history(db,admin_user,project.id,admin_user.id)
    batch=InternBatch(organization_id=1,name='Digital Marketing Internship',code='DM-2026',department_id=dept.id,manager_user_id=admin_user.id,mentor_user_id=admin_user.id,project_id=project.id,program='Internship',start_date=today()-timedelta(days=60),end_date=today()+timedelta(days=30),capacity=400,status='Active',policy={'weights':{'quality':40,'timeliness':20,'reports':15,'completion':15,'communication':10},'completion':{'minimum_days':0,'minimum_tasks':1,'minimum_reports_percent':0}})
    db.add(batch);db.flush()
    db.add(InternBatchMembership(batch_id=batch.id,employee_id=employee.id,assigned_by=admin_user.id))
    project2=PMSProject(organization_id=1,name='Frontend Delivery',project_key='WEB',manager_user_id=admin_user.id,department_id=dept.id,branch_id=branch.id)
    db.add(project2);db.flush()
    batch2=InternBatch(organization_id=1,name='Frontend QA Cohort',code='WEB-QA',department_id=dept.id,manager_user_id=admin_user.id,mentor_user_id=admin_user.id,project_id=project2.id,program='Frontend',start_date=today()-timedelta(days=60),end_date=today()+timedelta(days=30),capacity=100,status='Active',policy={'weights':{'quality':40,'timeliness':20,'reports':15,'completion':15,'communication':10},'completion':{'minimum_days':0,'minimum_tasks':1,'minimum_reports_percent':0}})
    db.add(batch2);db.flush();db.add(InternBatchMembership(batch_id=batch2.id,employee_id=employee.id,assigned_by=admin_user.id))
    manager.user_id=admin_user.id;manager.department_id=dept.id;manager.branch_id=branch.id
    db.commit()

app = FastAPI()
app.include_router(auth_router, prefix='/api/v1')
app.include_router(company_router,prefix='/api/v1')
app.include_router(employees_router,prefix='/api/v1')
app.include_router(pms_router, prefix='/api/v1')
app.include_router(router, prefix='/api/v1')
def qa_db():
    with Session() as db:
        yield db
app.dependency_overrides[get_db] = qa_db
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=1548)
