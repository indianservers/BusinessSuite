"""Pinned legacy PMS TensorFlow classifier, evaluated only on the server.

This preserves the existing grammar's advisory classification gate. It grants
no record access, generates no actions, and is not the unified dialogue model.
"""
import hashlib
import json
import math
import re
import struct
from functools import lru_cache

HASHES={'model.json':'94d1e01b7dd631bbe6fe496d10b71818f413372a4a5ce57720d5a4d27361ee73',
        'weights.bin':'026adc0db50e1ae823e59bf92a98e03248a6681ccfe7844dfc763d9422be111e'}


def directory():
    from app.ai_operator.training_storage import root
    return root()/'legacy-pms-router/v3'


def tokens(text):
    text=text.lower()
    for pattern,replacement in [(r'\bkey [a-z][a-z0-9_-]*','key slotkey'),
        (r'\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b',' slotuser '),
        (r'\b[a-z][a-z0-9]*-\d+\b',' slotkey '),(r'"[^"]*"',' slottext '),
        (r'\b\d{4}-\d{2}-\d{2}\b',' slotdate '),(r'\b\d+\b',' slotnumber ')]:
        text=re.sub(pattern,replacement,text,flags=re.ASCII)
    return re.findall('[a-z]+',text)


@lru_cache(maxsize=1)
def _load(raw,weights):
    if hashlib.sha256(raw).hexdigest()!=HASHES['model.json'] or hashlib.sha256(weights).hexdigest()!=HASHES['weights.bin']:
        raise ValueError('PMS routing model integrity check failed')
    metadata=json.loads(raw)['userDefinedMetadata']
    width=len(metadata['vocabulary']);classes=len(metadata['intents'])
    values=struct.unpack('<'+str((width+1)*classes)+'f',weights)
    if not all(math.isfinite(x) for x in values):raise ValueError('Nonfinite routing weights')
    return metadata,values[:width*classes],values[width*classes:]


def load():
    folder=directory()
    raw=(folder/'model.json').read_bytes();weights=(folder/'weights.bin').read_bytes()
    if len(raw)>20000 or len(weights)>100000:raise ValueError('Oversized routing model')
    return _load(raw,weights)


def probabilities(text,model):
    metadata,kernel,bias=model;words=set(tokens(text));classes=len(bias)
    active=[i for i,word in enumerate(metadata['vocabulary']) if word in words]
    logits=[bias[j]+sum(kernel[i*classes+j] for i in active) for j in range(classes)]
    maximum=max(logits);exponents=[math.exp(value-maximum) for value in logits];total=sum(exponents)
    return [value/total for value in exponents],len(active)/max(len(words),1)


def classify(texts):
    model=load();metadata=model[0];predictions=[]
    for text in texts:
        scores,known=probabilities(text,model)
        order=sorted(range(len(scores)),key=lambda i:scores[i],reverse=True);best,second=order[:2]
        intent=metadata['intents'][best];confidence=scores[best]
        predictions.append({'intent':intent,'confidence':confidence,'accepted':intent!='fallback' and confidence>=metadata['threshold'] and confidence-scores[second]>=metadata['margin'] and known>=.9})
    return {'predictions':predictions,'trainingExamples':metadata['trainingExamples'],
        'runtime':'server','model_version':'legacy-pms-router-v3','cloud_calls':0}
