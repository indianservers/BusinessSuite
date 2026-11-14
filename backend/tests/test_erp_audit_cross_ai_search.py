"""Literal cross-module search query regression fixtures."""
from types import SimpleNamespace
from datetime import date
import pytest
from app.ai_agents.adapters.cross_module_ai_adapter import CrossModuleAiAdapter
from app.apps.crm.models import CRMLead, CRMCompany
from app.models.employee import Employee
from tests.test_import_workspace import import_headers
NEEDLES=["%","_",chr(92),chr(92)+"%",chr(92)+"_","/"]
@pytest.mark.parametrize("needle",NEEDLES)
@pytest.mark.parametrize("model,field",[(CRMLead,"full_name"),(CRMLead,"email"),(CRMLead,"company_name"),(CRMCompany,"name"),(CRMCompany,"email"),(CRMCompany,"website"),(Employee,"first_name"),(Employee,"last_name"),(Employee,"employee_id"),(Employee,"work_email")])
def test_cross_search_text_literal(db,model,field,needle):
    def row(label):
        if model is CRMLead:return model(organization_id=1,first_name=label,full_name=label)
        if model is CRMCompany:return model(organization_id=1,name=label)
        return model(employee_id=label,first_name=label,last_name=label,date_of_joining=date(2025,1,1))
    ordinary=row("Ordinary");match=row("Match")
    setattr(match,field,"QA"+needle+"Literal")
    db.add_all([ordinary,match]);db.commit()
    adapter=CrossModuleAiAdapter(db);user=SimpleNamespace(is_superuser=False,employee=SimpleNamespace(organization_id=1))
    method=adapter.safe_search_hrms if model is Employee else adapter.safe_search_crm
    key="employees" if model is Employee else "leads" if model is CRMLead else "customers"
    assert [r["id"] for r in method(user,{"query":needle})[key]]==[match.id]
    assert [r["id"] for r in method(user,{"query":"ORDINARY"})[key]]==[ordinary.id]


@pytest.mark.parametrize("needle",NEEDLES)
@pytest.mark.parametrize("field",["name","description"])
def test_cross_deal_search_literal(db,needle,field):
    from app.apps.crm.models import CRMDeal, CRMPipeline, CRMPipelineStage
    pipeline=CRMPipeline(name="Synthetic pipeline",organization_id=1);db.add(pipeline);db.flush()
    stage=CRMPipelineStage(name="Draft",pipeline_id=pipeline.id);db.add(stage);db.flush()
    ordinary=CRMDeal(name="Ordinary",pipeline_id=pipeline.id,stage_id=stage.id,organization_id=1)
    match=CRMDeal(name="Match",pipeline_id=pipeline.id,stage_id=stage.id,organization_id=1)
    setattr(match,field,"QA"+needle+"Literal")
    foreign=CRMDeal(name="QA"+needle+"Literal",pipeline_id=pipeline.id,stage_id=stage.id,organization_id=2)
    db.add_all([ordinary,match,foreign]);db.commit()
    user=SimpleNamespace(is_superuser=False,employee=SimpleNamespace(organization_id=1))
    result=CrossModuleAiAdapter(db).safe_search_crm(user,{"query":needle})
    assert [r["id"] for r in result["deals"]]==[match.id]


@pytest.mark.parametrize("needle",NEEDLES)
@pytest.mark.parametrize("field",["project_name","title","task_key"])
def test_cross_project_task_search_literal(client,db,import_headers,needle,field):
    from app.models.user import User
    from app.apps.project_management.models import PMSProject, PMSTask
    from test_identity_utils import own_workflow_records
    actor=db.query(User).filter_by(email="testadmin@test.com").one()
    project=PMSProject(name="Ordinary project",project_key="QA",organization_id=1)
    foreign=PMSProject(name="QA"+needle+"Literal",project_key="FOREIGN",organization_id=2)
    if field=="project_name":project.name="QA"+needle+"Literal"
    db.add_all([project,foreign]);db.flush()
    ordinary=PMSTask(project_id=project.id,title="Ordinary task",task_key="ORD")
    match=PMSTask(project_id=project.id,title="Match",task_key="MATCH")
    if field!="project_name":setattr(match,field,"QA"+needle+"Literal")
    hidden=PMSTask(project_id=foreign.id,title="QA"+needle+"Literal",task_key="FOREIGN")
    db.add_all([ordinary,match,hidden]);own_workflow_records(db,project,ordinary,match);db.commit()
    result=CrossModuleAiAdapter(db).safe_search_pms(actor,{"query":needle})
    assert [r["id"] for r in result["projects"]]==([project.id] if field=="project_name" else [])
    assert [r["id"] for r in result["tasks"]]==([] if field=="project_name" else [match.id])
