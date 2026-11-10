"""Third synthetic workplace batch: 270 fresh training inputs and 270 separate
development scenarios. No customer data; scores are not production accuracy.
"""
from types import SimpleNamespace
from uuid import uuid4

TRAINING={
 'CRM':['Review the enterprise pilot acceptance form','Confirm the channel incentive calculation','Check the disputed freight surcharge','Arrange the branch opening demonstration','Verify the concession approval trail','Review the equipment rental extension','Collect the supplier compliance attestation','Confirm the regional service coverage','Check the order cancellation settlement'],
 'PMS':['Validate the multilingual search tokenization','Review the recurring job deduplication','Test the encrypted attachment retrieval','Check the invoice import error recovery','Verify the cross region failover alert','Document the mobile cache invalidation','Review the sandbox tenant provisioning','Resolve the calendar daylight offset defect','Test the warehouse label print queue'],
 'HRMS':['Review the hardship advance repayment','Check the deputation allowance correction','Resolve the unpaid internship stipend','Verify the accident coverage endorsement','Correct the biometric device registration','Review the secondment consent document','Check the transport pickup allocation','Resolve the retrospective salary revision','Verify the parental insurance renewal']}
EVALUATION={
 'CRM':['Review the reseller territory overlap','Check the seasonal discount exclusion','Confirm the bundled support entitlement','Review the contract novation documents','Collect the installation completion proof','Arrange the product trial extension','Check the disputed renewal escalation','Verify the customer deposit adjustment','Confirm the service downgrade notice'],
 'PMS':['Validate the concurrent stock adjustment','Check the lost notification replay','Review the database index rollout','Test the decimal rounding reconciliation','Verify the federated login logout','Document the scheduled worker shutdown','Review the delayed event ordering','Check the offline signature capture','Test the duplicate file import prevention'],
 'HRMS':['Review the volunteering leave allocation','Correct the joining bonus recovery','Check the employee meal card loading','Resolve the survivor benefit enquiry','Review the apprenticeship completion letter','Verify the regional minimum wage mapping','Correct the shift transport eligibility','Check the medical reimbursement exclusion','Resolve the second location attendance']}

def training_examples():
    rows=[]
    for module,subjects in TRAINING.items():
        for i,title in enumerate(subjects):
            obj='HR ticket' if module=='HRMS' else 'customer follow-up' if module=='CRM' else 'project milestone' if i%2 else 'project task'
            for text in [f'Please create a {obj} called {title}',f'Could you log a {obj} titled {title}',f'Submit a new {obj} named {title}',f'Can you open a {obj} for {title}',f'Help me draft a {obj} titled {title}',f'Prepare a fresh {obj} called {title}',f'Put together a {obj} named {title}',f'I want you to add a {obj} for {title}',f"Let's set up a {obj} titled {title}",f'For my work today, please make a {obj} called {title}']:
                rows.append({'module':module,'intent':'ticket.create' if module=='HRMS' else 'milestone.create' if obj.endswith('milestone') else 'tasks.create','text':text,'split':'train'})
    return rows

def scenarios():
    rows=[]
    for module,subjects in EVALUATION.items():
        obj={'CRM':'customer follow-up','PMS':'project task','HRMS':'HR ticket'}[module]
        noun='ticket' if module=='HRMS' else 'task'
        plural={'CRM':'tasks','PMS':'project tasks','HRMS':'HR tickets'}[module]
        for i,a in enumerate(subjects):
            b=subjects[(i+1)%9];c='Reviewed: '+b
            plain=f'Create a {obj} called {a}, then add a {obj} called {b}'
            dated=plain if module=='HRMS' else f'Create a {obj} called {a} due tomorrow, then add a {obj} called {b} due today'
            cases=[
                ([f'Create {plural}:\n1. {a}, terms and approval\n2. {b}'],[a+', terms and approval',b],{}),
                ([plain,'set the priority of item 2 to high'],[a,b],{'second_priority':'High'}),
                ([plain,f'rename the second {noun} to {c}'],[a,c],{}),
                ([plain,'forget this draft'],[],{'cancelled':True}),
                ([f'Create a {obj} called {a}','change its priority to high'],[a],{'all_priority':'High'}),
                ([plain,'set the priority of all '+('tickets' if module=='HRMS' else 'tasks')+' to low'],[a,b],{'all_priority':'Low'}),
                ([dated,'set the due date of item 2 to day after tomorrow'],[a,b],{'dates':['tomorrow','in 2 days'],'question':module=='HRMS'}),
                ([dated,'clear the due date of item 2'],[a,b],{'dates':['tomorrow',None],'question':module=='HRMS'}),
                ([dated,'push item 2 back by 2 days'],[a,b],{'dates':['tomorrow','in 2 days'],'question':module=='HRMS'}),
                ([plain,'push item 2 back by 3 days'],[],{'question':True}),
            ]
            for kind,(turns,titles,expected) in enumerate(cases):rows.append({'id':f'workplace-v3-{module}-{i}-{kind}','module':module,'turns':turns,'titles':titles,**expected})
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
                if turn==len(row['turns']) and row.get('cancelled'):
                    if not plan or plan.get('steps') or not state.get('cancelled'):raise ValueError('Cancellation retained actions')
                    break
                if not plan or plan.get('question') or not plan.get('steps'):raise ValueError('Expected a complete draft')
                if any(s['tool'].split('.')[0].upper()!=row['module'] for s in plan['steps']):raise ValueError('Wrong module')
                parent=SimpleNamespace(status='awaiting_approval',result={'workflow':state})
            else:
                payloads=[s['payload'] for s in plan['steps']]
                if [p.get('title',p.get('subject')) for p in payloads]!=row['titles']:raise ValueError('Wrong titles/count')
                if row.get('all_priority') and any(p.get('priority')!=row['all_priority'] for p in payloads):raise ValueError('Lost priority')
                if row.get('second_priority') and (payloads[1].get('priority')!=row['second_priority'] or payloads[0].get('priority')==row['second_priority']):raise ValueError('Wrong priority target')
                if row.get('dates') and [p.get('due_date') for p in payloads]!=[resolve_date(d) if d else None for d in row['dates']]:raise ValueError('Lost or incorrectly shifted deadline')
            counts[row['module']]=counts.get(row['module'],0)+1
        except Exception as exc:failures.append({'id':row['id'],'turn':turn,'message':row['turns'][turn-1],'error':str(exc)[:250]})
    fit_failures=[];training=training_examples()
    for sample in training:
        try:
            data=SimpleNamespace(text=sample['text'],module=sample['module'],project_id=12 if sample['module']=='PMS' else None,request_key=str(uuid4()),timezone='Asia/Kolkata')
            plan,_=local_plan(data,None,None)
            if not plan or plan.get('question') or len(plan.get('steps',[]))!=1:raise ValueError('Training utterance did not prepare one action')
            step=plan['steps'][0];payload=step['payload']
            expected=next(title for title in TRAINING[sample['module']] if sample['text'].endswith(title))
            if payload.get('title',payload.get('name',payload.get('subject')))!=expected:raise ValueError('Training title changed')
            if step['tool'].split('.')[0].upper()!=sample['module']:raise ValueError('Wrong training module')
        except Exception as exc:fit_failures.append({'module':sample['module'],'text':sample['text'],'error':str(exc)[:200]})
    return {'version':'workplace-actions-v3','total':len(rows),'messages':sum(len(r['turns']) for r in rows),'passed':len(rows)-len(failures),'by_module':counts,'failures':failures,
        'training_fit':{'total':len(training),'passed':len(training)-len(fit_failures),'failures':fit_failures,'limits':'Authored training commands checked for planning fit, not unseen language accuracy.'},
        'limits':'Third authored synthetic development batch. Separate subjects for fitting/evaluation. Planning only; native tests cover execution. Not production or competitor accuracy.'}
