"""Local-only real API + PostgreSQL acceptance server with blocked live accounting I/O."""
from pathlib import Path
import os,sys,json,secrets,argparse
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
os.chdir(ROOT/"backend")

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--port",type=int,default=1542);parser.add_argument("--frontend-port",type=int,default=5196);args=parser.parse_args()
    private=ROOT/".local"/"accounting-acceptance.env.json"
    db_config=json.loads(private.read_text(encoding="utf-8"))
    from sqlalchemy.engine import make_url
    url=make_url(db_config['database_url'])
    if url.host not in {"127.0.0.1","localhost"} or not url.database.startswith("business_suite_accounting_local_") or not url.database.endswith("_test"):
        raise RuntimeError("Dedicated local accounting QA database required")
    os.environ.update(DATABASE_URL=db_config['database_url'],ENVIRONMENT="test",SERVERLESS="false",DEBUG="false",TENANT_DATABASES_ENABLED="false",PLATFORM_DATABASE_URL="",TENANT_REGISTRY_URL="",TENANT_PROVISIONING_URL="",DATABASE_AUTO_MIGRATE="false",ACCOUNTING_SYNC_WORKER_ENABLED="false",SEED_DEMO_DATA="false",EMAIL_NOTIFICATIONS_ENABLED="false",MAIL_SERVER="",MAIL_USERNAME="",MAIL_PASSWORD="",SES_SMTP_USERNAME="",SES_SMTP_PASSWORD="",INTERN_HUB_SES_ENABLED="false",OPENAI_API_KEY="",ANTHROPIC_API_KEY="",FIREBASE_PROJECT_ID="",RECAPTCHA_SECRET_KEY="",CRON_SECRET=secrets.token_urlsafe(40),SECRET_KEY=secrets.token_urlsafe(48),REFRESH_SECRET_KEY=secrets.token_urlsafe(48),SECRET_KEY_PREVIOUS="",REFRESH_SECRET_KEY_PREVIOUS="")
    os.environ['BACKEND_CORS_ORIGINS']=json.dumps([f"http://127.0.0.1:{args.frontend_port}",f"http://localhost:{args.frontend_port}"])
    from app.main import app
    from app.db.session import SessionLocal
    from app.models.user import User,Role,Permission
    from app.models.company import Company,Branch
    from app.apps.crm.models import CRMCompany
    from app.shared.import_models import ImportConnection
    from app.shared.accounting_sync.models import SyncConnection,SyncRun
    from app.shared.import_connectors import seal
    from app.shared.accounting_sync import providers,service,jobs
    from app.core.security import get_password_hash
    from app.db.init_db import SYSTEM_PERMISSIONS
    from test_identity_utils import attach_test_identity,attach_workflow_branch,own_workflow_records
    from tests.rich_text_test_utils import workflow_seed_scope
    from datetime import datetime,timezone,timedelta
    from zoneinfo import ZoneInfo
    from uuid import uuid4
    password=secrets.token_urlsafe(18)+'!A7';email='accounting-local-qa@example.com'
    today=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
    bridge=secrets.token_urlsafe(32);control=secrets.token_urlsafe(32)
    ids={};state={'settled':False,'fail_zoho':False,'provider_requests':0}
    with SessionLocal() as db,workflow_seed_scope(db):
        for name,description,module in SYSTEM_PERMISSIONS:
            if not db.query(Permission).filter_by(name=name).first():db.add(Permission(name=name,description=description,module=module))
        db.flush()
        existing=db.query(User).filter_by(email=email).first()
        if existing:
            user=existing;user.hashed_password=get_password_hash(password)
            company=db.get(Company,1)
            branch=db.query(Branch).filter_by(company_id=1,name='Mock Accounting QA Branch').one()
            customer=db.query(CRMCompany).filter_by(organization_id=1,name='Mock Acme Trading').one()
            other=db.query(CRMCompany).filter_by(organization_id=1,name='Mock Unlinked Customer').one()
            for connection in db.query(SyncConnection).filter_by(organization_id=1,created_by=user.id):
                ids[connection.provider]=connection.id;connection.enabled=True
                connection.auto_sync=connection.provider!='tally';connection.active_token=None;connection.lease_until=None
                connection.next_sync_at=service.now() if connection.auto_sync else None
                if connection.provider=='tally':connection.bridge_secret=seal({'token':bridge})
        else:
            role=Role(name='accounting_qa_admin',description='Local mock accounting verification',is_system=True)
            role.permissions=list(db.query(Permission));db.add(role);db.flush()
            user=User(email=email,hashed_password=get_password_hash(password),role_id=role.id,is_active=True,is_superuser=True)
            db.add(user);db.flush();attach_test_identity(db,user);branch=attach_workflow_branch(db,user)
            company=db.get(Company,1);company.name='LOCAL MOCK Accounting QA';company.default_timezone='Asia/Kolkata'
            branch.name='Mock Accounting QA Branch'
            customer=CRMCompany(organization_id=1,name='Mock Acme Trading',email='acme@example.com',created_by_user_id=user.id)
            other=CRMCompany(organization_id=1,name='Mock Unlinked Customer',created_by_user_id=user.id)
            db.add_all([customer,other]);db.flush();own_workflow_records(db,customer,other)
            for provider,account in [('zoho','99001'),('quickbooks','99002'),('tally','mock-company-guid')]:
                source=None
                if provider!='tally':
                    source=ImportConnection(id=str(uuid4()),organization_id=1,branch_id=branch.id,created_by=user.id,provider=provider,account_id=account,region='in',secret=seal({'access_token':'local-mock-only','refresh_token':'local-mock-only','expires_at':9999999999}))
                    db.add(source);db.flush();own_workflow_records(db,source)
                connection=SyncConnection(id=str(uuid4()),organization_id=1,branch_id=branch.id,created_by=user.id,provider=provider,account_id=account,source_connection_id=source.id if source else None,sandbox=True,enabled=True,auto_sync=provider!='tally',interval_minutes=5,next_sync_at=service.now() if provider!='tally' else None,bridge_secret=seal({'token':bridge}) if provider=='tally' else None)
                db.add(connection);db.flush();own_workflow_records(db,connection);ids[provider]=connection.id
        db.commit();user_id=user.id;branch_id=branch.id;customer_id=customer.id;other_id=other.id
    def fixture_get(url,headers,params):
        state['provider_requests']+=1
        qb='sandbox-quickbooks.api.intuit.com' in url
        if not qb and not url.startswith('https://www.zohoapis.in/books/v3/'):
            raise providers.ProviderError('Live provider access is disabled in this local QA server')
        if not qb and state['fail_zoho']:raise providers.ProviderError('Mock Zoho outage for automatic retry verification')
        amount='2000.20' if qb else '1000.10';balance='1500.20' if qb else '0' if state['settled'] else '600.10'
        receipt='500' if qb else '1000.10' if state['settled'] else '400'
        if qb:
            kind=params['query'].split()[3]
            rows={'Customer':[{'Id':'c1','DisplayName':'Mock Acme Trading','PrimaryEmailAddr':{'Address':'acme@example.com'},'CurrencyRef':{'value':'INR'},'Active':True}],
             'Invoice':[{'Id':'i1','DocNumber':'MOCK-QB-1001','CustomerRef':{'value':'c1'},'CurrencyRef':{'value':'INR'},'TotalAmt':amount,'Balance':balance,'TxnDate':today,'DueDate':today}],
             'Payment':[{'Id':'p1','PaymentRefNum':'MOCK-QB-RCPT','CustomerRef':{'value':'c1'},'CurrencyRef':{'value':'INR'},'TotalAmt':receipt,'TxnDate':today}]}
            return {'QueryResponse':{kind:rows[kind]}}
        kind=url.rsplit('/',1)[1]
        rows={'contacts':[{'contact_id':'c1','contact_name':'Mock Acme Trading','email':'acme@example.com','currency_code':'INR','status':'active'}],
          'invoices':[{'invoice_id':'i1','invoice_number':'MOCK-ZOHO-1001','customer_id':'c1','currency_code':'INR','total':amount,'balance':balance,'date':today,'due_date':today,'status':'paid' if state['settled'] else 'partially_paid'},
                      {'invoice_id':'i2','invoice_number':'MOCK-ZOHO-USD','customer_id':'c1','currency_code':'USD','total':'20','balance':'10','date':today,'due_date':today,'status':'partially_paid'}],
          'customerpayments':[{'payment_id':'p1','reference_number':'MOCK-ZOHO-RCPT','customer_id':'c1','currency_code':'INR','amount':receipt,'date':today}]}
        return {kind:rows[kind],'page_context':{'has_more_page':False}}
    providers.get_json=fixture_get
    from app.shared import import_connectors
    def no_live(*a,**k):raise providers.ProviderError('Live OAuth and accounting requests are disabled in this local QA server')
    import_connectors.request_json=no_live
    from fastapi import Request,HTTPException
    def authorize_qa(request):
        if request.client.host not in {'127.0.0.1','::1'} or not secrets.compare_digest(request.headers.get('X-Accounting-QA',''),control):raise HTTPException(403,'Local QA authorization required')
    @app.get('/__qa/accounting/status')
    def qa_status(request:Request):
        authorize_qa(request)
        with SessionLocal() as db:
            runs=[{'provider':c.provider,'connection_id':c.id,'last_success_at':c.last_success_at,'schedule_error':c.schedule_error,'enabled':c.enabled,'next_sync_at':c.next_sync_at,'runs':db.query(SyncRun).filter_by(connection_id=c.id).count()} for c in db.query(SyncConnection).filter(SyncConnection.id.in_(ids.values()))]
        return {'state':state,'connections':runs}
    @app.post('/__qa/accounting/control')
    async def qa_control(request:Request):
        authorize_qa(request);data=await request.json()
        if 'settled' in data:state['settled']=bool(data['settled'])
        if 'fail_zoho' in data:state['fail_zoho']=bool(data['fail_zoho'])
        if data.get('due'):
            provider=data['due']
            if provider not in {'zoho','quickbooks'}:raise HTTPException(422,'Mock cloud provider required')
            with SessionLocal() as db:
                row=db.get(SyncConnection,ids[provider]);row.next_sync_at=service.now()-timedelta(seconds=1);db.commit()
        return {'state':state}
    metadata={**db_config,'backend_url':f'http://127.0.0.1:{args.port}','frontend_url':f'http://127.0.0.1:{args.frontend_port}','email':email,'password':password,'branch_id':branch_id,'user_id':user_id,'customer_id':customer_id,'unlinked_customer_id':other_id,'connections':ids,'bridge_token':bridge,'qa_control_token':control,'business_date':today}
    (ROOT/'.local'/'accounting-acceptance-session.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    worker=jobs.start_worker()
    print(json.dumps({'status':'local mock server ready','database':url.database,'backend_port':args.port,'frontend_port':args.frontend_port,'live_account_access':'blocked'}),flush=True)
    import uvicorn
    try:uvicorn.run(app,host='127.0.0.1',port=args.port,log_level='warning')
    finally:worker[0].set()

if __name__=='__main__':main()
