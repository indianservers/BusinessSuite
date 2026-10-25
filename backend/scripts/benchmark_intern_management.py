"""Repeatable, disposable SQLite benchmark; no application database access."""
import os
import sys
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['ENVIRONMENT']='test'
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session
from app.db.base import Base
from app.models.user import User,Role
from app.models.company import Company,Branch,Department
from app.models.employee import Employee
from app.apps.project_management.models import PMSProject,PMSTask,PMSTaskAssignee
from app.apps.interns_hub.management_models import InternBatch,InternBatchMembership
from app.apps.interns_hub.management_api import dashboard,batch_analytics
from app.apps.interns_hub.performance import performance

def main():
    output={'engine':'SQLite disposable local file','interns':10000,'batches':100,'shared_tasks':20,'assignees':10000,'page_size':50,'measurements':{},'scope':'Single-process read benchmark, not production PostgreSQL concurrency certification'}
    with TemporaryDirectory(prefix='intern-management-benchmark-') as temp:
        engine=create_engine('sqlite:///'+str(Path(temp)/'bench.db'))
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(Role(id=1,name='super_admin'));db.add(Role(id=2,name='intern'))
            db.add(Company(id=1,name='Synthetic benchmark'));db.add(Branch(id=1,company_id=1,name='HQ'));db.add(Department(id=1,branch_id=1,name='Engineering'))
            db.add(User(id=1,email='synthetic-admin@example.test',hashed_password='no-login',role_id=1,is_active=True,is_superuser=True));db.flush()
            db.bulk_insert_mappings(User,[dict(id=i+2,email=f'synthetic-{i}@example.test',hashed_password='no-login',role_id=2,is_active=True) for i in range(10000)])
            db.bulk_insert_mappings(Employee,[dict(id=i+1,user_id=i+2,employee_id=f'BENCH-{i:05}',first_name='Synthetic',last_name=str(i),employment_type='Intern',status='Active',department_id=1,branch_id=1,date_of_joining=date.today()-timedelta(days=90)) for i in range(10000)])
            db.add(PMSProject(id=1,name='Delivery',project_key='BENCH',organization_id=1,manager_user_id=1));db.flush()
            db.bulk_insert_mappings(InternBatch,[dict(id=i+1,name=f'Batch {i+1}',code=f'B-{i+1}',organization_id=1,department_id=1,manager_user_id=1,mentor_user_id=1,project_id=1,program='Internship',start_date=date.today()-timedelta(days=90),end_date=date.today()+timedelta(days=10),capacity=100,status='Active') for i in range(100)])
            db.bulk_insert_mappings(InternBatchMembership,[dict(batch_id=i//100+1,employee_id=i+1,status='Active',active_slot=1,assigned_by=1) for i in range(10000)])
            db.bulk_insert_mappings(PMSTask,[dict(id=i+1,project_id=1,title='Shared brief '+str(i+1),description='A single description per cohort assignment',task_key=f'BENCH-{i+1}',status='To Do',due_date=date.today()+timedelta(days=5)) for i in range(20)])
            db.bulk_insert_mappings(PMSTaskAssignee,[dict(task_id=i//500+1,user_id=i+2,execution_status='To Do',maximum_score=100,source_key='benchmark',due_date=date.today()+timedelta(days=5)) for i in range(10000)])
            db.commit();admin=db.get(User,1);_=admin.role;_=admin.employee
            calls=[0]
            def count(*args):calls[0]+=1
            event.listen(engine,'before_cursor_execute',count)
            for label,operation in [('directory_first',lambda:performance(db,admin,{},date.today(),page=1,per_page=50)),('directory_last',lambda:performance(db,admin,{},date.today(),page=200,per_page=50)),('dashboard',lambda:dashboard({},admin,db)),('batch_analytics',lambda:batch_analytics({},admin,db))]:
                calls[0]=0;start=time.perf_counter();result=operation();elapsed=(time.perf_counter()-start)*1000
                output['measurements'][label]={'elapsed_ms':round(elapsed,2),'sql_statements':calls[0],'returned':len(result.get('items',[])) if isinstance(result,dict) and 'items' in result else len(result) if isinstance(result,list) else 1}
                if label.startswith('directory'):assert result['total']==10000 and len(result['items'])==50
            from app.apps.interns_hub.distribution import publish,process_job
            calls[0]=0;started=time.perf_counter()
            command=dict(project_id=1,title='Bulk assignment benchmark',description='One PMS description shared by 10,000 recipients',target_type='all',reviewer_user_id=1,due_date=date.today()+timedelta(days=1),idempotency_key='benchmark-10000')
            job=publish(db,admin,command,process=False);chunks=0
            while job.status!='Completed':
                job=process_job(db,job.id);chunks+=1
                if job.status=='Failed':raise RuntimeError(job.error)
            assert publish(db,admin,command).id==job.id
            assert db.query(PMSTaskAssignee).filter_by(task_id=job.task_id).count()==10000
            assert db.query(PMSTask).count()==21
            output['measurements']['bulk_distribution']={'elapsed_ms':round((time.perf_counter()-started)*1000,2),'sql_statements':calls[0],'recipients':10000,'chunks':chunks,'chunk_size':500,'new_shared_tasks':1,'idempotent_replay':True}
            event.remove(engine,'before_cursor_execute',count)
        engine.dispose()
    destination=Path(__file__).resolve().parents[2]/'docs/qa/intern-management/benchmark.json'
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output,indent=2))
if __name__=='__main__':main()
