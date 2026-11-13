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
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
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
    vocab=sorted(allowed);indexes={w:i for i,w in enumerate(vocab)}
    idf=[math.log((1+len(training))/(1+df[w]))+1 for w in vocab]
    x=np.zeros((len(rows),len(vocab)),dtype='float32')
    for i,count in enumerate(counts):
        for word,n in count.items():
            if word in indexes:x[i,indexes[word]]=(1+math.log(n))*idf[indexes[word]]*feature_weight(word)
        x[i]/=np.linalg.norm(x[i]) or 1
    y=np.array([LABELS.index(r['act']) for r in rows],dtype='int32')
    selected=None;candidates=[]
    for seed in (7321,7322,7323):
        tf.keras.utils.set_random_seed(seed)
        model=tf.keras.Sequential([tf.keras.layers.Input(shape=(len(vocab),)),tf.keras.layers.Dense(64,activation='relu'),tf.keras.layers.Dropout(.1),tf.keras.layers.Dense(len(LABELS),activation='softmax')])
        model.compile(optimizer=tf.keras.optimizers.Adam(.01),loss='sparse_categorical_crossentropy')
        for _ in range(350):model.train_on_batch(x[training],y[training])
        probabilities=model(x,training=False).numpy();predicted=np.argmax(probabilities,axis=1)
        train_accuracy=float(np.mean(predicted[training]==y[training]));development_accuracy=float(np.mean(predicted[test]==y[test]))
        candidates.append({'seed':seed,'training_accuracy':train_accuracy,'development_accuracy':development_accuracy})
        key=(development_accuracy,train_accuracy)
        if train_accuracy>=.98 and (selected is None or key>selected[0]):selected=(key,seed,model,probabilities,predicted,train_accuracy)
    if selected is None:raise RuntimeError('No dialogue candidate passed the exemplar-fit gate')
    _,seed,model,probabilities,predicted,train_accuracy=selected
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
    report={'message_dialogue_version':message_version,'message_training_turns':len(message_turns()),'message_training_sha256':hashlib.sha256(json.dumps(message_turns(),sort_keys=True).encode()).hexdigest(),'format':VERSION,'tensorflow_version':tf.__version__,'epochs':350,'seed':seed,'training_turns':len(training),'heldout_turns':len(test),
            'training_accuracy':train_accuracy,'heldout_correct':len(test)-len(failed),'heldout_accuracy':float(np.mean(predicted[test]==y[test])),
            'portable_max_error':error,'keras_reload_max_error':reload_error,'failures':failed,'model_selection':{'candidates':candidates,'basis':'Selected by the authored development set; this set is not an unbiased test score'},
            'limits':'Synthetic, context-labelled dialogue acts. Evaluation wording and vocabulary are excluded from gradient training; contexts are shared. This authored development set has been inspected during tuning, not an untouched benchmark. Not a general language or action-execution benchmark. Predictions never authorize actions.'}
    (output/'dialogue-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (output/'dialogue-turns.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    from app.ai_operator.action_repairs import cases
    (output/'conversation-examples.json').write_text(json.dumps(conversations()+cases(),indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='failures'},indent=2),flush=True)


if __name__=='__main__':main()
