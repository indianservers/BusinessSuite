"""Fourth disjoint synthetic workplace batch: 150 new training utterances and
150 separate correction scenarios. Development regressions, not production data.
"""
from types import SimpleNamespace
from uuid import uuid4

TRAINING={
 'CRM':['Check the export licence acknowledgement','Review the customer credit reinstatement','Confirm the distributor rebate dispute','Collect the product recall acceptance','Arrange the facilities inspection visit','Verify the equipment buyback valuation','Review the commercial arbitration notice','Confirm the logistics damage evidence','Check the extended trial conversion','Review the solution certification request'],
 'PMS':['Validate the immutable audit archive','Review the queue poison message handling','Test the regional pricing cache refresh','Check the attachment virus scan callback','Verify the temporary access expiry','Document the retry storm recovery','Resolve the currency precision overflow','Review the reconciliation lock contention','Test the smart card session recovery','Check the permission inheritance migration'],
 'HRMS':['Review the sabbatical return clearance','Verify the flexible benefit carryover','Correct the relocation clawback schedule','Check the attendance device reassignment','Resolve the pension fund transfer delay','Review the apprenticeship stipend arrears','Verify the guardianship benefit declaration','Check the travel insurance cancellation','Correct the emergency duty allowance','Review the employee housing deduction']}
EVALUATION={
 'CRM':['Check the discontinued product replacement','Review the reseller insolvency notice','Confirm the customer training attendance','Arrange the tender presentation rehearsal','Verify the warranty transfer consent'],
 'PMS':['Review the queued payment reversal','Test the segmented upload checksum','Verify the offline role revocation','Check the expired signing certificate','Document the failover routing exception'],
 'HRMS':['Review the promotion effective date','Check the commuter benefit suspension','Correct the leave encashment exclusion','Verify the retirement counselling invite','Resolve the payroll garnishment enquiry']}

def training_examples():
    rows=[]
    for module,subjects in TRAINING.items():
        for i,title in enumerate(subjects):
            obj='HR ticket' if module=='HRMS' else 'customer follow-up' if module=='CRM' else 'project milestone' if i%2 else 'project task'
            for text in [f'I would like you to log a {obj} titled {title}',f'Please help me prepare a {obj} named {title}',f'Can you draft a fresh {obj} called {title}',f'Let us submit a {obj} for {title}',f'For the next step, set up a {obj} titled {title}']:
                rows.append({'module':module,'intent':'ticket.create' if module=='HRMS' else 'milestone.create' if obj.endswith('milestone') else 'tasks.create','text':text,'split':'train'})
    return rows

def scenarios():
    rows=[]
    for module,subjects in EVALUATION.items():
        obj={'CRM':'customer follow-up','PMS':'project task','HRMS':'HR ticket'}[module]
        for i,a in enumerate(subjects):
            b=subjects[(i+1)%5];c='Approved review: '+b
            plain=f'Create a {obj} called {a}, then add a {obj} called {b}'
            dated=plain if module=='HRMS' else f'Create a {obj} called {a} due in 1 week, then add a {obj} called {b} due in 4 days'
            long=plain if module=='HRMS' else f'Create a {obj} called {a} due in 1 week, then add a {obj} called {b} due in 2 weeks'
            cases=[([dated,'bring item 2 forward by 2 days'],[a,b],{'dates':['in 1 week','in 2 days'],'question':module=='HRMS'}),
                ([long,'move item 2 earlier by one week'],[a,b],{'dates':['in 1 week','in 1 week'],'question':module=='HRMS'}),
                ([plain,"change item 2's priority to high"],[a,b],{'second_priority':'High'}),
                ([plain,f'rename item 2 as {c}'],[a,c],{}),
                ([plain,f'change the title of item 2 to {c}'],[a,c],{}),
                ([dated,'remove the due date from item 2'],[a,b],{'dates':['in 1 week',None],'question':module=='HRMS'}),
                ([plain,'make both high priority'],[a,b],{'all_priority':'High'}),
                ([f'Create a {obj} called {a}',f'change its title to {c}'],[c],{}),
                ([plain,'increase the priority of item 2'],[],{'question':True}),
                ([plain,'bring item 2 forward by 2 days'],[],{'question':True})]
            for kind,(turns,titles,expected) in enumerate(cases):rows.append({'id':f'workplace-v4-{module}-{i}-{kind}','module':module,'turns':turns,'titles':titles,**expected})
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
                if [p.get('title',p.get('subject')) for p in payloads]!=row['titles']:raise ValueError('Wrong titles/count')
                if any(s['tool'].split('.')[0].upper()!=row['module'] for s in plan['steps']):raise ValueError('Wrong module')
                if row.get('all_priority') and any(p.get('priority')!=row['all_priority'] for p in payloads):raise ValueError('Lost both-item priority')
                if row.get('second_priority') and (payloads[1].get('priority')!=row['second_priority'] or payloads[0].get('priority')==row['second_priority']):raise ValueError('Wrong priority target')
                if row.get('dates') and [p.get('due_date') for p in payloads]!=[resolve_date(d) if d else None for d in row['dates']]:raise ValueError('Wrong date direction or target')
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
    return {'version':'workplace-actions-v4','total':len(rows),'messages':sum(len(r['turns']) for r in rows),'passed':len(rows)-len(failures),'by_module':counts,'failures':failures,
        'training_fit':{'total':len(training),'passed':len(training)-len(fit_failures),'failures':fit_failures,'limits':'Fit on authored commands, not generalization.'},
        'limits':'Fourth authored synthetic development batch, with separate fitting and scenario subjects. Native tests cover actual actions; not production accuracy.'}
