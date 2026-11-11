"""Verified numeric inference for the separate TensorFlow builder-role model."""
import hashlib,hmac,json,math
from functools import lru_cache
from pathlib import Path
from uuid import UUID
from app.ai_operator.agent_builder_corpus import VERSION,PHRASES,examples
from app.ai_operator.local_tensorflow import finite,vector,forward
from app.ai_operator.model_release import file_hash,digest,secret

FILES=('bundle.json','evaluation.json','dataset.json','builder.keras')


def root():
    from app.ai_operator.training_storage import root as storage_root
    return storage_root()/'agent-builder'


def validate(bundle):
    if not isinstance(bundle,dict):raise ValueError('Invalid builder model')
    if bundle.get('format')!='tensorflow-agent-builder-v1' or bundle.get('corpus_version')!=VERSION or bundle.get('labels')!=sorted(PHRASES):raise ValueError('Builder model version/labels differ')
    if bundle.get('corpus_sha256')!=hashlib.sha256(json.dumps(examples(),sort_keys=True).encode()).hexdigest():raise ValueError('Builder corpus changed')
    vocab=bundle['vocabulary'];idf=bundle['idf'];model=bundle['model'];hidden=len(model['b1']);outputs=len(bundle['labels'])
    if not isinstance(vocab,list) or not 1<=len(vocab)<=4096 or vocab!=sorted(set(vocab)) or any(not isinstance(v,str) or len(v)>160 for v in vocab):raise ValueError('Invalid builder vocabulary')
    if len(idf)!=len(vocab) or not finite(idf) or any(v<=0 for v in idf):raise ValueError('Invalid builder feature weights')
    if not 1<=hidden<=128 or len(model['w1'])!=len(vocab) or len(model['w2'])!=hidden or len(model['b2'])!=outputs:raise ValueError('Invalid builder dimensions')
    if not finite(model['b1']) or not finite(model['b2']) or any(len(r)!=hidden or not finite(r) for r in model['w1']) or any(len(r)!=outputs or not finite(r) for r in model['w2']):raise ValueError('Invalid numeric builder weights')
    return bundle


@lru_cache(maxsize=2)
def verified(folder,stamp):
    directory=Path(folder);release=json.loads((directory/'release.json').read_text(encoding='utf-8'));signature=release.pop('signature')
    if not hmac.compare_digest(signature,hmac.new(secret(),digest(release).encode(),hashlib.sha256).hexdigest()):raise ValueError('Invalid builder release signature')
    if release.get('policy')!='builder-model-release-v1' or not release.get('passed') or set(release['files'])!=set(FILES):raise ValueError('Builder release is not approved')
    for name in FILES:
        if file_hash(directory/name)!=release['files'][name]:raise ValueError('Builder release changed')
    return validate(json.loads((directory/'bundle.json').read_text(encoding='utf-8'))),json.loads((directory/'evaluation.json').read_text(encoding='utf-8'))


def load():
    try:
        pointer=root()/'active.json'
        if pointer.stat().st_size>4096:return None
        ident=str(UUID(json.loads(pointer.read_text(encoding='utf-8'))['release']))
        directory=root()/'releases'/ident
        if not directory.resolve().is_relative_to(root().resolve()):return None
        names=(*FILES,'release.json');stamp=tuple((name,(directory/name).stat().st_mtime_ns,(directory/name).stat().st_size) for name in names)
        if any(size>10_000_000 for _,_,size in stamp):return None
        return verified(str(directory),stamp)
    except (OSError,ValueError,KeyError,TypeError,OverflowError):return None


def predict(text):
    active=load()
    if not active:return None
    bundle,_=active;sparse=vector(text,bundle)
    if not sparse:return None
    values=forward(sparse,bundle['model']);ranked=sorted(range(len(values)),key=lambda i:-values[i])
    return {'label':bundle['labels'][ranked[0]],'score':values[ranked[0]],'margin':values[ranked[0]]-values[ranked[1]],'engine':bundle['format']}


def status():
    active=load()
    if not active:return {'active':False,'engine':'typed-builder-fallback'}
    bundle,report=active
    return {'active':True,'engine':bundle['format'],'tensorflow_version':bundle['tensorflow_version'],'training_commands':report['training_commands'],
        'development_commands':report['development_commands'],'development_accuracy':report['development_accuracy'],'limits':report['limits']}


def activate(directory):
    directory=Path(directory).resolve();base=(root()/'releases').resolve()
    if directory.parent!=base:raise ValueError('Use a private server release folder')
    ident=str(UUID(directory.name));bundle=validate(json.loads((directory/'bundle.json').read_text(encoding='utf-8')))
    report=json.loads((directory/'evaluation.json').read_text(encoding='utf-8'))
    if any(type(report.get(k)) not in (int,float) or not math.isfinite(report[k]) for k in ('training_commands','training_accuracy','development_accuracy','portable_max_error')):raise ValueError('Invalid builder evaluation metrics')
    if report['training_commands']<600 or not .99<=report['training_accuracy']<=1 or not .80<=report['development_accuracy']<=1 or not 0<=report['portable_max_error']<=1e-5:raise ValueError('Builder model quality gates failed')
    release={'policy':'builder-model-release-v1','passed':True,'corpus_version':VERSION,'files':{name:file_hash(directory/name) for name in FILES}}
    release['signature']=hmac.new(secret(),digest(release).encode(),hashlib.sha256).hexdigest()
    (directory/'release.json').write_text(json.dumps(release),encoding='utf-8')
    temporary=root()/'active.tmp';temporary.write_text(json.dumps({'release':ident}),encoding='utf-8');temporary.replace(root()/'active.json')
    verified.cache_clear();return status()
