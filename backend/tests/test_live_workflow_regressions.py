from app.ai_operator.pms_agent import bind_selected_project
from app.ai_operator.pms_agent import task_execution_mode
from app.ai_operator.suite import Plan, Step
from app.ai_operator.suite_tools import minimize_source


def test_frozen_project_fills_only_missing_required_project_adapter_targets():
    plan=Plan(summary='Review',steps=[
        Step(tool='pms.task_plan'),Step(tool='pms.schedule',record_id=90),
        Step(tool='pms.kickoff'),Step(tool='crm.update_task'),
        Step(tool='pms.update_milestone',record_id=75)])
    bind_selected_project(plan,89)
    assert [s.record_id for s in plan.steps]==[89,90,None,None,75]
    empty=Plan(summary='No selection',steps=[Step(tool='pms.task_plan')])
    bind_selected_project(empty,None)
    assert empty.steps[0].record_id is None


def test_task_edit_context_retains_bounded_description_without_private_extras():
    source={'id':42,'description':'existing task text','private_secret':'exclude'}
    assert minimize_source('crm.task',source)=={'id':42,'description':'existing task text'}
    assert 'description' not in minimize_source('crm.leads',source)
    assert len(minimize_source('crm.task',{'description':'x'*9000})['description'])==8000


def test_assignment_groups_commit_atomically_before_acl_invalidation():
    assert task_execution_mode({'plan':{'steps':[{'tool':'update_task','changes':{'assignee_user_ids':[1]}}]},'mode':'checkpointed'})=='atomic'
    assert task_execution_mode({'plan':{'steps':[{'tool':'update_task','changes':{'priority':'High'}}]},'mode':'checkpointed'})=='checkpointed'
