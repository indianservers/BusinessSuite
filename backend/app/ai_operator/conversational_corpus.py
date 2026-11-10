"""Authored ERP language examples and compositional planning probes.

The training rows label individual intents. Complete workflow probes test the
composer separately; neither is a production-accuracy or competitor benchmark.
"""
from types import SimpleNamespace
from uuid import uuid4

PREFIXES=['Could you help me','I need you to',"I'd like you to",'Please help me to',"Let's go ahead and",
    'For my work today, please','As the next action,','Would you mind helping me','I want you to','Can you please']

def training_examples():
    result=[]
    families=[('CRM','tasks.create',['create a new CRM task','add a customer follow-up task','make a new follow-up task','prepare a fresh CRM task','draft a customer task','set up a new CRM task','put together a follow-up task','open a new CRM task']),
        ('PMS','tasks.create',['create a new project task','add a PMS task','make a project task','prepare a fresh project task','draft a new PMS task','set up a new project task','put together a project task','open a new project task']),
        ('PMS','milestone.create',['create a project milestone','add a new milestone','make a new PMS milestone','prepare a fresh milestone','draft a project milestone','set up a new milestone','put together a project milestone','open a new milestone']),
        ('HRMS','ticket.create',['create an HR ticket','add a new HR ticket','make a helpdesk ticket','prepare an HR support ticket','draft a new HR ticket','set up an HR ticket','put together an HR ticket','open a new HR ticket'])]
    for module,intent,objects in families:
        for prefix in PREFIXES:
            for obj in objects:
                result.append({'module':module,'intent':intent,'text':f'{prefix} {obj} called "Review sample delivery requirements"','split':'train'})
    return result

def probes():
    rows=[]
    for i,prefix in enumerate(PREFIXES):
        for titles in [('Design','Build','Test'),('Discover','Implement','Validate'),('Research','Prepare','Review'),('Plan','Develop','Release')]:
            rows.append({'id':f'batch-{i}-{titles[0]}','module':'CRM','project_id':None,'turns':[f'{prefix} create tasks for {titles[0]}, {titles[1]} and {titles[2]}',
                'make them all high priority','rename the second one to Review handover','add another task called Collect feedback','remove the last task'],'count':3,'title':'Review handover','title_step':1})
        for title in ('Product launch','Customer onboarding','Website delivery','Service rollout'):
            rows.append({'id':f'project-{i}-{title}','module':'PMS','project_id':None,'turns':[f'{prefix} create a project called {title} with tasks Design, Build and Test',
                'make them all high priority','rename the second one to Draft design'],'count':4,'title':'Draft design','title_step':1})
            rows.append({'id':f'subtasks-{i}-{title}','module':'PMS','project_id':12,'turns':[f'{prefix} create a project task called {title} with subtasks Prepare, Review and Release'],
                'count':4,'parent_refs':True})
    return rows

def benchmark():
    from app.ai_operator.workflows import local_plan
    failures=[];rows=probes()
    for row in rows:
        try:
            parent=None;plan=None
            for text in row['turns']:
                data=SimpleNamespace(text=text,module=row['module'],project_id=row['project_id'],request_key=str(uuid4()),timezone='Asia/Kolkata')
                plan,state=local_plan(data,parent,None)
                if not plan or plan.get('question') or not plan.get('steps'):raise ValueError('No complete reviewable draft')
                parent=SimpleNamespace(status='awaiting_approval',result={'workflow':state})
            if len(plan['steps'])!=row['count']:raise ValueError('Wrong action count')
            if row.get('title') and plan['steps'][row['title_step']]['payload'].get('title')!=row['title']:raise ValueError('Ordinal correction changed the wrong item')
            if row.get('parent_refs') and any(s['payload'].get('parent_task_id')!={'$step':1,'field':'id'} for s in plan['steps'][1:]):raise ValueError('Subtask parent reference lost')
        except Exception as error:failures.append({'id':row['id'],'error':str(error)[:200]})
    return {'total':len(rows),'passed':len(rows)-len(failures),'failures':failures,
        'limits':'Authored compositional planning probes, not independent language accuracy. They do not execute business actions; canonical API tests cover execution and permissions.'}
