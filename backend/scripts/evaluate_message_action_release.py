"""Candidate message actions on disposable local PostgreSQL; never the app DB."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
TESTS=('tests/test_event_message_evidence.py','tests/test_suite_operator.py','tests/test_suite_conversations.py','tests/test_local_action_dialogue.py','tests/test_message_project_choices.py')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-dir',required=True);args=parser.parse_args()
    folder=Path(args.model_dir).resolve();backend=Path(__file__).resolve().parents[1]
    native_path=folder/'action-release-evaluation.json';native=json.loads(native_path.read_text(encoding='utf-8'))
    fingerprint=lambda name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
    if native.get('model_sha256')!=fingerprint('bundle.json') or native.get('dialogue_sha256')!=fingerprint('dialogue.json'):raise ValueError('Evaluate these exact candidate weights with the canonical suite first')
    from action_release_postgres import isolated_environment
    report=folder/'message-action-tests.xml'
    with isolated_environment(folder,'message') as env, (folder/'message-action-tests.log').open('w',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,str(backend/'scripts/run_postgres_tests.py'),*TESTS,'-q','--tb=short','--junitxml='+str(report)],cwd=backend,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1000)
    suites=list(ET.parse(report).getroot().iter('testsuite'))
    counts={key:sum(int(row.attrib.get(key,0)) for row in suites) for key in ('tests','failures','errors','skipped')}
    if result.returncode and not counts['failures'] and not counts['errors']:counts['errors']=1
    counts.update(format='message-action-postgres-v1',database='postgresql',test_files=list(TESTS),model_sha256=fingerprint('bundle.json'),dialogue_sha256=fingerprint('dialogue.json'),
        limits='Synthetic authenticated native API conversations in a disposable local PostgreSQL database. No live records, outbound communication or external LLM calls.')
    native['message_actions']=counts
    native_path.write_bytes(json.dumps(native,indent=2).encode('utf-8'))
    print(json.dumps(counts),flush=True)
    return 0 if result.returncode==0 and counts['tests']>=64 and not any(counts[k] for k in ('failures','errors','skipped')) else 1


if __name__=='__main__':raise SystemExit(main())
