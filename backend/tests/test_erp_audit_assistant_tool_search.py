"""Literal queries in native assistant project read tools."""
import pytest
from tests.test_import_workspace import import_headers
from app.models.user import User
from app.ai_operator.assistant_tools import Intent,read_tool
from app.apps.project_management.models import PMSProject,PMSTask,PMSDocument,PMSCustomField
@pytest.mark.parametrize("needle",["%","_",chr(92),chr(92)+"%",chr(92)+"_","/"])
def test_assistant_read_queries_literal(client,db,import_headers,needle):
    actor=db.query(User).filter_by(email='testadmin@test.com').one()
    plain=PMSProject(name='Ordinary project',project_key='ORD',organization_id=1,manager_user_id=actor.id)
    match=PMSProject(name='QA'+needle+'Literal',project_key='MATCH',organization_id=1,manager_user_id=actor.id)
    foreign=PMSProject(name='QA'+needle+'Literal',project_key='FOREIGN',organization_id=2)
    db.add_all([plain,match,foreign]);db.flush()
    rows=[]
    for model,field,extra in [(PMSTask,'title',{'task_key':'TASK'}),(PMSDocument,'title',{'author_id':actor.id,'updated_by':actor.id}),(PMSCustomField,'name',{'field_type':'text'})]:
        values=[]
        for index,label in enumerate(['Ordinary','QA'+needle+'Literal']):
            attrs={**extra,'project_id':plain.id,field:label}
            if model is PMSTask:attrs['task_key']+=str(index)
            values.append(model(**attrs))
        db.add_all(values);rows.extend(values)
    from test_identity_utils import own_workflow_records
    own_workflow_records(db,plain,match,*rows);db.commit()
    result=read_tool(db,actor,Intent(tool='projects.search',query=needle))
    assert [r['id'] for r in result['items']]==[match.id]
    for tool,index in [('tasks.search',1),('documents.search',3),('custom_fields.get',5)]:
        result=read_tool(db,actor,Intent(tool=tool,project_id=plain.id,query=needle))
        assert [r['id'] for r in result['items']]==[rows[index].id]
