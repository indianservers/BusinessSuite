"""Evaluate candidate numeric models against isolated canonical ERP action tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from action_release_postgres import isolated_environment

TESTS=('tests/test_suite_workflows.py','tests/test_suite_conversations.py','tests/test_suite_workspace.py','tests/test_local_nlp_workflows.py','tests/test_learning_feedback.py','tests/test_conversational_actions.py','tests/test_bot_reliability.py','tests/test_common_actions.py','tests/test_local_writing.py','tests/test_media_actions.py','tests/test_media_policy.py','tests/test_gemini_media.py','tests/test_prompt_registry.py','tests/test_image_actions.py','tests/test_artifact_images.py')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-dir',required=True);args=parser.parse_args()
    folder=Path(args.model_dir).resolve();backend=Path(__file__).resolve().parents[1]
    report=folder/'action-release-tests.xml'
    with isolated_environment(folder,'action') as env, (folder/'action-release-tests.log').open('w',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,str(backend/'scripts/run_postgres_tests.py'),*TESTS,'-q','--tb=short','--disable-warnings','--junitxml='+str(report)],
            cwd=backend,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    root=ET.parse(report).getroot();suites=list(root.iter('testsuite'))
    counts={key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
    if result.returncode and not counts['failures'] and not counts['errors']:counts['errors']=1
    counts.update(format='canonical-action-release-v1',database='postgresql',test_files=list(TESTS),model_sha256=hashlib.sha256((folder/'bundle.json').read_bytes()).hexdigest(),
        dialogue_sha256=hashlib.sha256((folder/'dialogue.json').read_bytes()).hexdigest(),
        limits='Isolated local PostgreSQL canonical API integration tests with synthetic users and records. No live customer database, outbound messages or cloud model calls.')
    dialogue=json.loads((folder/'dialogue-evaluation.json').read_text(encoding='utf-8'))
    if not result.returncode and dialogue.get('workplace_dialogue_version'):
        with (folder/'action-release-tests.log').open('a',encoding='utf-8') as log:
            runtime=subprocess.run([sys.executable,str(backend/'scripts/evaluate_workplace_dialogue_runtime.py'),'--model-dir',str(folder)],cwd=backend,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
        if runtime.returncode:counts['errors']+=1
        value=json.loads((folder/'workplace-runtime-evaluation.json').read_text(encoding='utf-8'))
        counts['workplace_dialogue']={**value,'model_sha256':counts['model_sha256'],'dialogue_sha256':counts['dialogue_sha256']}
    (folder/'action-release-evaluation.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
    print(json.dumps(counts),flush=True)
    if result.returncode or counts['errors']:raise SystemExit(result.returncode or 1)

if __name__=='__main__':main()
