"""TensorFlow training in the isolated training environment; no ERP/private data."""
import argparse,json,os,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS','0')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    import numpy as np
    import tensorflow as tf
    from app.ai_operator.agent_builder_corpus import VERSION,examples,development,PHRASES
    from app.ai_operator.local_features import fit_rows,features
    from app.ai_operator.local_tensorflow import vector,forward
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--epochs',type=int,default=300);args=parser.parse_args()
    if not 20<=args.epochs<=1000:parser.error('Use 20..1000 epochs')
    folder=Path(args.output).resolve();folder.mkdir(parents=True,exist_ok=True)
    tf.config.set_visible_devices([],'GPU');tf.config.threading.set_intra_op_parallelism_threads(2);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(811);tf.config.experimental.enable_op_determinism()
    rows=examples();probes=development();labels=sorted(PHRASES)
    normalized={tuple(sorted(features(r['text']).items())) for r in rows}
    if any(tuple(sorted(features(r['text']).items())) in normalized for r in probes):raise ValueError('Development phrase overlaps training features')
    idf,vectors=fit_rows(rows);vocabulary=sorted(idf);indexes={word:i for i,word in enumerate(vocabulary)}
    x=np.zeros((len(rows),len(vocabulary)),dtype='float32')
    for i,values in enumerate(vectors):
        for term,value in values.items():x[i,indexes[term]]=value
    y=np.array([labels.index(r['label']) for r in rows],dtype='int32')
    model=tf.keras.Sequential([tf.keras.layers.Input(shape=(len(vocabulary),)),tf.keras.layers.Dense(64,activation='relu'),tf.keras.layers.Dense(len(labels),activation='softmax')])
    model.compile(optimizer=tf.keras.optimizers.Adam(.015),loss='sparse_categorical_crossentropy')
    for epoch in range(args.epochs):
        model.train_on_batch(x,y)
        if epoch%50==0:print(json.dumps({'epoch':epoch,'training_commands':len(rows)}),flush=True)
    w1,b1,w2,b2=model.get_weights()
    bundle={'format':'tensorflow-agent-builder-v1','corpus_version':VERSION,'tensorflow_version':tf.__version__,
        'training_commands':len(rows),'labels':labels,'vocabulary':vocabulary,'idf':[idf[v] for v in vocabulary],
        'model':{'w1':w1.tolist(),'b1':b1.tolist(),'w2':w2.tolist(),'b2':b2.tolist()},
        'corpus_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()}
    dx=np.zeros((len(probes),len(vocabulary)),dtype='float32')
    for i,row in enumerate(probes):
        for j,value in vector(row['text'],bundle).items():dx[i,j]=value
    tf_probs=model(dx,training=False).numpy();portable=np.array([forward(vector(row['text'],bundle),bundle['model']) for row in probes])
    predictions=tf_probs.argmax(axis=1);truth=np.array([labels.index(r['label']) for r in probes])
    report={'version':VERSION,'tensorflow_version':tf.__version__,'created_at':datetime.now(timezone.utc).isoformat(),
        'training_commands':len(rows),'training_accuracy':float(np.mean(model(x,training=False).numpy().argmax(axis=1)==y)),
        'development_commands':len(probes),'development_accuracy':float(np.mean(predictions==truth)),
        'portable_max_error':float(np.max(np.abs(tf_probs-portable))),
        'failures':[{'text':r['text'],'expected':r['label'],'predicted':labels[int(predictions[i])]} for i,r in enumerate(probes) if predictions[i]!=truth[i]],
        'limits':'Authored role classification examples and authored development probes, not independent human evaluation or an LLM. Typed configuration validation and review remain required.'}
    model.save(folder/'builder.keras')
    for name,data in [('bundle.json',bundle),('evaluation.json',report),('dataset.json',{'version':VERSION,'training':rows,'development':probes})]:
        (folder/name).write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('training_commands','training_accuracy','development_commands','development_accuracy','portable_max_error')}),flush=True)


if __name__=='__main__':main()
