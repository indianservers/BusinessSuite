from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.apps.power_apps.integrations.contracts import IntegrationFailure
from app.apps.power_apps.integrations.marketplace_actions import normalize, page_result, build
from app.apps.power_apps.integrations.marketplace_sync import failure_details, public


def test_facebook_capture_preserves_custom_multiselect_and_attribution():
    result = normalize('facebook_lead_ads', {
        'id':'lead-123','form_id':'form-456','ad_id':'ad-789','created_time':'2026-11-11T10:00:00+0000',
        'field_data':[
            {'name':'full_name','values':['Asha Kumar']},
            {'name':'phone_number','values':['+919876543210']},
            {'name':'interests','values':['CRM','Accounting']},
            {'name':'external_id','values':['untrusted-answer']},
        ],
    })
    assert result['external_id']=='lead-123'
    assert result['phone']=='+919876543210'
    assert result['answer_interests']=='CRM; Accounting'
    assert result['answer_external_id']=='untrusted-answer'
    assert result['meta_form_id']=='form-456'
    assert 'interests: CRM; Accounting' in result['notes']
    assert 'ad_id: ad-789' in result['notes']


@pytest.mark.parametrize('fields',[{},[None],[{'name':'email','values':'invalid'}]])
def test_malformed_facebook_answers_fail_with_provider_error(fields):
    with pytest.raises(IntegrationFailure):
        normalize('facebook_lead_ads',{'id':'123','field_data':fields})


def test_facebook_pagination_does_not_silently_drop_remaining_leads():
    conn=SimpleNamespace(connector_id='facebook_lead_ads')
    with pytest.raises(IntegrationFailure):
        page_result(conn,{'cursor':'0'},{'data':[{'id':'1'}],'paging':{'next':'https://graph.facebook.com/next'}})
    path,_=build(conn,'sync_page',{'cursor':'next-page'},'/form/leads',None)
    assert 'field_data' in path and 'after=next-page' in path


def test_retry_after_backoff_and_exhaustion_do_not_leak_provider_details():
    error=HTTPException(422,{'category':'rate_limit','message':'secret-token-from-provider', 'retryable':True,'retry_after':3600})
    first=failure_details(error,1,'facebook_lead_ads')
    assert first['retryable'] and first['error_category']=='rate_limit'
    assert 'secret-token' not in str(first)
    exhausted=failure_details(error,8,'facebook_lead_ads')
    assert not exhausted['retryable']
    assert 'stopped' in exhausted['last_error']


@pytest.mark.parametrize('error,provider',[
    (IntegrationFailure('authentication','bad token'),'facebook_lead_ads'),
    (IntegrationFailure('network','unknown result',retryable=True,uncertain=True),'facebook_lead_ads'),
    (IntegrationFailure('pending','enrichment pending',retryable=True),'surfe'),
])
def test_unsafe_or_permanent_failure_never_automatically_retries(error,provider):
    assert failure_details(error,1,provider)['retryable'] is False


def test_sync_health_distinguishes_attention_and_hides_leases():
    row=SimpleNamespace(id=1,version=3,values_json={'enabled':True,'state':'error','retryable':False,'lease':'private-lease','lease_until':None})
    result=public(row)
    assert result['health']=='attention'
    assert 'lease' not in result and 'lease_until' not in result


def test_business_read_preserves_numeric_ids_without_exposing_credentials():
    from app.apps.power_apps.integrations.transport import scrub
    value={'id':'1234567890123456','phone':'+919876543210','access_token':'do-not-return',
           'note':'private-credential-value','nested':[{'password':'hidden'}]}
    business=scrub(value,['private-credential-value'],redact_debug_strings=False)
    assert business['id']=='1234567890123456' and business['phone']=='+919876543210'
    assert business['note']=='[REDACTED]' and 'access_token' not in business
    assert business['nested']==[{}]
    assert scrub(value)['phone']!=value['phone']
    page=scrub({'next':'https://graph.facebook.com/leads?access_token=provider-added-token&after=1234567890123456'},redact_debug_strings=False)
    assert 'provider-added-token' not in page['next'] and 'after=1234567890123456' in page['next']


def test_scheduler_skips_permanent_failures_but_allows_manual_recovery(client,db,native_actor,monkeypatch):
    import json
    from tests.test_marketplace_sync_workflows import create_connection, fixture_page
    from tests.test_marketplace_provider_authorization import CASES
    from app.apps.power_apps.integrations import adapters
    from app.apps.power_apps.integrations.marketplace_sync import dispatch_due
    from app.shared.models import ServicePolicy
    headers,user=native_actor
    # Later jobs must not be starved by the old first-1,000 candidate limit.
    db.add_all([ServicePolicy(scope_key=f'paused-filler:{i}',organization_id=1,module_key='crm',kind='connector_sync',
        updated_by=user.id,values_json={'enabled':False}) for i in range(1001)])
    db.commit()
    calls=[]
    failing=[True]
    class Transport:
        def request(self,method,url,**kwargs):
            calls.append(url)
            return SimpleNamespace(status=401 if failing[0] else 200,headers={},body=json.dumps({} if failing[0] else fixture_page('facebook_lead_ads')).encode())
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    ident=create_connection(client,headers,next(c for c in CASES if c[0]=='facebook_lead_ads'))
    root='/api/v1/power-apps/integrations/sync'
    made=client.post(root+'/jobs',headers=headers,json={'connection_id':ident,'name':'Facebook lead capture','source':{'resource_id':'form-1'},'automatic':True,'apply_new_records':True})
    assert made.status_code==201,made.text
    job=db.get(ServicePolicy,made.json()['id'])
    assert dispatch_due(db)['failed_jobs']==1
    db.refresh(job)
    assert job.values_json['error_category']=='authentication'
    job.values_json={**job.values_json,'next_at':'2020-01-01T00:00:00+00:00'};db.commit()
    assert dispatch_due(db)=={'completed_pages':0,'failed_jobs':0}
    assert len(calls)==1
    failing[0]=False
    response=client.post(f'{root}/jobs/{job.id}/run',headers=headers,json={})
    assert response.status_code==200,response.text
    assert response.json()['health']=='healthy'
    assert response.json()['consecutive_failures']==0


# Reuse the tenant/branch fixture, not an independently configured database.
from tests.test_marketplace_sync_workflows import native_actor
from tests.test_power_apps import actors


def test_power_worker_dispatches_import_sync_even_without_workflow_jobs(db,monkeypatch):
    from app.apps.power_apps import worker, telegram, runtime_retention
    from app.apps.power_apps.integrations import automation_triggers, native_runtime, marketplace_sync
    calls=[]
    monkeypatch.setattr(worker,'tick',lambda db:None)
    monkeypatch.setattr(worker,'scheduler_tick',lambda db:None)
    monkeypatch.setattr(telegram,'poll_tick',lambda db:None)
    monkeypatch.setattr(automation_triggers,'poll_tick',lambda db:None)
    monkeypatch.setattr(native_runtime,'tick',lambda db:None)
    monkeypatch.setattr(runtime_retention,'purge_payloads',lambda db:None)
    monkeypatch.setattr(marketplace_sync,'dispatch_due',lambda db:calls.append('sync'))
    monkeypatch.setattr(worker,'claim',lambda db,ident:None)
    assert worker.worker_tick(db,'crm-sync-regression-worker') is False
    assert calls==['sync']


def test_lead_can_be_used_for_confirmed_contact_workflow(client,db,native_actor,monkeypatch):
    from tests.test_marketplace_sync_workflows import create_connection, stamp
    from tests.test_marketplace_provider_authorization import CASES
    from app.apps.power_apps.integrations import adapters
    from app.apps.crm.models import CRMLead
    from app.models.company import Branch
    headers,user=native_actor
    branch=db.query(Branch).filter_by(company_id=1).first()
    lead=CRMLead(organization_id=1,branch_id=branch.id,owner_user_id=user.id,first_name='Asha',last_name='Kumar',full_name='Asha Kumar',email='asha@example.com')
    db.add(lead);stamp(db,lead,branch.id);db.commit()
    ident=create_connection(client,headers,next(c for c in CASES if c[0]=='activecampaign'),True)
    calls=[]
    class Transport:
        def request(self,method,url,**kwargs):
            calls.append(kwargs['body'])
            return SimpleNamespace(status=200,headers={},body=b'{"contact":{"id":"remote-lead"}}')
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    root='/api/v1/power-apps/integrations/sync'
    sources=client.get(root+'/sources/leads',headers=headers)
    assert sources.status_code==200,sources.text
    assert any(r['id']==lead.id for r in sources.json()['items'])
    payload={'connection_id':ident,'action_id':'upsert_contact','source_kind':'leads','source_id':lead.id,'settings':{},'request_id':'native-lead-workflow-123'}
    preview=client.post(root+'/workflow/preview',headers=headers,json=payload)
    assert preview.status_code==200,preview.text
    assert preview.json()['payload']['email']=='asha@example.com'
    assert not calls
    payload.update(expected_hash=preview.json()['source_hash'],confirmed=True)
    response=client.post(root+'/workflow/execute',headers=headers,json=payload)
    assert response.status_code==200,response.text
    assert client.post(root+'/workflow/execute',headers=headers,json=payload).status_code==200
    assert len(calls)==1


def test_phone_only_facebook_form_imports_notes_and_deduplicates(client,db,native_actor,monkeypatch):
    import json
    from tests.test_marketplace_sync_workflows import create_connection
    from tests.test_marketplace_provider_authorization import CASES
    from app.apps.power_apps.integrations import adapters
    from app.apps.crm.models import CRMLead
    headers,_=native_actor
    class Transport:
        def request(self,method,url,**kwargs):
            return SimpleNamespace(status=200,headers={},body=json.dumps({'data':[{
                'id':'phone-only-lead','form_id':'phone-form','ad_id':'phone-ad',
                'field_data':[{'name':'full_name','values':['Asha Kumar']},
                    {'name':'phone_number','values':['+919876543210']},
                    {'name':'interests','values':['CRM','Finance']},
                    {'name':'job_title','values':['Director']}]
            }]}).encode())
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    ident=create_connection(client,headers,next(c for c in CASES if c[0]=='facebook_lead_ads'))
    root='/api/v1/power-apps/integrations/sync'
    made=client.post(root+'/jobs',headers=headers,json={'connection_id':ident,'name':'Phone leads','source':{'resource_id':'phone-form'},'apply_new_records':True})
    assert made.status_code==201,made.text
    response=client.post(f"{root}/jobs/{made.json()['id']}/run",headers=headers,json={})
    assert response.status_code==200,response.text
    from app.shared.import_models import ImportBatch
    batch=db.get(ImportBatch,response.json()['batches'][0])
    assert batch.table_json['rows'][0][batch.table_json['headers'].index('phone')]=='+919876543210'
    assert 'phone_country_code' in batch.mapping_json, batch.table_json['headers']
    assert batch.table_json['rows'][0][batch.table_json['headers'].index('phone_country_code')]=='+91'
    assert batch.status=='imported',(batch.preview_json,batch.table_json,batch.mapping_json)
    lead=db.query(CRMLead).filter_by(full_name='Asha Kumar').one()
    assert lead.phone=='9876543210' and lead.phone_country_code=='+91'
    assert not lead.email
    assert lead.job_title=='Director'
    assert 'phone-ad' in lead.notes and 'CRM; Finance' in lead.notes
    # A second form/connector job with the same person must not create another lead.
    another=client.post(root+'/jobs',headers=headers,json={'connection_id':ident,'name':'Other form','source':{'resource_id':'other-form'},'apply_new_records':True})
    assert another.status_code==201,another.text
    response=client.post(f"{root}/jobs/{another.json()['id']}/run",headers=headers,json={})
    assert response.status_code==200,response.text
    assert db.query(CRMLead).filter_by(phone='9876543210',phone_country_code='+91').count()==1
