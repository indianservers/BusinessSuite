"""Explicit conversational proposals for signed native record webhooks."""
import pytest
from app.ai_operator.agent_builder import local_draft


@pytest.mark.parametrize('quoted', ['"Record.WhereChanged"', "'Record.WhereChanged'", '“Record.WhereChanged”'])
def test_webhook_authoring_retains_case_objective_and_limits(quoted):
    draft = local_draft(f'Create a CRM sales assistant that reviews leads when CRM webhook #42 receives event {quoted}', None, 'CRM')
    assert not draft.question
    assert draft.trigger.event == 'crm.webhook_received'
    assert draft.trigger.webhook_endpoint_id == 42
    assert draft.trigger.webhook_event == 'Record.WhereChanged'
    assert draft.run_prompt == 'reviews leads' and draft.schedule is None
    revised = local_draft('At most two preparations per day, cooldown 10 minutes', draft.model_dump(), 'CRM')
    assert revised.trigger.max_per_day == 2 and revised.trigger.min_interval_minutes == 10
    assert revised.trigger.webhook_endpoint_id == 42 and not revised.question
    changed = local_draft('When a deal enters a pipeline stage', revised.model_dump(), 'CRM')
    assert changed.trigger.event == 'crm.deal_stage'
    assert changed.trigger.webhook_endpoint_id is None and changed.trigger.webhook_event is None


def test_webhook_followup_collects_endpoint_and_event():
    first = local_draft('Create a CRM sales assistant that reviews leads when a webhook arrives', None, 'CRM')
    assert first.question and first.trigger is None
    second = local_draft('CRM webhook #42 event "record.changed"', first.model_dump(), 'CRM')
    assert not second.question and second.trigger.webhook_endpoint_id == 42
    assert second.run_prompt == 'reviews leads'


def test_webhook_module_does_not_expand_permissions():
    first = local_draft('Create a CRM sales assistant that reviews leads', None, 'CRM')
    draft = local_draft('When HRMS webhook #42 event "record.changed" arrives', first.model_dump(), 'CRM')
    assert draft.question and 'Include HRMS' in draft.question
    assert draft.trigger is None
