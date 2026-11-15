from tests.rich_text_test_utils import organization_context
import copy
from datetime import datetime, timedelta, timezone
from app.apps.crm.lead_management import DEFAULTS, state
from app.apps.crm.models import CRMLead, CRMMeeting, CRMActivity, CRMPipeline, CRMPipelineStage, CRMDeal, CRMCompany
from app.apps.crm.lead_models import CRMLeadManagementConfig
from app.apps.crm.sales_process import sales_reminders
from app.models.notification import Notification
from app.models.user import User
ROOT='/api/v1/crm/lead-management'

def create(client, headers, **values):
    r=client.post(ROOT+'/leads', headers=headers, json={'values':{'full_name':'Prospective buyer',**values}})
    assert r.status_code==201,r.text
    return r.json()

def enable(client,db,headers):
    info=client.get(ROOT+'/settings',headers=headers).json()
    ident=info['userId']
    r=client.post(ROOT+'/sales-process/setup',headers=headers,json={'ownerIds':[ident],'managerId':ident})
    assert r.status_code==200,r.text
    return r.json(),ident

def test_setup_idempotent_and_settings_preserve(client,db,superuser_headers):
    first,ident=enable(client,db,superuser_headers)
    second,_=enable(client,db,superuser_headers)
    assert first['pipelineId']==second['pipelineId']
    assert db.query(CRMPipelineStage).filter_by(pipeline_id=first['pipelineId']).count()==6
    settings=client.get(ROOT+'/settings',headers=superuser_headers).json()['settings']
    assert settings['assignment']['mode']=='round_robin'
    r=client.put(ROOT+'/settings',headers=superuser_headers,json=settings)
    assert r.status_code==200,r.text
    assert client.get(ROOT+'/sales-process',headers=superuser_headers).json()['enabled']

def test_metrics_and_meeting_outcomes_are_real_and_retry_safe(client,db,superuser_headers):
    _,owner=enable(client,db,superuser_headers)
    lead=create(client,superuser_headers)
    start=datetime.now(timezone.utc)-timedelta(hours=2)
    meeting=CRMMeeting(organization_id=lead['organization_id'],owner_user_id=owner,lead_id=lead['id'],title='Demo',start_time=start,end_time=start+timedelta(minutes=30),status='Scheduled',created_by_user_id=owner)
    db.add(meeting);db.commit()
    url=f"{ROOT}/leads/{lead['id']}/meetings/{meeting.id}"
    assert client.patch(url,headers=superuser_headers,json={'status':'Confirmed'}).status_code==200
    assert client.patch(url,headers=superuser_headers,json={'status':'Attended'}).status_code==200
    assert client.patch(url,headers=superuser_headers,json={'status':'Attended'}).status_code==200
    assert db.query(CRMActivity).filter(CRMActivity.subject=='Follow up after completed demo').count()==1
    counts=client.get(ROOT+'/meeting-metrics',headers=superuser_headers).json()['counts']
    assert counts['Attended']==1 and counts['Confirmed']==0
    assert client.get(ROOT+'/meeting-metrics',params={'search':'no matching lead'},headers=superuser_headers).json()['counts']['Attended']==0

def test_reschedule_preserves_old_occurrence_and_blocks_overlap(client,db,superuser_headers):
    _,owner=enable(client,db,superuser_headers)
    lead=create(client,superuser_headers)
    start=datetime.now(timezone.utc)+timedelta(days=2)
    meeting=CRMMeeting(organization_id=lead['organization_id'],owner_user_id=owner,lead_id=lead['id'],title='Consultation',start_time=start,end_time=start+timedelta(minutes=30),status='Scheduled',created_by_user_id=owner)
    db.add(meeting);db.commit()
    url=f"{ROOT}/leads/{lead['id']}/meetings/{meeting.id}"
    r=client.patch(url,headers=superuser_headers,json={'status':'Rescheduled','startAt':(start+timedelta(days=1)).isoformat()})
    assert r.status_code==200,r.text
    counts=client.get(ROOT+'/meeting-metrics',headers=superuser_headers).json()['counts']
    assert counts['Scheduled']==1 and counts['Rescheduled']==1
    assert client.patch(url,headers=superuser_headers,json={'status':'Rescheduled','startAt':(start+timedelta(days=2)).isoformat()}).status_code==409
    replacement=db.query(CRMMeeting).filter(CRMMeeting.id!=meeting.id).first()
    assert client.patch(f"{ROOT}/leads/{lead['id']}/meetings/{replacement.id}",headers=superuser_headers,json={'status':'Attended'}).status_code==422

def test_manager_and_nurture_reminders_require_permission_and_are_idempotent(client,db,superuser_headers):
    _,owner=enable(client,db,superuser_headers)
    record=create(client,superuser_headers)
    lead=db.get(CRMLead,record['id'])
    lead.created_at=datetime.now(timezone.utc)-timedelta(days=40)
    row=state(db,lead)
    row.data_json={**row.data_json,'lastResponseAt':lead.created_at.isoformat()}
    db.commit()
    assert sales_reminders(db,lead.organization_id,200)==1
    db.commit()
    assert sales_reminders(db,lead.organization_id,200)==0
    assert db.query(Notification).filter_by(event_type='lead_nurture_due').count()==0
    r=client.put(f"{ROOT}/leads/{lead.id}/nurture-consent",headers=superuser_headers,json={'allowed':True,'evidence':'Permission given on a call'})
    assert r.status_code==200,r.text
    # A new permission starts its own 30-day clock.
    assert sales_reminders(db,lead.organization_id,200)==0
    data=copy.deepcopy(row.data_json);data['nurtureConsent']['recordedAt']=(datetime.now(timezone.utc)-timedelta(days=31)).isoformat();row.data_json=data;db.commit()
    assert sales_reminders(db,lead.organization_id,200)==1
    db.commit()
    assert sales_reminders(db,lead.organization_id,200)==0
    assert db.query(Notification).filter_by(event_type='lead_nurture_due').count()==1

def test_conversion_uses_sales_pipeline_and_prospect_until_won(client,db,superuser_headers):
    process,owner=enable(client,db,superuser_headers)
    record=create(client,superuser_headers,company_name='Example Business',status='Qualified')
    r=client.post(f"{ROOT}/leads/{record['id']}/convert",headers=superuser_headers,json={'createDeal':True})
    assert r.status_code==200,r.text
    lead=db.get(CRMLead,record['id']);db.refresh(lead)
    deal=db.get(CRMDeal,lead.converted_deal_id)
    assert deal.pipeline_id==process['pipelineId']
    assert db.get(CRMPipelineStage,deal.stage_id).name=='Consultation Scheduled'
    assert db.get(CRMCompany,deal.company_id).account_type=='Prospect'
    proposal=db.query(CRMPipelineStage).filter_by(pipeline_id=deal.pipeline_id,name='Proposal Sent').one()
    r=client.patch(f'/api/v1/crm/deals/{deal.id}',headers=superuser_headers,json={'stageId':proposal.id})
    assert r.status_code==200,r.text
    row=state(db,lead);db.refresh(row)
    assert 'proposalReminder' in row.data_json
    assert db.query(CRMActivity).filter(CRMActivity.subject=='Follow up on proposal (2 days)').count()==1
    data=copy.deepcopy(row.data_json);data['proposalReminder']['dueAt']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat();row.data_json=data;db.commit()
    assert sales_reminders(db,lead.organization_id,200)==1
    db.commit()
    assert sales_reminders(db,lead.organization_id,200)==0
    r=client.post(f"{ROOT}/leads/{lead.id}/activity",headers=superuser_headers,json={'type':'call','outcome':'Buyer replied','responded':True})
    assert r.status_code==200,r.text
    db.refresh(row)
    assert 'proposalReminder' not in row.data_json

def test_loss_reason_still_required(client,db,superuser_headers):
    enable(client,db,superuser_headers)
    record=create(client,superuser_headers)
    r=client.patch(f"{ROOT}/leads/{record['id']}",headers=superuser_headers,json={'values':{'status':'Lost'}})
    assert r.status_code==422


def test_demo_stage_creates_task_and_won_sets_customer(client,db,superuser_headers):
    from app.apps.crm.sales_process import deal_changed
    from app.apps.crm.models import CRMContact
    process,owner=enable(client,db,superuser_headers)
    record=create(client,superuser_headers,company_name="Example consultancy",status="Qualified")
    r=client.post(f"{ROOT}/leads/{record['id']}/convert",headers=superuser_headers,json={"createDeal":True})
    assert r.status_code==200,r.text
    lead=db.get(CRMLead,record['id']);db.refresh(lead)
    deal=db.get(CRMDeal,lead.converted_deal_id)
    contact=db.get(CRMContact,deal.contact_id)
    assert contact.lifecycle_stage=="Opportunity" and contact.customer_since is None
    demo=db.query(CRMPipelineStage).filter_by(pipeline_id=deal.pipeline_id,name="Demo Completed").one()
    r=client.patch(f'/api/v1/crm/deals/{deal.id}',headers=superuser_headers,json={'stageId':demo.id})
    assert r.status_code==200,r.text
    assert db.query(CRMActivity).filter_by(subject="Follow up after completed demo").count()==1
    won=db.query(CRMPipelineStage).filter_by(pipeline_id=deal.pipeline_id,name="Won").one()
    before={'stage_id':deal.stage_id}
    deal.stage_id=won.id
    deal_changed(db,deal,db.get(User,owner),before)
    db.commit()
    assert db.get(CRMCompany,deal.company_id).account_type=="Customer"
    assert contact.lifecycle_stage=="Customer" and contact.customer_since is not None


def test_meeting_and_consent_permissions_and_validation(client,db,superuser_headers):
    enable(client,db,superuser_headers)
    lead=create(client,superuser_headers)
    assert client.get(ROOT+'/meeting-metrics').status_code in {401,403}
    assert client.patch(f"{ROOT}/leads/{lead['id']}/meetings/9999",headers=superuser_headers,json={'status':'Attended'}).status_code==404
    assert client.put(f"{ROOT}/leads/{lead['id']}/nurture-consent",headers=superuser_headers,json={'allowed':True,'evidence':'   '}).status_code==422
    r=client.put(f"{ROOT}/leads/{lead['id']}/nurture-consent",headers=superuser_headers,json={'allowed':False,'evidence':'Customer withdrew permission'})
    assert r.status_code==200
    assert client.get(f"{ROOT}/leads/{lead['id']}/nurture-consent",headers=superuser_headers).json()['allowed'] is False


def test_booking_creates_calendar_event_for_demo(client,db,superuser_headers):
    _,owner=enable(client,db,superuser_headers)
    lead=create(client,superuser_headers)
    r=client.post(f"{ROOT}/leads/{lead['id']}/activity",headers=superuser_headers,json={'type':'meeting','purpose':'demo','outcome':'Requirements review and demo','startAt':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()})
    assert r.status_code==200,r.text
    meetings=client.get(f"{ROOT}/leads/{lead['id']}/meetings",headers=superuser_headers).json()
    assert len(meetings)==1 and meetings[0]['description']=='Sales meeting: demo'
    assert client.get(ROOT+'/meeting-metrics',headers=superuser_headers).json()['counts']['Scheduled']==1
