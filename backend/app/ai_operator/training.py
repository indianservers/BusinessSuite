"""Excel dataset review and durable, server-only TensorFlow training jobs."""
from collections import Counter
from datetime import datetime,timedelta,timezone
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID
from zipfile import ZipFile,BadZipFile

from fastapi import APIRouter,BackgroundTasks,Depends,File,Form,HTTPException,Query,UploadFile
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.ai_operator.local_corpus import FAMILIES,examples
from app.ai_operator.local_features import features
from app.ai_operator.query_models import NlpDataset,NlpQuery
from app.ai_operator.query_memory import sanitize,private,branch_id,SCOPES,visible
from app.ai_operator.suite_tools import Strict
from app.apps.automation.models import AutomationScheduledJob as Job
from app.ai_operator import training_storage as storage

def platform_training_only():
    raise HTTPException(403, 'Training is available only in the platform administrator portal')

router=APIRouter(prefix='/suite/training',tags=['Server local NLP training'],dependencies=[Depends(platform_training_only)])


def admin(db,user,workspace_id=None,modules=()):
    platform_training_only()
    from app.ai_agents.api import _require_ai_admin
    from app.ai_operator.suite import authorize,MODULES
    from app.access.service import check_background_access
    _require_ai_admin(user);authorize(db,user,workspace_id)
    if not branch_id(db):raise HTTPException(422,'Select a concrete branch for private training data and models')
    for module in modules:
        native=MODULES[SCOPES[module]]
        authorize(db,user,workspace_id,SCOPES[module]);check_background_access(db,user,native,'view')
        if not user.is_superuser and (getattr(user,'_suite_grants',{}) or {}).get(native,{}).get('scope') not in {'all','company','organization'}:
            raise HTTPException(403,'Company-level visibility is required for each training module')


def datasets(db,user,workspace_id):
    from app.ai_agents.security import company
    return db.query(NlpDataset).filter_by(company_id=company(user),branch_id=branch_id(db),workspace_id=workspace_id)


def fingerprint(row):return (row['module'],tuple(sorted(features(row['text']).items())))


def parse_excel(content,max_rows=2000):
    import openpyxl
    if len(content)>5_000_000:raise HTTPException(413,'Workbook limit is 5 MB')
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(info.file_size for info in archive.infolist())>20_000_000:raise HTTPException(413,'Workbook expands beyond 20 MB')
            if any(info.filename.lower().endswith('vbaproject.bin') for info in archive.infolist()):raise HTTPException(422,'Macros are not accepted')
        workbook=openpyxl.load_workbook(BytesIO(content),read_only=True,data_only=False,keep_links=False)
    except HTTPException:raise
    except Exception:raise HTTPException(422,'Upload a valid .xlsx workbook') from None
    errors=[];result=[];seen={}
    base={fingerprint(r):r['intent'] for r in examples()}
    # Platform fitting includes this authored baseline even when it is not in
    # the workbook. Such phrases cannot be advertised as unseen holdouts.
    from app.ai_operator.expanded_corpus import examples as expanded_examples
    holdout_base=set(base)|{fingerprint(r) for r in expanded_examples(60)}
    try:
        if 'Commands' not in workbook.sheetnames:raise HTTPException(422,'Add a Commands worksheet with module, query, intent, split columns')
        sheet=workbook['Commands']
        if sheet.max_row and sheet.max_row>max_rows+1:raise HTTPException(413,f'Use at most {max_rows} rows per workbook')
        rows=sheet.iter_rows(max_row=max_rows+2,max_col=5)
        header=next(rows,None)
        if not header or [str(c.value or '').strip().lower() for c in header[:4]]!=['module','query','intent','split']:
            raise HTTPException(422,'Commands row 1 must be: module, query, intent, split')
        for number,cells in enumerate(rows,2):
            if all(c.value is None for c in cells):continue
            if number>max_rows+1:raise HTTPException(413,f'Use at most {max_rows} rows')
            if any(c.data_type=='f' for c in cells):errors.append({'row':number,'message':'Formula cells are not allowed'});continue
            module,text,intent,split=[str(c.value or '').strip() for c in cells[:4]]
            module={'SRM':'Sales','HR':'HRMS'}.get(module.upper(),next((m for m in FAMILIES if m.lower()==module.lower()),module))
            split=split.lower() or 'train'
            if module not in FAMILIES or intent not in FAMILIES.get(module,{}):errors.append({'row':number,'message':'Use a module and intent from the Intents worksheet'});continue
            if not 3<=len(text)<=6000 or split not in {'train','validation','test'}:errors.append({'row':number,'message':'Query must have 3–6000 characters; split must be train, validation or test'});continue
            text=sanitize(text);sample={'module':module,'text':text,'intent':intent,'split':split};key=fingerprint(sample)
            if key in seen:
                if seen[key]!=(intent,split):errors.append({'row':number,'message':'Conflicting label or split for an equivalent query'})
                continue
            if key in base and base[key]!=intent:errors.append({'row':number,'message':'Label conflicts with a built-in command'});continue
            if split!='train' and key in holdout_base:errors.append({'row':number,'message':'Holdout query already occurs in authored training; use an unseen phrase'});continue
            seen[key]=(intent,split);result.append(sample)
            if len(errors)>=100:break
    finally:workbook.close()
    if errors:raise HTTPException(422,{'message':'Workbook validation failed; no dataset saved','rows':errors})
    if not result:raise HTTPException(422,'Workbook has no usable command rows')
    return result,{'total':len(result),'modules':dict(Counter(r['module'] for r in result)),'splits':dict(Counter(r['split'] for r in result)),
                   'base_duplicates':sum(fingerprint(r) in base for r in result)}


@router.get('/template')
def template(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    admin(db,user)
    path=Path(__file__).parent/'assets/nlp-training-template.xlsx'
    if not path.exists():raise HTTPException(503,'Training template is not installed')
    return FileResponse(path,filename='NLP-training-template.xlsx',media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Cache-Control':'private, no-store'})


@router.get('/datasets')
def list_datasets(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    admin(db,user,workspace_id)
    rows=datasets(db,user,workspace_id).filter(NlpDataset.status!='deleted').order_by(NlpDataset.id.desc()).limit(100).all()
    permitted=[]
    for row in rows:
        try:admin(db,user,workspace_id,row.counts['modules']);permitted.append(row)
        except HTTPException:pass
    return private({'items':[{'id':r.id,'name':r.name,'counts':r.counts,'status':r.status,'revision':r.revision,'created_at':r.created_at,'preview':r.samples[:12]} for r in permitted],
                    'intents':{m:list(values) for m,values in FAMILIES.items()}})


@router.post('/datasets')
async def upload(file:UploadFile=File(...),name:str=Form('Uploaded commands'),workspace_id:int|None=Form(None),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_agents.security import company
    from app.ai_operator.service import digest
    admin(db,user,workspace_id)
    if not (file.filename or '').lower().endswith('.xlsx'):raise HTTPException(422,'Use .xlsx; macros and legacy .xls files are not accepted')
    content=await file.read(5_000_001)
    samples,counts=parse_excel(content);admin(db,user,workspace_id,counts['modules'])
    row=NlpDataset(company_id=company(user),branch_id=branch_id(db),workspace_id=workspace_id,created_by=user.id,
        name=sanitize(name)[:180] or 'Uploaded commands',samples=samples,counts=counts,content_hash=digest(samples),status='pending')
    db.add(row);db.commit();return private({'id':row.id,'counts':counts,'status':row.status,'revision':row.revision})


class DatasetReview(Strict):
    revision:int=Field(ge=1)
    approved:bool
    privacy_reviewed:bool=False


@router.put('/datasets/{ident}')
def review_dataset(ident:int,data:DatasetReview,workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    admin(db,user,workspace_id)
    row=datasets(db,user,workspace_id).filter_by(id=ident).with_for_update().first()
    if not row or row.status=='deleted':raise HTTPException(404,'Dataset not found')
    admin(db,user,workspace_id,row.counts['modules'])
    if row.revision!=data.revision:raise HTTPException(409,'Dataset changed; reload')
    if data.approved and not data.privacy_reviewed:raise HTTPException(422,'Confirm the labels and removal of private/customer information')
    row.status='approved' if data.approved else 'rejected';row.reviewed_by=user.id;row.revision+=1;db.commit()
    return private({'id':row.id,'status':row.status,'revision':row.revision})


@router.delete('/datasets/{ident}')
def delete_dataset(ident:int,workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    admin(db,user,workspace_id)
    row=datasets(db,user,workspace_id).filter_by(id=ident).with_for_update().first()
    if not row:raise HTTPException(404,'Dataset not found')
    if row.status!='deleted':admin(db,user,workspace_id,row.counts['modules'])
    row.status='deleted';row.samples=[];row.counts={};row.revision+=1;db.commit();return private({'deleted':True})


class Train(Strict):
    request_key:UUID
    dataset_ids:list[int]=Field(default_factory=list,max_length=20)
    include_queries:bool=False
    workspace_id:int|None=Field(default=None,gt=0)
    epochs:int=Field(default=220,ge=50,le=400)


def jobs(db,user,workspace_id):
    from app.ai_agents.security import company
    return db.query(Job).filter_by(job_type='ai_nlp_training',organization_id=company(user)).filter(Job.payload_json['branch_id'].as_integer()==branch_id(db),
        Job.payload_json['workspace_id'].as_integer()==workspace_id if workspace_id is not None else Job.payload_json['workspace_id'].as_integer().is_(None))


def sources_valid(db,user,payload):
    for ident,revision in payload.get('datasets',{}).items():
        row=datasets(db,user,payload['workspace_id']).filter_by(id=int(ident),status='approved',revision=revision).first()
        if not row:raise HTTPException(409,'A source dataset was removed or its approval changed')
    for ident,revision in payload.get('queries',{}).items():
        row=db.query(NlpQuery).filter_by(id=int(ident),company_id=payload['company_id'],branch_id=payload['branch_id'],review_status='approved',privacy_reviewed=True,revision=revision).first()
        if not row:raise HTTPException(409,'A reviewed query changed or was deleted')
        visible(db,user,row)


def public_job(row):
    value=row.payload_json or {}
    return {'id':row.id,'status':row.status.removeprefix('ai_'),'created_at':row.created_at,'epochs':value.get('epochs'),
            'counts':value.get('counts'),'metrics':value.get('metrics'),'error':row.last_error,'started_at':value.get('started_at'),'finished_at':value.get('finished_at')}


@router.post('/jobs')
def queue(data:Train,background:BackgroundTasks,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_agents.security import company
    from app.ai_operator.service import digest
    from app.models.company import Company
    admin(db,user,data.workspace_id)
    signature=digest(data.model_dump(mode='json',exclude={'request_key'}))
    existing=jobs(db,user,data.workspace_id).filter_by(created_by=user.id).filter(Job.payload_json['ai_request_key'].as_string()==str(data.request_key)).first()
    if existing:
        if existing.payload_json['signature']!=signature:raise HTTPException(409,'Request key belongs to another training request')
        return private(public_job(existing))
    db.query(Company).filter_by(id=company(user)).with_for_update().first()
    if jobs(db,user,data.workspace_id).filter(Job.status.in_(['ai_queued','ai_training'])).count()>=2:raise HTTPException(409,'Wait for an active training job in this scope')
    samples=[];dataset_revisions={};query_revisions={}
    for ident in sorted(set(data.dataset_ids)):
        row=datasets(db,user,data.workspace_id).filter_by(id=ident,status='approved').first()
        if not row:raise HTTPException(422,'Select approved datasets in this branch/workspace')
        samples.extend(row.samples);dataset_revisions[str(row.id)]=row.revision
    if data.include_queries:
        rows=db.query(NlpQuery).filter_by(company_id=company(user),branch_id=branch_id(db),workspace_id=data.workspace_id,review_status='approved',privacy_reviewed=True).order_by(NlpQuery.id).limit(2001).all()
        for row in rows:
            visible(db,user,row)
            samples.append({'module':row.reviewed_module,'intent':row.reviewed_intent,'text':row.training_text,'split':'train'});query_revisions[str(row.id)]=row.revision
    if not samples or len(samples)>2000:raise HTTPException(422,'Select 1–2000 approved training/evaluation examples')
    admin(db,user,data.workspace_id,{r['module'] for r in samples})
    seen={};dedup=[]
    for sample in samples:
        key=fingerprint(sample)
        if key in seen:
            if seen[key]!=(sample['intent'],sample['split']):raise HTTPException(422,'Conflicting labels or train/test leakage across selected sources')
            continue
        seen[key]=(sample['intent'],sample['split']);dedup.append(sample)
    if not any(r['split']=='train' for r in dedup):raise HTTPException(422,'Add at least one approved train row')
    payload={'company_id':company(user),'branch_id':branch_id(db),'workspace_id':data.workspace_id,'epochs':data.epochs,'samples':dedup,
        'datasets':dataset_revisions,'queries':query_revisions,'ai_request_key':str(data.request_key),'signature':signature,
        'counts':{'examples':len(dedup),'modules':dict(Counter(r['module'] for r in dedup)),'splits':dict(Counter(r['split'] for r in dedup))}}
    row=Job(organization_id=company(user),created_by=user.id,job_type='ai_nlp_training',module_name='ai',status='ai_queued',run_at=datetime.now(timezone.utc),payload_json=payload)
    db.add(row)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Training request already queued; reload jobs') from None
    background.add_task(run_background,row.id)
    return private(public_job(row))


@router.get('/jobs')
def list_jobs(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.local_tensorflow import runtime_scope,status
    admin(db,user,workspace_id)
    rows=jobs(db,user,workspace_id).order_by(Job.id.desc()).limit(50).all()
    permitted=[]
    for row in rows:
        try:admin(db,user,workspace_id,row.payload_json['counts']['modules']);permitted.append(row)
        except HTTPException:pass
    scope=runtime_scope(db,user,workspace_id)
    return private({'items':[public_job(r) for r in permitted],'active_model':status(scope),'active_job_id':storage.active_id(scope),
                    'storage':'Server/local only. No weights or training process run in the browser.'})


@router.post('/jobs/{ident}/cancel')
def cancel_job(ident:int,workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    admin(db,user,workspace_id)
    row=jobs(db,user,workspace_id).filter_by(id=ident).with_for_update().first()
    if not row:raise HTTPException(404,'Training job not found')
    admin(db,user,workspace_id,row.payload_json['counts']['modules'])
    if row.status in {'ai_queued','ai_training'}:row.status='ai_cancelled';db.commit()
    return private(public_job(row))


@router.post('/jobs/{ident}/activate')
def activate_job(ident:int,workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.local_tensorflow import validate,runtime_scope
    admin(db,user,workspace_id)
    row=jobs(db,user,workspace_id).filter_by(id=ident,status='ai_succeeded').first()
    if not row:raise HTTPException(409,'Only successful jobs can be activated')
    admin(db,user,workspace_id,row.payload_json['counts']['modules']);sources_valid(db,user,row.payload_json)
    try:
        bundle=validate(json.loads((storage.run_dir(row.id)/'model/bundle.json').read_text()))
        scope=runtime_scope(db,user,workspace_id)
        if bundle.get('training_scope')!=scope:raise ValueError('Model scope mismatch')
        storage.activate(scope,row.id)
    except (OSError,ValueError,KeyError,TypeError):raise HTTPException(409,'Model artifact is missing or incompatible; train again') from None
    return private({'activated':True,'job_id':row.id,'scope':scope})


@router.post('/models/reset')
def reset_model(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.local_tensorflow import runtime_scope,status
    admin(db,user,workspace_id)
    scope=runtime_scope(db,user,workspace_id);path=storage.pointer(scope)
    if path:path.unlink(missing_ok=True)
    return private({'reset':True,'active_model':status(scope)})


def training_python():
    configured=os.environ.get('LOCAL_NLP_TRAINING_PYTHON')
    if configured:return Path(configured)
    candidate=Path(__file__).resolve().parents[3]/'.local/tensorflow-venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    return candidate if candidate.is_file() else Path(sys.executable)


def process_training(db,target_id=None):
    from app.access.service import activate_run_context,release_run_context,background_scope
    instant=datetime.now(timezone.utc)
    # A killed worker has no publish authority. Retraining is explicit.
    for stale in db.query(Job).filter_by(job_type='ai_nlp_training',status='ai_training').filter(Job.run_at<instant).limit(10):
        stale.status='ai_failed';stale.last_error='WORKER_INTERRUPTED; queue a fresh training run'
    db.commit()
    query=db.query(Job).filter_by(job_type='ai_nlp_training',status='ai_queued')
    if target_id:query=query.filter_by(id=target_id)
    row=query.order_by(Job.id).with_for_update(skip_locked=True).first()
    if not row:return {'processed':0}
    ident=row.id;payload=dict(row.payload_json);actor=db.query(User).filter_by(id=row.created_by,is_active=True).first()
    claimed=db.query(Job).filter_by(id=ident,status='ai_queued').update({'status':'ai_training','run_at':instant+timedelta(minutes=5)},synchronize_session=False)
    if not claimed:db.rollback();return {'processed':0}
    row.payload_json={**payload,'started_at':instant.isoformat()};db.commit()
    try:
        if not actor:raise HTTPException(403,'Training owner is unavailable')
        activate_run_context(db,actor,SimpleNamespace(scope_key=f'company:{row.organization_id}'))
        with background_scope(db,actor,'ai','configure',branch_id=payload['branch_id']):
            admin(db,actor,payload['workspace_id'],payload['counts']['modules']);sources_valid(db,actor,payload)
            directory=storage.run_dir(ident);directory.mkdir(parents=True,exist_ok=True)
            scope={key:payload[key] for key in ('company_id','branch_id','workspace_id')}
            source={'format':'reviewed-nlp-queries-v1','training_scope':scope,'examples':[{k:r[k] for k in ('module','intent','text')} for r in payload['samples'] if r['split']=='train']}
            (directory/'reviewed.json').write_text(json.dumps(source),encoding='utf-8')
            holdout=[r for r in payload['samples'] if r['split']!='train']
            (directory/'holdout.json').write_text(json.dumps(holdout),encoding='utf-8')
            script=Path(__file__).resolve().parents[2]/'scripts/train_tensorflow_local_nlp.py'
            with (directory/'training.log').open('w',encoding='utf-8') as log:
                completed=subprocess.run([str(training_python()),str(script),'--reviewed-examples',str(directory/'reviewed.json'),'--output',str(directory/'model'),
                    '--epochs',str(payload['epochs']),'--evaluation-examples',str(directory/'holdout.json')],stdout=log,stderr=subprocess.STDOUT,timeout=240,cwd=script.parents[1])
            db.expire_all();row=db.query(Job).filter_by(id=ident).with_for_update().one()
            if row.status=='ai_cancelled':db.commit();return {'processed':1,'cancelled':1}
            admin(db,actor,payload['workspace_id'],payload['counts']['modules']);sources_valid(db,actor,payload)
            if completed.returncode:raise RuntimeError('TRAINING_FAILED; check the server training runtime and dataset')
            metrics=json.loads((directory/'model/evaluation.json').read_text())
            metrics.pop('development_paraphrases',None)  # Raw failures stay in the private server report.
            row.status='ai_succeeded';row.last_error=None;row.payload_json={**row.payload_json,'metrics':metrics,'finished_at':datetime.now(timezone.utc).isoformat()};db.commit()
    except (HTTPException,RuntimeError,ValueError,OSError,subprocess.TimeoutExpired):
        db.rollback();row=db.query(Job).filter_by(id=ident).first()
        if row and row.status!='ai_cancelled':row.status='ai_failed';row.last_error='Training failed or source access changed. Check the server runtime, labels and approvals.';db.commit()
    finally:release_run_context(db)
    return {'processed':1}


def run_background(ident):
    from app.db.session import SessionLocal
    with SessionLocal() as db:process_training(db,ident)
