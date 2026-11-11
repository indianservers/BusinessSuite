"""Evaluate candidate numeric models against isolated canonical ERP action tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

TESTS=('tests/test_suite_workflows.py','tests/test_suite_conversations.py','tests/test_suite_workspace.py','tests/test_local_nlp_workflows.py','tests/test_learning_feedback.py','tests/test_conversational_actions.py','tests/test_bot_reliability.py','tests/test_common_actions.py','tests/test_local_writing.py')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-dir',required=True);args=parser.parse_args()
    folder=Path(args.model_dir).resolve();backend=Path(__file__).resolve().parents[1]
    env=os.environ.copy();env.pop('TEST_DATABASE_URL',None)
    env.update(ENVIRONMENT='test',LOCAL_NLP_MODEL_DIR=str(folder),LOCAL_NLP_TRAINING_DIR=str(folder/'isolated-native-evaluation'))
    report=folder/'action-release-tests.xml'
    with (folder/'action-release-tests.log').open('w',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,'-m','pytest',*TESTS,'-q','--tb=short','--disable-warnings','--junitxml='+str(report)],
            cwd=backend,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    root=ET.parse(report).getroot();suites=list(root.iter('testsuite'))
    counts={key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
    if result.returncode and not counts['failures'] and not counts['errors']:counts['errors']=1
    counts.update(format='canonical-action-release-v1',test_files=list(TESTS),model_sha256=hashlib.sha256((folder/'bundle.json').read_bytes()).hexdigest(),
        dialogue_sha256=hashlib.sha256((folder/'dialogue.json').read_bytes()).hexdigest(),
        limits='Isolated SQLite canonical API integration tests with synthetic users and records. No live customer database, outbound messages or cloud model calls.')
    (folder/'action-release-evaluation.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
    print(json.dumps(counts),flush=True)
    if result.returncode:raise SystemExit(result.returncode)

if __name__=='__main__':main()
