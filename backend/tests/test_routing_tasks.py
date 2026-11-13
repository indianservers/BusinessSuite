"""Request shape and final-output attribution are independent of provider brands."""
from types import SimpleNamespace
import pytest
from app.ai_operator.routing_tasks import profile,final_provider,reviewed_output


@pytest.mark.parametrize(('spec','text','operation','complexity','features'),[
    ({'module':'CRM'},'Show leads','answer','simple',[]),
    ({'module':'CRM'},'Create a follow-up task','actions','simple',[]),
    ({'module':'CRM'},'Create a task then assign it','actions','complex',[]),
    ({'module':'CRM','mode':'summary'},'Create a task','answer','simple',[]),
    ({'module':'CRM'},'How do I create a task?','answer','simple',[]),
    ({'module':'PMS','attachment_ids':[7]},'Analyze this file','answer','complex',['uploads']),
    ({'module':'HRMS'},'Prepare an onboarding document','actions','complex',['artifacts']),
    ({'module':'CRM','artifact_id':8},'Revise its introduction','actions','complex',['artifacts']),
    ({'module':'PMS','workflow_id':4},'Review specialist findings','answer','complex',['workflow']),
    ({'module':'CRM','context':[{'tool':'crm.report'}]},'Show report','answer','standard',['reporting']),
])
def test_profile_classifies_work_without_granting_capabilities(spec,text,operation,complexity,features):
    result=profile(spec,text)
    assert (result['operation'],result['complexity'],result['features'])==(operation,complexity,features)
    assert result['version']==1


def test_profiles_are_stable_across_wording_but_separate_module_output_and_complexity():
    a=profile({'module':'CRM'},'Show leads')
    assert a==profile({'module':'CRM'},'List all visible leads')
    assert a!=profile({'module':'HRMS'},'Show employees')
    assert a!=profile({'module':'CRM','mode':'summary'},'Show leads')
    assert a!=profile({'module':'CRM'},'Create a task then assign it')
    cross=profile({'module':'CRM','context':[{'tool':'pms.tasks'}]},'Review work')
    assert cross['modules']==['CRM','PMS'] and cross['complexity']=='complex'


def test_only_final_provider_receives_review_credit_and_unfinished_outputs_are_excluded():
    run=SimpleNamespace(result={'intelligence':{'provider':'openai','model':'actual','engine':'provider'},
        'routing':{'selected_provider':'gemini','selected_model':'initial'}},status='answered',plan={'summary':'Answer','steps':[]})
    assert final_provider(run)==('openai','actual')
    assert reviewed_output(run,{'operation':'answer'})
    assert not reviewed_output(run,{'operation':'actions'})
    run.status='failed';assert not reviewed_output(run,None)
    run.status='awaiting_approval';run.plan={'steps':[{'tool':'crm.create_task'}]}
    assert reviewed_output(run,{'operation':'actions'})
    run.plan['question']='Which customer?';assert not reviewed_output(run,{'operation':'actions'})
    run.result['intelligence']={'provider':'auto','model':'initial','engine':'provider'}
    assert final_provider(run)==('gemini','initial')
    run.result['intelligence']['engine']='server';assert final_provider(run) is None
