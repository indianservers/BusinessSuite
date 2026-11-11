import hashlib,json
from pathlib import Path
from uuid import uuid4
import pytest
from app.ai_operator import builder_tensorflow as local
from app.ai_operator.agent_builder_corpus import VERSION,PHRASES,examples


def bundle():
    labels=sorted(PHRASES);weights=[0.0]*len(labels);weights[labels.index('lead-qualification')]=10.0
    return {'format':'tensorflow-agent-builder-v1','corpus_version':VERSION,'tensorflow_version':'unit-test',
        'training_commands':640,'labels':labels,'vocabulary':['lead'],'idf':[1.0],
        'corpus_sha256':hashlib.sha256(json.dumps(examples(),sort_keys=True).encode()).hexdigest(),
        'model':{'w1':[[1.0]],'b1':[0.0],'w2':[weights],'b2':[0.0]*len(labels)}}


def test_numeric_release_is_verified_and_tampering_disables_it(tmp_path,monkeypatch):
    monkeypatch.setattr(local,'root',lambda:tmp_path)
    monkeypatch.setattr(local,'secret',lambda:b'only-for-isolated-builder-tests')
    directory=tmp_path/'releases'/str(uuid4());directory.mkdir(parents=True)
    (directory/'bundle.json').write_text(json.dumps(bundle()),encoding='utf-8')
    (directory/'dataset.json').write_text('{}',encoding='utf-8');(directory/'builder.keras').write_bytes(b'never executed by API')
    report={'training_commands':640,'training_accuracy':1.0,'development_commands':48,'development_accuracy':.9,'portable_max_error':1e-7,'limits':'Isolated test artifact'}
    (directory/'evaluation.json').write_text(json.dumps(report),encoding='utf-8')
    assert local.activate(directory)['active']
    assert local.predict('lead')['label']=='lead-qualification'
    (directory/'bundle.json').write_text('{}',encoding='utf-8')
    assert local.load() is None


@pytest.mark.parametrize('mutation',['labels','weights','corpus'])
def test_builder_numeric_model_rejects_invalid_shape_or_provenance(mutation):
    data=bundle()
    if mutation=='labels':data['labels']=['invented']
    elif mutation=='weights':data['model']['w1']=[[float('nan')]]
    else:data['corpus_sha256']='changed'
    with pytest.raises(ValueError):local.validate(data)
