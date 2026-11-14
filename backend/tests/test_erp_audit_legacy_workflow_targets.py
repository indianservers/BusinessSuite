import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_erp_audit_workflow_targets import people
from app.models.workflow_engine import WorkflowDefinition, WorkflowStepDefinition

ROOT='/api/v1/workflow/definitions'


def definition(client,headers):
    response=client.post(ROOT,headers=headers,json={'name':'Synthetic legacy workflow','module':'leave','trigger_event':'submitted'})
    assert response.status_code==201,response.text
    return response.json()['id']


@pytest.mark.parametrize('kind',['approver','escalation','delegation','role'])
def test_legacy_step_rejects_foreign_recipient(client,db,kind):
    headers,_,local,foreign=people(client,db)
    ident=definition(client,headers)
    payload={'step_order':1,'approver_type':'User','approver_value':str(local.id)}
    if kind=='approver':payload['approver_value']=str(foreign.id)
    if kind=='escalation':payload['escalation_user_id']=foreign.id
    if kind=='delegation':payload.update(delegation_type='User',delegation_value=str(foreign.id))
    if kind=='role':payload.update(approver_type='role',approver_value=foreign.role.name)
    response=client.post(f'{ROOT}/{ident}/steps',headers=headers,json=payload)
    assert response.status_code==422,response.text
    assert db.query(WorkflowStepDefinition).filter_by(workflow_id=ident).count()==0


def test_legacy_invalid_edit_preserves_step(client,db):
    headers,_,local,foreign=people(client,db)
    ident=definition(client,headers)
    payload={'step_order':1,'approver_type':'User','approver_value':str(local.id),'metadata_json':{'audit_note':'Retain original'}}
    response=client.post(f'{ROOT}/{ident}/steps',headers=headers,json=payload)
    assert response.status_code==201,response.text
    step_id=response.json()['id']
    response=client.put(f'{ROOT}/{ident}/steps/{step_id}',headers=headers,
        json={**payload,'approver_value':str(foreign.id),'metadata_json':{'audit_note':'Invalid overwrite'}})
    assert response.status_code==422,response.text
    db.expire_all()
    step=db.get(WorkflowStepDefinition,step_id)
    assert step.approver_value==str(local.id) and step.metadata_json=={'audit_note':'Retain original'}


def test_legacy_default_role_is_canonical_for_engine(client,db):
    headers,_,local,_=people(client,db)
    ident=definition(client,headers)
    response=client.post(f'{ROOT}/{ident}/steps',headers=headers,
        json={'approver_value':local.role.name,'delegation_type':'role','delegation_value':local.role.name})
    assert response.status_code==201,response.text
    assert response.json()['approver_type']=='Role' and response.json()['delegation_type']=='Role'
    step_id=response.json()['id']
    response=client.put(f'{ROOT}/{ident}/steps/{step_id}',headers=headers,
        json={'approver_value':local.role.name,'delegation_type':'user','delegation_value':str(local.id)})
    assert response.status_code==200,response.text
    assert response.json()['step_order']==1
    assert response.json()['approver_type']=='Role' and response.json()['delegation_type']=='User'


def test_legacy_activation_rechecks_recipient(client,db):
    headers,_,local,_=people(client,db)
    ident=definition(client,headers)
    response=client.post(f'{ROOT}/{ident}/steps',headers=headers,json={'step_order':1,'approver_type':'User','approver_value':str(local.id)})
    assert response.status_code==201,response.text
    assert client.post(f'{ROOT}/{ident}/deactivate',headers=headers).status_code==200
    local.is_active=False;db.commit()
    response=client.post(f'{ROOT}/{ident}/activate',headers=headers)
    assert response.status_code==422,response.text
    db.refresh(db.get(WorkflowDefinition,ident))
    assert not db.get(WorkflowDefinition,ident).is_active
    local.is_active=True;db.commit()
    assert client.post(f'{ROOT}/{ident}/activate',headers=headers).status_code==200
