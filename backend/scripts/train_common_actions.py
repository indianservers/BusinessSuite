"""Reproducible offline candidate for the 200-request-per-module catalog.

Does not activate models or modify business records. Native release gates and
platform activation remain separate from TensorFlow fitting.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    from app.ai_operator.common_actions import VERSION,catalog,examples
    from app.ai_operator.local_corpus import FAMILIES
    from app.ai_operator.local_features import features
    from app.ai_operator.expanded_corpus import examples as baseline
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--epochs',type=int,default=400)
    parser.add_argument('--export-only',action='store_true')
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[2];folder=Path(args.output).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    rows=catalog()
    for module in ('PMS','CRM','HRMS'):
        selected=[r for r in rows if r['module']==module]
        if len(selected)!=200 or len({r['text'] for r in selected})!=200:
            raise ValueError('Each module must contain 200 distinct requests')
        if {r['intent'] for r in selected}!=set(FAMILIES[module]):
            raise ValueError('Cover every existing intent family')
    labels={}
    for row in baseline(60)+examples():
        key=(row['module'],tuple(sorted(features(row['text']).items())))
        if key in labels and labels[key]!=row['intent']:raise ValueError('Conflicting normalized labels')
        labels[key]=row['intent']
    (folder/'catalog.json').write_text(json.dumps({'version':VERSION,'requests':rows},indent=2),encoding='utf-8')
    reviewed=folder/'reviewed.json'
    reviewed.write_text(json.dumps({'format':'reviewed-nlp-queries-v1','training_scope':{'platform':True},'examples':examples()},indent=2),encoding='utf-8')
    from app.ai_operator.common_actions_holdout import examples as heldout
    holdout=folder/'holdout.json'
    holdout.write_text(json.dumps(heldout(),indent=2),encoding='utf-8')
    if args.export_only:return
    python=Path(os.environ.get('LOCAL_NLP_TRAINING_PYTHON') or repo/'.local/tensorflow-venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python'))
    subprocess.run([str(python),str(repo/'backend/scripts/train_tensorflow_local_nlp.py'),
        '--output',str(folder/'model'),'--epochs',str(args.epochs),'--reviewed-examples',str(reviewed),
        '--evaluation-examples',str(holdout)],check=True)
    subprocess.run([sys.executable,str(repo/'backend/scripts/benchmark_common_actions.py'),
        '--model-dir',str(folder/'model')],check=True)
    subprocess.run([sys.executable,str(repo/'backend/scripts/evaluate_common_holdout.py'),
        '--model-dir',str(folder/'model')],check=True)


if __name__=='__main__':main()
