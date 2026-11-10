"""Dependency-free reader for explicitly reviewed, single-scope training exports."""
import hashlib
import json
from pathlib import Path
from app.ai_operator.local_corpus import FAMILIES


def load_reviewed(path):
    path=Path(path)
    if path.stat().st_size>15_000_000:raise ValueError('Reviewed training export exceeds size limit')
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict) or value.get('format')!='reviewed-nlp-queries-v1':raise ValueError('Use the approved NLP-query export format')
    scope=value.get('training_scope')
    platform=scope=={'platform':True}
    if not platform and (not isinstance(scope,dict) or set(scope)!={'company_id','branch_id','workspace_id'} or type(scope.get('company_id')) is not int or scope['company_id']<1):
        raise ValueError('Reviewed exports need one explicit company/branch/workspace scope')
    if not platform and any(scope[key] is not None and (type(scope[key]) is not int or scope[key]<1) for key in ('branch_id','workspace_id')):
        raise ValueError('Invalid training scope')
    rows=value.get('examples')
    if not isinstance(rows,list) or not 1<=len(rows)<=4000:raise ValueError('Use 1–4000 approved examples')
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'module','intent','text'}:raise ValueError('Only curated module/intent/text examples are accepted')
        if row['module'] not in FAMILIES or row['intent'] not in FAMILIES[row['module']]:raise ValueError('Unknown module/intent; implement the capability before training it')
        if not isinstance(row['text'],str) or not 3<=len(row['text'])<=6000:raise ValueError('Invalid training text')
    digest=hashlib.sha256(json.dumps({'scope':scope,'examples':rows},sort_keys=True).encode()).hexdigest()
    return rows,scope,digest
