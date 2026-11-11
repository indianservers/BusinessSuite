"""Fail the candidate if any catalog request is misrouted or loses its draft."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-dir',required=True)
    args=parser.parse_args();folder=Path(args.model_dir).resolve()
    os.environ['LOCAL_NLP_MODEL_DIR']=str(folder)
    os.environ['LOCAL_NLP_TRAINING_DIR']=str(folder/'isolated-common-audit')
    from app.ai_operator.common_action_evaluation import benchmark
    report=benchmark()
    (folder/'common-action-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    return int(bool(report['failures']))

if __name__=='__main__':raise SystemExit(main())
