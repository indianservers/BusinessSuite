"""Server-owned training files. No model/download endpoint exposes these files."""
import json
import os
from uuid import uuid4
from pathlib import Path


def root():
    from app.core.config import settings
    return Path(os.environ.get('LOCAL_NLP_TRAINING_DIR') or settings.LOCAL_NLP_TRAINING_DIR or Path(__file__).resolve().parents[3]/'.local/nlp-training').resolve()


def run_dir(ident):
    if type(ident) is not int or ident<1:raise ValueError('Invalid training job')
    return root()/'runs'/str(ident)


def platform_active_bundle():
    try:
        path=root()/'platform/active.json'
        if path.stat().st_size>4096:return None
        value=json.loads(path.read_text(encoding='utf-8'));ident=value['job_id']
        if type(ident) is not int or ident<1:return None
        if value.get('release_sha256'):
            from app.ai_operator.model_release import verify,file_hash
            directory=root()/'platform/runs'/str(ident)/'model'
            if file_hash(directory/'release.json')!=value['release_sha256']:return None
            verify(directory,ident)
        return root()/'platform/runs'/str(ident)/'model/bundle.json'
    except (OSError,ValueError,KeyError,TypeError):return None


def pointer(scope):
    if not scope or type(scope.get('company_id')) is not int:return None
    parts=[scope['company_id'],scope.get('branch_id'),scope.get('workspace_id')]
    if any(v is not None and (type(v) is not int or v<1) for v in parts):return None
    return root()/'active'/('-'.join(str(v) if v is not None else 'all' for v in parts)+'.json')


def active_bundle(scope):
    path=pointer(scope)
    try:
        if not path or path.stat().st_size>4096:return None
        value=json.loads(path.read_text())
        return run_dir(value['job_id'])/'model/bundle.json'
    except (OSError,ValueError,KeyError,TypeError):return None


def active_id(scope):
    bundle=active_bundle(scope)
    return int(bundle.parents[1].name) if bundle else None


def activate(scope,ident):
    path=pointer(scope)
    if not path:raise ValueError('Invalid activation scope')
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.'+uuid4().hex+'.pending')
    tmp.write_text(json.dumps({'job_id':ident}),encoding='utf-8');tmp.replace(path)
