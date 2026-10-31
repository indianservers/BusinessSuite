from tests.test_people_workspace import directory_data, studio, account, middleware_database, organization_context, ROOT
from app.apps.project_management.models import PMSWorkspaceMember, PMSWorkspaceTeam, PMSWorkspaceTeamMember, PMSTask
from app.apps.project_management.models import PMSProjectMember
from app.models.employee import Employee
from app.apps.interns_hub.management_models import InternBatchMembership
from app.apps.interns_hub.management_models import InternBatch

ACTIONS = ROOT + '/actions'

def request(kind, ids, destinations, **extra):
    return dict(kind=kind, user_ids=ids, destination_ids=destinations, reason='Reviewed directory assignment', **extra)

def apply_plan(client, headers, body):
    preview = client.post(ACTIONS+'/preview', headers=headers, json=body)
    assert preview.status_code == 200, preview.text
    response = client.post(ACTIONS+'/apply', headers=headers, json={**body, 'version':preview.json()['version']})
    assert response.status_code == 200, response.text
    return response.json()

def test_destinations_scope_and_selection(client, db, directory_data):
    data, foreign, fh = directory_data
    owner, member, outsider, h, mh, oh, project, team, batch = data
    for kind in ['projects', 'teams', 'batches']:
        response=client.get(ACTIONS+'/destinations',headers=h,params={'kind':kind})
        assert response.status_code==200,response.text
        assert response.json()['items']
    response=client.get(ACTIONS+'/selection',headers=h,params={'ids':str(member.id)})
    assert response.status_code==200,response.text
    assert response.json()['people'][0]['workload']['pending']==0
    assert client.get(ACTIONS+'/selection',headers=h,params={'ids':str(foreign.id)}).status_code==404
    assert client.post(ACTIONS+'/preview',headers=oh,json=request('teams',[outsider.id],[team.id])).status_code in (403,404)

def test_add_duplicate_stale_and_undo(client, db, directory_data):
    data, foreign, fh=directory_data
    owner, member, outsider, h, mh, oh, project, team, batch=data
    body=request('teams',[outsider.id],[team.id])
    assert client.post(ACTIONS+'/apply',headers=h,json=body).status_code==409
    result=apply_plan(client,h,body)
    assert result['rows'][0]['status']=='applied'
    assert db.query(PMSWorkspaceTeamMember).filter_by(team_id=team.id,user_id=outsider.id).count()==1
    assert db.query(PMSWorkspaceMember).filter_by(workspace_id=team.workspace_id,user_id=outsider.id).count()==1
    assert client.post(ACTIONS+f"/{result['undo_ids'][0]}/undo",headers=oh).status_code==404
    undone=client.post(ACTIONS+f"/{result['undo_ids'][0]}/undo",headers=h)
    assert undone.status_code==200,undone.text
    assert not db.query(PMSWorkspaceTeamMember).filter_by(team_id=team.id,user_id=outsider.id).first()
    apply_plan(client,h,body)
    duplicate=apply_plan(client,h,body)
    assert duplicate['rows'][0]['status']=='already_present'
    assert not duplicate['undo_ids']

def test_transfer_and_protected_removal(client, db, directory_data):
    data, foreign, fh=directory_data
    owner, member, outsider, h, mh, oh, project, team, batch=data
    target=PMSWorkspaceTeam(workspace_id=team.workspace_id,name='Target team',alias='target');db.add(target);db.commit()
    result=apply_plan(client,h,request('teams',[member.id],[target.id],action='transfer',source_id=team.id))
    assert result['rows'][0]['status']=='applied'
    assert not db.query(PMSWorkspaceTeamMember).filter_by(team_id=team.id,user_id=member.id).first()
    assert db.query(PMSWorkspaceTeamMember).filter_by(team_id=target.id,user_id=member.id).first()
    db.add(PMSTask(project_id=project['id'],task_key='guard-work',title='Open work',assignee_user_id=member.id));db.commit()
    result=apply_plan(client,h,request('teams',[member.id],[target.id],action='remove'))
    assert result['rows'][0]['status']=='failed'
    assert db.query(PMSWorkspaceTeamMember).filter_by(team_id=target.id,user_id=member.id).first()

def test_mixed_invalid_batch_and_selected_export(client, db, directory_data):
    data, foreign, fh=directory_data
    owner, member, outsider, h, mh, oh, project, team, batch=data
    result=apply_plan(client,h,request('batches',[member.id,outsider.id],[batch.id]))
    assert {r['status'] for r in result['rows']}=={'already_present','failed'}
    response=client.get(ROOT+'/export',headers=h,params={'selected_ids':str(member.id)})
    assert response.status_code==200,response.text
    assert member.email in response.text and outsider.email not in response.text
    assert client.get(ROOT+'/export',headers=h,params={'selected_ids':str(foreign.id)}).status_code==404
    response=client.get(ROOT+'/people',headers=h,params={'kind':'needs_attention'})
    assert response.status_code==200,response.text

def test_stale_preview_does_not_write(client, db, directory_data):
    data, foreign, fh=directory_data
    owner, member, outsider, h, mh, oh, project, team, batch=data
    body=request('teams',[outsider.id],[team.id])
    preview=client.post(ACTIONS+'/preview',headers=h,json=body).json()
    db.add(PMSWorkspaceTeamMember(team_id=team.id,user_id=outsider.id));db.commit()
    response=client.post(ACTIONS+'/apply',headers=h,json={**body,'version':preview['version']})
    assert response.status_code==409,response.text
    assert not db.query(PMSWorkspaceMember).filter_by(workspace_id=team.workspace_id,user_id=outsider.id).first()

def test_project_roles_and_batch_capacity(client, db, directory_data):
    data, foreign, fh=directory_data
    owner, member, outsider, h, mh, oh, project, team, batch=data
    db.add(PMSProjectMember(project_id=project['id'],user_id=member.id,role='Member'));db.commit()
    result=apply_plan(client,h,request('projects',[member.id],[project['id']],action='role',role='Viewer'))
    assert result['rows'][0]['status']=='applied'
    assert db.query(PMSProjectMember).filter_by(project_id=project['id'],user_id=member.id).one().role=='Viewer'
    db.add(Employee(employee_id='CAP-TEST',first_name='Capacity',last_name='Intern',user_id=outsider.id,employment_type='Intern',department_id=member.employee.department_id,date_of_joining=member.employee.date_of_joining,status='Active'))
    batch.capacity=1;db.commit()
    result=apply_plan(client,h,request('batches',[outsider.id],[batch.id]))
    assert result['rows'][0]['status']=='failed'
    assert 'capacity' in result['rows'][0]['reason']
    assert db.query(InternBatchMembership).filter_by(batch_id=batch.id,status='Active').count()==1

def test_batch_transfer_preserves_history(client, db, directory_data):
    data, foreign, fh=directory_data
    owner, member, outsider, h, mh, oh, project, team, batch=data
    target=InternBatch(organization_id=1,name='Next batch',code='NEXT',department_id=batch.department_id,manager_user_id=owner.id,mentor_user_id=owner.id,project_id=project['id'],start_date=batch.start_date,end_date=batch.end_date,capacity=5,status='Active')
    db.add(target);db.commit()
    body=request('batches',[member.id],[target.id],action='transfer',source_id=batch.id)
    result=apply_plan(client,h,body)
    assert result['rows'][0]['status']=='applied'
    original=db.query(InternBatchMembership).filter_by(batch_id=batch.id,employee_id=member.employee.id).one()
    current=db.query(InternBatchMembership).filter_by(batch_id=target.id,employee_id=member.employee.id,status='Active').one()
    assert original.status=='Transferred' and original.left_at and original.active_slot is None
    assert current.previous_batch_id==batch.id and current.reason==body['reason']

def test_undo_rejects_edited_project_role(client, db, directory_data):
    data, foreign, fh=directory_data
    owner, member, outsider, h, mh, oh, project, team, batch=data
    result=apply_plan(client,h,request('projects',[outsider.id],[project['id']]))
    seat=db.query(PMSProjectMember).filter_by(project_id=project['id'],user_id=outsider.id).one()
    seat.role='Viewer';db.commit()
    response=client.post(ACTIONS+f"/{result['undo_ids'][0]}/undo",headers=h)
    assert response.status_code==409,response.text
    assert db.query(PMSProjectMember).filter_by(project_id=project['id'],user_id=outsider.id).one().role=='Viewer'
