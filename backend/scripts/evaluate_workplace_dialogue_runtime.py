"""Planning-only dialogue checks using the exact exported candidate weights."""
import argparse,json,os,sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-dir',required=True);args=parser.parse_args()
    folder=Path(args.model_dir).resolve();os.environ['LOCAL_NLP_MODEL_DIR']=str(folder);os.environ['LOCAL_NLP_TRAINING_DIR']=str(folder/'isolated-workplace-runtime')
    from app.ai_operator.local_nlp import parse
    from app.ai_operator.local_dialogue import continue_action
    from app.ai_operator.local_runtime import task_plan
    failures=[];total=0
    cancel='Please withdraw the unexecuted work item we are preparing'
    probes=[('help','Could you describe the detail still missing from this draft','question'),
            ('cancel',cancel,'cancelled'),('quoted_title','"'+cancel+'"','title'),
            ('labelled_title','Title: '+cancel,'title'),
            ('independent_request','Open an independent discussion about a different work item','question'),
            ('acknowledgement','Okay I am following the discussion so far','question'),
            ('missing_field_not_approval','I approve only the exact action currently displayed for review','question')]
    for module in ('CRM','PMS','HRMS'):
        initial=module+': create '+('HR ticket' if module=='HRMS' else 'task')
        data=SimpleNamespace(project_id=1 if module=='PMS' else None,request_key=str(uuid4()),timezone='Asia/Kolkata')
        current=parse(initial,module);first=task_plan(current,data,[],[])
        assert first and first.get('question'),'Initial action must request missing details'
        prior={'module':current.module,'intent':current.intent,'slots':dict(current.slots)}
        for name,text,expected in probes:
            total+=1
            try:
                result=continue_action(parse(text,module),prior,text,data.timezone)
                plan=task_plan(result,data,[],[])
                assert plan is not None
                if expected=='question':assert plan.get('question') and not plan.get('steps')
                elif expected=='cancelled':assert result.intent=='cancelled' and not plan.get('steps')
                else:assert len(plan.get('steps',[]))==1 and plan['steps'][0]['payload'].get('title',plan['steps'][0]['payload'].get('subject'))==cancel
            except AssertionError:failures.append({'module':module,'case':name,'expected':expected})
    report={'format':'workplace-dialogue-runtime-v1','total':total,'passed':total-len(failures),'failures':failures,'business_actions_executed':0,'limits':'Synthetic planning-only checks. Some wording is fitted training data; this verifies integration, not independent generalization. Native API execution and approval tests remain separate.'}
    (folder/'workplace-runtime-evaluation.json').write_bytes(json.dumps(report,indent=2).encode());print(json.dumps(report),flush=True)
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
