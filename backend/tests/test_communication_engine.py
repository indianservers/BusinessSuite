from uuid import uuid4
import pytest
from app.main import app
from app.core.security import create_access_token
from app.models.user import User
from app.models.notification import Notification
from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember, PMSProject, PMSTask
from app.apps.project_management.chat_models import ChatMessage
from app.shared.communication.models import Revision
from tests.tenant_test_utils import assign_company
from tests.test_pms_workspaces import middleware_database

BASE = "/api/v1/collaboration"

@pytest.fixture
def team(db, client):
    users = [User(email=f"collab{i}@test.com", hashed_password="unused", is_superuser=i == 0, is_active=True) for i in range(4)]
    db.add_all(users); db.flush()
    for i, user in enumerate(users): assign_company(db, user, 2 if i == 3 else 1)
    workspace = PMSWorkspace(name="Shared team", organization_id=1)
    db.add(workspace); db.flush()
    db.add_all([PMSWorkspaceMember(workspace_id=workspace.id, user_id=users[i].id, role="Owner" if i == 0 else "Member") for i in range(3)])
    db.commit()
    headers = [{"Authorization": "Bearer " + create_access_token(str(u.id))} for u in users]
    base = f"{BASE}/workspaces/{workspace.id}/chat"
    result = client.post(base+"/conversations", headers=headers[0], json={"kind":"channel","name":"general","visibility":"private","participants":[users[1].id]})
    assert result.status_code == 201, result.text
    room = result.json(); path=base+f"/conversations/{room['id']}"
    msg = client.post(path+"/messages", headers=headers[0], json={"client_id":str(uuid4()),"body":"Review the deployment"})
    assert msg.status_code == 200, msg.text
    return users, headers, workspace, path, msg.json()


def test_reactions_pins_saved_drafts_and_revisions(client,db,team):
    users,h,w,path,msg=team
    for actor in [h[0],h[1]]:
        assert client.put(path+f"/messages/{msg['id']}/reactions/👍",headers=actor,json={"enabled":True}).status_code == 200
    assert client.put(path+f"/messages/{msg['id']}/reactions/👍",headers=h[1],json={"enabled":True}).status_code == 200
    assert client.put(path+f"/messages/{msg['id']}/pin",headers=h[1],json={"enabled":True}).status_code == 403
    assert client.put(path+f"/messages/{msg['id']}/pin",headers=h[0],json={"enabled":True}).status_code == 200
    assert client.put(path+f"/messages/{msg['id']}/saved",headers=h[1],json={"enabled":True}).status_code == 200
    result=client.get(path+"/collaboration",headers=h[1]); assert result.status_code == 200,result.text
    assert result.json()["reactions"][0]["count"] == 2
    assert result.json()["saved_ids"] == [msg["id"]]
    assert client.get(path+"/collaboration",headers=h[0]).json()["saved_ids"] == []
    assert client.put(path+"/draft",headers=h[1],json={"body":"Private draft","thread_id":0}).status_code == 200
    assert client.get(path+"/draft",headers=h[1]).json()["body"] == "Private draft"
    assert client.get(path+"/draft",headers=h[0]).json()["body"] == ""
    response=client.patch(path+f"/messages/{msg['id']}",headers=h[0],json={"body":"Updated message"})
    assert response.status_code == 200,response.text
    assert db.query(Revision).filter_by(message_id=msg["id"]).one().body == "Review the deployment"


def test_followups_idempotency_assignment_and_task_sync(client,db,team):
    users,h,w,path,msg=team
    payload={"client_id":str(uuid4()),"message_id":msg["id"],"title":"Ship fix","assignee_id":users[1].id,"due_at":"2026-11-01T10:00:00Z"}
    assert client.post(path+"/followups",headers=h[1],json={**payload,"assignee_id":users[0].id}).status_code == 403
    response=client.post(path+"/followups",headers=h[0],json=payload); assert response.status_code == 201,response.text
    fid=response.json()["id"]
    assert client.post(path+"/followups",headers=h[0],json=payload).json()["id"] == fid
    assert client.post(path+"/followups",headers=h[0],json={**payload,"title":"Different"}).status_code == 409
    assert db.query(Notification).filter_by(event_type="chat.followup.assigned").count() == 1
    assert client.patch(path+f"/followups/{fid}",headers=h[1],json={"status":"Completed"}).json()["status"] == "Completed"
    project=client.post("/api/v1/project-management/projects",headers=h[0],json={"name":"Delivery","project_key":"COM","workspace_id":w.id})
    assert project.status_code == 200,project.text
    response=client.post(path+"/followups",headers=h[0],json={**payload,"client_id":str(uuid4()),"project_id":project.json()["id"]})
    assert response.status_code == 201,response.text
    task_id=response.json()["task_id"]; assert task_id
    cursor=client.get(BASE+"/events",headers=h[0]).json()["cursor"]
    completed=client.patch(f"/api/v1/project-management/tasks/{task_id}",headers=h[0],json={"status":"Done"})
    assert completed.status_code==200,completed.text
    assert client.get(BASE+"/events",headers=h[0],params={"cursor":cursor}).json()["changed"] is True
    result=client.get(path+"/collaboration",headers=h[0]); assert result.status_code == 200,result.text
    assert next(f for f in result.json()["followups"] if f["task_id"]==task_id)["status"] == "Completed"
    assert client.get(BASE+f"/tasks/{task_id}/source",headers=h[0]).json()["source"]["message_id"] == msg["id"]
    assert client.patch(path+f"/followups/{response.json()['id']}",headers=h[0],json={"status":"Completed"}).status_code == 409


def test_private_data_tenant_id_and_membership_tampering(client,db,team):
    users,h,w,path,msg=team
    for actor in [h[2],h[3]]:
        for suffix in ["/messages","/collaboration","/draft"]:
            assert client.get(path+suffix,headers=actor).status_code in {403,404}
        for suffix in [f"/messages/{msg['id']}/pin",f"/messages/{msg['id']}/saved",f"/messages/{msg['id']}/reactions/👍"]:
            assert client.put(path+suffix,headers=actor,json={"enabled":True}).status_code in {403,404}
    assert client.put(path+f"/messages/{msg['id']}/saved",headers=h[0],json={"enabled":True,"user_id":users[1].id}).status_code == 422
    db.query(PMSWorkspaceMember).filter_by(workspace_id=w.id,user_id=users[1].id).delete(); db.commit()
    assert client.get(path+"/collaboration",headers=h[1]).status_code == 404
    assert client.post(path+"/followups",headers=h[0],json={"client_id":str(uuid4()),"message_id":msg["id"],"title":"Wrong","assignee_id":users[3].id}).status_code == 422


def test_context_allowlist_and_xss_sanitization(client,db,team):
    users,h,w,path,msg=team
    response=client.post(path+"/contexts",headers=h[0],json={"module":"database","entity_type":"sql","entity_id":1})
    assert response.status_code == 422,response.text
    response=client.put(path+"/draft",headers=h[0],json={"body":"<!--suite-richtext:v1--><p>safe</p><script>alert(1)</script>"})
    assert response.status_code == 200,response.text
    assert "<script" not in client.get(path+"/draft",headers=h[0]).json()["body"]


def test_context_is_canonical_and_record_access_is_rechecked(client,db,team):
    users,h,w,path,msg=team
    project=client.post("/api/v1/project-management/projects",headers=h[0],json={"name":"Context project","project_key":"CTX","workspace_id":w.id})
    assert project.status_code == 200,project.text
    payload={"workspace_id":w.id,"module":"project_management","entity_type":"project","entity_id":project.json()["id"]}
    response=client.post(BASE+"/context-conversations",headers=h[0],json=payload)
    assert response.status_code == 201,response.text
    rid=response.json()["conversation_id"]
    assert client.post(BASE+"/context-conversations",headers=h[0],json=payload).json()["conversation_id"] == rid
    assert client.get(BASE+"/contexts/lookup",headers=h[0],params=payload).json()["conversation_id"] == rid
    assert client.post(BASE+"/context-conversations",headers=h[3],json=payload).status_code in {403,404}


def test_events_preferences_reminders_and_presence(client,db,team):
    from datetime import datetime, timezone
    from app.shared.communication.reminders import run_reminders
    users,h,w,path,msg=team
    cursor=client.get(BASE+"/events",headers=h[1]).json()["cursor"]
    assert client.get(BASE+"/events",headers=h[1],params={"cursor":cursor}).json()["changed"] is False
    assert client.put(path+"/preferences",headers=h[1],json={"mode":"mentions","favorite":True}).status_code == 200
    assert client.get(path+"/preferences",headers=h[1]).json()["favorite"] is True
    assert client.put(path+"/presence",headers=h[1],json={"typing":True}).status_code == 200
    assert next(p for p in client.get(path+"/presence",headers=h[0]).json()["users"] if p["id"] == users[1].id)["typing"] is True
    before=db.query(Notification).filter_by(user_id=users[1].id,event_type="chat.message").count()
    for body in ["not a mention", "@"+users[1].email+" review this"]:
        response=client.post(path+"/messages",headers=h[0],json={"client_id":str(uuid4()),"body":body})
        assert response.status_code == 200,response.text
    assert db.query(Notification).filter_by(user_id=users[1].id,event_type="chat.message").count() == before+1
    assert client.get(BASE+"/events",headers=h[1],params={"cursor":cursor}).json()["changed"] is True
    assert client.get(BASE+"/events",headers=h[3],params={"cursor":0}).json()["changed"] is False
    assert client.put(path+"/preferences",headers=h[1],json={"mode":"all"}).status_code == 200
    response=client.post(path+"/followups",headers=h[0],json={"client_id":str(uuid4()),"message_id":msg["id"],"title":"Due now","assignee_id":users[1].id,"due_at":"2020-01-01T10:00:00Z"})
    assert response.status_code == 201,response.text
    assert run_reminders(db)["sent"] == 1
    assert run_reminders(db)["sent"] == 0
    assert db.query(Notification).filter_by(event_type="chat.followup.due").count() == 1


def test_additive_migrations_preserve_existing_chat_history():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.db.base_class import Base
    from app.models.user import User
    from app.apps.project_management.models import PMSWorkspace
    from app.apps.project_management.chat_models import ChatConversation
    for folder,name in [("alembic","20261027_031_communication.py"),("alembic_postgresql","pg_20261027_031_communication.py")]:
        engine=create_engine("sqlite://")
        Base.metadata.create_all(engine,tables=[table for table in Base.metadata.sorted_tables if not table.name.startswith("communication_chat_")])
        with engine.begin() as connection:
            connection.execute(User.__table__.insert().values(id=901,email="migration@communication.test",hashed_password="unused",is_active=True))
            connection.execute(PMSWorkspace.__table__.insert().values(id=901,name="Existing workspace"))
            connection.execute(ChatConversation.__table__.insert().values(id=901,workspace_id=901,key="retained",kind="channel",name="History",owner_id=901))
            connection.execute(ChatMessage.__table__.insert().values(id=901,conversation_id=901,author_id=901,client_id="retained",body="Retain this history"))
            target=Path(__file__).resolve().parents[1]/folder/"versions"/name
            spec=importlib.util.spec_from_file_location("migration_communication",target);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
            assert connection.execute(ChatMessage.__table__.select().where(ChatMessage.id==901)).mappings().one()["body"] == "Retain this history"
            created=set(inspect(connection).get_table_names())
            assert all(table.name in created for table in Base.metadata.tables.values() if table.name.startswith("communication_chat_"))
        engine.dispose()


def test_private_meetings_use_calendar_and_replay_safely(client,db,team):
    from app.apps.project_management.models import PMSCalendarEvent
    users,h,w,path,msg=team
    payload={"client_id":str(uuid4()),"title":"Sprint review","start_at":"2027-01-10T10:00:00Z","end_at":"2027-01-10T10:30:00Z","meeting_url":"https://meet.example.com/review","timezone":"UTC"}
    result=client.post(path+"/meetings",headers=h[0],json=payload)
    assert result.status_code == 201,result.text
    event_id=result.json()["id"]
    assert db.get(PMSCalendarEvent,event_id).visibility == "private"
    assert client.post(path+"/meetings",headers=h[0],json=payload).json()["id"] == event_id
    assert db.query(PMSCalendarEvent).count() == 1
    assert client.get(path+"/meetings",headers=h[1]).json()["meetings"][0]["id"] == event_id
    assert client.get(path+"/meetings",headers=h[2]).status_code == 404
    invalid=client.post(path+"/meetings",headers=h[0],json={**payload,"client_id":str(uuid4()),"meeting_url":"javascript:alert(1)"})
    assert invalid.status_code == 422,invalid.text


def test_existing_channels_groups_files_threads_and_revocation_still_work(client,db,team):
    users,h,w,path,msg=team
    base=f"{BASE}/workspaces/{w.id}/chat"
    public=client.post(base+"/conversations",headers=h[0],json={"kind":"channel","name":"Public release","visibility":"public"})
    assert public.status_code==201,public.text
    pub=base+f"/conversations/{public.json()['id']}"
    assert client.post(pub+"/join",headers=h[2]).status_code==200
    dm=client.post(base+"/conversations",headers=h[0],json={"kind":"dm","participants":[users[1].id]})
    assert dm.status_code==201,dm.text
    assert client.get(base+f"/conversations/{dm.json()['id']}/messages",headers=h[2]).status_code==404
    group=client.post(base+"/conversations",headers=h[1],json={"kind":"group","name":"Reviewers","participants":[users[0].id,users[2].id]})
    assert group.status_code==201,group.text
    upload=client.post(path+"/attachments",headers=h[0],files={"file":("release-checklist.txt",b"Review before release","text/plain")})
    assert upload.status_code==201,upload.text
    file=upload.json()
    payload={"client_id":str(uuid4()),"body":"Checklist","attachment_ids":[file["id"]]}
    posted=client.post(path+"/messages",headers=h[0],json=payload)
    assert posted.status_code==200,posted.text
    assert client.post(path+"/messages",headers=h[0],json=payload).json()["id"]==posted.json()["id"]
    assert client.get(path+f"/attachments/{file['id']}",headers=h[1]).content==b"Review before release"
    assert client.get(path+f"/attachments/{file['id']}",headers=h[2]).status_code==404
    assert client.get(base+"/search",headers=h[1],params={"q":"release-checklist.txt"}).json()["results"][0]["id"]==posted.json()["id"]
    assert client.get(base+"/search",headers=h[2],params={"q":"release-checklist.txt"}).json()["results"]==[]
    reply=client.post(path+"/messages",headers=h[1],json={"client_id":str(uuid4()),"body":"<!--suite-richtext:v1--><p>Reviewed</p>","parent_id":msg["id"]})
    assert reply.status_code==200,reply.text
    thread=client.get(path+"/threads",headers=h[0]);assert thread.status_code==200,thread.text
    assert thread.json()["messages"][0]["latest_reply"]=="Reviewed"
    assert client.get(path+"/files",headers=h[1]).json()["files"][0]["id"]==file["id"]
    assert client.put(path+f"/messages/{msg['id']}/saved",headers=h[1],json={"enabled":True}).status_code==200
    assert client.get(path+"/saved",headers=h[1]).json()["messages"][0]["id"]==msg["id"]
    assert client.get(path+"/saved",headers=h[0]).json()["messages"]==[]
    assert client.delete(path+f"/messages/{posted.json()['id']}",headers=h[1]).status_code==404
    assert client.delete(path+f"/messages/{posted.json()['id']}",headers=h[0]).status_code==200
    removed=client.delete(path+f"/members/{users[1].id}",headers=h[0]);assert removed.status_code==200,removed.text
    assert client.get(path+"/messages",headers=h[1]).status_code==404
    assert client.get(path+f"/attachments/{file['id']}",headers=h[1]).status_code==404


def test_ai_never_executes_or_grants_access(client,db,team):
    users,h,w,path,msg=team
    response=client.post(path+"/ai",headers=h[2],json={"action":"summary"})
    assert response.status_code==404,response.text
    response=client.post(path+"/ai",headers=h[1],json={"action":"summary"})
    assert response.status_code in {403,503},response.text
    response=client.post(path+"/ai",headers=h[0],json={"action":"summary","is_superuser":True})
    assert response.status_code==422,response.text
    assert not db.get(User,users[1].id).is_superuser


def test_crm_and_hrms_adapters_reuse_authorized_native_records(client,db,team):
    from datetime import date
    from app.apps.crm.models import CRMLead,CRMDeal,CRMPipeline,CRMPipelineStage
    from app.models.employee import Employee
    users,h,w,path,msg=team
    lead=CRMLead(organization_id=1,first_name="Client",full_name="Client discussion",owner_user_id=users[0].id)
    pipeline=CRMPipeline(name="Communication QA");db.add_all([lead,pipeline]);db.flush()
    stage=CRMPipelineStage(pipeline_id=pipeline.id,name="Qualified");db.add(stage);db.flush()
    deal=CRMDeal(organization_id=1,name="Deal discussion",pipeline_id=pipeline.id,stage_id=stage.id,owner_user_id=users[0].id)
    employee=Employee(employee_id="COLLAB-EMP",first_name="Team",last_name="Member",date_of_joining=date(2026,1,1),user_id=users[1].id,status="Active")
    db.add_all([deal,employee]);db.commit()
    for module,entity,ident in [("crm","lead",lead.id),("crm","deal",deal.id),("hrms","employee",employee.id)]:
        payload={"workspace_id":w.id,"module":module,"entity_type":entity,"entity_id":ident}
        response=client.post(BASE+"/context-conversations",headers=h[0],json=payload)
        assert response.status_code==201,(entity,response.text)
        rid=response.json()["conversation_id"]
        source=BASE+f"/workspaces/{w.id}/chat/conversations/{rid}"
        message=client.post(source+"/messages",headers=h[0],json={"client_id":str(uuid4()),"body":"Internal record discussion"})
        assert message.status_code==200,(entity,message.text)
        assert client.post(BASE+"/context-conversations",headers=h[3],json=payload).status_code in {403,404}
        assert client.get(source+"/messages",headers=h[1]).status_code==404
