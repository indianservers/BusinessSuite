"""Platform-only benchmark jobs reuse the local model storage and permissions."""
import json,subprocess,sys
from pathlib import Path
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException,BackgroundTasks
from app.platform_owner.auth import current_platform_admin
from app.platform_owner import service
from app.ai_operator.training_storage import root
from app.ai_operator.action_benchmark import manifest

router=APIRouter(prefix='/action-benchmarks',tags=['Platform action benchmarks'])


def admin(actor=Depends(current_platform_admin)):
    service.require(actor,'nlp.train');return actor


def directory(ident):
    try:value=str(UUID(ident))
    except (ValueError,TypeError):raise HTTPException(404,'Benchmark not found') from None
    return root()/'benchmarks'/value


def run(ident):
    folder=directory(ident)
    try:
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[2]/'scripts/run_action_benchmark.py'),'--output',str(folder)],cwd=Path(__file__).resolve().parents[2],timeout=1230,check=False)
    except subprocess.TimeoutExpired:
        (folder/'report.json').write_text(json.dumps({'status':'failed','error':'BENCHMARK_DEADLINE_EXCEEDED'}),encoding='utf-8')


@router.get('/manifest')
def get_manifest(actor=Depends(admin)):return manifest()


@router.post('')
def start(tasks:BackgroundTasks,actor=Depends(admin)):
    ident=str(uuid4());folder=directory(ident);folder.mkdir(parents=True,exist_ok=False)
    (folder/'report.json').write_text(json.dumps({'status':'queued','version':manifest()['version']}),encoding='utf-8')
    tasks.add_task(run,ident)
    return {'id':ident,'status':'queued','storage':'server-only','limits':manifest()['limits']}


@router.get('')
def listing(actor=Depends(admin)):
    base=root()/'benchmarks';items=[]
    if base.exists():
        for p in sorted(base.glob('*/report.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]:
            try:r=json.loads(p.read_text(encoding='utf-8'));items.append({'id':p.parent.name,**{k:r.get(k) for k in ('status','version','passed','failed','conversations','started_at')}})
            except (OSError,ValueError):continue
    return {'items':items}


@router.get('/{ident}')
def report(ident:str,actor=Depends(admin)):
    path=directory(ident)/'report.json'
    if not path.exists():raise HTTPException(404,'Benchmark not found')
    return json.loads(path.read_text(encoding='utf-8'))
