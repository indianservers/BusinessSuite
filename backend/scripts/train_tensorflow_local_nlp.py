"""Train four genuine TensorFlow intent networks; export Keras + safe portable weights."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS','0')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    import numpy as np
    import tensorflow as tf
    from app.ai_operator.local_corpus import VERSION,FAMILIES
    from app.ai_operator.local_features import fit
    from app.ai_operator.local_tensorflow import FORMAT,FEATURES,corpus_hash,validate,vector,forward
    # The isolated TensorFlow environment deliberately has no ERP/Pydantic dependencies.
    backend_root=Path(__file__).resolve().parents[1]
    configured=os.environ.get('LOCAL_NLP_MODEL_DIR')
    if not configured and (backend_root/'.env').exists():
        for line in (backend_root/'.env').read_text(encoding='utf-8-sig').splitlines():
            key,sep,value=line.partition('=')
            if sep and key.strip()=='LOCAL_NLP_MODEL_DIR':
                configured=value.strip().strip('\"\'')
    base_output=Path(configured) if configured else backend_root/'../.local/local-tensorflow-v1'
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default=str(base_output.resolve()))
    parser.add_argument('--epochs',type=int,default=220)
    parser.add_argument('--reviewed-examples',help='Approved JSON export from the NLP query review API')
    parser.add_argument('--evaluation-examples',help='Separate sanitized validation/test rows; never used for training')
    args=parser.parse_args()
    if not 20<=args.epochs<=1000:parser.error('epochs must be 20–1000')
    root=Path(__file__).resolve().parents[1]; output=Path(args.output)
    if not output.is_absolute():output=root/output
    if args.reviewed_examples and output.resolve() in {(root/'../.local/local-tensorflow-v1').resolve(),base_output.resolve()}:
        parser.error('Use a separate --output directory for company-reviewed models; do not overwrite the global authored model')
    output.mkdir(parents=True,exist_ok=True)
    tf.config.set_visible_devices([],'GPU')
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.config.experimental.enable_op_determinism()
    rows,idf,vectors=fit();base_count=len(rows);vocab=sorted(idf);indexes={word:i for i,word in enumerate(vocab)}
    scope=dataset_hash=None;reviewed_count=0;baseline_count=0
    if args.reviewed_examples:
        from app.ai_operator.reviewed_data import load_reviewed
        from app.ai_operator.local_features import features
        import math
        extra,scope,dataset_hash=load_reviewed(args.reviewed_examples)
        submitted={(r['module'],r['text'].casefold()) for r in extra}
        from app.ai_operator.expanded_corpus import with_platform_baseline
        extra=with_platform_baseline(extra,scope)
        rows=list(rows);vectors=list(vectors);known={(r['module'],r['text'].casefold()):r['intent'] for r in rows}
        for row in extra:
            key=(row['module'],row['text'].casefold())
            if key in known:
                if known[key]!=row['intent']:raise ValueError('Reviewed label conflicts with an existing example')
                continue
            count=features(row['text']);raw={word:(1+math.log(n))*idf[word] for word,n in count.items() if word in idf}
            norm=math.sqrt(sum(v*v for v in raw.values())) or 1
            rows.append(row);vectors.append({word:v/norm for word,v in raw.items()});known[key]=row['intent']
            if key in submitted:reviewed_count+=1
            else:baseline_count+=1
        by_features={}
        for row in rows:
            key=(row['module'],tuple(sorted(features(row['text']).items())))
            if key in by_features and by_features[key]!=row['intent']:raise ValueError('Conflicting reviewed labels after slot anonymization; correct the dataset first')
            by_features[key]=row['intent']
        from app.ai_operator.local_features import fit_rows
        idf,vectors=fit_rows(rows,max_vocabulary=4096);vocab=sorted(idf);indexes={word:i for i,word in enumerate(vocab)}
    if args.evaluation_examples:
        from app.ai_operator.local_features import features
        training_keys={(r['module'],tuple(sorted(features(r['text']).items()))) for r in rows}
        evaluation_rows=json.loads(Path(args.evaluation_examples).read_text(encoding='utf-8'))
        for sample in evaluation_rows:
            if (sample['module'],tuple(sorted(features(sample['text']).items()))) in training_keys:
                raise ValueError('Holdout overlaps the final training corpus after normalization')
    matrix=np.zeros((len(rows),len(vocab)),dtype='float32')
    for i,values in enumerate(vectors):
        for term,value in values.items():matrix[i,indexes[term]]=value
    bundle={'format':FORMAT,'feature_version':FEATURES,'corpus_version':VERSION,'corpus_sha256':corpus_hash(),
            'tensorflow_version':tf.__version__,'vocabulary':vocab,'idf':[idf[word] for word in vocab],
            'training_commands':dict(Counter(row['module'] for row in rows)),'models':{}}
    if scope:
        bundle['training_scope']=scope;bundle['reviewed_dataset_sha256']=dataset_hash;bundle['vocabulary_source']='reviewed-training'
    report={'format':FORMAT,'tensorflow_version':tf.__version__,'created_at':datetime.now(timezone.utc).isoformat(),
            'keras_version':tf.keras.__version__,'numpy_version':np.__version__,'python_version':sys.version.split()[0],
            'seed':137,'epochs':args.epochs,'architecture':'TF-IDF → Dense(64, relu) → Dropout(0.1) → Dense(20, softmax)',
            'modules':{},'limits':'Small authored/reviewed corpus. Internal validation holds out one example per intent with a fixed base vocabulary. Final models refit all selected examples. Accuracy is not a general-language or competitor benchmark.'}
    report.update(training_scope=scope,reviewed_examples_added=reviewed_count,authored_baseline_examples_added=baseline_count,reviewed_dataset_sha256=dataset_hash)

    def network(seed):
        tf.keras.utils.set_random_seed(seed)
        model=tf.keras.Sequential([tf.keras.layers.Input(shape=(len(vocab),)),tf.keras.layers.Dense(64,activation='relu'),
            tf.keras.layers.Dropout(.1),tf.keras.layers.Dense(20,activation='softmax')])
        model.compile(optimizer=tf.keras.optimizers.Adam(.015),loss='sparse_categorical_crossentropy')
        return model

    parity=0.0
    for ordinal,(module,intents) in enumerate(FAMILIES.items()):
        selected=[i for i,row in enumerate(rows) if row['module']==module]
        x=matrix[selected];labels=sorted(intents);y=np.array([labels.index(rows[i]['intent']) for i in selected],dtype='int32')
        rng=np.random.default_rng(137+ordinal)
        validation=np.array([rng.choice(np.flatnonzero(y==i)) for i in range(len(labels))])
        training=np.array([i for i in range(len(y)) if i not in validation])
        print(f'{module}: internal train={len(training)}, validation={len(validation)}; final train={len(y)}',flush=True)
        candidate=network(137+ordinal);best=None;best_key=(-1,float('-inf'))
        for epoch in range(args.epochs):
            candidate.train_on_batch(x[training],y[training])
            if epoch%10==0 or epoch==args.epochs-1:
                probs=candidate(x[validation],training=False).numpy()
                acc=float(np.mean(np.argmax(probs,axis=1)==y[validation]))
                loss=float(-np.log(np.maximum(probs[np.arange(len(validation)),y[validation]],1e-9)).mean())
                if (acc,-loss)>best_key:best_key=(acc,-loss);best=candidate.get_weights()
        candidate.set_weights(best)
        internal_accuracy=best_key[0]
        # Validation selected no training records for the final model; this refit
        # uses a fixed epoch count and never trains on the paraphrase evaluation.
        model=network(1137+ordinal)
        for epoch in range(args.epochs):model.train_on_batch(x,y)
        probabilities=model(x,training=False).numpy()
        accuracy=float(np.mean(np.argmax(probabilities,axis=1)==y))
        if accuracy<.99:raise RuntimeError(f'{module} failed the 99% exemplar-fit gate: {accuracy}')
        base_positions=[j for j,index in enumerate(selected) if index<base_count]
        if any(int(np.argmax(probabilities[j]))!=int(y[j]) for j in base_positions):
            raise RuntimeError(f'{module} regressed a base command; do not publish this reviewed model')
        w1,b1,w2,b2=model.get_weights()
        portable={'labels':labels,'w1':w1.tolist(),'b1':b1.tolist(),'w2':w2.tolist(),'b2':b2.tolist()}
        bundle['models'][module]=portable
        errors=[max(abs(a-b) for a,b in zip(forward(vector(rows[index]['text'],bundle),portable),probabilities[j].tolist())) for j,index in enumerate(selected)]
        parity=max(parity,max(errors))
        filename=module+'.keras';model.save(output/filename)
        restored=tf.keras.models.load_model(output/filename,compile=False,safe_mode=True)
        reload_error=float(np.max(np.abs(restored(x,training=False).numpy()-probabilities)))
        report['modules'][module]={'training_commands':len(y),'intent_families':len(labels),'internal_training_commands':len(training),
            'internal_validation_commands':len(validation),'internal_validation_accuracy':internal_accuracy,'training_accuracy':accuracy,
            'portable_max_error':max(errors),'keras_reload_max_error':reload_error,'keras_file':filename}
        print(json.dumps({module:report['modules'][module]}),flush=True)
    if parity>1e-5:raise RuntimeError(f'Portable/TensorFlow parity failed: {parity}')
    validate(bundle)
    evaluation=json.loads((root/'tests/fixtures/local-nlp-holdout-v1.json').read_text())
    passed=Counter();totals=Counter();failures=[]
    for module,text,expected in evaluation:
        model=bundle['models'][module];values=forward(vector(text,bundle),model)
        predicted=model['labels'][int(np.argmax(values))];totals[module]+=1
        if predicted==expected:passed[module]+=1
        else:failures.append({'module':module,'text':text,'expected':expected,'actual':predicted})
    report['development_paraphrases']={'passed':sum(passed.values()),'total':len(evaluation),'modules':{m:{'passed':passed[m],'total':totals[m]} for m in FAMILIES},'failures':failures,
        'basis':'Raw neural predictions only, no exact-example or semantic rules. Existing authored development set; not an untouched benchmark.'}
    report['portable_max_error']=parity
    if args.evaluation_examples:
        frozen=json.loads(Path(args.evaluation_examples).read_text())
        if not isinstance(frozen,list) or len(frozen)>2000:raise ValueError('Invalid evaluation file')
        trained={(r['module'],tuple(sorted(__import__('app.ai_operator.local_features',fromlist=['features']).features(r['text']).items()))) for r in rows}
        results={}
        from app.ai_operator.local_features import features
        for sample in frozen:
            if sample.get('split') not in {'validation','test'} or sample.get('module') not in FAMILIES or sample.get('intent') not in FAMILIES[sample['module']]:raise ValueError('Invalid evaluation row')
            if (sample['module'],tuple(sorted(features(sample['text']).items()))) in trained:raise ValueError('Training/evaluation leakage')
            values=forward(vector(sample['text'],bundle),bundle['models'][sample['module']])
            actual=bundle['models'][sample['module']]['labels'][int(np.argmax(values))]
            key=sample['split'];group=results.setdefault(key,{'passed':0,'total':0});group['total']+=1;group['passed']+=int(actual==sample['intent'])
        report['uploaded_evaluation']=results
    # Publish the complete four-model bundle atomically only after parity/load gates.
    temporary=output/'bundle.pending.json'
    temporary.write_text(json.dumps(bundle,separators=(',',':')),encoding='utf-8')
    temporary.replace(output/'bundle.json')
    (output/'commands.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
    (output/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for module in FAMILIES:
        (output/(module+'-commands.json')).write_text(json.dumps([r for r in rows if r['module']==module],indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
