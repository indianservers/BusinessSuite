"""Server-only, isolated native benchmark. Never opens the live ERP database."""
import argparse,json,os,subprocess,sys,statistics,time
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.ai_operator.action_benchmark import manifest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    folder=Path(args.output).resolve();folder.mkdir(parents=True,exist_ok=True)
    environment=os.environ.copy();environment.pop('TEST_DATABASE_URL',None)
    environment.update(ACTION_BENCHMARK_RESULTS=str(folder/'cases'),ENVIRONMENT='test')
    start=time.monotonic();report=manifest()
    report.update(status='running',started_at=datetime.now(timezone.utc).isoformat())
    (folder/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    try:
        with (folder/'native-tests.log').open('w',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,'-m','pytest','tests/test_phase4_workplace.py','tests/test_suite_workflows.py','tests/test_saved_agents.py','-q','--disable-warnings','--junitxml='+str(folder/'evidence.xml')],cwd=Path(__file__).resolve().parents[1],env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        observations=[json.loads(p.read_text(encoding='utf-8')) for p in (folder/'cases').glob('*.json')]
        by_family={}
        for item in observations:
            group=by_family.setdefault(item['family'],{'passed':0,'failed':0});group['passed' if item['outcome']=='passed' else 'failed']+=1
        durations=sorted(r['duration_ms'] for r in observations)
        report.update(status='passed' if result.returncode==0 and len(observations)==report['conversations'] else 'failed',
            measured_conversations=len(observations),passed=sum(r['outcome']=='passed' for r in observations),failed=sum(r['outcome']=='failed' for r in observations),
            by_family=by_family,observations=observations,duration_ms=round((time.monotonic()-start)*1000),
            median_conversation_ms=statistics.median(durations) if durations else None,
            p95_conversation_ms=durations[max(0,__import__('math').ceil(.95*len(durations))-1)] if durations else None,
            planning_engine='Installed local action model plus explicit grammar; canonical API integration fixtures',
            evidence='evidence.xml',training_used=False,cloud_calls=0,
            ranking='No overall ClickUp ranking: native ERP fixtures and vendor capabilities are not equivalent measured evidence.')
    except subprocess.TimeoutExpired:report.update(status='failed',error='BENCHMARK_DEADLINE_EXCEEDED')
    finally:
        (folder/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('version','status','passed','failed','conversations','user_messages','median_conversation_ms','p95_conversation_ms')}),flush=True)
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
