"""Planning-only synthetic conversation benchmark; native execution is tested separately."""
import argparse
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-dir',required=True);args=parser.parse_args()
    folder=Path(args.model_dir).resolve()
    os.environ['LOCAL_NLP_MODEL_DIR']=str(folder)
    # Ignore the currently activated global model while evaluating a candidate.
    os.environ['LOCAL_NLP_TRAINING_DIR']=str(folder/'benchmark-isolated-storage')
    from app.ai_operator.dialogue_corpus import conversations
    from app.ai_operator.local_nlp import parse
    from app.ai_operator.local_dialogue import continue_action
    from app.ai_operator.local_runtime import task_plan
    from app.ai_operator.expanded_corpus import examples
    from app.ai_operator.action_repairs import cases
    failures=[];counts={};rows=conversations()+cases()
    for row in rows:
        try:
            if row['kind']=='independent_conversations':
                request,read=row['chats']
                a=parse(request[0],row['module']);b=parse(read[0],row['module'])
                if a.slots.get('title')==b.slots.get('title') or b.intent==a.intent:raise ValueError('New chat inherited the action')
            else:
                data=SimpleNamespace(project_id=row.get('context',{}).get('project_id'),request_key=str(uuid4()),timezone='Asia/Kolkata')
                prior=None;plan=None
                for message in row['messages']:
                    if message=='yes' and plan and plan.get('steps') and not plan.get('question'):
                        continue  # This benchmark never executes business actions.
                    current=parse(message,row['module'])
                    if prior:current=continue_action(current,prior,message,data.timezone)
                    if current.slots.get('project_id'):data.project_id=current.slots['project_id']
                    plan=task_plan(current,data,[],[])
                    if plan is None:raise ValueError('Action changed into an unrelated read')
                    prior={'module':current.module,'intent':current.intent,'slots':dict(current.slots)}
                if row.get('expected')=='cancelled':
                    if not plan or plan.get('steps') or current.intent!='cancelled':raise ValueError('Cancellation retained executable steps')
                else:
                    if not plan or not plan.get('steps') or plan.get('question'):raise ValueError('Conversation ended without a reviewable action')
                    payload=plan['steps'][0]['payload']
                    if any(payload.get(k)!=v for k,v in row.get('expected_payload',{}).items()):raise ValueError('Correction did not retain the expected exact payload')
            counts[row['kind']]=counts.get(row['kind'],0)+1
        except Exception as error:failures.append({'id':row['id'],'error':str(error)})
    development=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/local-nlp-holdout-v1.json').read_text())
    recognition_failures=[]
    for module,text,intent in development:
        actual=parse(text,module).intent
        if actual!=intent:recognition_failures.append({'module':module,'text':text,'expected':intent,'actual':actual})
    from app.ai_operator.local_tensorflow import load
    from app.ai_operator.local_corpus import examples as base_examples
    trained=(load() or {}).get('training_commands',{})
    size=min(trained.get(module,0) for module in ('CRM','PMS','HRMS'))
    authored=examples(60 if size>=1200 else 50) if size>=1000 else base_examples()
    exemplar_failures=[]
    for row in authored:
        actual=parse(row['text'],row['module']).intent
        if actual!=row['intent']:exemplar_failures.append({**row,'actual':actual})
    from app.ai_operator.conversational_corpus import benchmark
    natural=benchmark()
    from app.ai_operator.realworld_action_corpus import benchmark as workplace_benchmark
    workplace=workplace_benchmark()
    from app.ai_operator.workplace_actions_v2 import benchmark as workplace_v2_benchmark
    workplace_v2=workplace_v2_benchmark()
    from app.ai_operator.workplace_actions_v3 import benchmark as workplace_v3_benchmark
    workplace_v3=workplace_v3_benchmark()
    from app.ai_operator.workplace_actions_v4 import benchmark as workplace_v4_benchmark
    workplace_v4=workplace_v4_benchmark()
    from app.ai_operator.workplace_actions_v5 import benchmark as workplace_v5_benchmark
    workplace_v5=workplace_v5_benchmark()
    report={'total':len(rows),'passed':len(rows)-len(failures),'by_kind':counts,'failures':failures,'natural_actions':natural,'workplace_actions':workplace,'workplace_actions_v2':workplace_v2,'workplace_actions_v3':workplace_v3,'workplace_actions_v4':workplace_v4,'workplace_actions_v5':workplace_v5,
            'existing_development':{'passed':len(development)-len(recognition_failures),'total':len(development),'failures':recognition_failures},
            'authored_training_recognition':{'passed':len(authored)-len(exemplar_failures),'total':len(authored),'failures':exemplar_failures},
            'limits':'Synthetic authored planning cases, not independent language tests. No business actions, permission checks or deliveries are executed here; separate native integration tests cover those.'}
    (folder/'conversation-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    if failures or recognition_failures or exemplar_failures or natural['failures'] or workplace['failures'] or workplace_v2['failures'] or workplace_v3['failures'] or workplace_v3['training_fit']['failures'] or workplace_v4['failures'] or workplace_v4['training_fit']['failures'] or workplace_v5['failures'] or workplace_v5['training_fit']['failures']:raise SystemExit(1)


if __name__=='__main__':main()
