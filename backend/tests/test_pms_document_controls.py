from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE


def test_document_save_link_changes_and_conflicts_under_branch_guards(client, db):
    wid, pid, owner, headers, _, member, _, guest, guest_headers = setup_workspace(client, db)
    task = client.post(f"{BASE}/projects/{pid}/tasks", headers=headers, json={"title":"Linked work", "task_key":"DOC-1"})
    assert task.status_code == 200, task.text
    created = client.post(f"{BASE}/projects/{pid}/docs", headers=headers, json={"title":"Audit brief", "content":"First draft"})
    assert created.status_code == 201, created.text
    path = f"{BASE}/docs/{created.json()['id']}"
    updated = client.put(path, headers=headers, json={"version":1,"title":"Reviewed brief","content":"Reviewed content","task_id":task.json()["id"]})
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2 and updated.json()["task_id"] == task.json()["id"]
    stale = client.put(path, headers=headers, json={"version":1,"title":"Overwrite","content":"Old version"})
    assert stale.status_code == 409
    assert client.get(path, headers=headers).json()["title"] == "Reviewed brief"
    revisions = client.get(path+'/revisions', headers=headers).json()
    assert [row["version"] for row in revisions] == [2,1]
    assert client.get(path+'/revisions/1', headers=headers).json()["content"] == "First draft"
    cleared = client.put(path, headers=headers, json={"version":2,"title":"Final brief","content":"Final content","task_id":None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["version"] == 3 and cleared.json()["task_id"] is None
    assert client.put(path, headers=guest_headers, json={"version":3,"title":"Guest edit"}).status_code in (403,404)


def test_document_rejects_cross_project_task_without_creating_revision(client, db):
    wid,pid,owner,headers,*_ = setup_workspace(client,db)
    other = client.post(BASE+'/projects', headers=headers, json={"name":"Other project","project_key":"OTHER","workspace_id":wid}).json()["id"]
    foreign = client.post(f"{BASE}/projects/{other}/tasks", headers=headers, json={"title":"Other work","task_key":"OTHER-1"}).json()["id"]
    document = client.post(f"{BASE}/projects/{pid}/docs", headers=headers, json={"title":"Scoped document"}).json()
    path = f"{BASE}/docs/{document['id']}"
    invalid = client.put(path, headers=headers, json={"version":1,"title":"Scoped document","task_id":foreign})
    assert invalid.status_code == 422, invalid.text
    assert client.get(path, headers=headers).json()["version"] == 1
    assert len(client.get(path+'/revisions', headers=headers).json()) == 1


def test_document_mapper_rejects_a_racing_session():
    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.orm.exc import StaleDataError
    from app.apps.project_management.models import PMSDocument
    # Independent sessions must not share the API fixture's nested savepoints.
    engine = create_engine("sqlite://")
    PMSDocument.__table__.create(engine)
    try:
        with Session(engine) as seed:
            doc = PMSDocument(project_id=1, title="Concurrent brief", content="", version=1, author_id=1, updated_by=1)
            seed.add(doc); seed.commit(); identity = doc.id
        with Session(engine) as first, Session(engine) as second:
            winner = first.get(PMSDocument, identity)
            stale = second.get(PMSDocument, identity)
            winner.title = "First writer"; winner.version = 2
            first.commit()
            stale.title = "Stale writer"; stale.version = 2
            with pytest.raises(StaleDataError):
                second.commit()
            second.rollback()
        with Session(engine) as check:
            assert check.get(PMSDocument, identity).title == "First writer"
    finally:
        engine.dispose()
