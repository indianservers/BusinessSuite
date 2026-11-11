"""Compare neural inference and full parsing on frozen, non-overlapping probes."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-dir',required=True)
    args=parser.parse_args();folder=Path(args.model_dir).resolve()
    os.environ['LOCAL_NLP_MODEL_DIR']=str(folder)
    os.environ['LOCAL_NLP_TRAINING_DIR']=str(folder/'isolated-common-holdout')
    from app.ai_operator.common_actions_holdout import examples
    from app.ai_operator.local_features import features
    from app.ai_operator.local_tensorflow import load,predict
    from app.ai_operator.local_nlp import parse
    bundle=load()
    if not bundle:raise ValueError('No valid candidate model')
    training=json.loads((folder/'commands.json').read_text(encoding='utf-8'))
    keys={(r['module'],tuple(sorted(features(r['text']).items()))) for r in training}
    rows=examples()
    if any((r['module'],tuple(sorted(features(r['text']).items()))) in keys for r in rows):
        raise ValueError('Holdout overlaps training after slot normalization')
    failures=[];counts={m:{'total':0,'neural_passed':0,'parser_passed':0} for m in ('PMS','CRM','HRMS')}
    for row in rows:
        neural=predict(row['text'],row['module'])['intent']
        parsed=parse(row['text'],row['module']).intent
        count=counts[row['module']];count['total']+=1
        count['neural_passed']+=int(neural==row['intent']);count['parser_passed']+=int(parsed==row['intent'])
        if neural!=row['intent'] or parsed!=row['intent']:failures.append({**row,'neural':neural,'parser':parsed})
    report={'total':len(rows),'neural_passed':sum(v['neural_passed'] for v in counts.values()),
        'parser_passed':sum(v['parser_passed'] for v in counts.values()),'by_module':counts,'failures':failures,
        'limits':'Frozen synthetic development wording, distinct after feature normalization; never used to fit this release. 20 probes per module are not production accuracy evidence.'}
    (folder/'common-holdout-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
