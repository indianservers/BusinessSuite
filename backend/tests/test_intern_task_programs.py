from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from tests.test_intern_management import program, publish
from tests.test_interns_hub import interns
from app.apps.interns_hub.router import today
from app.apps.project_management.models import (PMSTask, PMSTaskAssignee, PMSInternAssignmentPlan,
    PMSInternTaskPack, PMSInternPackRun, PMSBulkDeadlineChange, PMSActivity)
from app.models.notification import Notification

ROOT = "/api/v1/interns-hub/management/learning"
PMS = "/api/v1/project-management"


def definition(p):
    def variant(level, stage):
        return {"title":f"{level} stage {stage}", "instructions":f"Follow {level} instructions.", "deliverables":"Working solution and explanation",
            "rubric":[{"key":"correctness", "label":"Correctness", "points":70, "description":"Meets requirements"}, {"key":"quality", "label":"Quality", "points":30, "description":"Clear evidence"}]}
    return {"project_id":p["project"].id, "name":"Weekly Internship Pack", "description":"Versioned learning path", "steps":[
        {"key":"intro", "week":1, "due_day":1, "depends_on":[], "variants":{l:variant(l,1) for l in ("beginner","intermediate","advanced")}},
        {"key":"build", "week":1, "due_day":4, "depends_on":["intro"], "variants":{l:variant(l,2) for l in ("beginner","intermediate","advanced")}}], "is_active":True}


def create(client, p):
    result = client.post(ROOT+"/packs", headers=p["headers"], json=definition(p))
    assert result.status_code == 201, result.text
    return result.json()


def run_body(p):
    return {"batch_id":p["batches"][0], "pack_version":1, "start_date":str(today()), "reviewer_user_id":p["admin"].id,
        "levels":{"beginner":[p["interns"][0][0].id], "advanced":[p["interns"][1][0].id]}, "request_key":str(uuid4())}


def extension(p, task_id):
    return {"project_id":p["project"].id, "assignments":[{"task_id":task_id, "user_id":e.user_id, "expected_due_date":str(today())} for e,_,_ in p["interns"]],
        "due_date":str(today()+timedelta(days=3)), "reason":"Additional time for project review", "request_key":str(uuid4())}


def test_bulk_extension_selected_only_notification_audit_and_retry(client, db, program):
    p=program; job,_=publish(client,p); data=extension(p,job["task_id"]); data["assignments"]=data["assignments"][:1]
    count_before=db.query(Notification).filter_by(event_type="intern_deadline_extended").count()
    assert client.post(ROOT+"/deadlines/preview",json=data,headers=p["headers"]).json()["count"] == 1
    assert db.query(PMSTaskAssignee).first().due_date == today()
    result=client.post(ROOT+"/deadlines/extend",json=data,headers=p["headers"])
    assert result.status_code == 200, result.text
    assert client.post(ROOT+"/deadlines/extend",json=data,headers=p["headers"]).json()["id"] == result.json()["id"]
    first,second=p["interns"][0][0],p["interns"][1][0]
    assert db.get(PMSTaskAssignee,(job["task_id"],first.user_id)).due_date == today()+timedelta(days=3)
    assert db.get(PMSTaskAssignee,(job["task_id"],second.user_id)).due_date == today()
    assert db.get(PMSTask,job["task_id"]).due_date == today()
    assert db.query(Notification).filter_by(event_type="intern_deadline_extended").count() == count_before+1
    audit=db.query(PMSActivity).filter_by(action="assignment.deadline_extended").one()
    assert data["reason"] in audit.metadata_json
    assert db.query(PMSBulkDeadlineChange).count() == 1
    assert client.get(ROOT+"/deadlines/history", params={"project_id":p["project"].id}, headers=p["headers"]).json()["total"] == 1
    assert client.get("/api/v1/interns-hub/tasks",headers=p["interns"][0][1]).json()[0]["due_date"] == data["due_date"]


def test_extension_atomic_stale_rejected_completed_and_permission_checks(client, db, program):
    p=program;job,_=publish(client,p);data=extension(p,job["task_id"])
    second=db.get(PMSTaskAssignee,(job["task_id"],p["interns"][1][0].user_id));second.execution_status="Done";db.commit()
    response=client.post(ROOT+"/deadlines/extend",json=data,headers=p["headers"])
    assert response.status_code == 409
    assert db.get(PMSTaskAssignee,(job["task_id"],p["interns"][0][0].user_id)).due_date == today()
    assert db.query(PMSBulkDeadlineChange).count() == 0
    second.execution_status="To Do";second.due_date=today()+timedelta(days=1);db.commit()
    assert client.post(ROOT+"/deadlines/extend",json=data,headers=p["headers"]).status_code == 409
    data["assignments"]=data["assignments"][:1];data["due_date"]=str(today())
    assert client.post(ROOT+"/deadlines/extend",json=data,headers=p["headers"]).status_code == 422
    assert client.post(ROOT+"/deadlines/extend",json=data,headers=p["interns"][0][1]).status_code == 403
    data["due_date"]=str(today()+timedelta(days=3));data["assignments"][0]["user_id"]=p["admin"].id
    assert client.post(ROOT+"/deadlines/extend",json=data,headers=p["headers"]).status_code == 403


def test_packs_skill_variants_preview_idempotency_and_frozen_versions(client, db, program):
    p=program;pack=create(client,p);body=run_body(p)
    preview=client.post(f"{ROOT}/packs/{pack['id']}/preview",json=body,headers=p["headers"])
    assert preview.status_code == 200,preview.text
    assert preview.json()["tasks"] == 4 and preview.json()["assignments"] == 4
    assert db.query(PMSTask).count() == 0
    result=client.post(f"{ROOT}/packs/{pack['id']}/publish",json=body,headers=p["headers"])
    assert result.status_code == 201,result.text
    assert client.post(f"{ROOT}/packs/{pack['id']}/publish",json=body,headers=p["headers"]).json() == result.json()
    assert db.query(PMSTaskAssignee).count() == 4 and db.query(PMSInternPackRun).count() == 1
    assert db.query(Notification).filter_by(event_type="intern_task_pack").count() == 2
    own=client.get("/api/v1/interns-hub/tasks",headers=p["interns"][0][1]).json()
    assert len(own) == 2 and all(t["skill_level"]=="beginner" for t in own)
    assert all("advanced" not in t["title"] for t in own)
    tasks_before=[t.description for t in db.query(PMSTask).order_by(PMSTask.id)]
    updated={k:v for k,v in pack.items() if k!="id"};updated["steps"][0]["variants"]["beginner"]["instructions"]="New future instructions"
    response=client.put(f"{ROOT}/packs/{pack['id']}",json=updated,headers=p["headers"])
    assert response.status_code == 200 and response.json()["version"] == 2
    assert [t.description for t in db.query(PMSTask).order_by(PMSTask.id)] == tasks_before
    assert "New future instructions" not in str(db.query(PMSInternPackRun).one().snapshot)
    assert client.put(f"{ROOT}/packs/{pack['id']}",json=updated,headers=p["headers"]).status_code == 409
    assert client.post(f"{ROOT}/packs/{pack['id']}/preview",json=body,headers=p["headers"]).status_code == 409


def test_dependencies_are_per_intern_and_rubric_is_enforced(client, db, program):
    p=program;pack=create(client,p);body=run_body(p)
    # Both interns use the same brief; approval for one must not unlock the other.
    body["levels"]={"beginner":[e.id for e,_,_ in p["interns"]]}
    response=client.post(f"{ROOT}/packs/{pack['id']}/publish",json=body,headers=p["headers"])
    assert response.status_code == 201,response.text
    plans=db.query(PMSInternAssignmentPlan).filter_by(user_id=p["interns"][0][0].user_id).all()
    first=next(a for a in plans if a.step_key=="intro");second=next(a for a in plans if a.step_key=="build")
    h=p["interns"][0][1];h2=p["interns"][1][1]
    assert client.post(f"/api/v1/interns-hub/tasks/{second.task_id}/start",headers=h).status_code == 409
    assert client.post(f"/api/v1/interns-hub/tasks/{second.task_id}/submissions",json={"notes":"Bypass attempt", "confirmed":True},headers=h).status_code == 409
    submission=client.post(f"/api/v1/interns-hub/tasks/{first.task_id}/submissions",json={"notes":"Completed first stage", "confirmed":True},headers=h)
    assert submission.status_code == 201,submission.text
    sid=submission.json()["id"]
    decision={"status":"Approved", "score":90, "feedback":"Good work", "inspected":True}
    assert client.post(f"{PMS}/work/submissions/{sid}/review",json=decision,headers=p["headers"]).status_code == 422
    decision["rubric"]={"correctness":65,"quality":25}
    assert client.post(f"{PMS}/work/submissions/{sid}/review",json=decision,headers=p["headers"]).status_code == 200
    assert client.post(f"/api/v1/interns-hub/tasks/{second.task_id}/start",headers=h).status_code == 200
    assert client.post(f"/api/v1/interns-hub/tasks/{second.task_id}/start",headers=h2).status_code == 409
    rows=client.get("/api/v1/interns-hub/tasks",headers=h).json()
    assert not next(t for t in rows if t["id"]==second.task_id)["blocked_by"]
    assert client.post(f"{PMS}/work/tasks/{first.task_id}/assignees/{p['interns'][0][0].user_id}/control",json={"action":"reassign","new_user_id":p["admin"].id,"reason":"Testing reassignment"},headers=p["headers"]).status_code == 409


def test_pack_validation_scope_and_future_release(client, db, program):
    p=program;data=definition(p)
    invalid=deepcopy(data);invalid["steps"][0]["depends_on"]=["build"]
    assert client.post(ROOT+"/packs",json=invalid,headers=p["headers"]).status_code == 422
    invalid=deepcopy(data);del invalid["steps"][0]["variants"]["advanced"]
    assert client.post(ROOT+"/packs",json=invalid,headers=p["headers"]).status_code == 422
    pack=create(client,p);body=run_body(p)
    body["levels"]["advanced"]=body["levels"]["beginner"]
    assert client.post(f"{ROOT}/packs/{pack['id']}/preview",json=body,headers=p["headers"]).status_code == 422
    body=run_body(p);body["levels"]["advanced"]=[p["admin"].id+99999]
    assert client.post(f"{ROOT}/packs/{pack['id']}/publish",json=body,headers=p["headers"]).status_code == 403
    assert db.query(PMSInternPackRun).count() == 0
    assert client.get(ROOT+"/packs",params={"project_id":p["project"].id},headers=p["interns"][0][1]).status_code == 403
    body=run_body(p);body["start_date"]=str(today()+timedelta(days=7))
    result=client.post(f"{ROOT}/packs/{pack['id']}/publish",json=body,headers=p["headers"])
    assert result.status_code == 201,result.text
    assert client.post(f"/api/v1/interns-hub/tasks/{result.json()['task_ids'][0]}/start",headers=p["interns"][0][1]).status_code == 409


def test_company_scope_is_explicit_even_for_superuser(client, db, program):
    from app.models.company import Company
    from app.apps.project_management.models import PMSProject
    p=program
    db.add(Company(id=90,name="Unrelated company"));db.flush()
    project=PMSProject(name="Other company program",project_key="OTHERPROG",organization_id=90)
    db.add(project);db.flush()
    foreign=PMSInternTaskPack(organization_id=90,project_id=project.id,name="Private pack",steps=definition(p)["steps"],created_by=p["admin"].id)
    db.add(foreign);db.commit()
    data=definition(p);data["project_id"]=project.id
    assert client.post(ROOT+"/packs",json=data,headers=p["headers"]).status_code in (403,404)
    assert client.post(f"{ROOT}/packs/{foreign.id}/preview",json=run_body(p),headers=p["headers"]).status_code == 404


@pytest.mark.parametrize("folder,prefix",[("alembic",""),("alembic_postgresql","pg_")])
def test_task_program_migration_roundtrip(folder,prefix):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine,MetaData,Table,Column,Integer,inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path=Path(__file__).resolve().parents[1]/folder/"versions"/(prefix+"20261027_039_intern_task_packs.py")
    spec=importlib.util.spec_from_file_location("task_program_migration",path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine("sqlite://");metadata=MetaData()
    for name in ("users","pms_projects","pms_tasks"):Table(name,metadata,Column("id",Integer,primary_key=True))
    with engine.begin() as connection:
        metadata.create_all(connection);migration.op=Operations(MigrationContext.configure(connection))
        migration.upgrade();migration.upgrade()
        assert "pms_intern_assignment_plans" in inspect(connection).get_table_names()
        migration.downgrade()
        assert set(inspect(connection).get_table_names()) == {"users","pms_projects","pms_tasks"}
        migration.upgrade()
        assert "pms_bulk_deadline_changes" in inspect(connection).get_table_names()
    engine.dispose()
