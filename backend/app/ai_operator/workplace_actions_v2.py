"""Second, disjoint synthetic workplace batch; no production conversations.

150 new training utterances plus 150 separate development scenarios. These
exercise numeric references, ordinal dates, counts, semicolons and routing.
"""
from types import SimpleNamespace
from uuid import uuid4

EVALUATION={
 'CRM':['Discuss HR policy requirements with the prospect','Confirm the regional distributor margin','Review the rejected commercial amendment','Arrange the technical presales workshop','Validate the reseller onboarding pack','Check the revised warranty conditions','Collect the procurement escalation details','Review the annual maintenance scope','Confirm the customer acceptance criteria','Arrange the proof of concept review'],
 'PMS':['Resolve the payroll API mapping defect','Review the SSO tenant isolation tests','Validate the warehouse barcode sync','Check the offline form recovery','Prepare the disaster recovery exercise','Review the mobile push delivery trace','Verify the audit log retention job','Test the credit note reconciliation','Document the release dependency matrix','Check the scheduled report permissions'],
 'HRMS':['Review the compensatory off mismatch','Correct the overtime approval routing','Check the dependent medical card','Resolve the missing induction invitation','Verify the revised designation letter','Check the maternity benefit paperwork','Correct the remote work policy mapping','Review the cafeteria deduction discrepancy','Resolve the pension nomination error','Check the relocation allowance claim']}
TRAINING={
 'CRM':['Check the franchise eligibility documents','Arrange the solution architecture walkthrough','Review the distributor credit terms','Confirm the replacement shipment status','Collect the security questionnaire response','Review the subscription downgrade request','Check the installation site readiness','Confirm the partner referral agreement','Review the tender clarification response','Arrange the customer success handover'],
 'PMS':['Review the object storage lifecycle rule','Validate the timesheet rounding patch','Prepare the webhook replay drill','Check the browser permission fallback','Resolve the fiscal period locking defect','Document the incident escalation matrix','Verify the masking rules in exports','Review the API throttling dashboard','Test the interrupted upload recovery','Check the deployment approval matrix'],
 'HRMS':['Check the revised gratuity nomination','Review the late joining regularization','Correct the professional tax state mapping','Verify the paternity leave entitlement','Resolve the laptop return acknowledgement','Check the union membership deduction','Review the transfer reimbursement claim','Correct the retirement date notification','Check the employee referral payout','Resolve the missing appraisal invitation']}

def training_examples():
    rows=[]
    for module,subjects in TRAINING.items():
        for i,title in enumerate(subjects):
            obj='HR ticket' if module=='HRMS' else 'customer follow-up' if module=='CRM' else 'project milestone' if i%2 else 'project task'
            for phrase in [f'Could you log a {obj} titled {title}',f'Please submit a new {obj} called {title}',f'For the next step, create a {obj} named {title}',f'Please help me set up a {obj} for {title}',f'Let us prepare a {obj} titled {title}']:
                rows.append({'module':module,'intent':'ticket.create' if module=='HRMS' else 'milestone.create' if obj.endswith('milestone') else 'tasks.create','text':phrase,'split':'train'})
    return rows

def scenarios():
    rows=[]
    for module,subjects in EVALUATION.items():
        obj='HR ticket' if module=='HRMS' else 'project task' if module=='PMS' else 'customer follow-up'
        plural='HR tickets' if module=='HRMS' else 'project tasks' if module=='PMS' else 'tasks'
        noun='ticket' if module=='HRMS' else 'task'
        for i,a in enumerate(subjects):
            b=subjects[(i+1)%10];c='Final check: '+a
            pair=f'Log a {obj} called {a}, then submit a {obj} called {b}'
            cases=[
                ([pair,f'move the second {noun} to tomorrow'],[a,b],{'date':module!='HRMS','question':module=='HRMS'}),
                ([f'Please create {plural}: {a}; {b}',f'rename item 2 to {c}'],[a,c],{}),
                ([f'For the next step, create a {obj} named {a}','set item 1 to critical priority'],[a],{'priority':'Critical'}),
                ([pair,f'remove {noun} 1'],[b],{}),
                ([f'Create {3 if i%2 else 2} {plural} for {a}, {b}'],[a,b],{'question':bool(i%2)}),
            ]
            for kind,(turns,titles,expected) in enumerate(cases):rows.append({'id':f'workplace-v2-{module}-{i}-{kind}','module':module,'turns':turns,'titles':titles,**expected})
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
                if row.get('question') and turn==len(row['turns']):
                    if not plan or not plan.get('question') or plan.get('steps'):raise ValueError('Expected clarification, not executable steps')
                    break
                if not plan or plan.get('question') or not plan.get('steps'):raise ValueError('Expected a complete reviewable draft')
                if any(s['tool'].split('.')[0].upper()!=row['module'] for s in plan['steps']):raise ValueError('Title text changed the module')
                parent=SimpleNamespace(status='awaiting_approval',result={'workflow':state})
            else:
                payloads=[s['payload'] for s in plan['steps']]
                if [p.get('title',p.get('subject')) for p in payloads]!=row['titles']:raise ValueError('Wrong titles or action count')
                if row.get('priority') and any(p.get('priority')!=row['priority'] for p in payloads):raise ValueError('Numeric priority correction lost')
                if row.get('date') and (payloads[1].get('due_date')!=resolve_date('tomorrow') or payloads[0].get('due_date')):raise ValueError('Changed the wrong deadline')
            counts[row['module']]=counts.get(row['module'],0)+1
        except Exception as exc:failures.append({'id':row['id'],'turn':turn,'message':row['turns'][turn-1],'error':str(exc)[:250]})
    return {'version':'workplace-actions-v2','total':len(rows),'messages':sum(len(r['turns']) for r in rows),'passed':len(rows)-len(failures),'by_module':counts,'failures':failures,
        'limits':'Second authored synthetic development batch, disjoint from v1 and its training. Planning checks; native tests cover execution. Not production language accuracy.'}
