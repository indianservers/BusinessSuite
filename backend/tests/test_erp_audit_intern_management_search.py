"""Literal Interns Hub performance, distribution and task selection."""
import pytest
from tests.test_intern_management import program
from tests.test_interns_hub import interns
from tests.rich_text_test_utils import organization_context
from app.apps.interns_hub.performance import filtered_employees
from app.apps.interns_hub.distribution import recipients
from app.apps.interns_hub.management_api import project_tasks
from app.apps.project_management.models import PMSTask
@pytest.mark.parametrize("needle",["%","_",chr(92),chr(92)+"%",chr(92)+"_","/"])
def test_intern_selection_search_literal(db,program,needle):
    actor=program['admin'];first=program['interns'][0][0];second=program['interns'][1][0]
    first.first_name='QA'+needle+'Literal';second.first_name='Ordinary'
    ordinary=PMSTask(project_id=program['project'].id,title='Ordinary task',task_key='ORD')
    match=PMSTask(project_id=program['project'].id,title='QA'+needle+'Literal',task_key='MATCH')
    from app.models.employee import EmployeeEducation,EmployeeSkill
    db.add_all([ordinary,match,EmployeeEducation(employee_id=first.id,degree='BSc',institution='QA'+needle+'College'),EmployeeEducation(employee_id=second.id,degree='BSc',institution='Ordinary College'),EmployeeSkill(employee_id=first.id,skill_name='QA'+needle+'Skill'),EmployeeSkill(employee_id=second.id,skill_name='Ordinary Skill')]);db.flush()
    from test_identity_utils import own_workflow_records
    own_workflow_records(db,ordinary,match);db.commit()
    assert [e.id for e in filtered_employees(db,actor,{'search':needle}).all()]==[first.id]
    assert [e.id for e in recipients(db,actor,{'target_type':'all','search':needle}).all()]==[first.id]
    assert [e.id for e in filtered_employees(db,actor,{'college':needle}).all()]==[first.id]
    assert [e.id for e in filtered_employees(db,actor,{'skill':needle}).all()]==[first.id]
    result=project_tasks(project_id=program['project'].id,search=needle,page=1,per_page=1,user=actor,db=db)
    assert result['total']==1
    assert [r['id'] for r in result['items']]==[match.id]
    assert [e.id for e in filtered_employees(db,actor,{'search':'ORDINARY'}).all()]==[second.id]
