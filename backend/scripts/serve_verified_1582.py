"""Serve current source on 1582 using a preserved copy of its original QA database."""
import os,sys,json,secrets,asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from contextvars import ContextVar
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
local=ROOT/'.local';local.mkdir(exist_ok=True)
keyfile=local/'crud121-1582-keys.json'
if not keyfile.exists():keyfile.write_text(json.dumps({'SECRET_KEY':secrets.token_urlsafe(48),'REFRESH_SECRET_KEY':secrets.token_urlsafe(48)}),encoding='utf-8')
os.environ.update(ENVIRONMENT='test',DEBUG='false',BACKEND_PUBLIC_URL='http://127.0.0.1:1582',FRONTEND_PUBLIC_URL='http://127.0.0.1:1582',DATABASE_URL='sqlite:///'+str(local/'crud121-1582.sqlite'),INSTALLED_APPS='hrms,crm,project_management,srm,fam,power_apps',STORAGE_BACKEND='local',UPLOAD_DIR=os.environ['PRESERVED_QA_UPLOADS'],SECRET_KEY_PREVIOUS='',REFRESH_SECRET_KEY_PREVIOUS='',OPENAI_API_KEY='',ANTHROPIC_API_KEY='',GEMINI_API_KEY='',MAIL_USERNAME='',MAIL_PASSWORD='',MAIL_SERVER='',FIREBASE_PROJECT_ID='',FIREBASE_WEB_CONFIG='{}',CRM_WHATSAPP_PROVIDER='mock',CRM_WHATSAPP_ACCESS_TOKEN='',CRM_WHATSAPP_PHONE_NUMBER_ID='',CRM_WHATSAPP_BUSINESS_ACCOUNT_ID='',CRM_WHATSAPP_APP_ID='',CRM_WHATSAPP_EMBEDDED_CONFIG_ID='',BUSINESSSUITE_BACKUP_SCHEDULER='false',SEED_DEMO_DATA='false',SECURITY_RATE_LIMIT_ENABLED='false',DB_POOL_SIZE='100',DB_MAX_OVERFLOW='100')
os.environ.update(json.loads(keyfile.read_text(encoding='utf-8')))
from app.main import app
from app.db.base import Base
from app.db.session import engine,SessionLocal
from app.access.catalog import MODULE_PERMISSIONS
from app.models.user import User,Role,Permission
from app.common.models import CommonPerson
from app.access.models import AccessPolicy,AccessMembership
from app.models.company import Branch
from app.branches.models import BranchGrant,BranchPolicy
from app.apps.business_os.models import BOSEnabledModule
from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember,PMSProject,PMSProjectMember
from app.core.security import get_password_hash,pwd_context
pwd_context.update(bcrypt__rounds=4)
from sqlalchemy import event
@event.listens_for(engine, "connect")
def sqlite_settings(connection, _):
    cursor=connection.cursor();cursor.execute("PRAGMA journal_mode=WAL");cursor.execute("PRAGMA busy_timeout=5000");cursor.close()
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker
audit_engine=create_engine(os.environ["DATABASE_URL"],poolclass=NullPool,connect_args={"check_same_thread":False,"timeout":5})
event.listen(audit_engine,"connect",sqlite_settings)
app.state.audit_session_factory=sessionmaker(bind=audit_engine)
Base.metadata.create_all(engine)
with SessionLocal() as db:

    all_names=set().union(*MODULE_PERMISSIONS.values())
    all_names.update({'portal_manage','tenant_admin','crm_view','crm_manage','analytics_view','analytics_manage','analytics_export','analytics_report_builder','analytics_schedule','analytics_financial_view','analytics_profitability_view','customization_view','customization_manage','power_apps_view','power_apps_create','power_apps_edit','power_apps_delete'})
    for suffix,company,readonly in [('reader',1,True),('outsider',2,False),('reviewer',1,False)]:
        if db.query(User).filter_by(email=f'{suffix}@crudqa.example.com').first():continue
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
    # PMS uses native workspace membership rather than RequirePermission routes,
    # so its grant must be explicit in the acceptance policy.
    reader=db.query(User).filter_by(email='reader@crudqa.example.com').one()
    reader_policy=db.query(AccessPolicy).filter_by(user_id=reader.id,company_id=1).one()
    if 'project_management' not in reader_policy.grants:
        reader_policy.grants={**reader_policy.grants,'project_management':{'enabled':True,'role':'viewer','scope':'organization','permissions':[],'actions':['view','export']}}
    from datetime import date
    from app.models.employee import Employee
    from test_identity_utils import own_workflow_records, complete_workflow_company
    for company in [1,2]:complete_workflow_company(db,company)
    own_workflow_records(db,reader,*db.query(PMSWorkspaceMember).filter_by(user_id=reader.id).all(),*db.query(PMSProjectMember).filter_by(user_id=reader.id).all(),company_id=1)
    for email in ['admin@suiteqa.example.com','reader@crudqa.example.com','outsider@crudqa.example.com']:
        actor=db.query(User).filter_by(email=email).one()
        company=2 if email.startswith('outsider') else 1
        if db.query(Employee).filter_by(user_id=actor.id).first():continue
        employee=Employee(employee_id=f"CRUD-{actor.id}",first_name='Acceptance',last_name=email.split('@')[0],work_email=email,date_of_joining=date.today(),user_id=actor.id,status='Active')
        db.add(employee);own_workflow_records(db,employee,company_id=company)
    from app.models.attendance import Shift
    from datetime import time
    shift=db.query(Shift).filter_by(code='UI-ACCEPTANCE').first()
    if not shift:
        shift=Shift(name='UI acceptance work shift',code='UI-ACCEPTANCE',start_time=time(9),end_time=time(17),working_hours=8,is_active=True)
        db.add(shift);own_workflow_records(db,shift,company_id=1)
    from tests.srm_test_utils import seed_invoice_parties
    seed_invoice_parties(db)
    from app.apps.power_apps.models import PowerEnvironment
    for company in [1,2]:
        if not db.query(PowerEnvironment).filter_by(organization_id=company,key='development').first():db.add(PowerEnvironment(organization_id=company,key='development',enabled=True))
    db.commit()

def approval_worker_once():
    from app.apps.power_apps.runtime import claim,process,now,tick
    from app.apps.power_apps.runtime_models import AutomationJob,AutomationWorker
    from app.apps.power_apps.approvals.models import RequestState
    with SessionLocal() as db:
        approval_runs={row[0] for row in db.query(RequestState.run_id).all()}
        # This QA worker never starts arbitrary workflows, connector polling or delivery.
        if not approval_runs:return
        tick(db,run_ids=approval_runs)
        worker='acceptance-approval-worker'
        if not db.get(AutomationWorker,worker):
            db.add(AutomationWorker(id=worker,heartbeat_at=now(),processed=0));db.commit()
        work=claim(db,worker,run_ids=approval_runs)
        if work:process(db,*work)
@asynccontextmanager
async def lifespan(application):
    async def loop():
        while True:
            try:
                async with lock:await asyncio.to_thread(approval_worker_once)
            except Exception as exc:print('Acceptance approval worker',type(exc).__name__,str(getattr(exc,'orig',''))[:150],flush=True)
            await asyncio.sleep(.5)
    task=asyncio.create_task(loop())
    try:yield
    finally:
        task.cancel()
        from contextlib import suppress
        with suppress(asyncio.CancelledError):await task
app.router.lifespan_context=lifespan
# Serialize SQLite mutations/reads while allowing long polls to release the queue.
lock=asyncio.Lock();nested=ContextVar('verified_nested',default=False)
@app.middleware('http')
async def sqlite_request_queue(request,call_next):
    if not request.url.path.startswith('/api/') or request.url.path.endswith('/realtime/events') or nested.get():
        return await call_next(request)
    async with lock:
        token=nested.set(True)
        try:return await call_next(request)
        finally:nested.reset(token)
from sqlalchemy.exc import IntegrityError
from fastapi.responses import JSONResponse
@app.exception_handler(IntegrityError)
async def acceptance_constraint(request,exc):
    print("Acceptance constraint",request.url.path,str(exc.orig),flush=True)
    return JSONResponse({"detail":"This record conflicts with an existing record or referenced value. Refresh the form and check its identifiers."},status_code=409)
from fastapi import HTTPException
from fastapi.responses import FileResponse
frontend=(ROOT/'.local/workspace-experience-review-build').resolve()
from fastapi import Depends
from app.core.deps import get_current_user,get_db
from sqlalchemy.orm import Session
@app.post('/api/v1/ai-agents/_acceptance/fixtures',include_in_schema=False)
def acceptance_ai_fixture(project_id:int,db:Session=Depends(get_db),actor:User=Depends(get_current_user)):
    if not actor.is_superuser:raise HTTPException(403,'Acceptance fixture requires administrator')
    project=db.get(PMSProject,project_id)
    if not project or not project.name.startswith('UI reference'):raise HTTPException(422,'Use an acceptance project')
    from app.ai_agents.models import AiAgent,AiConversation,AiMessage,AiMessageFeedback,AiActionApproval
    from app.ai_agents.security import seal,company
    agent=db.query(AiAgent).filter_by(code='pms_task_planning').first()
    if not agent:agent=db.query(AiAgent).filter_by(module='PMS').first()
    if not agent:raise HTTPException(409,'Load the agent catalogue first')
    tenant=company(actor)
    conversation=AiConversation(user_id=actor.id,agent_id=agent.id,module='PMS',title='Acceptance conversation (provider not called)',organization_id=tenant)
    db.add(conversation);db.flush();conversation.security_context=seal(db,actor)
    message=AiMessage(conversation_id=conversation.id,role='assistant',content='Acceptance response fixture; no provider was called.')
    db.add(message);db.flush()
    db.add(AiMessageFeedback(message_id=message.id,conversation_id=conversation.id,user_id=actor.id,agent_id=agent.id,rating='thumbs_up',feedback_type='helpful',feedback_text='Synthetic acceptance feedback'))
    rows=[]
    for title in ['UI reference approved task','UI reference rejected task']:
        payload={'project_id':project_id,'title':title,'description':'Synthetic acceptance action; no external communication'}
        approval=AiActionApproval(organization_id=tenant,conversation_id=conversation.id,agent_id=agent.id,user_id=actor.id,module='PMS',action_type='CREATE_PMS_TASK',proposed_action_json=payload,status='pending',security_context=seal(db,actor,payload=payload))
        db.add(approval);db.flush();rows.append(approval.id)
    db.commit();return {'approvals':rows,'conversation_id':conversation.id,'message_id':message.id,'project_id':project_id}
@app.get('/{path:path}',include_in_schema=False)
def spa(path:str):
    if path.startswith('api/'):raise HTTPException(404,'API route not found')
    candidate=(frontend/path).resolve()
    if not candidate.is_relative_to(frontend):raise HTTPException(404)
    return FileResponse(candidate if candidate.is_file() else frontend/'index.html')
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('VERIFIED_PORT','1582')),log_level='warning')
