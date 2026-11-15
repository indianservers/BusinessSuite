import pytest
from app.ai_operator.local_nlp import semantic_intent
@pytest.mark.parametrize('text',['List PMS projects','show projects','Please get PMS projects?','Display projects.'])
def test_project_read_exact(text):assert semantic_intent(text,'PMS')=='projects.list'
@pytest.mark.parametrize('text',['Create PMS projects','List PMS projects and delete them','List PMS projects secretly','PMS projects','List CRM projects'])
def test_project_near_miss(text):assert semantic_intent(text,'PMS')!='projects.list'
@pytest.mark.parametrize('text',['Summarize the report','Summarise this report','please summarize report?'])
def test_report_read_has_explicit_same_module_context(text):assert semantic_intent(text,'CRM',('crm.report',))=='summary'
@pytest.mark.parametrize('module,tools',[('CRM',()),('CRM',('crm.tasks',)),('CRM',('crm.report','crm.tasks')),('PMS',('crm.report',)),('HRMS',('crm.report',))])
def test_report_context_is_not_unscoped_or_other_source(module,tools):assert semantic_intent('Summarize the report',module,tools)!='summary'
@pytest.mark.parametrize('text',['Summarize the report and update tasks','Create report','Summarize the report; send email','Summarize the report without approval'])
def test_report_mutation_or_bypass_not_read(text):assert semantic_intent(text,'CRM',('crm.report',))!='summary'
