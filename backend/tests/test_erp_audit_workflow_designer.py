import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_workflow_engine_depth import init_db, _login, _ensure_user, _ensure_leave_request
from app.models.workflow_engine import WorkflowStepDefinition


@pytest.mark.parametrize('decision', ['approve','reject'])
def test_configured_role_delegation_and_audit_note_survive_execution(client, db, decision):
    init_db(db)
    headers=_login(client)
    approver=_ensure_user(db,'designer-approver@example.com','workflow_approver')
    delegate=_ensure_user(db,'designer-delegate@example.com','workflow_delegate')
    leave=_ensure_leave_request(db);db.commit()
    response=client.post('/api/v1/workflow-engine/definitions',headers=headers,json={
        'name':'Synthetic retained designer options','module':'leave','trigger_event':'submitted',
        'steps':[{'step_order':1,'approver_type':'User','approver_value':str(approver.id),
            'delegation_type':'Role','delegation_value':'workflow_delegate',
            'metadata_json':{'audit_note':'Retain configured evidence & reason','other':'preserved'}}]})
    assert response.status_code==201,response.text
    step=db.query(WorkflowStepDefinition).filter_by(workflow_id=response.json()['id']).one()
    assert step.delegation_value=='workflow_delegate'
    assert step.metadata_json['audit_note']=='Retain configured evidence & reason'
    instance=client.post('/api/v1/workflow-engine/instances',headers=headers,json={
        'workflow_id':response.json()['id'],'module':'leave','entity_type':'leave_request','entity_id':leave.id})
    assert instance.status_code==201,instance.text
    delegated_headers=_login(client,'designer-delegate@example.com','User@123456')
    tasks=client.get('/api/v1/workflow-engine/tasks',headers=delegated_headers).json()
    task=next(t for t in tasks if t['instance_id']==instance.json()['id'])
    assert task['assigned_role']=='workflow_delegate' and task['original_assigned_to_user_id']==approver.id
    result=client.put(f"/api/v1/workflow-engine/tasks/{task['id']}/decision",headers=delegated_headers,
        json={'decision':decision,'reason':'Actual decision reason'})
    assert result.status_code==200,result.text
    audit=client.get(f"/api/v1/workflow-engine/instances/{instance.json()['id']}/audit",headers=headers)
    assert audit.status_code==200,audit.text
    events=[e for e in audit.json() if e['step_definition_id']==step.id]
    assert {e['event_type'] for e in events} >= {'task_created','task_approved' if decision=='approve' else 'task_rejected'}
    assert all(e['details_json']['audit_note']=='Retain configured evidence & reason' for e in events)
    assert next(e for e in events if e['event_type']!='task_created')['reason']=='Actual decision reason'
