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
    from app.core.config import settings
    from sqlalchemy.engine import URL
    if settings.POSTGRES_SERVER not in {'127.0.0.1','localhost','::1'}:raise ValueError('Only disposable local PostgreSQL evaluation is supported')
    # Provisioning credentials exist only in the child environment. They are
    # never written to candidate files or printed in evaluation output.
    url=URL.create('postgresql+psycopg',username=settings.POSTGRES_USER,password=settings.POSTGRES_PASSWORD,host=settings.POSTGRES_SERVER,port=settings.POSTGRES_PORT,database=settings.POSTGRES_DB)
    name='business_suite_message_release_'+hashlib.sha256(str(folder).encode()).hexdigest()[:12]+'_test'
    env=dict(os.environ,DATABASE_URL=url.render_as_string(hide_password=False),POSTGRES_TEST_DATABASE=name,LOCAL_NLP_MODEL_DIR=str(folder),LOCAL_NLP_TRAINING_DIR=str(folder/'isolated-message-evaluation'),ENVIRONMENT='test')
    env.pop('TEST_DATABASE_URL',None)
    report=folder/'message-action-tests.xml'
    with (folder/'message-action-tests.log').open('w',encoding='utf-8') as log:
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
