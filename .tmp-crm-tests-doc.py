from pathlib import Path
p=Path('backend/app/apps/crm/sales_process.py');s=p.read_text(encoding='utf-8').replace('    query = m.visible_query(db, user)\n    if search:', '    query = m.filter_record_type(m.visible_query(db, user), "Lead")\n    if search:');p.write_text(s,encoding='utf-8')
p=Path('backend/tests/test_crm_sales_process.py');s=p.read_text(encoding='utf-8');s+='''

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
''';p.write_text(s,encoding='utf-8')
p=Path('docs/crm/lead-management-implementation.md');s=p.read_text(encoding='utf-8');s+='''

## General sales conversion process (15 November 2026)

CRM → Leads now includes consultation/demo metrics for Scheduled, Confirmed, Attended,
No-show and Rescheduled. These are current occurrence counts across all permitted leads
matching search, stage and owner, excluding potential clients. They are not cumulative
funnel counts. Rescheduling retains the old occurrence and creates a new scheduled one.
The example 40/30/18/12/8 is used only in a disposable browser fixture.

Expand **Sales process & automation** to select the sales manager and assignment pool,
then enable the process. Provisioning is idempotent and preserves existing pipelines;
it creates a general **Sales Conversion** pipeline. Its stages can be edited through the
existing pipeline tools. No industry or school-specific behavior is introduced.

The default process is New → Contacted → Qualified in Leads. Conversion creates an
opportunity in Consultation Scheduled → Demo Completed → Proposal Sent → Negotiation
→ Won / Lost. Conversion retains prospect/opportunity classification; Won promotes linked
company/contact records to Customer. Existing customers retain their classification.

The lead drawer provides consultation/demo booking, confirmation, attendance, no-show,
rescheduling and cancellation. Attendance on a product demo creates a next-day follow-up
task and advances an earlier linked deal to Demo Completed. Entering Demo Completed from
the deal pipeline also creates a follow-up task. Consultations do not count as completed demos.

Enabled automation uses the existing assignment engine (round-robin), 24-hour first-contact
SLA, real CRM calendar events, next-day demo tasks, a two-day proposal task/reminder,
seven-day no-response alerts to the configured sales manager, mandatory loss reasons,
and a 30-day nurture reminder only with explicit recorded permission. A new response
resets the no-response clock and cancels the pending proposal reminder. Permission records
include evidence, actor and time; withdrawal prevents nurture reminders. The nurture clock
starts at the later of the last recorded response and recorded permission. These are internal
notifications/tasks, not outbound email or messaging.

Timed evaluation uses the protected cron and, for configured processes, the existing
once-per-minute local follow-up worker. It skips archived records, closed proposals,
and recipients who no longer have access. Repeat evaluation does not duplicate reminders.
External calendar synchronization still requires the existing provider connection.

Implementation checks use disposable databases and a browser fixture; fixture writes never
reach the developer's CRM database. Local configuration must be enabled for the intended
company with an appropriate manager and assignment pool.
''';p.write_text(s,encoding='utf-8')
