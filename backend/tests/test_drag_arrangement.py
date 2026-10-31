from datetime import date
from tests.rich_text_test_utils import organization_context
from tests.test_pms_task_studio import studio
from tests.test_pms_workspaces import BASE, middleware_database
from app.apps.project_management.models import PMSTask, PMSSprint


def create_task(client, studio, key):
    response = client.post(f"{BASE}/task-studio/projects/{studio[6]['id']}/tasks", headers=studio[3], json={"task": {"title":key,"task_key":key},"assignment":{"people":[studio[0].id]}})
    assert response.status_code == 201, response.text
    return response.json()["task"]["id"]


def arrange(client, studio, tid, **data):
    detail = client.get(f"{BASE}/task-studio/tasks/{tid}", headers=studio[3]).json()
    return client.post(f"{BASE}/my-work/tasks/{tid}/arrange", headers=studio[3], json={"version":detail["version"],**data})


def test_sprint_move_is_atomic_preserves_hidden_siblings_and_rejects_stale(client, db, studio):
    first, hidden, last = [create_task(client, studio, key) for key in ["ORDER-1","ORDER-2","ORDER-3"]]
    sprint = PMSSprint(project_id=studio[6]["id"], name="Next sprint", start_date=date(2026,11,1), end_date=date(2026,11,14), status="Planned")
    db.add(sprint); db.commit()
    result=arrange(client,studio,last,group_by="sprint",sprint_id=None,before_id=first)
    assert result.status_code==200,result.text
    rows=client.get(BASE+"/backlog",params={"projectId":studio[6]["id"]},headers=studio[3]).json()["backlog"]
    assert [r["id"] for r in rows]==[last,first,hidden]
    detail=client.get(f"{BASE}/task-studio/tasks/{last}",headers=studio[3]).json()
    moved=arrange(client,studio,last,group_by="sprint",sprint_id=sprint.id)
    assert moved.status_code==200,moved.text
    stale=client.post(f"{BASE}/my-work/tasks/{last}/arrange",headers=studio[3],json={"version":detail["version"],"group_by":"sprint","sprint_id":None})
    assert stale.status_code==409,stale.text
    invalid=arrange(client,studio,last,group_by="sprint",sprint_id=None,before_id=999999)
    assert invalid.status_code==404
    db.expire_all();assert db.get(PMSTask,last).sprint_id==sprint.id
    denied=client.post(f"{BASE}/my-work/tasks/{first}/arrange",headers=studio[5],json={"group_by":"status","status":"Done","version":"old"})
    assert denied.status_code in (403,404)
    sprint=db.get(PMSSprint,sprint.id);sprint.status="Completed";db.commit()
    assert arrange(client,studio,last,group_by="sprint",sprint_id=None).status_code==409



def test_status_reorder_keeps_board_and_workflow_guards(client,db,studio):
    tid=create_task(client,studio,"STATUS-1")
    result=arrange(client,studio,tid,group_by="status",status="In Progress")
    assert result.status_code==200,result.text
    assert client.get(f"{BASE}/tasks/{tid}",headers=studio[3]).json()["status"]=="In Progress"
    block=client.post(f"{BASE}/task-workspace/tasks/{tid}/entries",headers=studio[3],json={"kind":"blocker","body":"Missing access","revision":0})
    assert block.status_code==201,block.text
    denied=arrange(client,studio,tid,group_by="status",status="Done")
    assert denied.status_code==409,denied.text


def test_project_upload_and_folders_are_scoped(client,db,studio,tmp_path,monkeypatch):
    from app.apps.project_management.api import router as module
    monkeypatch.setattr(module,"PMS_UPLOAD_ROOT",tmp_path)
    project=studio[6]["id"];h=studio[3]
    folder=client.post(BASE+"/file-folders",headers=h,json={"project_id":project,"name":"Design"})
    assert folder.status_code==201,folder.text
    fid=folder.json()["id"]
    uploaded=client.post(f"{BASE}/projects/{project}/files/upload",headers=h,data={"folder_id":fid},files={"file":("test.txt",b"private project bytes","text/plain")})
    assert uploaded.status_code==201,uploaded.text
    identity=uploaded.json()["id"]
    assert uploaded.json()["folder_id"]==fid
    assert client.get(f"{BASE}/attachments/{identity}/download",headers=h).content==b"private project bytes"
    assert client.post(f"{BASE}/projects/{project}/files/upload",headers=studio[5],files={"file":("x.txt",b"x","text/plain")}).status_code in (403,404)
    assert client.patch(f"{BASE}/files/{identity}",headers=h,json={"folder_id":999999}).status_code==404
    assert client.patch(f"{BASE}/files/{identity}",headers=h,json={"folder_id":None}).json()["folder_id"] is None


def test_quote_order_persists_rejects_duplicates_stale_and_finalized(client,db,studio):
    h=studio[3]
    quote=client.post("/api/v1/crm/quotes",headers=h,json={"quoteNumber":"ARR-1","issueDate":"2026-10-01","expiryDate":"2026-11-30"})
    assert quote.status_code==201,quote.text
    qid=quote.json()["id"]
    ids=[]
    for name in ["First","Second"]:
        r=client.post(f"/api/v1/crm/quotes/{qid}/lines",headers=h,json={"name":name,"quantity":1,"unit_price":100})
        assert r.status_code==201,r.text
        ids.append(r.json()["id"])
    root=f"/api/v1/crm/quotes/{qid}/lines/reorder"
    r=client.post(root,headers=h,json={"ids":ids[::-1],"previous_order":ids})
    assert r.status_code==200,r.text
    assert [x["id"] for x in r.json()["lines"]]==ids[::-1]
    assert client.post(root,headers=h,json={"ids":ids,"previous_order":ids}).status_code==409
    assert client.post(root,headers=h,json={"ids":[ids[0],ids[0]],"previous_order":ids[::-1]}).status_code==422
    from app.apps.crm.models import CRMQuotation
    db.get(CRMQuotation,qid).status="Accepted";db.commit()
    assert client.post(root,headers=h,json={"ids":ids,"previous_order":ids[::-1]}).status_code==409


def test_onboarding_and_custom_field_orders_are_complete(client,db,studio):
    from app.models.onboarding import OnboardingTemplate,OnboardingTemplateTask
    from app.models.platform import CustomFieldDefinition
    template=OnboardingTemplate(name="Start",organization_id=1);db.add(template);db.flush()
    steps=[OnboardingTemplateTask(template_id=template.id,task_name=name,order_index=index) for index,name in enumerate(["Equipment","Welcome"])]
    db.add_all(steps);db.commit();ids=[s.id for s in steps]
    r=client.post(f"/api/v1/onboarding/templates/{template.id}/tasks/reorder",headers=studio[3],json={"ids":ids[::-1],"previous_order":ids})
    assert r.status_code==200,r.text
    fields=[CustomFieldDefinition(module="arrange_test",field_key=f"key{i}",label=f"Field{i}",display_order=i) for i in range(2)]
    db.add_all(fields);db.commit();ids=[f.id for f in fields]
    r=client.post("/api/v1/custom-fields/definitions/reorder?module=arrange_test",headers=studio[3],json={"ids":ids[::-1],"previous_order":ids})
    assert r.status_code==200,r.text
    assert client.post("/api/v1/custom-fields/definitions/reorder?module=arrange_test",headers=studio[3],json={"ids":ids[:1],"previous_order":ids[::-1]}).status_code==422


def test_curriculum_and_chart_layout_revision_checks(client,db,studio):
    from app.models.lms import LearningCourse
    course=LearningCourse(code="ARR",title="Arrange",metadata_json={"preserved":"yes"});db.add(course);db.commit()
    url=f"/api/v1/lms/courses/{course.id}/curriculum"
    payload={"revision":0,"sections":[{"id":"s1","title":"One","lessons":[{"id":"l1","title":"Lesson","content":"Text"}]}]}
    r=client.put(url,headers=studio[3],json=payload)
    assert r.status_code==200,r.text
    assert client.put(url,headers=studio[3],json=payload).status_code==409
    assert client.put(url,headers=studio[3],json={"revision":1,"sections":[{"id":"s2","title":"   ","lessons":[]}]}).status_code==422
    db.expire_all();assert db.get(LearningCourse,course.id).metadata_json["preserved"]=="yes"
    url=BASE+f"/workspaces/{studio[6]['workspace_id']}/org-chart"
    chart=client.get(url,headers=studio[3]).json()
    payload={"revision":chart["revision"],"positions":{str(studio[0].id):{"x":400,"y":200}}}
    r=client.put(url+"/layout",headers=studio[3],json=payload)
    assert r.status_code==200,r.text
    assert r.json()["positions"][str(studio[0].id)]["x"]==400
    assert client.put(url+"/layout",headers=studio[3],json=payload).status_code==409


def test_crm_upload_folders_and_download_are_authenticated(client,db,studio,tmp_path,monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,"UPLOAD_DIR",str(tmp_path))
    h=studio[3];root="/api/v1/crm/file-workspace"
    created=client.post(root+"/folders",headers=h,json={"name":"Proposals"})
    assert created.status_code==201,created.text
    folder=created.json()["id"]
    r=client.post(root+"/upload",headers=h,files={"file":("proposal.txt",b"commercial information","text/plain")})
    assert r.status_code==201,r.text
    fid=r.json()["id"]
    moved=client.put(f"{root}/files/{fid}/folder",headers=h,json={"folder_id":folder,"previous_folder_id":None})
    assert moved.status_code==200,moved.text
    assert client.put(f"{root}/files/{fid}/folder",headers=h,json={"folder_id":None,"previous_folder_id":None}).status_code==409
    listing=client.get(root,headers=h)
    assert listing.status_code==200,listing.text
    assert listing.json()["files"][0]["folder_id"]==folder
    assert client.get(f"{root}/files/{fid}/download",headers=h).content==b"commercial information"
    assert client.get(f"{root}/files/{fid}/download").status_code in (401,403)


def test_position_reporting_rejects_cycles_and_cross_company(client,db,studio):
    from app.models.company import Position,Company
    db.add(Company(id=77,name="Foreign"));db.flush()
    parent=Position(company_id=1,organization_id=1,title="Manager",position_code="ARR-M")
    db.add(parent);db.flush()
    child=Position(company_id=1,organization_id=1,title="Report",position_code="ARR-R",manager_position_id=parent.id)
    foreign=Position(company_id=77,organization_id=77,title="Foreign",position_code="ARR-F")
    db.add_all([child,foreign]);db.commit()
    url=f"/api/v1/company/positions/{parent.id}/reporting"
    assert client.put(url,headers=studio[3],json={"manager_position_id":child.id}).status_code==422
    assert client.put(url,headers=studio[3],json={"manager_position_id":foreign.id}).status_code==422
    r=client.put(f"/api/v1/company/positions/{child.id}/reporting",headers=studio[3],json={"manager_position_id":None,"previous_manager_position_id":parent.id})
    assert r.status_code==200,r.text


def test_arrangement_migration_preserves_existing_files_and_quote_lines():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine,text,inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    spec=importlib.util.spec_from_file_location("arrangement_migration",Path(__file__).resolve().parents[1]/"alembic/versions/20261031_048_drag_arrangement.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine("sqlite://")
    with engine.begin() as connection:
        for table in ["users","pms_projects","pms_file_assets","crm_file_assets","crm_quotation_items"]:
            connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, label TEXT)"))
            connection.execute(text(f"INSERT INTO {table} VALUES (1,'Original')"))
        with Operations.context(MigrationContext.configure(connection)):module.upgrade()
        assert connection.execute(text("SELECT sort_order FROM crm_quotation_items")).scalar()==0
        assert connection.execute(text("SELECT label FROM pms_file_assets")).scalar()=="Original"
        assert "pms_file_folders" in inspect(connection).get_table_names()
        with Operations.context(MigrationContext.configure(connection)):module.downgrade()
        assert connection.execute(text("SELECT label FROM crm_quotation_items")).scalar()=="Original"
    engine.dispose()


def test_customization_layout_and_pipeline_orders_are_atomic(client,db,studio):
    from app.apps.customization.models import CustomizationLayout,CustomizationLayoutSection,CustomizationLayoutField,CustomizationField
    layout=CustomizationLayout(module_name="arrange",name="Arrange");db.add(layout);db.flush()
    sections=[CustomizationLayoutSection(layout_id=layout.id,title=name,order_index=i) for i,name in enumerate(["A","B"])];db.add_all(sections);db.flush()
    definition=CustomizationField(module_name="arrange",field_api_name="name",field_label="Name",field_type="text");db.add(definition);db.flush()
    field=CustomizationLayoutField(layout_id=layout.id,section_id=sections[0].id,field_id=definition.id,order_index=0);db.add(field);db.commit()
    root=f"/api/v1/customization/layouts/{layout.id}"
    detail=client.get(root,headers=studio[3]);assert detail.status_code==200,detail.text
    payload={"version":detail.json()["arrange_version"],"section_ids":[s.id for s in sections][::-1],"fields":[{"id":field.id,"section_id":sections[1].id}]}
    changed=client.post(root+"/arrange",headers=studio[3],json=payload);assert changed.status_code==200,changed.text
    assert client.post(root+"/arrange",headers=studio[3],json=payload).status_code==409
    from app.apps.crm.models import CRMPipeline,CRMPipelineStage
    pipeline=CRMPipeline(organization_id=1,name="Arrange");db.add(pipeline);db.flush()
    stages=[CRMPipelineStage(organization_id=1,pipeline_id=pipeline.id,name=name,position=i,order_index=i) for i,name in enumerate(["First","Next"])];db.add_all(stages);db.commit()
    ids=[s.id for s in stages]
    result=client.post(f"/api/v1/crm/pipelines/{pipeline.id}/stages/reorder",headers=studio[3],json={"ids":ids[::-1],"previous_order":ids})
    assert result.status_code==200,result.text
    db.expire_all();assert db.get(CRMPipelineStage,ids[1]).position==0
    assert db.get(CRMPipelineStage,ids[1]).order_index==0
