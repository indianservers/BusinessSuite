"""Literal collaborator lookup in PMS and native assistant."""
import pytest
from tests.test_import_workspace import import_headers
from app.models.user import User
from app.apps.project_management.models import PMSProject,PMSProjectMember,PMSTask
from app.ai_operator.assistant_tools import Intent,read_tool
from test_identity_utils import attach_test_identity,attach_workflow_branch,own_workflow_records
@pytest.mark.parametrize('needle',['%','_',chr(92),chr(92)+'%',chr(92)+'_','/'])
def test_collaborator_email_search_literal(client,db,import_headers,needle):
    actor=db.query(User).filter_by(email='testadmin@test.com').one()
    project=PMSProject(name='QA project',project_key='QA',organization_id=1,manager_user_id=actor.id)
    db.add(project);db.flush()
    users=[]
    for prefix,active in [('plain',True),('qa'+needle,True),('inactive'+needle,False),('nonmember'+needle,True)]:
        user=User(email=prefix+'@example.com',hashed_password='unused',is_active=active)
        db.add(user);db.flush();attach_test_identity(db,user);attach_workflow_branch(db,user);users.append(user)
    members=[PMSProjectMember(project_id=project.id,user_id=user.id) for user in users[:3]]
    db.add_all(members)
    task=PMSTask(project_id=project.id,title='QA task',task_key='TASK');db.add(task)
    own_workflow_records(db,project,task,*members);db.commit()
    for context in [{},{'projectId':project.id},{'taskId':task.id}]:
        result=client.get('/api/v1/project-management/users/search',headers=import_headers,params={'q':needle,**context})
        assert result.status_code==200,result.text
        assert [r['id'] for r in result.json()]==[users[1].id],(context,result.text)
    native=read_tool(db,actor,Intent(tool='users.search',project_id=project.id,query=needle))
    assert [r['id'] for r in native['items']]==[users[1].id]
