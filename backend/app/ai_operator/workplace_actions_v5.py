"""Fifth synthetic workplace batch. 150 new fitting inputs and 150 separate
development scenarios for exact-title references; never production accuracy.
"""
from types import SimpleNamespace
from uuid import uuid4

TRAINING={
 'CRM':['Review the cross border servicing restriction','Confirm the dealer succession arrangement','Collect the installation readiness affidavit','Check the fleet maintenance concession','Verify the public sector purchase exemption','Arrange the customer steering committee','Review the equipment lease novation','Confirm the product end of support notice','Check the distributor stock rotation claim','Collect the managed service renewal annexure'],
 'PMS':['Validate the tenant key rotation schedule','Review the shipment event replay offset','Test the appointment slot contention','Check the reversible data masking migration','Verify the failed refund reconciliation','Document the customer export throttling','Review the single use token consumption','Test the archival search pagination','Resolve the persistent upload lease','Verify the payment webhook signature expiry'],
 'HRMS':['Review the international assignment tax equalization','Check the apprenticeship extension approval','Correct the dependent scholarship eligibility','Verify the annual mobility allowance','Resolve the delayed service certificate','Review the disaster relief grant request','Check the union leave reimbursement','Correct the parental return shift mapping','Verify the salary advance foreclosure','Resolve the missing wellness benefit credit']}
EVALUATION={
 'CRM':['Review the equipment disposal quotation','Confirm the replacement unit serial approval','Check the dealer exit inventory settlement','Arrange the extended warranty workshop','Verify the customer escrow release'],
 'PMS':['Test the tenant archive rehydration','Review the orphan document cleanup preview','Verify the transfer acknowledgement retry','Check the workflow approval expiry','Document the search synonym rollback'],
 'HRMS':['Review the commuter pass refund','Verify the emergency relocation approval','Correct the leave donation eligibility','Check the retirement benefit nomination','Resolve the missing field allowance']}

def training_examples():
    rows=[]
    for module,subjects in TRAINING.items():
        for i,title in enumerate(subjects):
            obj='HR ticket' if module=='HRMS' else 'customer follow-up' if module=='CRM' else 'project milestone' if i%2 else 'project task'
            for text in [f'Could you help me log a {obj} called {title}',f'I need you to draft a {obj} titled {title}',f'Please set up a new {obj} named {title}',f'Let us open a fresh {obj} for {title}',f'As the next action, submit a {obj} titled {title}']:
                rows.append({'module':module,'intent':'ticket.create' if module=='HRMS' else 'milestone.create' if obj.endswith('milestone') else 'tasks.create','text':text,'split':'train'})
    return rows

def scenarios():
    rows=[]
    for module,subjects in EVALUATION.items():
        obj={'CRM':'customer follow-up','PMS':'project task','HRMS':'HR ticket'}[module]
        for i,a in enumerate(subjects):
            b=subjects[(i+1)%5];c='Approved handover: '+b
            plain=f'Create a {obj} called {a}, then add a {obj} called {b}'
            dated=plain if module=='HRMS' else f'Create a {obj} called {a} due tomorrow, then add a {obj} called {b} due today'
            duplicate=f'Create a {obj} called {a}, then add a {obj} called {a}'
            cases=[([plain,f'set "{b}" to high priority'],[a,b],{'priorities':[None,'High']}),
                ([plain,f'rename "{b}" to {c}'],[a,c],{}),
                ([dated,f'move "{b}" to tomorrow'],[a,b],{'dates':['tomorrow','tomorrow'],'question':module=='HRMS'}),
                ([dated,f'clear the due date of "{b}"'],[a,b],{'dates':['tomorrow',None],'question':module=='HRMS'}),
                ([dated,f'push "{b}" back by one week'],[a,b],{'dates':['tomorrow','in 1 week'],'question':module=='HRMS'}),
                ([plain,f'remove "{a}"'],[b],{}),
                ([plain,'set "Missing draft item" to high priority'],[],{'question':True}),
                ([duplicate,f'rename "{a}" to {c}'],[],{'question':True}),
                ([plain,f'make "{a}" low priority'],[a,b],{'priorities':['Low',None]}),
                ([plain,f'mark "{b}" high priority'],[a,b],{'priorities':[None,'High']})]
            for kind,(turns,titles,expected) in enumerate(cases):rows.append({'id':f'workplace-v5-{module}-{i}-{kind}','module':module,'turns':turns,'titles':titles,**expected})
    return rows

def benchmark():
    from app.ai_operator.workflows import local_plan
    from app.ai_operator.pms_agent import resolve_date
    rows=scenarios();failures=[];counts={}
    for row in rows:
        turn=0
        try:
            parent=None
            for turn,text in enumerate(row['turns'],1):
                data=SimpleNamespace(text=text,module=row['module'],project_id=12 if row['module']=='PMS' else None,request_key=str(uuid4()),timezone='Asia/Kolkata')
                plan,state=local_plan(data,parent,None)
                if turn==len(row['turns']) and row.get('question'):
                    if not plan or not plan.get('question') or plan.get('steps'):raise ValueError('Expected clarification without actions')
                    break
                if not plan or plan.get('question') or not plan.get('steps'):raise ValueError('Expected complete draft')
                parent=SimpleNamespace(status='awaiting_approval',result={'workflow':state})
            else:
                payloads=[s['payload'] for s in plan['steps']]
                if [p.get('title',p.get('subject')) for p in payloads]!=row['titles']:raise ValueError('Changed the wrong title/count')
                if any(s['tool'].split('.')[0].upper()!=row['module'] for s in plan['steps']):raise ValueError('Wrong module')
                if row.get('priorities') and [p.get('priority','Medium') for p in payloads]!=[v or 'Medium' for v in row['priorities']]:raise ValueError('Changed the wrong priority')
                if row.get('dates') and [p.get('due_date') for p in payloads]!=[resolve_date(d) if d else None for d in row['dates']]:raise ValueError('Changed the wrong deadline')
            counts[row['module']]=counts.get(row['module'],0)+1
        except Exception as exc:failures.append({'id':row['id'],'turn':turn,'message':row['turns'][turn-1],'error':str(exc)[:200]})
    training=training_examples();fit_failures=[]
    for sample in training:
        try:
            data=SimpleNamespace(text=sample['text'],module=sample['module'],project_id=12 if sample['module']=='PMS' else None,request_key=str(uuid4()),timezone='Asia/Kolkata')
            plan,_=local_plan(data,None,None)
            if not plan or plan.get('question') or len(plan.get('steps',[]))!=1:raise ValueError('Expected one training action')
            p=plan['steps'][0]['payload'];expected=next(t for t in TRAINING[sample['module']] if sample['text'].endswith(t))
            if p.get('title',p.get('name',p.get('subject')))!=expected:raise ValueError('Training title changed')
        except Exception as exc:fit_failures.append({'module':sample['module'],'text':sample['text'],'error':str(exc)[:200]})
    return {'version':'workplace-actions-v5','total':len(rows),'messages':sum(len(r['turns']) for r in rows),'passed':len(rows)-len(failures),'by_module':counts,'failures':failures,
        'training_fit':{'total':len(training),'passed':len(training)-len(fit_failures),'failures':fit_failures,'limits':'Authored command fit, not unseen language accuracy.'},
        'limits':'Fifth authored synthetic development batch; fitting and scenario subjects are separate. Planning only; native tests cover execution.'}
