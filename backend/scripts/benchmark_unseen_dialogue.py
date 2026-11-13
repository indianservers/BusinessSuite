"""Evaluate frozen wording after model selection; never train on these probes."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-dir',required=True);args=parser.parse_args()
    folder=Path(args.model_dir).resolve();os.environ['LOCAL_NLP_MODEL_DIR']=str(folder);os.environ['LOCAL_NLP_TRAINING_DIR']=str(folder/'isolated-unseen-evaluation')
    from app.ai_operator.dialogue_unseen import cases
    from app.ai_operator.dialogue_tensorflow import predict
    failures=[];rows=cases();by_class={}
    for row in rows:
        prediction=predict(row['module'],row['intent'],row['pending'],row['text'])
        success=bool(prediction and prediction['act']==row['act'])
        metric=by_class.setdefault(row['act'],{'passed':0,'total':0});metric['total']+=1;metric['passed']+=int(success)
        if not success:failures.append({**row,'actual':prediction['act'] if prediction else None})
    report={'total':len(rows),'passed':len(rows)-len(failures),'accuracy':(len(rows)-len(failures))/len(rows),'by_class':by_class,'failures':failures,
            'limits':'120 authored wording probes, excluded from training and model selection. Small synthetic set, not production accuracy. Predictions do not authorize execution.'}
    from app.ai_operator.message_dialogue_holdout import VERSION as message_version,cases as message_cases
    extra=message_cases();extra_failures=[];extra_classes={}
    for row in extra:
        prediction=predict(row['module'],row['intent'],row['pending'],row['text'])
        success=bool(prediction and prediction['act']==row['act'])
        metric=extra_classes.setdefault(row['act'],{'passed':0,'total':0});metric['total']+=1;metric['passed']+=int(success)
        if not success:extra_failures.append({**row,'actual':prediction['act'] if prediction else None})
    report['message_followups']={'version':message_version,'total':len(extra),'passed':len(extra)-len(extra_failures),'by_class':extra_classes,'failures':extra_failures,
        'limits':'Authored v1 regression wording; inspected after candidate 241. Excluded from gradient fitting; not an independent generalization score.'}
    from app.ai_operator.message_dialogue_validation import VERSION as fresh_version,cases as fresh_cases
    fresh=fresh_cases();fresh_failures=[];fresh_classes={}
    for row in fresh:
        prediction=predict(row['module'],row['intent'],row['pending'],row['text'])
        success=bool(prediction and prediction['act']==row['act'])
        metric=fresh_classes.setdefault(row['act'],{'passed':0,'total':0});metric['total']+=1;metric['passed']+=int(success)
        if not success:fresh_failures.append({**row,'actual':prediction['act'] if prediction else None})
    report['message_followups_validation']={'version':fresh_version,'total':len(fresh),'passed':len(fresh)-len(fresh_failures),'by_class':fresh_classes,'failures':fresh_failures,
        'limits':'Fresh authored v2 wording, excluded from gradient fitting and development-set seed selection. Shared synthetic contexts; not production accuracy.'}
    from app.ai_operator.workplace_dialogue_validation import VERSION as workplace_version,cases as workplace_cases
    workplace=workplace_cases();workplace_failures=[];workplace_classes={}
    for row in workplace:
        prediction=predict(row['module'],row['intent'],row['pending'],row['text'])
        success=bool(prediction and prediction['act']==row['act'])
        metric=workplace_classes.setdefault(row['act'],{'passed':0,'total':0});metric['total']+=1;metric['passed']+=int(success)
        if not success:workplace_failures.append({**row,'actual':prediction['act'] if prediction else None})
    report['workplace_followups']={'version':workplace_version,'total':len(workplace),'passed':len(workplace)-len(workplace_failures),'by_class':workplace_classes,'failures':workplace_failures,
        'limits':'90 frozen synthetic context-labelled probes using 30 authored phrases. Excluded from fitting and development-set seed selection. Shared contexts; not production accuracy or an execution benchmark.'}
    (folder/'unseen-dialogue-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='failures'},indent=2))


if __name__=='__main__':main()
