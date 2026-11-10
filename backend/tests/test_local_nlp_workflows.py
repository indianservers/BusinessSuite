from tests.rich_text_test_utils import organization_context
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.ai_operator.models import OperatorApiLog
from app.apps.crm.models import CRMTask
from app.models.email_outbox import EmailOutbox
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick

ROOT='/api/v1/ai-operator/suite'


def test_untrained_local_finance_does_not_fall_back_to_crm(client,db):
    h,*_=setup_suite(client,db)
    for text,extra in [('Summarize financial records',{'module':'FAM'}),('FAM: show invoices',{})]:
        response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','text':text,**extra})
        assert response.status_code==422,response.text
        assert 'not trained for Finance' in response.json()['detail']


def command(client,h,text,**extra):
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','text':text,**extra})
    assert response.status_code in (200,201),response.text
    assert response.json()['status']!='failed',response.text
    return response.json()


def test_local_jobs_and_task_nlp_use_real_canonical_data_and_review(client,db,monkeypatch):
    h,user,project,task=setup_suite(client,db)
    def forbidden(*args,**kwargs):raise AssertionError('No cloud calls permitted in local NLP')
    monkeypatch.setattr('app.ai_operator.suite.generate_json',forbidden)
    today=datetime.now(ZoneInfo('Asia/Kolkata')).date()
    response=client.post('/api/v1/crm/tasks',headers=h,json={'title':'Today client job','due_date':today.isoformat()+'T12:00:00+05:30','owner_user_id':user.id})
    assert response.status_code in (200,201),response.text
    row=response.json()
    jobs=command(client,h,'what are todays jobs',module='CRM')
    assert jobs['status']=='answered' and 'Today client job' in jobs['plan']['summary']
    assert jobs['result']['local_nlp']['cloud_calls']==0
    draft=command(client,h,'CRM: create a task "Call client" due tomorrow')
    assert draft['status']=='awaiting_approval' and db.query(CRMTask).count()==1
    approve(client,h,draft);tick(client,db)
    assert db.query(CRMTask).count()==2
    change=command(client,h,f'CRM: set task #{row["id"]} priority to high')
    assert change['status']=='awaiting_approval'
    approve(client,h,change);tick(client,db)
    assert db.get(CRMTask,row['id']).priority=='High'
    assert db.query(OperatorApiLog).count()==0


def test_local_today_reminders_match_branch_timezone_and_native_source_access(client,db):
    from tests.test_ai_reminders import draft,approve as approve_reminder
    from app.ai_operator.reminders import Job
    h,user,reminder,spec=draft(client,db)
    approve_reminder(client,h,reminder)
    # Choose a due instant within today's timezone without making any delivery.
    due=datetime.now(timezone.utc)
    row=db.get(Job,reminder['id']);row.run_at=due;db.commit()
    reply=command(client,h,'PMS: check todays reminder')
    assert reply['result']['local_nlp']['intent']=='reminders.today'
    assert reply['result']['local_nlp']['items'][0]['id']==row.id
    assert db.query(EmailOutbox).filter_by(module='ai_reminder').count()==0
    row.status='ai_cancelled';db.commit()
    reply=command(client,h,'PMS: check todays reminder')
    assert reply['result']['local_nlp']['items']==[]


def test_message_all_leads_requires_details_and_only_previews_authorized_recipients(client,db,monkeypatch):
    from app.apps.communication.models import CommunicationEmailMessage
    from app.core.config import settings
    monkeypatch.setattr(settings,'COMMUNICATION_EMAIL_PROVIDER','stub')
    h,user,project,task=setup_suite(client,db)
    leads=[]
    for name,email in [('Allowed recipient','allowed@example.com'),('Opted out recipient','blocked@example.com')]:
        response=client.post('/api/v1/crm/leads',headers=h,json={'first_name':name,'full_name':name,'email':email})
        assert response.status_code in (200,201),response.text
        leads.append(response.json())
    response=client.post('/api/v1/communication/consents',headers=h,json={'email':'blocked@example.com','record_type':'lead','record_id':leads[1]['id'],'consent_type':'email','status':'opted_out'})
    assert response.status_code in (200,201),response.text
    incomplete=command(client,h,'send a message to all leads')
    assert incomplete['status']=='needs_clarification' and 'channel' in incomplete['plan']['question'].lower()
    reply=command(client,h,'email subject "Check-in" body "Hello {{name}}, may we arrange a call?"',parent_run_id=incomplete['id'])
    details=reply['result']['local_nlp']
    assert reply['status']=='awaiting_approval' and details['sent'] is False
    assert details['preview']['eligible']==1 and details['preview']['blocked']==1
    assert 'preview_token' not in details['preview']
    assert len(details['draft']['recipients'])==2
    assert db.query(CommunicationEmailMessage).count()==0
    assert db.query(OperatorApiLog).count()==0
    # Native final review and delivery use a test-only provider, never SMTP.
    draft=details['draft']
    preview=client.post('/api/v1/crm/growth/greetings/preview',headers=h,json=draft)
    assert preview.status_code==200 and preview.json()['simulation'] is True,preview.text
    send={**draft,'preview_token':preview.json()['preview_token'],'request_id':str(uuid4())}
    assert client.post('/api/v1/crm/growth/greetings/send',headers=h,json={**send,'body':'Changed after review'}).status_code==409
    delivered=client.post('/api/v1/crm/growth/greetings/send',headers=h,json=send)
    assert delivered.status_code==200,delivered.text
    assert db.query(CommunicationEmailMessage).filter_by(to_email='allowed@example.com').count()==1
    assert db.query(CommunicationEmailMessage).filter_by(to_email='blocked@example.com').count()==0
    repeated=client.post('/api/v1/crm/growth/greetings/send',headers=h,json=send)
    assert repeated.status_code==200 and repeated.json()['replayed'] is True,repeated.text


def test_partial_all_leads_is_never_silently_messaged(client,db,monkeypatch):
    h,user,project,task=setup_suite(client,db)
    from app.ai_operator import suite
    real=suite.api_call
    async def source(app,authorization,method,path,payload=None):
        if path=='/crm/leads':return {'items':[{'id':index,'title':'Visible lead'} for index in range(1,51)],'total':51}
        assert not path.endswith('/greetings/preview')
        return await real(app,authorization,method,path,payload)
    monkeypatch.setattr(suite,'api_call',source)
    reply=command(client,h,'email all leads subject "Hello" body "Hello {{name}}"')
    assert reply['status']=='needs_clarification' and 'partial sample' in reply['plan']['question']


def test_local_library_exposes_120_commands_per_module_without_business_data(client,db):
    h,_,_,_=setup_suite(client,db)
    response=client.get(ROOT+'/local-model',headers=h,params={'module':'HRMS'})
    assert response.status_code==200,response.text
    data=response.json()
    assert len(data['examples'])==data['modules']['HRMS']['commands'] and all(row['module']=='HRMS' for row in data['examples'])
    assert all(row['commands']>=120 for row in data['modules'].values())


def test_local_pms_hrms_and_sales_commands_use_real_module_apis(client,db,monkeypatch):
    from app.models.employee import Employee
    from app.models.helpdesk import HelpdeskTicket
    from app.apps.project_management.models import PMSTask
    from app.apps.srm.models import SRMInvoice
    h,user,project,task=setup_suite(client,db)
    monkeypatch.setattr('app.ai_operator.suite.generate_json',lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('No cloud')))
    created=command(client,h,'PMS: create project task "Local project QA" due tomorrow',project_id=project)
    assert created['status']=='awaiting_approval'
    assert db.query(PMSTask).filter_by(title='Local project QA').count()==0
    approve(client,h,created);tick(client,db)
    assert db.query(PMSTask).filter_by(title='Local project QA').count()==1
    db.add(Employee(employee_id='LOCAL-NLP',user_id=user.id,first_name='Local',last_name='QA',date_of_joining=datetime.now().date()))
    db.commit();db.expire_all()
    ticket=command(client,h,'HRMS: create HR ticket "Laptop access"')
    assert ticket['status']=='awaiting_approval' and db.query(HelpdeskTicket).count()==0
    approve(client,h,ticket);tick(client,db)
    assert db.query(HelpdeskTicket).one().subject=='Laptop access'
    invoice=SRMInvoice(organization_id=1,invoice_number='LOCAL-INV',currency='INR',status='sent',total_amount=10,balance_amount=10,created_by=user.id)
    db.add(invoice);db.commit()
    sales=command(client,h,'Sales: show unpaid invoices')
    assert sales['status']=='answered' and 'LOCAL-INV' in sales['plan']['summary']
    assert db.query(OperatorApiLog).count()==0


def test_local_lead_commands_respect_module_permissions(client,db):
    from ai_test_utils import auth_headers
    h,user,project,task=setup_suite(client,db)
    client.post('/api/v1/crm/leads',headers=h,json={'first_name':'Private lead','full_name':'Private lead','email':'private@example.com'})
    restricted,_=auth_headers(client,db,email=f'local-denied-{uuid4()}@example.com',permissions=['ai_assistant'])
    response=client.post(ROOT+'/commands',headers=restricted,json={'request_key':str(uuid4()),'text':'email all leads subject "Hello" body "Hello {{name}}"','provider':'local'})
    assert response.status_code in {200,403},response.text
    assert 'Private lead' not in response.text and 'private@example.com' not in response.text
    if response.status_code==200:assert response.json()['status']=='failed'
