"""Admission receipts and fixed native record references across registered modules."""
import json
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.db.tenant import current_tenant
from app.shared import webhook_receipts as receipts
from app.ai_operator import webhook_sources as sources,agent_events


ENTITIES={'CRM':'lead','PMS':'task','HRMS':'employee','SRM':'invoice','FAM':'voucher'}


def sample(module='CRM'):
    native=sources.MODULES[module];entity=ENTITIES[module]
    endpoint=SimpleNamespace(id=7,organization_id=1,target_url='internal:'+native,secret_ref='synthetic-opaque-ciphertext',
        event_types_json={'module':native,'entity':entity,'events':['record.changed'],'runAsUserId':2})
    event=SimpleNamespace(id=51,organization_id=1,module_key=native,event_type='record.changed',entity_type=entity,
        entity_id=41,actor_id=2,request_key='webhook:7:synthetic-event-0001',payload_json={'data':{'text':'Untrusted private payload'},'depth':0})
    return endpoint,event


def test_receipt_rejects_payload_reference_configuration_and_tenant_changes():
    endpoint,event=sample();receipts.admit(endpoint,event)
    assert receipts.verified(endpoint,event)
    proof=json.dumps(event.payload_json[receipts.FIELD])
    assert endpoint.secret_ref not in proof and 'Untrusted private payload' not in proof
    event.entity_id=42;assert not receipts.verified(endpoint,event);event.entity_id=41
    event.payload_json['data']['text']='Changed payload';assert not receipts.verified(endpoint,event)
    event.payload_json['data']['text']='Untrusted private payload'
    endpoint.secret_ref='Rotated ciphertext';assert not receipts.verified(endpoint,event)
    endpoint.secret_ref='synthetic-opaque-ciphertext'
    token=current_tenant.set(SimpleNamespace(tenant_uuid='different-company-database'))
    try:assert not receipts.verified(endpoint,event)
    finally:current_tenant.reset(token)
    assert receipts.verified(endpoint,event)


@pytest.mark.parametrize('module',list(sources.MODULES))
def test_webhook_source_re_reads_only_the_bound_registered_record(monkeypatch,module):
    endpoint,event=sample(module);receipts.admit(endpoint,event)
    monkeypatch.setattr(sources,'endpoint',lambda *args:(endpoint,receipts.binding(endpoint)))
    calls=[]
    from app.shared import gateway
    monkeypatch.setattr(gateway,'read_record',lambda db,user,company,native,entity,ident:calls.append((company,native,entity,ident)) or {'id':ident,'project_id':9})
    db=SimpleNamespace(get=lambda model,ident:SimpleNamespace(workspace_id=3))
    data={'spec':{'event':module.lower()+'.webhook_received','webhook_endpoint_id':7,'webhook_event':'record.changed'},
        'source_binding':receipts.binding(endpoint),'company_id':1,'snapshot':{'workspace_id':3,'project_id':9 if module=='PMS' else None}}
    assert sources.record_reference(db,object(),data,event)==[(ENTITIES[module],41)]
    assert calls==[(1,sources.MODULES[module],ENTITIES[module],41)]
    event.payload_json.pop(receipts.FIELD)
    with pytest.raises(HTTPException):sources.record_reference(db,object(),data,event)
    assert len(calls)==1


def test_webhook_fields_are_explicit_and_do_not_change_legacy_subscription_digests():
    old=agent_events.EventSettings(event='crm.deal_stage').model_dump(mode='json')
    assert 'webhook_endpoint_id' not in old and 'webhook_event' not in old
    with pytest.raises(ValueError):agent_events.EventSettings(event='crm.webhook_received')
    with pytest.raises(ValueError):agent_events.EventSettings(event='crm.deal_stage',webhook_endpoint_id=7,webhook_event='record.changed')
    new=agent_events.EventSettings(event='crm.webhook_received',webhook_endpoint_id=7,webhook_event='record.changed')
    assert new.model_dump()['webhook_endpoint_id']==7


def test_pms_record_must_stay_in_reviewed_workspace_and_project(monkeypatch):
    endpoint,event=sample('PMS');receipts.admit(endpoint,event)
    monkeypatch.setattr(sources,'endpoint',lambda *args:(endpoint,receipts.binding(endpoint)))
    from app.shared import gateway
    monkeypatch.setattr(gateway,'read_record',lambda *args:{'id':41,'project_id':9})
    data={'spec':{'event':'pms.webhook_received','webhook_endpoint_id':7,'webhook_event':'record.changed'},
        'source_binding':receipts.binding(endpoint),'company_id':1,'snapshot':{'workspace_id':3,'project_id':9}}
    db=SimpleNamespace(get=lambda *args:SimpleNamespace(workspace_id=4))
    with pytest.raises(HTTPException) as error:sources.record_reference(db,object(),data,event)
    assert error.value.status_code==404
