"""Train/export a genuine TensorFlow dialogue-act model with unseen wording tests."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import sys
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS','0')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.ai_operator.dialogue_corpus import VERSION,LABELS,features,feature_weight,turns,conversations


def main():
    import numpy as np
    import tensorflow as tf
    from app.ai_operator.local_tensorflow import forward
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--hidden',type=int,choices=(64,96,128),default=64);parser.add_argument('--dropout',type=float,default=.1);parser.add_argument('--initialize-from');parser.add_argument('--epochs',type=int,default=350);parser.add_argument('--learning-rate',type=float);args=parser.parse_args()
    if not math.isfinite(args.dropout) or not 0<=args.dropout<=.5:parser.error('dropout must be finite and between 0 and 0.5')
    if not 1<=args.epochs<=1000:parser.error('epochs must be between 1 and 1000')
    rate=args.learning_rate if args.learning_rate is not None else (.0005 if args.initialize_from else .01)
    if not math.isfinite(rate) or not .000001<=rate<=.1:parser.error('learning rate must be finite and between 0.000001 and 0.1')
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    tf.config.set_visible_devices([],'GPU');tf.config.threading.set_intra_op_parallelism_threads(2);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(7321);tf.config.experimental.enable_op_determinism()
    rows=turns();counts=[features(r['module'],r['intent'],r['pending'],r['text']) for r in rows]
    training=[i for i,r in enumerate(rows) if r['split']=='train'];test=[i for i,r in enumerate(rows) if r['split']=='test']
    keys={tuple(sorted(counts[i].items())) for i in training}
    if any(tuple(sorted(counts[i].items())) in keys for i in test):raise ValueError('Evaluation feature leakage')
    df=Counter(term for i in training for term in counts[i])
    required={term for term in df if not term.startswith('c:')}
    allowed=required|{term for term,_ in Counter({t:n for t,n in df.items() if t.startswith('c:')}).most_common(max(0,4096-len(required)))}
    vocab=sorted(allowed)
    idf=[math.log((1+len(training))/(1+df[w]))+1 for w in vocab]
    initial=None;initial_hash=None
    if args.initialize_from:
        from app.ai_operator.dialogue_tensorflow import read
        path=Path(args.initialize_from).resolve()/'dialogue.json';stat=path.stat()
        initial=read(str(path),stat.st_size,stat.st_mtime_ns)
        if initial['format']!=VERSION:raise ValueError('Fine tuning requires the current feature format')
        if len(initial['model']['b1'])!=args.hidden:raise ValueError('Fine tuning must retain the initial hidden width')
        vocab=initial['vocabulary'];idf=initial['idf'];initial_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    indexes={w:i for i,w in enumerate(vocab)}
    x=np.zeros((len(rows),len(vocab)),dtype='float32')
    for i,count in enumerate(counts):
        for word,n in count.items():
            if word in indexes:x[i,indexes[word]]=(1+math.log(n))*idf[indexes[word]]*feature_weight(word)
        x[i]/=np.linalg.norm(x[i]) or 1
    y=np.array([LABELS.index(r['act']) for r in rows],dtype='int32')
    selected=None;candidates=[]
    for seed in (7321,7322,7323):
        tf.keras.utils.set_random_seed(seed)
        if initial:
            model=tf.keras.models.load_model(Path(args.initialize_from)/'dialogue.keras',compile=False,safe_mode=True)
            if not math.isclose(model.layers[1].rate,args.dropout):raise ValueError('Fine tuning must retain the initial dropout')
            # Verify that the Keras starting point matches the approved portable
            # export before a gradient update or development-set selection.
            if any(not np.allclose(actual,np.asarray(initial['model'][key]),rtol=0,atol=1e-7) for actual,key in zip(model.get_weights(),('w1','b1','w2','b2'))):raise ValueError('Initial Keras/portable weights disagree')
        else:model=tf.keras.Sequential([tf.keras.layers.Input(shape=(len(vocab),)),tf.keras.layers.Dense(args.hidden,activation='relu'),tf.keras.layers.Dropout(args.dropout),tf.keras.layers.Dense(len(LABELS),activation='softmax')])
        model.compile(optimizer=tf.keras.optimizers.Adam(rate),loss='sparse_categorical_crossentropy')
        for epoch in range(1,args.epochs+1):
            model.train_on_batch(x[training],y[training])
            if epoch!=args.epochs and (not initial or epoch%25):continue
            probabilities=model(x,training=False).numpy();predicted=np.argmax(probabilities,axis=1)
            train_accuracy=float(np.mean(predicted[training]==y[training]));development_accuracy=float(np.mean(predicted[test]==y[test]))
            candidates.append({'seed':seed,'epoch':epoch,'training_accuracy':train_accuracy,'development_accuracy':development_accuracy})
            key=(development_accuracy,train_accuracy)
            if train_accuracy>=.98 and (selected is None or key>selected[0]):selected=(key,seed,model,probabilities,predicted,train_accuracy,epoch,[w.copy() for w in model.get_weights()])
    if selected is None:raise RuntimeError('No dialogue candidate passed the exemplar-fit gate')
    _,seed,model,probabilities,predicted,train_accuracy,selected_epoch,weights=selected
    model.set_weights(weights)
    w1,b1,w2,b2=model.get_weights()
    portable={'labels':LABELS,'w1':w1.tolist(),'b1':b1.tolist(),'w2':w2.tolist(),'b2':b2.tolist()}
    error=max(max(abs(a-b) for a,b in zip(forward({j:float(value) for j,value in enumerate(x[i]) if value},portable),probabilities[i].tolist())) for i in range(len(rows)))
    if error>1e-5:raise RuntimeError('Portable probability parity failed')
    model.save(output/'dialogue.keras');restored=tf.keras.models.load_model(output/'dialogue.keras',compile=False,safe_mode=True)
    reload_error=float(np.max(np.abs(restored(x,training=False).numpy()-probabilities)))
    if reload_error>1e-6:raise RuntimeError('Keras reload mismatch')
    bundle={'format':VERSION,'vocabulary':vocab,'idf':idf,'model':portable,'tensorflow_version':tf.__version__,
            'training_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()}
    (output/'dialogue.json').write_text(json.dumps(bundle,separators=(',',':')),encoding='utf-8')
    failed=[{'module':rows[i]['module'],'pending':rows[i]['pending'],'text':rows[i]['text'],'expected':rows[i]['act'],'actual':LABELS[int(predicted[i])]} for i in test if predicted[i]!=y[i]]
    from app.ai_operator.message_dialogue_corpus import VERSION as message_version,turns as message_turns
    report={'message_dialogue_version':message_version,'message_training_turns':len(message_turns()),'message_training_sha256':hashlib.sha256(json.dumps(message_turns(),sort_keys=True).encode()).hexdigest(),'format':VERSION,'tensorflow_version':tf.__version__,'epochs':selected_epoch,'trained_epochs_per_seed':args.epochs,'learning_rate':rate,'initial_dialogue_sha256':initial_hash,'retained_initial_features':bool(initial),'hidden_units':args.hidden,'dropout':args.dropout,'seed':seed,'training_turns':len(training),'heldout_turns':len(test),
            'training_accuracy':train_accuracy,'heldout_correct':len(test)-len(failed),'heldout_accuracy':float(np.mean(predicted[test]==y[test])),
            'portable_max_error':error,'keras_reload_max_error':reload_error,'failures':failed,'model_selection':{'candidates':candidates,'basis':'Selected by the authored development set; this set is not an unbiased test score'},
            'limits':'Synthetic, context-labelled dialogue acts. Evaluation wording is excluded from gradient training; a fine-tune retains only the baseline training vocabulary; contexts are shared. This authored development set has been inspected during tuning, not an untouched benchmark. Not a general language or action-execution benchmark. Predictions never authorize actions.'}
    from app.ai_operator.workplace_dialogue_corpus import VERSION as workplace_version,turns as workplace_turns
    report.update(workplace_dialogue_version=workplace_version,workplace_training_turns=len(workplace_turns()),workplace_training_sha256=hashlib.sha256(json.dumps(workplace_turns(),sort_keys=True).encode()).hexdigest())
    (output/'dialogue-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (output/'dialogue-turns.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    from app.ai_operator.action_repairs import cases
    (output/'conversation-examples.json').write_text(json.dumps(conversations()+cases(),indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='failures'},indent=2),flush=True)


if __name__=='__main__':main()
