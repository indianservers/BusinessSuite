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
if __name__=='__main__':
    import uvicorn
    try:uvicorn.run(qa.app,host='127.0.0.1',port=1568,log_level='warning')
    finally:qa.engine.dispose();qa.temporary.cleanup()
