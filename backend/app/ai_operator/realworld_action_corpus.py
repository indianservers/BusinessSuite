"""Versioned, synthetic workplace language. No customer messages or PII.

Training and evaluation subjects are disjoint. This is a development regression
suite, not an untouched production holdout or a claim of general intelligence.
"""
from types import SimpleNamespace
from uuid import uuid4

SUBJECTS={
 'CRM':['Call the buyer about revised pricing','Chase the unsigned renewal','Check the demo feedback','Confirm the purchase order','Review the stalled proposal','Collect the billing address','Arrange the discovery call','Verify the decision maker','Share the implementation checklist','Check the delivery commitment'],
 'PMS':['Review the mobile login flow','Test the payment callback','Prepare the migration checklist','Validate the staging deployment','Document the rollback procedure','Check the accessibility fixes','Review the release notes','Verify the backup restore','Prepare the sprint handover','Resolve the integration blocker'],
 'HRMS':['Correct the attendance mismatch','Check the missing payslip','Replace the damaged access card','Review the reimbursement delay','Fix the incorrect reporting manager','Check the onboarding documents','Resolve the insurance enrolment issue','Update the emergency contact form','Investigate the shift allocation error','Check the leave balance discrepancy']}
TRAIN_SUBJECTS={
 'CRM':['Schedule the showroom visit','Collect the trial evaluation','Verify the quotation validity','Check the contract annexure','Review the prospect requirements','Confirm the sample dispatch','Arrange the account review','Record the negotiation notes','Prepare the commercial handover','Check the service renewal'],
 'PMS':['Validate the inventory import','Review the search pagination','Test the session expiry','Document the database upgrade','Prepare the UAT checklist','Review the performance trace','Check the feature flag rollout','Verify the export permissions','Resolve the build dependency','Plan the support transition'],
 'HRMS':['Correct the bank verification issue','Check the tax declaration status','Review the probation document','Fix the holiday calendar mapping','Check the travel claim receipt','Resolve the benefit selection error','Review the workstation request','Check the employment certificate','Correct the roster assignment','Review the exit clearance']}

def training_examples():
    rows=[]
    for module,titles in TRAIN_SUBJECTS.items():
        obj={'CRM':'customer follow-up','PMS':'project task','HRMS':'HR ticket'}[module]
        templates=[f'Please create a {obj} called {{title}}',f'Can you add a {obj} for {{title}}',f'I need you to prepare a new {obj} named {{title}}',
            f'Would you please open a {obj} titled {{title}}',f'Help me create a {obj}: {{title}}']
        for title in titles:
            for template in templates:rows.append({'module':module,'intent':'ticket.create' if module=='HRMS' else 'tasks.create','text':template.format(title=title),'split':'train'})
    return rows

def scenarios():
    rows=[]
    for module,subjects in SUBJECTS.items():
        obj={'CRM':'customer follow-up','PMS':'project task','HRMS':'HR ticket'}[module]
        for i,a in enumerate(subjects):
            b=subjects[(i+1)%len(subjects)];c='Final review: '+a
            pair=f'Create a {obj} called {a}, then add a {obj} called {b}'
            bulk=f'Please create {"project " if module=="PMS" else ""}tasks for {a}, {b} with high priority' if module!='HRMS' else pair
            bullet=f'Create {"project tasks" if module=="PMS" else "HR tickets" if module=="HRMS" else "tasks"}:\n- {a}\n- {b}'
            cases=[
                ([bulk,'make them all high priority'],[a,b],{'priority':'High'}),
                ([f'Could you create a {obj} called {a}','make it low priority'],[a],{'priority':'Low'}),
                ([pair,'set the second '+('ticket' if module=='HRMS' else 'task')+' to high priority'],[a,b],{'ordinal_priority':True}),
                ([bullet,f'rename the last one to {c}'],[a,c],{}),
                ([f'Help me create a {obj}: {a}','set it for tomorrow' if module=='HRMS' else 'move it to Friday'],[a],{'question':module=='HRMS','date':module!='HRMS'}),
                ([f'Create a {obj} called {a} assigned to Anita'],[],{'question':True}),
            ]
            for kind,(turns,titles,expected) in enumerate(cases):rows.append({'id':f'{module}-{i}-{kind}','module':module,'turns':turns,'titles':titles,**expected})
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
                    if not plan or not plan.get('question') or plan.get('steps'):raise ValueError('Expected clarification without executable steps')
                    break
                if not plan or plan.get('question') or not plan.get('steps'):raise ValueError('Expected a complete reviewable draft')
                parent=SimpleNamespace(status='awaiting_approval',result={'workflow':state})
            else:
                payloads=[s['payload'] for s in plan['steps']]
                if [p.get('title',p.get('subject')) for p in payloads]!=row['titles']:raise ValueError('Wrong titles or action count')
                if row.get('priority') and any(p.get('priority')!=row['priority'] for p in payloads):raise ValueError('Lost bulk/singular priority')
                if row.get('ordinal_priority') and (payloads[1].get('priority')!='High' or payloads[0].get('priority')=='High'):raise ValueError('Changed the wrong priority')
                if row.get('date') and payloads[0].get('due_date')!=resolve_date('next friday','Asia/Kolkata'):raise ValueError('Lost weekday deadline')
            counts[row['module']]=counts.get(row['module'],0)+1
        except Exception as exc:failures.append({'id':row['id'],'turn':turn,'message':row['turns'][turn-1],'error':str(exc)[:250]})
    return {'version':'workplace-actions-v1','total':len(rows),'messages':sum(len(r['turns']) for r in rows),'passed':len(rows)-len(failures),'by_module':counts,'failures':failures,
        'limits':'Synthetic realistic workplace scenarios, checked as development regressions; evaluation subjects are excluded from training. Planning only; native integration tests cover actual writes and permissions.'}
