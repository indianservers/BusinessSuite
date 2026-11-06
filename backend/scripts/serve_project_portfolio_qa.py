"""Disposable loopback-only Projects acceptance workspace. Never deploy."""
from datetime import date, timedelta
import suite_navigation_qa_server as qa
from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember, PMSProject, PMSProjectMember, PMSClient, PMSTask, PMSMilestone
from app.apps.business_os.models import BOSEnabledModule
from app.branches.migration import backfill
with qa.SessionLocal() as db:
    owner=db.query(qa.User).filter_by(email='admin@suiteqa.example.com').one()
    member=db.query(qa.User).filter_by(email='employee@suiteqa.example.com').one()
    workspace=PMSWorkspace(name='Portfolio acceptance workspace', organization_id=1)
    db.add(workspace);db.flush()
    db.add_all([PMSWorkspaceMember(workspace_id=workspace.id,user_id=owner.id,role='Admin'),PMSWorkspaceMember(workspace_id=workspace.id,user_id=member.id,role='Member')])
    clients=[PMSClient(organization_id=1,name=name,company_name=name) for name in ['Acme Enterprises','Zenith Solutions','Vertex Tech','Nova Retail']]
    db.add_all(clients);db.flush()
    titles=['BusinessSuite Website Redesign','CRM Lead Management Rollout','Sales Pipeline Automation','Customer Self-Service Portal','WhatsApp Customer Support','Inventory Barcode Implementation','Warehouse Management Upgrade','Purchase Approval Workflow','Finance & Accounting Integration']
    for i in range(36):
        status=['Active','Active','Completed','On Hold','Planned','Draft'][i%6]
        project=PMSProject(organization_id=1,workspace_id=workspace.id,name=titles[i%9]+(f' - Phase {i//9+1}' if i>=9 else ''),project_key=f'BS{i+1:03}',description='Coordinate delivery, project ownership, and launch readiness with the project team.',client_id=clients[i%4].id,owner_user_id=owner.id if i%2==0 else member.id,manager_user_id=owner.id,status=status,priority=['High','Medium','Low','Critical'][i%4],health='Good',start_date=date.today()-timedelta(days=20),due_date=date.today()+timedelta(days=i-4),is_archived=i==35,budget_amount=100000)
        db.add(project);db.flush()
        db.add_all([PMSProjectMember(project_id=project.id,user_id=owner.id,role='Manager'),PMSProjectMember(project_id=project.id,user_id=member.id,role='Member')])
        for n in range(5):db.add(PMSTask(project_id=project.id,title=['Confirm requirements','Design review','Implementation','Quality assurance','Launch checklist'][n],task_key=f'BS{i+1:03}-{n+1}',status='Done' if status=='Completed' or n<i%5 else 'To Do',due_date=project.due_date))
        db.add(PMSMilestone(project_id=project.id,name='Release readiness',due_date=project.due_date,status='Completed' if status=='Completed' else 'Not Started'))
    db.query(BOSEnabledModule).filter_by(company_id=1,module_key='project_management').update({'enabled':True})
    from test_identity_utils import own_workflow_records
    for model in [PMSWorkspace,PMSWorkspaceMember,PMSProject,PMSProjectMember,PMSClient,PMSTask,PMSMilestone]:
        own_workflow_records(db,*db.query(model).all())
    db.flush();backfill(db.connection(),1);db.commit()
from app.apps.crm.models import CRMCompany, CRMPipeline, CRMPipelineStage, CRMDeal, CRMLead
with qa.SessionLocal() as db:
    actor=db.query(qa.User).filter_by(email='admin@suiteqa.example.com').one()
    pipeline=CRMPipeline(organization_id=1,name='Growth opportunities',is_default=True,created_by_user_id=actor.id)
    db.add(pipeline);db.flush()
    stages=[]
    for index,(name,probability,color) in enumerate([('Discovery',15,'#648be2'),('Qualified',35,'#8b5cf6'),('Proposal',60,'#d49a46'),('Negotiation',80,'#d176a3'),('Won',100,'#23a58c')]):
        stage=CRMPipelineStage(organization_id=1,pipeline_id=pipeline.id,name=name,probability=probability,position=index,order_index=index,color=color,is_won=name=='Won',stage_type='won' if name=='Won' else 'open')
        db.add(stage);stages.append(stage)
    db.flush()
    for index,name in enumerate(['Acme Enterprises','Zenith Solutions','Vertex Tech','Nova Retail']):
        company=CRMCompany(organization_id=1,name=name,owner_user_id=actor.id,account_type='Customer')
        db.add(company);db.flush()
        for offset,title in enumerate(['Platform implementation','Customer success expansion','Workflow automation']):
            stage=stages[(index+offset)%len(stages)]
            db.add(CRMDeal(organization_id=1,owner_user_id=actor.id,company_id=company.id,pipeline_id=pipeline.id,stage_id=stage.id,name=f'{name} · {title}',amount=125000+index*30000+offset*15000,currency='INR',probability=stage.probability,status='Won' if stage.is_won else 'Open',expected_close_date=date.today()+timedelta(days=index*7+offset*3),planning={'start_date':str(date.today()-timedelta(days=10+offset))},created_by_user_id=actor.id))
        db.add(CRMLead(organization_id=1,owner_user_id=actor.id,first_name=['Avery','Jordan','Morgan','Taylor'][index],full_name=['Avery Quinn','Jordan Lee','Morgan Reed','Taylor Blake'][index],company_name=name,status='New',source='Website',next_follow_up_at=qa.datetime.now(qa.timezone.utc)+timedelta(days=index),created_by_user_id=actor.id))
    db.flush()
    from test_identity_utils import own_workflow_records
    for model in [CRMCompany,CRMPipeline,CRMPipelineStage,CRMDeal,CRMLead]:own_workflow_records(db,*db.query(model).all())
    db.flush();backfill(db.connection(),1);db.commit()
import os
if os.environ.get('PROJECTS_QA_FRONTEND'):
    from pathlib import Path
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    frontend=Path(os.environ['PROJECTS_QA_FRONTEND']).resolve()
    workspace_root=Path(__file__).resolve().parents[2]
    if not frontend.is_relative_to(workspace_root):raise RuntimeError('QA frontend must remain in the workspace')
    @qa.app.get('/{path:path}',include_in_schema=False)
    def serve_frontend(path:str):
        candidate=(frontend/path).resolve()
        if not candidate.is_relative_to(frontend):raise HTTPException(404)
        return FileResponse(candidate if candidate.is_file() else frontend/'index.html')
if __name__=='__main__':
    import uvicorn
    try:uvicorn.run(qa.app,host='127.0.0.1',port=int(os.environ.get('PROJECTS_QA_PORT','1568')),log_level='warning')
    finally:qa.engine.dispose();qa.temporary.cleanup()
