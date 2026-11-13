"""Transparent request-shape matching, never a permission or model quality score."""
import re
from app.ai_operator.suite_tools import TOOLS


def profile(request,text):
    from app.ai_operator.artifacts import creation_request
    sources=request.get('context') or []
    modules={request['module']} if request.get('module') else set()
    modules.update(TOOLS[s['tool']].module for s in sources if s.get('tool') in TOOLS)
    if request.get('project_id'):modules.add('PMS')
    features=set()
    if request.get('attachment_ids'):features.add('uploads')
    if request.get('workflow_id'):features.add('workflow')
    if request.get('artifact_id') or any('artifact' in s.get('tool','') for s in sources):features.add('artifacts')
    artifact_write=creation_request(text) or bool(re.search(r'\b(?:create|write|edit|revise|prepare|generate)\b.*\b(?:document|spreadsheet|presentation|dashboard|chart|artifact)\b',text,re.I|re.S))
    if artifact_write:features.add('artifacts')
    if any(s.get('tool','').endswith('.report') for s in sources) or re.search(r'\b(?:reports?|analysis|analytics)\b',text,re.I):features.add('reporting')
    action=artifact_write or bool(re.search(r'\b(?:create|update|assign|schedule|send|delete|remove|convert|approve|edit|revise|change|move|set)\b',text,re.I))
    if re.match(r'\s*(?:how|why|what does|explain how)\b',text,re.I):action=False
    operation='actions' if request.get('mode')!='summary' and action else 'answer'
    complex_task=bool(len(modules)>1 or features&{'uploads','workflow','artifacts'} or len(sources)>3 or
        len(request.get('task_ids') or [])>5 or len(text)>1500 or re.search(r'\b(?:then|after that|multi.step|dependencies)\b',text,re.I))
    standard=len(sources)>1 or len(request.get('task_ids') or [])>1 or len(text)>240 or bool(features)
    return {'version':1,'modules':sorted(modules),'operation':operation,
            'complexity':'complex' if complex_task else 'standard' if standard else 'simple',
            'features':sorted(features),'output_schema':'summary' if request.get('mode')=='summary' else 'plan'}


def final_provider(run):
    result=run.result or {};intelligence=result.get('intelligence') or {}
    if intelligence.get('engine')=='server':return None
    provider=intelligence.get('provider')
    if provider=='auto':
        decision=result.get('routing') or {}
        return decision.get('selected_provider'),decision.get('selected_model')
    return provider,intelligence.get('model')


def reviewed_output(run,task):
    if run.status in {'failed','needs_reconciliation','planning','needs_clarification'}:return False
    if not task:return True
    plan=run.plan or {}
    if plan.get('question'):return False
    return bool(plan.get('steps')) if task['operation']=='actions' else not plan.get('steps')
