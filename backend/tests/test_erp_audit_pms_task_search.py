"""Literal native task/backlog/tag API search."""
import pytest
from tests.test_import_workspace import import_headers
from app.models.user import User
from app.apps.project_management.models import PMSProject,PMSTask,PMSTag
BASE='/api/v1/project-management'
@pytest.mark.parametrize('needle',['%','_',chr(92),chr(92)+'%',chr(92)+'_','/'])
def test_native_pms_task_search_literal(client,db,import_headers,needle):
    actor=db.query(User).filter_by(email='testadmin@test.com').one()
    project=PMSProject(name='QA project',project_key='QA',organization_id=1,manager_user_id=actor.id)
    db.add(project);db.flush()
    ordinary=PMSTask(project_id=project.id,title='Ordinary task',task_key='ORD')
    match=PMSTask(project_id=project.id,title='QA'+needle+'Literal',task_key='MATCH')
    tags=[PMSTag(name='Ordinary tag',organization_id=1),PMSTag(name='QA'+needle+'Literal',organization_id=1)]
    db.add_all([ordinary,match,*tags]);db.flush()
    from test_identity_utils import own_workflow_records
    own_workflow_records(db,project,ordinary,match,*tags);db.commit()
    result=client.get(BASE+'/tasks',headers=import_headers,params={'search':needle,'pageSize':1})
    assert result.status_code==200,result.text
    assert result.json()['total']==1
    assert result.json()['summary']['total']==1
    assert [r['id'] for r in result.json()['items']]==[match.id]
    backlog=client.get(BASE+'/backlog',headers=import_headers,params={'projectId':project.id,'search':needle})
    assert backlog.status_code==200,backlog.text
    assert [r['id'] for r in backlog.json()['backlog']]==[match.id]
    result=client.get(BASE+'/tags',headers=import_headers,params={'q':needle})
    assert result.status_code==200,result.text
    assert [r['id'] for r in result.json()]==[tags[1].id]
