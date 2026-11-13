"""Exact core v1 compatibility and fingerprints independent of business input."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.ai_operator import prompt_registry as registry
from app.ai_operator.prompt_provenance import compatible

BASELINE=json.loads((Path(__file__).parent/'fixtures/core_prompt_v1_baseline.json').read_text())


@pytest.mark.parametrize('purpose',list(BASELINE['instructions']))
def test_v1_retains_exact_previous_instruction_bytes(purpose):
    text,manifest=registry.render(purpose,BASELINE['schema'])
    assert registry.sha(text)==BASELINE['instructions'][purpose]
    assert manifest['instruction_sha256']==BASELINE['instructions'][purpose]
    assert manifest['version']==1 and manifest['format']=='core-prompt-v1'


def test_templates_are_immutable_and_unknown_revisions_are_not_selected():
    with pytest.raises(TypeError):registry.TEMPLATES['authorized-json'][1]='User override'
    with pytest.raises(TypeError):registry.ACTIVE['authorized-json']=9
    with pytest.raises(ValueError):registry.render('suite_plan',{},version=9)
    items=registry.catalog();assert len(items)==5 and all(i['active'] for i in items)
    assert all('instruction' not in i and 'template' not in i for i in items)


def test_schema_and_exact_instruction_fingerprints_have_distinct_meanings():
    a={'type':'object','properties':{'summary':{'type':'string'}}}
    b=dict(reversed(list(a.items())))
    _,one=registry.render('suite_plan',a);_,two=registry.render('suite_plan',b)
    assert one['template_sha256']==two['template_sha256']
    assert one['schema_sha256']==two['schema_sha256']
    assert one['instruction_sha256']!=two['instruction_sha256']


def test_only_exact_logged_prompt_revision_qualifies_current_task_evidence():
    _,expected=registry.render('suite_plan',BASELINE['schema'])
    log=SimpleNamespace(id=5,provider='gemini',model='test-model')
    run=SimpleNamespace(result={'prompt_versions':[{**expected,'api_log_id':5,'provider':'gemini','model':'test-model','status':'success'}]})
    assert compatible(run,log,expected)
    for key in ('version','template_sha256','schema_sha256','instruction_sha256'):
        changed={**expected,key:'changed'};assert not compatible(run,log,changed)
    run.result={};assert not compatible(run,log,expected)
    assert compatible(run,log,None)  # Global historical statistics remain inspectable.
