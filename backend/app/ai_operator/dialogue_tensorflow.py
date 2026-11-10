"""Safe numeric inference for a server-local, context-conditioned dialogue model."""
import json
import math
from functools import lru_cache
from pathlib import Path
from app.ai_operator.dialogue_corpus import VERSION,LEGACY_VERSION,LABELS,features,feature_weight
from app.ai_operator.local_tensorflow import artifact_path,forward,finite


@lru_cache(maxsize=8)
def read(path,size,mtime):
    if size>20_000_000:raise ValueError('Dialogue artifact too large')
    value=json.loads(Path(path).read_text(encoding='utf-8'))
    vocab=value['vocabulary'];idf=value['idf'];model=value['model']
    if value.get('format') not in {VERSION,LEGACY_VERSION} or model['labels']!=LABELS or not 1<=len(vocab)<=4096 or vocab!=sorted(set(vocab)) or len(idf)!=len(vocab) or not finite(idf):raise ValueError('Invalid dialogue vocabulary')
    if any(not isinstance(w,str) for w in vocab) or any(v<=0 for v in idf):raise ValueError('Invalid dialogue features')
    hidden=len(model['b1'])
    if not 1<=hidden<=128 or len(model['w1'])!=len(vocab) or len(model['w2'])!=hidden or len(model['b2'])!=len(LABELS):raise ValueError('Invalid dialogue dimensions')
    if not finite(model['b1']) or not finite(model['b2']) or any(len(r)!=hidden or not finite(r) for r in model['w1']) or any(len(r)!=len(LABELS) or not finite(r) for r in model['w2']):raise ValueError('Invalid dialogue weights')
    return value


def load(scope=None):
    try:
        path=artifact_path(scope).parent/'dialogue.json';stat=path.stat();bundle=read(str(path),stat.st_size,stat.st_mtime_ns)
        return bundle
    except (OSError,ValueError,KeyError,TypeError,OverflowError):return None


def predict(module,intent,pending,text,scope=None):
    try:
        bundle=load(scope)
        if not bundle:return None
        index={w:i for i,w in enumerate(bundle['vocabulary'])};count=features(module,intent,pending or '_approval',text,bundle['format'])
        raw={index[w]:(1+math.log(n))*bundle['idf'][index[w]]*feature_weight(w,bundle['format']) for w,n in count.items() if w in index};norm=math.sqrt(sum(v*v for v in raw.values())) or 1
        values=forward({i:v/norm for i,v in raw.items()},bundle['model']);ranked=sorted(range(len(values)),key=lambda i:-values[i])
        return {'act':LABELS[ranked[0]],'score':round(values[ranked[0]],5),'margin':round(values[ranked[0]]-values[ranked[1]],5),
                'engine':bundle['format'],'authorizes_execution':False}
    except (OSError,ValueError,KeyError,TypeError,OverflowError):return None
