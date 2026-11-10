"""Portable forward pass for TensorFlow-trained Dense/ReLU/Softmax classifiers.

The ERP does not import TensorFlow or execute serialized model code. Training
exports verified numeric weights; parity against TensorFlow is a release gate.
"""
import hashlib
import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path

from app.ai_operator.local_corpus import VERSION,FAMILIES,examples

FORMAT='tensorflow-local-intents-v1'
FEATURES='redacted-slots-tfidf-bigrams-v2'


def corpus_hash():
    return hashlib.sha256(json.dumps(examples(),ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def artifact_path(scope=None):
    from app.ai_operator.training_storage import active_bundle
    private=active_bundle(scope)
    if private is not None:return private
    from app.ai_operator.training_storage import platform_active_bundle
    platform=platform_active_bundle()
    if platform is not None:return platform
    from app.core.config import settings
    return Path(os.environ.get('LOCAL_NLP_MODEL_DIR') or settings.LOCAL_NLP_MODEL_DIR or Path(__file__).resolve().parents[3]/'.local/local-tensorflow-v1')/'bundle.json'


def finite(values):
    return all(type(value) in (int,float) and math.isfinite(value) and abs(value)<1000 for value in values)


def validate(bundle):
    from app.ai_operator.local_features import fit
    if not isinstance(bundle,dict) or not isinstance(bundle.get('models'),dict):raise ValueError('Invalid bundle structure')
    if bundle.get('format')!=FORMAT or bundle.get('feature_version')!=FEATURES or bundle.get('corpus_version')!=VERSION or bundle.get('corpus_sha256')!=corpus_hash():
        raise ValueError('Model/corpus version mismatch')
    vocab=bundle['vocabulary']; idf=bundle['idf']
    expected=fit()[1]
    adaptive=bundle.get('vocabulary_source')=='reviewed-training' and bundle.get('training_scope') is not None
    if not isinstance(vocab,list) or len(vocab)>4096 or len(idf)!=len(vocab) or not finite(idf):
        raise ValueError('Feature vocabulary mismatch')
    if adaptive:
        if vocab!=sorted(set(vocab)) or not set(expected)<=set(vocab) or any(not isinstance(word,str) or not re.fullmatch(r'[a-z0-9 ]{1,160}',word) for word in vocab) or any(value<=0 for value in idf):
            raise ValueError('Invalid reviewed feature vocabulary')
    elif vocab!=sorted(expected) or any(abs(idf[i]-expected[word])>1e-10 for i,word in enumerate(vocab)):
        raise ValueError('Feature vocabulary mismatch')
    if set(bundle['models'])!=set(FAMILIES):raise ValueError('Incomplete module models')
    scope=bundle.get('training_scope')
    if scope is not None and scope!={'platform':True}:
        if not isinstance(scope,dict) or set(scope)!={'company_id','branch_id','workspace_id'} or type(scope['company_id']) is not int or scope['company_id']<1:
            raise ValueError('Invalid training scope')
        if any(scope[k] is not None and (type(scope[k]) is not int or scope[k]<1) for k in ('branch_id','workspace_id')):
            raise ValueError('Invalid training scope')
    for module,model in bundle['models'].items():
        labels=model['labels']; hidden=len(model['b1'])
        if labels!=sorted(FAMILIES[module]) or not 1<=hidden<=128:raise ValueError('Invalid model labels/dimensions')
        if len(model['w1'])!=len(vocab) or len(model['w2'])!=hidden or len(model['b2'])!=len(labels):raise ValueError('Invalid layer dimensions')
        if not finite(model['b1']) or not finite(model['b2']):raise ValueError('Invalid bias')
        if any(len(row)!=hidden or not finite(row) for row in model['w1']):raise ValueError('Invalid input weights')
        if any(len(row)!=len(labels) or not finite(row) for row in model['w2']):raise ValueError('Invalid output weights')
    return bundle


@lru_cache(maxsize=2)
def _load(path,mtime,size):
    if size>20_000_000:raise ValueError('Artifact exceeds size limit')
    return validate(json.loads(Path(path).read_text(encoding='utf-8')))


def load(scope=None):
    path=artifact_path(scope)
    try:
        stat=path.stat()
        return _load(str(path),stat.st_mtime_ns,stat.st_size)
    except (OSError,ValueError,TypeError,KeyError,OverflowError):
        return None


def vector(text,bundle):
    from app.ai_operator.local_features import features
    count=features(text); raw={i:(1+math.log(count[word]))*bundle['idf'][i] for i,word in enumerate(bundle['vocabulary']) if count.get(word)}
    norm=math.sqrt(sum(value*value for value in raw.values()))
    return {i:value/norm for i,value in raw.items()} if norm else {}


def forward(sparse,model):
    hidden=list(model['b1'])
    for index,value in sparse.items():
        for j,weight in enumerate(model['w1'][index]):hidden[j]+=value*weight
    hidden=[max(0,value) for value in hidden]
    logits=[bias+sum(hidden[i]*model['w2'][i][j] for i in range(len(hidden))) for j,bias in enumerate(model['b2'])]
    peak=max(logits);values=[math.exp(value-peak) for value in logits];denom=sum(values)
    return [value/denom for value in values]


def runtime_scope(db,user,workspace_id=None):
    if db is None:return None
    from app.ai_agents.security import company
    return {'company_id':company(user),'branch_id':getattr(db.info.get('branch_context'),'branch_id',None),'workspace_id':workspace_id}


def scope_matches(bundle,scope):
    required=bundle.get('training_scope')
    return required is None or required=={'platform':True} or required==scope


def predict(text,module,scope=None):
    bundle=load(scope)
    if not bundle or not scope_matches(bundle,scope):return None
    sparse=vector(text,bundle)
    if not sparse:return None
    model=bundle['models'][module]; probabilities=forward(sparse,model)
    ranked=sorted(range(len(probabilities)),key=lambda i:-probabilities[i])
    return {'intent':model['labels'][ranked[0]],'score':probabilities[ranked[0]],'margin':probabilities[ranked[0]]-probabilities[ranked[1]],
            'reviewed_training':bool(bundle.get('training_scope')),'feature_support':len(sparse)/max(1,len(__import__('app.ai_operator.local_features',fromlist=['features']).features(text))),
            'engine':FORMAT,'tensorflow_version':bundle['tensorflow_version'],'used':False,
            'score_note':'Softmax model score, not a calibrated correctness probability'}


def status(scope=None):
    from app.ai_operator.dialogue_tensorflow import load as dialogue_load
    bundle=load(scope)
    if bundle and not scope_matches(bundle,scope):bundle=None
    release=None
    if bundle:
        path=artifact_path(scope)
        ident=path.parent.parent.name
        release={'job_id':int(ident) if ident.isdecimal() else None,
            'scope':'platform' if bundle.get('training_scope')=={'platform':True} else 'scoped' if bundle.get('training_scope') else 'authored',
            'dataset_sha256':bundle.get('reviewed_dataset_sha256')}
    return {'active':bool(bundle),'engine':FORMAT if bundle else 'retrieval-rules-fallback',
            'description':'TensorFlow-trained neural intent models + typed rules' if bundle else 'Local retrieval + typed rules; TensorFlow artifact missing or incompatible',
            'tensorflow_version':bundle.get('tensorflow_version') if bundle else None,
            'training_commands':bundle.get('training_commands') if bundle else None,'release':release,
            'dialogue_model':{'active':bool(bundle and dialogue_load(scope)),'execution_policy':'Typed validation and explicit action review remain required'}}
