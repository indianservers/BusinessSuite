import pytest
from ai_test_utils import auth_headers
from tests.rich_text_test_utils import organization_context
from app.models.workflow_engine import WorkflowDefinition, WorkflowStepDefinition

ROOT='/api/v1/workflow-engine'


def people(client,db):
    headers,actor=auth_headers(client,db,'workflow-owner@example.com',['company_manage'])
    _,local=auth_headers(client,db,'workflow-person@example.com',['employee_view'])
    _,foreign=auth_headers(client,db,'workflow-foreign@example.com',['employee_view'],company_id=2)
    return headers,actor,local,foreign


def body(local,**changes):
    return {'name':'Synthetic named workflow','module':'leave','trigger_event':'submitted',
        'steps':[{'step_order':1,'approver_type':'User','approver_value':str(local.id),**changes}]}


def test_workflow_targets_match_designer_authorization_and_company(client,db):
    headers,_,local,foreign=people(client,db)
    response=client.get(ROOT+'/approval-targets',headers=headers)
    assert response.status_code==200,response.text
    assert local.id in {r['id'] for r in response.json()['users']}
    assert foreign.id not in {r['id'] for r in response.json()['users']}
    assert local.role.name in {r['name'] for r in response.json()['roles']}
    assert foreign.role.name not in {r['name'] for r in response.json()['roles']}
    found=client.get(ROOT+'/approval-targets',headers=headers,params={'search':'WORKFLOW-PERSON'})
    assert [r['id'] for r in found.json()['users']]==[local.id]
    reader,_=auth_headers(client,db,'workflow-reader@example.com',['employee_view'])
    assert client.get(ROOT+'/approval-targets',headers=reader).status_code==403


@pytest.mark.parametrize('kind',['approver','escalation','delegate_user','delegate_role','role'])
def test_foreign_workflow_recipient_rejected_before_definition_creation(client,db,kind):
    headers,_,local,foreign=people(client,db)
    changes={}
    if kind=='approver':changes={'approver_value':str(foreign.id)}
    if kind=='escalation':changes={'escalation_user_id':foreign.id}
    if kind=='delegate_user':changes={'delegation_type':'User','delegation_value':str(foreign.id)}
    if kind=='delegate_role':changes={'delegation_type':'Role','delegation_value':foreign.role.name}
    if kind=='role':changes={'approver_type':'Role','approver_value':foreign.role.name}
    count=db.query(WorkflowDefinition).count()
    response=client.post(ROOT+'/definitions',headers=headers,json=body(local,**changes))
    assert response.status_code==422,response.text
    assert db.query(WorkflowDefinition).count()==count


def test_invalid_step_edit_preserves_saved_recipient_and_metadata(client,db):
    headers,_,local,foreign=people(client,db)
    response=client.post(ROOT+'/definitions',headers=headers,json=body(local,metadata_json={'audit_note':'Original note'}))
    assert response.status_code==201,response.text
    workflow=response.json()['id']
    step=db.query(WorkflowStepDefinition).filter_by(workflow_id=workflow).one()
    response=client.put(f'{ROOT}/definitions/{workflow}/steps/{step.id}',headers=headers,
        json={'step_order':1,'approver_type':'User','approver_value':str(foreign.id),'metadata_json':{'audit_note':'Invalid overwrite'}})
    assert response.status_code==422,response.text
    db.refresh(step)
    assert step.approver_value==str(local.id) and step.metadata_json=={'audit_note':'Original note'}


@pytest.mark.parametrize('value',['0','-1','2147483648','9'*5000,'²'])
def test_invalid_recipient_ids_return_validation_without_partial_definition(client,db,value):
    headers,_,local,_=people(client,db)
    count=db.query(WorkflowDefinition).count()
    response=client.post(ROOT+'/definitions',headers=headers,json=body(local,approver_value=value))
    assert response.status_code==422,response.text
    assert db.query(WorkflowDefinition).count()==count


def test_reactivation_rechecks_disabled_recipient(client,db):
    headers,_,local,_=people(client,db)
    response=client.post(ROOT+'/definitions',headers=headers,json=body(local))
    assert response.status_code==201,response.text
    ident=response.json()['id']
    endpoint=f'{ROOT}/definitions/{ident}/toggle-active'
    assert client.put(endpoint,headers=headers).status_code==200
    local.is_active=False;db.commit()
    response=client.put(endpoint,headers=headers)
    assert response.status_code==422,response.text
    db.expire_all()
    assert not db.get(WorkflowDefinition,ident).is_active
    local.is_active=True;db.commit()
    response=client.put(endpoint,headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['is_active']
