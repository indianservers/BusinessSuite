"""Repair and enrich only the manifest-owned local sample dataset.

No ORM flush events, workers, messages or published automations are invoked.
All changes commit together; the batch marker makes repeat runs a no-op.
"""
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select, text
from app.db.base import Base
from app.db.session import engine
from app.branches.catalog import SHARED, resource_key
from app.apps.power_apps.graph import VisualWorkflowDefinition

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'backups/local_suite_manifest.json'
MARK='LOCAL-SUITE-20261103-ENRICHED'
NOW=datetime(2026,11,3,14,0,tzinfo=timezone.utc)
TODAY=date(2026,11,3)


def main():
    if engine.url.host not in {'127.0.0.1','localhost','::1'}:
        raise RuntimeError('Loopback database required')
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    engine.echo=False
    tables=Base.metadata.tables
    counts,ids=Counter(),defaultdict(list)
    company,branch=manifest['company_id'],manifest['branch_id']
    with engine.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock(20261103)'))
        if db.execute(select(tables['intern_batches'].c.id).where(tables['intern_batches'].c.code=='LS26-BATCH-1')).first():
            print('Already enriched; no duplicate records added.')
            return
        admin=db.execute(text("select id from users where email='admin@aihrms.com' and is_superuser=true")).scalar_one()

        def add(table_name,**values):
            t=tables[table_name]
            for key,val in {'organization_id':company,'company_id':company,'created_by':admin,'created_at':NOW}.items():
                if key in t.c:values.setdefault(key,val)
            if 'id' in t.c:
                rid=db.execute(t.insert().values(**values).returning(t.c.id)).scalar_one()
                values['id']=rid
                ids[table_name].append(rid)
            else:
                db.execute(t.insert().values(**values))
                rid=None
            if table_name not in SHARED:
                db.execute(tables['suite_branch_ownership'].insert().values(resource_table=table_name,resource_key=resource_key(t,values),company_id=company,branch_id=branch,source=MARK))
            if rid and 'company_id' not in t.c and 'organization_id' not in t.c:
                db.execute(tables['security_resource_ownership'].insert().values(resource_table=table_name,resource_id=rid,company_id=company))
            counts[table_name]+=1
            return rid

        # Parent task state and individual execution state must agree in samples.
        reconciled=db.execute(text("""update pms_task_assignees a set execution_status=t.status,
            due_date=t.due_date, reviewer_user_id=:admin,
            progress_percent=case when t.status='Done' then 100 when t.status='In Review' then 90 when t.status='In Progress' then 40 else 0 end,
            completed_at=t.completed_at, source_key=:mark
            from pms_tasks t where a.task_id=t.id and t.id=any(:ids)"""),{'admin':admin,'mark':MARK,'ids':manifest['ids']['pms_tasks']}).rowcount
        employees=db.execute(select(tables['employees']).where(tables['employees'].c.id.in_(manifest['ids']['employees']),tables['employees'].c.employment_type=='Intern').order_by(tables['employees'].c.id)).mappings().all()
        departments=manifest['ids']['departments']
        projects=manifest['ids']['pms_projects']
        workspace=manifest['workspace_id']
        batch_by_department={}
        for i,department in enumerate(departments):
            batch_by_department[department]=add('intern_batches',name=f'Local sample · Internship cohort {i+1}',code=f'LS26-BATCH-{i+1}',department_id=department,manager_user_id=admin,mentor_user_id=admin,project_id=projects[i],project_ids=[projects[i]],program='Local sample internship',description=MARK,start_date=TODAY-timedelta(days=30),end_date=TODAY+timedelta(days=60),capacity=8,status='Active')
        for i,employee in enumerate(employees):
            uid,eid=employee['user_id'],employee['id']
            di=departments.index(employee['department_id'])
            project=projects[di]
            add('intern_batch_memberships',batch_id=batch_by_department[employee['department_id']],employee_id=eid,assigned_by=admin,status='Active',reason=MARK)
            db.execute(tables['employees'].update().where(tables['employees'].c.id==eid).values(contract_start_date=TODAY-timedelta(days=30),contract_end_date=TODAY+timedelta(days=60)))
            for name,values in [('pms_workspace_members',{'workspace_id':workspace,'user_id':uid,'role':'Member'}),('pms_project_members',{'project_id':project,'user_id':uid,'role':'Member','allocation_percent':25})]:
                t=tables[name]
                if not db.execute(select(t.c.id).filter_by(**{k:v for k,v in values.items() if k.endswith('_id')})).first():add(name,**values)
            for j,title in enumerate(['Document the requirements','Build the sample feature','Review test coverage','Prepare the handover guide','Present the weekly progress']):
                status=['Done','Done','In Review','In Progress','To Do'][j]
                due=TODAY+timedelta(days=j-2)
                tid=add('pms_tasks',project_id=project,title=title+' · intern '+str(i+1),task_key=f'LS26INT{i+1:02}-{j+1}',description=MARK+': fictional supervised work example',assignee_user_id=uid,reporter_user_id=admin,status=status,priority='Medium',due_date=due,estimated_hours=4,actual_hours=4 if j<2 else 1,completed_at=NOW-timedelta(days=1) if j<2 else None)
                add('pms_task_assignees',task_id=tid,user_id=uid,execution_status=status,due_date=due,reviewer_user_id=admin,progress_percent=100 if j<2 else 90 if j==2 else 40 if j==3 else 0,maximum_score=100,source_key=MARK,completed_at=NOW-timedelta(days=1) if j<2 else None)
                if j<3:
                    submission=add('pms_work_submissions',task_id=tid,user_id=uid,version=1,notes=MARK+': completed sample deliverable and documented validation.',links=[],files=[],status='Approved' if j<2 else 'Pending Review')
                    if j<2:add('pms_work_reviews',submission_id=submission,reviewer_user_id=admin,decision='Approved',score=80+i%16,maximum_score=100,communication_score=85,feedback=MARK+': clear documentation and acceptance criteria met.')
        # Existing sample reports were drafts, so the daily-report view omitted them.
        reports=tables['intern_hub_reports']
        db.execute(reports.update().where(reports.c.id.in_(manifest['ids']['intern_hub_reports'])).values(status='Submitted',submitted_at=NOW,minutes=240))
        for report in db.execute(select(reports).where(reports.c.id.in_(manifest['ids']['intern_hub_reports']),reports.c.report_date<TODAY)).mappings():
            add('intern_report_reviews',report_id=report['id'],reviewer_user_id=admin,decision='Approved',note=MARK+': fictional report review.')

        # Drafts should contain inspectable, side-effect-free steps, not empty graphs.
        graph=VisualWorkflowDefinition.model_validate({'nodes':[
            {'id':'start','type':'manual_trigger','label':'Start local sample','position':{'x':0,'y':100},'config':{}},
            {'id':'prepare','type':'set_variable','label':'Prepare sample request','position':{'x':320,'y':100},'config':{'name':'request_status','value':'Ready for review'}}],
            'edges':[{'id':'start_prepare','source':'start','target':'prepare'}]}).model_dump()
        db.execute(tables['power_apps_resources'].update().where(tables['power_apps_resources'].c.id.in_(manifest['ids']['power_apps_resources'])).values(definition=graph))
        # Assert the new cohort and pending review records exist inside this transaction.
        assert len(employees)==24 and counts['intern_batch_memberships']==24
        assert counts['pms_tasks']==120 and counts['pms_work_submissions']==72 and counts['pms_work_reviews']==48
        assert counts['intern_report_reviews']==96
    result={'marker':MARK,'counts':dict(counts),'ids':dict(ids),'reconciled_assignments':reconciled,'automation_graphs_updated':len(manifest['ids']['power_apps_resources'])}
    (ROOT/'backups/local_suite_enrichment_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='ids'},indent=2))


if __name__=='__main__':main()
