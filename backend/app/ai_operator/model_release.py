"""Server-only model release evidence. Training success is not release approval."""
import hashlib
import hmac
import json
import math
from datetime import datetime,timezone
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

POLICY='action-model-release-v1'
FILES=('bundle.json','dialogue.json','CRM.keras','PMS.keras','HRMS.keras','Sales.keras','dialogue.keras',
    'evaluation.json','dialogue-evaluation.json','conversation-evaluation.json','unseen-dialogue-evaluation.json','action-release-evaluation.json')

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def read(path):
    path=Path(path)
    if path.stat().st_size>25_000_000:raise ValueError('Release file exceeds size limit')
    return json.loads(path.read_text(encoding='utf-8'))

def file_hash(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size>25_000_000:raise ValueError('Invalid release artifact')
    return hashlib.sha256(path.read_bytes()).hexdigest()

def secret():
    from app.core.config import settings
    if len(settings.PLATFORM_SECRET_KEY)<32:raise ValueError('Platform release signing key is unavailable')
    return settings.PLATFORM_SECRET_KEY.encode()

def assess(folder,baseline=None):
    folder=Path(folder);checks=[]
    def check(name,ok,actual,target):checks.append({'name':name,'passed':bool(ok),'actual':actual,'required':target})
    def metric(value,minimum,maximum=1):return type(value) in (int,float) and math.isfinite(value) and minimum<=value<=maximum
    report=read(folder/'evaluation.json');dialogue=read(folder/'dialogue-evaluation.json')
    conversations=read(folder/'conversation-evaluation.json');unseen=read(folder/'unseen-dialogue-evaluation.json');native=read(folder/'action-release-evaluation.json')
    for module in ('CRM','PMS','HRMS'):
        item=report['modules'][module]
        check(module+' training coverage',item['training_commands']>=1000,item['training_commands'],'at least 1,000 authored/reviewed commands')
        check(module+' exemplar fit',metric(item.get('training_accuracy'),.99),item.get('training_accuracy'),'at least 0.99 on training exemplars; not generalization')
        check(module+' internal validation',metric(item['internal_validation_accuracy'],.8),item['internal_validation_accuracy'],'at least 0.80; synthetic internal split')
        check(module+' numeric parity',metric(item['portable_max_error'],0,1e-5),item['portable_max_error'],'at most 0.00001')
    check('Dialogue development',metric(dialogue['heldout_accuracy'],.85),dialogue['heldout_accuracy'],'at least 0.85; development data')
    check('Dialogue numeric parity',metric(dialogue['portable_max_error'],0,1e-5),dialogue['portable_max_error'],'at most 0.00001')
    check('Authored conversation scenarios',conversations['total']>=600 and conversations['passed']==conversations['total'] and not conversations.get('failures'),
        f"{conversations['passed']}/{conversations['total']}",'all scenarios; at least 600')
    natural=conversations.get('natural_actions')
    if natural:
        check('Conversational action programs',natural['total']>=100 and natural['passed']==natural['total'] and not natural.get('failures'),
            f"{natural['passed']}/{natural['total']}",'all authored workflow probes; at least 100')
    workplace=conversations.get('workplace_actions')
    if workplace:
        check('Workplace action regressions',workplace['total']>=150 and workplace['passed']==workplace['total'] and not workplace.get('failures'),
            f"{workplace['passed']}/{workplace['total']}",'all realistic authored scenarios; at least 150')
    workplace_v2=conversations.get('workplace_actions_v2')
    if workplace_v2:
        check('Workplace action batch 2',workplace_v2['total']>=150 and workplace_v2['passed']==workplace_v2['total'] and not workplace_v2.get('failures'),
            f"{workplace_v2['passed']}/{workplace_v2['total']}",'all fresh authored scenarios; at least 150')
    workplace_v3=conversations.get('workplace_actions_v3')
    if workplace_v3:
        check('Workplace action batch 3',workplace_v3['total']>=250 and workplace_v3['passed']==workplace_v3['total'] and not workplace_v3.get('failures'),
            f"{workplace_v3['passed']}/{workplace_v3['total']}",'all fresh authored scenarios; at least 250')
        fit=workplace_v3.get('training_fit') or {}
        check('Workplace batch 3 command fit',fit.get('total',0)>=250 and fit.get('passed')==fit.get('total') and not fit.get('failures'),
            f"{fit.get('passed',0)}/{fit.get('total',0)}",'all authored training commands prepare exact drafts; not generalization')
    workplace_v4=conversations.get('workplace_actions_v4')
    if workplace_v4:
        fit=workplace_v4.get('training_fit') or {}
        check('Workplace action batch 4',workplace_v4['total']>=150 and workplace_v4['passed']==workplace_v4['total'] and not workplace_v4.get('failures') and fit.get('total',0)>=150 and fit.get('passed')==fit.get('total') and not fit.get('failures'),
            {'scenarios':f"{workplace_v4['passed']}/{workplace_v4['total']}",'fit':f"{fit.get('passed',0)}/{fit.get('total',0)}"},'all 150+ fresh authored scenarios and training draft checks')
    workplace_v5=conversations.get('workplace_actions_v5')
    if workplace_v5:
        fit=workplace_v5.get('training_fit') or {}
        check('Workplace action batch 5',workplace_v5['total']>=150 and workplace_v5['passed']==workplace_v5['total'] and not workplace_v5.get('failures') and fit.get('total',0)>=150 and fit.get('passed')==fit.get('total') and not fit.get('failures'),
            {'scenarios':f"{workplace_v5['passed']}/{workplace_v5['total']}",'fit':f"{fit.get('passed',0)}/{fit.get('total',0)}"},'all 150+ fresh title-reference scenarios and training draft checks')
    check('Frozen unseen dialogue',unseen['total']>=120 and metric(unseen['passed']/max(unseen['total'],1),.75),
        unseen['passed']/max(unseen['total'],1),'at least 0.75 on 120+ frozen synthetic probes')
    check('Canonical actions and safety',native.get('model_sha256')==file_hash(folder/'bundle.json') and native.get('dialogue_sha256')==file_hash(folder/'dialogue.json') and native.get('tests',0)>=20 and native.get('failures')==0 and native.get('errors')==0 and native.get('skipped')==0,
        {k:native.get(k) for k in ('tests','failures','errors','skipped')},'all native integration tests; at least 20, none skipped')
    uploaded=report.get('uploaded_evaluation') or {}
    for split,counts in uploaded.items():
        check('Uploaded '+split,counts['total']>0 and counts['passed']/counts['total']>=.8,f"{counts['passed']}/{counts['total']}",'at least 0.80; never used as training labels')
    scores={'dialogue_development':dialogue['heldout_accuracy'],'unseen_dialogue':unseen['passed']/max(1,unseen['total'])}
    if baseline:
        for key,value in scores.items():check('Regression '+key,value>=baseline['scores'][key]-.02,value,f"at least {baseline['scores'][key]-.02:.4f}")
    return {'policy':POLICY,'passed':all(c['passed'] for c in checks),'checks':checks,'scores':scores,
        'limitations':'Small authored and synthetic evaluations, not production accuracy or a competitor benchmark. Neural predictions never authorize actions. Sales remains experimental. No customer queries or uploads are imported automatically.'}

def seal(folder,job_id,dataset_sha256,baseline=None):
    folder=Path(folder)
    from app.ai_operator.local_tensorflow import validate
    if validate(read(folder/'bundle.json')).get('training_scope')!={'platform':True}:raise ValueError('Not a platform model')
    from app.ai_operator.dialogue_tensorflow import read as read_dialogue
    path=folder/'dialogue.json';stat=path.stat();read_dialogue(str(path),stat.st_size,stat.st_mtime_ns)
    gate=assess(folder,baseline)
    value={'format':POLICY,'job_id':job_id,'dataset_sha256':dataset_sha256,'created_at':datetime.now(timezone.utc).isoformat(),
        'artifacts':{name:file_hash(folder/name) for name in FILES},'gate':gate}
    value['signature']=hmac.new(secret(),digest(value).encode(),hashlib.sha256).hexdigest()
    temporary=folder/('release-'+uuid4().hex+'.tmp');temporary.write_text(json.dumps(value,indent=2),encoding='utf-8');temporary.replace(folder/'release.json')
    return gate

@lru_cache(maxsize=16)
def _verify(folder,signature_key):
    folder=Path(folder);value=read(folder/'release.json');signature=value.pop('signature')
    expected=hmac.new(secret(),digest(value).encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,expected) or value.get('format')!=POLICY:raise ValueError('Release signature changed')
    if set(value['artifacts'])!=set(FILES):raise ValueError('Release evidence is incomplete')
    for name in FILES:
        if not hmac.compare_digest(file_hash(folder/name),value['artifacts'][name]):raise ValueError('Release artifact changed')
    # Recompute policy from immutable report files, not an editable passed flag.
    current=assess(folder)
    if not current['passed'] or not value['gate']['passed']:raise ValueError('Release gates did not pass')
    return value

def verify(folder,job_id=None):
    folder=Path(folder)
    stats=tuple((name,(folder/name).stat().st_size,(folder/name).stat().st_mtime_ns) for name in (*FILES,'release.json'))
    value=_verify(str(folder.resolve()),(stats,hashlib.sha256(secret()).hexdigest()))
    if job_id is not None and value['job_id']!=job_id:raise ValueError('Release job changed')
    return value

def pointer(platform_root,job_id,previous=None):
    platform_root=Path(platform_root)
    release=verify(platform_root/'runs'/str(job_id)/'model',job_id)
    value={'job_id':job_id,'release_sha256':file_hash(platform_root/'runs'/str(job_id)/'model/release.json'),
        'previous_job_id':previous,'activated_at':datetime.now(timezone.utc).isoformat()}
    temporary=platform_root/('active-'+uuid4().hex+'.tmp');temporary.write_text(json.dumps(value),encoding='utf-8');temporary.replace(platform_root/'active.json')
    return release
