"""Platform-only, synthetic/curated NLP workbooks; never opens customer databases."""
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4
from datetime import timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import update
from app.platform_owner.auth import current_platform_admin
from app.platform_owner.session import get_platform_db, platform_factory
from app.platform_owner.models import PlatformAdmin, PlatformRecord
from app.platform_owner import service as s
from app.ai_operator.training import parse_excel
from app.ai_operator.training_storage import root
from app.ai_operator.model_release import digest as dataset_digest

router=APIRouter(prefix='/nlp-training',tags=['Platform NLP training'])


def release_lock(db):
    """Serialize pointer changes across platform API processes, not just threads."""
    if db.get_bind().dialect.name=='postgresql':
        from sqlalchemy import text
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':741903628})


def trainer(actor=Depends(current_platform_admin)):
    s.require(actor,'nlp.train')
    if getattr(actor,'_api_scopes',None) is not None:raise HTTPException(403,'Interactive platform session required')
    return actor


def record(db,ident,kind):
    row=db.query(PlatformRecord).filter_by(id=ident,kind=kind).first()
    if not row:raise HTTPException(404,'Training record not found')
    return row


def public(row):
    data=row.data or {}
    return {'id':row.id,'name':row.title,'status':row.state,'created_at':row.created_at,
            **{key:data[key] for key in ('counts','dataset_id','epochs','metrics','error','release','evaluation') if key in data}}


@router.get('')
def listing(actor=Depends(trainer),db=Depends(get_platform_db)):
    rows=db.query(PlatformRecord).filter(PlatformRecord.kind.in_(['nlp_dataset','nlp_training'])).order_by(PlatformRecord.id.desc()).limit(100).all()
    active=None
    try:active=json.loads((root()/'platform/active.json').read_text())['job_id']
    except (OSError,ValueError,KeyError,TypeError):pass
    previous=None
    try:previous=json.loads((root()/'platform/active.json').read_text()).get('previous_job_id')
    except (OSError,ValueError,TypeError):pass
    integrity='authored' if active is None else 'legacy'
    if active is not None:
        try:
            pointer_data=json.loads((root()/'platform/active.json').read_text())
            if pointer_data.get('release_sha256'):
                from app.ai_operator.model_release import verify,file_hash
                folder=root()/'platform/runs'/str(active)/'model';verify(folder,active)
                if file_hash(folder/'release.json')!=pointer_data['release_sha256']:raise ValueError('Pointer changed')
                integrity='verified'
        except (OSError,ValueError,KeyError,TypeError):integrity='invalid'
    return {'datasets':[public(r) for r in rows if r.kind=='nlp_dataset'],
            'jobs':[public(r) for r in rows if r.kind=='nlp_training'],'active_job_id':active,'active_integrity':integrity,'previous_job_id':previous,'storage':str(root().parent),
            'release_policy':'action-model-release-v1','learning_policy':'Only reviewed, privacy-approved synthetic/anonymized datasets are used. Feedback is not an automatic training label.'}


@router.get('/template')
def template(actor=Depends(trainer)):
    return FileResponse(Path(__file__).resolve().parents[1]/'ai_operator/assets/nlp-training-template.xlsx',filename='nlp-training-template.xlsx')


@router.post('/datasets')
async def upload(file:UploadFile=File(...),name:str=Form('Training commands'),actor=Depends(trainer),db=Depends(get_platform_db)):
    if not (file.filename or '').lower().endswith('.xlsx'):raise HTTPException(422,'Upload an .xlsx workbook')
    raw=await file.read(5_000_001)
    rows,counts=parse_excel(raw,max_rows=4000)
    row=PlatformRecord(kind='nlp_dataset',title=name.strip()[:180] or 'Training commands',state='pending',owner_id=actor.id,
        data={'samples':rows,'counts':counts})
    db.add(row);db.flush();s.event(db,actor,'nlp.dataset.uploaded',entity_id=row.id);db.commit()
    return public(row)


class Review(BaseModel):
    privacy_reviewed:bool=False


@router.post('/datasets/{ident}/approve')
def approve(ident:int,data:Review,actor=Depends(trainer),db=Depends(get_platform_db)):
    if not data.privacy_reviewed:raise HTTPException(422,'Review every row and remove all customer/personal/secret data first')
    row=record(db,ident,'nlp_dataset');row.state='approved'
    row.data={**row.data,'reviewed_by':actor.id,'privacy_reviewed':True}
    s.event(db,actor,'nlp.dataset.approved',entity_id=ident);db.commit();return public(row)


@router.delete('/datasets/{ident}')
def remove(ident:int,actor=Depends(trainer),db=Depends(get_platform_db)):
    row=record(db,ident,'nlp_dataset');row.state='deleted';row.data={'counts':row.data['counts']}
    s.event(db,actor,'nlp.dataset.deleted',entity_id=ident);db.commit();return public(row)


class Train(BaseModel):
    dataset_id:int=Field(gt=0)
    epochs:int=Field(default=220,ge=50,le=400)
    request_key:UUID


@router.post('/jobs')
def queue(data:Train,background:BackgroundTasks,actor=Depends(trainer),db=Depends(get_platform_db)):
    key=s.digest('nlp-training:'+str(actor.id)+':'+str(data.request_key))
    old=db.query(PlatformRecord).filter_by(kind='nlp_training',token_hash=key).first()
    if old:
        if old.data['dataset_id']!=data.dataset_id or old.data['epochs']!=data.epochs:raise HTTPException(409,'Request key already used')
        return public(old)
    dataset=record(db,data.dataset_id,'nlp_dataset')
    if dataset.state!='approved':raise HTTPException(422,'Approve the dataset before training')
    if not any(r['split']=='train' for r in dataset.data['samples']):raise HTTPException(422,'Dataset needs training rows')
    if db.query(PlatformRecord).filter(PlatformRecord.kind=='nlp_training',PlatformRecord.state.in_(['queued','training'])).count()>=2:
        raise HTTPException(409,'Two training runs are already queued/running')
    row=PlatformRecord(kind='nlp_training',title=dataset.title,state='queued',owner_id=actor.id,token_hash=key,
        data={'dataset_id':dataset.id,'dataset_sha256':dataset_digest(dataset.data['samples']),'epochs':data.epochs,'counts':dataset.data['counts']})
    db.add(row);db.flush();s.event(db,actor,'nlp.training.queued',entity_id=row.id);db.commit()
    background.add_task(run_background,row.id)
    return public(row)


def valid_source(db,job):
    actor=db.get(PlatformAdmin,job.owner_id)
    dataset=record(db,job.data['dataset_id'],'nlp_dataset')
    if not actor or not actor.is_active or 'nlp.train' not in s.permissions(actor) or dataset.state!='approved':
        raise ValueError('Training authorization or dataset approval changed')
    from app.ai_operator.model_release import digest
    if job.data.get('dataset_sha256') and digest(dataset.data['samples'])!=job.data['dataset_sha256']:
        raise ValueError('Reviewed dataset contents changed')
    return actor,dataset


def baseline_release():
    from app.ai_operator.model_release import verify
    try:
        ident=json.loads((root()/'platform/active.json').read_text())['job_id']
        return verify(root()/'platform/runs'/str(ident)/'model',ident)['gate']
    except (OSError,ValueError,KeyError,TypeError):return None


def native_evaluation(directory):
    repo=Path(__file__).resolve().parents[3]
    subprocess.run([sys.executable,str(repo/'backend/scripts/evaluate_action_release.py'),'--model-dir',str(directory/'model')],
        cwd=repo/'backend',check=True,timeout=630,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    dialogue=json.loads((directory/'model/dialogue-evaluation.json').read_text(encoding='utf-8'))
    if dialogue.get('message_dialogue_version'):
        subprocess.run([sys.executable,str(repo/'backend/scripts/evaluate_message_action_release.py'),'--model-dir',str(directory/'model')],
            cwd=repo/'backend',check=True,timeout=1080,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def process(db,ident):
    claimed=db.execute(update(PlatformRecord).where(PlatformRecord.id==ident,PlatformRecord.kind=='nlp_training',PlatformRecord.state=='queued').values(state='training'))
    db.commit()
    if claimed.rowcount!=1:return
    job=db.get(PlatformRecord,ident)
    try:
        actor,dataset=valid_source(db,job)
        directory=root()/'platform/runs'/str(ident);directory.mkdir(parents=True,exist_ok=True)
        samples=dataset.data['samples']
        rows=[{'module':r['module'],'intent':r['intent'],'text':r['text']} for r in samples if r['split']=='train']
        (directory/'reviewed.json').write_text(json.dumps({'format':'reviewed-nlp-queries-v1','training_scope':{'platform':True},'examples':rows}),encoding='utf-8')
        heldout=[r for r in samples if r['split']!='train']
        (directory/'holdout.json').write_text(json.dumps(heldout),encoding='utf-8')
        repo=Path(__file__).resolve().parents[3]
        python=Path(os.environ.get('LOCAL_NLP_TRAINING_PYTHON') or repo/'.local/tensorflow-venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python'))
        with (directory/'training.log').open('w',encoding='utf-8') as log:
            subprocess.run([str(python),str(repo/'backend/scripts/train_tensorflow_local_nlp.py'),'--output',str(directory/'model'),
                '--epochs',str(job.data['epochs']),'--reviewed-examples',str(directory/'reviewed.json'),
                '--evaluation-examples',str(directory/'holdout.json')],cwd=repo/'backend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
            subprocess.run([str(python),str(repo/'backend/scripts/train_action_dialogue.py'),'--output',str(directory/'model')],
                cwd=repo/'backend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
            subprocess.run([sys.executable,str(repo/'backend/scripts/benchmark_action_dialogue.py'),'--model-dir',str(directory/'model')],
                cwd=repo/'backend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
            subprocess.run([sys.executable,str(repo/'backend/scripts/benchmark_unseen_dialogue.py'),'--model-dir',str(directory/'model')],
                cwd=repo/'backend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        db.expire_all();job=db.get(PlatformRecord,ident);valid_source(db,job)
        if job.state!='training':return
        native_evaluation(directory)
        db.expire_all();job=db.get(PlatformRecord,ident);actor,dataset=valid_source(db,job)
        if job.state!='training':return
        from app.ai_operator.model_release import seal,digest
        release=seal(directory/'model',job.id,digest(dataset.data['samples']),baseline_release())
        report=json.loads((directory/'model/evaluation.json').read_text())
        metrics={k:v for k,v in report.items() if k in {'modules','uploaded_evaluation','tensorflow_version','training_examples'}}
        dialogue=json.loads((directory/'model/dialogue-evaluation.json').read_text())
        metrics['dialogue']={k:dialogue[k] for k in ('training_turns','heldout_turns','training_accuracy','heldout_accuracy','portable_max_error','limits')}
        conversation=json.loads((directory/'model/conversation-evaluation.json').read_text())
        metrics['conversations']={k:conversation[k] for k in ('total','passed','by_kind','limits')}
        unseen=json.loads((directory/'model/unseen-dialogue-evaluation.json').read_text())
        metrics['unseen_dialogue']={k:unseen[k] for k in ('total','passed','accuracy','by_class','limits')}
        # Do not expose raw evaluation failures or example text through metrics.
        if isinstance(metrics.get('uploaded_evaluation'),dict):
            metrics['uploaded_evaluation']={k:v for k,v in metrics['uploaded_evaluation'].items() if k in {'passed','total'}}
        job.state='succeeded';job.data={**job.data,'metrics':metrics,'release':release}
        s.event(db,actor,'nlp.training.succeeded',entity_id=ident);db.commit()
    except Exception:
        db.rollback();job=db.get(PlatformRecord,ident)
        if job and job.state=='training':
            job.state='failed';job.data={**job.data,'error':'Training failed or approval changed. Check the private server training log.'};db.commit()


def run_background(ident):
    with platform_factory()() as db:process(db,ident)


@router.post('/jobs/{ident}/activate')
def activate(ident:int,actor=Depends(trainer),db=Depends(get_platform_db)):
    release_lock(db)
    job=record(db,ident,'nlp_training')
    if job.state!='succeeded':raise HTTPException(409,'Only successful runs can be activated')
    if (job.data.get('evaluation') or {}).get('state') in {'queued','running'}:raise HTTPException(409,'Wait for candidate evaluation before activation')
    try:valid_source(db,job)
    except ValueError:raise HTTPException(409,'Dataset approval or training permission changed')
    directory=root()/'platform'
    from app.ai_operator.model_release import verify,pointer,digest,assess
    try:
        release=verify(directory/'runs'/str(ident)/'model',ident)
        _,dataset=valid_source(db,job)
        if release['dataset_sha256']!=digest(dataset.data['samples']):raise ValueError('Source changed')
        prior=None
        if (directory/'active.json').exists():prior=json.loads((directory/'active.json').read_text())['job_id']
        if prior==ident:return {'active_job_id':ident}
        if not assess(directory/'runs'/str(ident)/'model',baseline_release())['passed']:raise ValueError('Candidate regresses against the active release')
        pointer(directory,ident,previous=prior)
    except (OSError,ValueError,KeyError,TypeError):raise HTTPException(409,'Evaluate and pass the signed model release gates before activation')
    s.event(db,actor,'nlp.model.activated',entity_id=ident);db.commit();return {'active_job_id':ident}


@router.post('/jobs/{ident}/evaluate')
def queue_evaluation(ident:int,background:BackgroundTasks,actor=Depends(trainer),db=Depends(get_platform_db)):
    release_lock(db)
    job=record(db,ident,'nlp_training')
    if job.state!='succeeded':raise HTTPException(409,'Evaluate a completed training run')
    try:
        active=json.loads((root()/'platform/active.json').read_text())
        if active.get('job_id')==ident and active.get('release_sha256'):
            raise HTTPException(409,'Active releases are immutable. Train a separate candidate to evaluate new changes.')
    except (OSError,ValueError,TypeError):pass
    try:_,dataset=valid_source(db,job)
    except ValueError:raise HTTPException(409,'Source approval changed')
    if (job.data.get('evaluation') or {}).get('state') in {'queued','running'}:raise HTTPException(409,'Evaluation is already queued or running')
    from app.ai_operator.model_release import digest
    job.data={**job.data,'dataset_sha256':digest(dataset.data['samples']),'evaluation':{'state':'queued'}}
    db.commit();s.event(db,actor,'nlp.evaluation.queued',entity_id=ident);db.commit()
    background.add_task(evaluate_background,ident)
    return public(job)


def evaluate_background(ident):
    with platform_factory()() as db:evaluate(db,ident)


def evaluate(db,ident):
    job=record(db,ident,'nlp_training')
    data=job.data or {}
    changed=db.execute(update(PlatformRecord).where(PlatformRecord.id==ident,PlatformRecord.state=='succeeded',
        PlatformRecord.data['evaluation']['state'].as_string()=='queued').values(data={**data,'evaluation':{'state':'running'}}))
    db.commit()
    if changed.rowcount!=1:return
    job=record(db,ident,'nlp_training')
    try:
        actor,dataset=valid_source(db,job);directory=root()/'platform/runs'/str(ident)
        repo=Path(__file__).resolve().parents[3]
        for script in ('benchmark_action_dialogue.py','benchmark_unseen_dialogue.py'):
            subprocess.run([sys.executable,str(repo/'backend/scripts'/script),'--model-dir',str(directory/'model')],cwd=repo/'backend',check=True,timeout=120,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        native_evaluation(directory)
        release_lock(db)
        db.expire_all();job=record(db,ident,'nlp_training');actor,dataset=valid_source(db,job)
        from app.ai_operator.model_release import seal,digest
        gate=seal(directory/'model',ident,digest(dataset.data['samples']),baseline_release())
        job.data={**job.data,'release':gate,'evaluation':{'state':'passed' if gate['passed'] else 'blocked'}}
        if gate['passed']:
            try:
                path=root()/'platform/active.json';active=json.loads(path.read_text())
                if active.get('job_id')==ident and not active.get('release_sha256'):
                    from app.ai_operator.model_release import pointer
                    pointer(root()/'platform',ident,previous=active.get('previous_job_id'))
            except (OSError,ValueError,KeyError,TypeError):pass
        s.event(db,actor,'nlp.evaluation.finished',entity_id=ident);db.commit()
    except Exception:
        db.rollback();job=record(db,ident,'nlp_training')
        job.data={**job.data,'evaluation':{'state':'failed','error':'Evaluation failed. Active model unchanged; inspect the private server logs.'}}
        db.commit()


@router.post('/rollback')
def rollback(actor=Depends(trainer),db=Depends(get_platform_db)):
    release_lock(db)
    from app.ai_operator.model_release import pointer
    try:
        active=json.loads((root()/'platform/active.json').read_text());previous=active['previous_job_id']
        if type(previous) is not int:raise ValueError('No verified previous model')
        job=record(db,previous,'nlp_training');valid_source(db,job)
        pointer(root()/'platform',previous,previous=active['job_id'])
    except (OSError,ValueError,KeyError,TypeError):raise HTTPException(409,'No valid, approved previous release is available')
    s.event(db,actor,'nlp.model.rolled_back',entity_id=previous);db.commit();return {'active_job_id':previous}


@router.post('/reset')
def reset(actor=Depends(trainer),db=Depends(get_platform_db)):
    release_lock(db)
    (root()/'platform/active.json').unlink(missing_ok=True)
    s.event(db,actor,'nlp.model.reset');db.commit();return {'active_job_id':None}
