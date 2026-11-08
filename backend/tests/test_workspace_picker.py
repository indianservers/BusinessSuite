from tests.rich_text_test_utils import organization_context
from app.models.company import Company
from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember
from tests.test_pms_task_studio import studio
from tests.test_pms_workspaces import middleware_database,BASE


def test_picker_metadata_and_organization_boundary(client,db,studio):
    owner,member,outsider,headers,*_=studio
    db.add(Company(id=2,name="Foreign picker company"));db.flush()
    foreign=PMSWorkspace(organization_id=2,name="Foreign workspace")
    db.add(foreign);db.flush()
    db.add(PMSWorkspaceMember(workspace_id=foreign.id,user_id=owner.id,role="Owner"));db.commit()
    response=client.get(BASE+"/workspaces",headers=headers)
    assert response.status_code==200,response.text
    assert foreign.id not in [row["id"] for row in response.json()]
    for row in response.json():
        assert row["member_count"]==db.query(PMSWorkspaceMember).filter_by(workspace_id=row["id"]).count()
        assert row["created_at"]
        assert row["role"] in {"Owner","Admin","Member","Guest"}


def test_directory_metrics_follow_overview_and_membership_removal(client, db, studio):
    from datetime import datetime
    from app.apps.project_management.models import PMSTask, PMSProject
    owner, member, outsider, headers, member_headers, outsider_headers, project, *_ = studio
    pid, wid = project["id"], project["workspace_id"]
    # The studio member is an intern; use a regular member for directory access.
    from tests.test_pms_workspaces import account
    member, member_headers = account(db, "directory-member@test.com")
    member_headers.update({key: headers[key] for key in ("X-Suite-Organization", "X-Suite-Branch")})
    db.add(PMSWorkspaceMember(workspace_id=wid, user_id=member.id, role="Member"))
    db.add_all([
        PMSTask(project_id=pid, task_key="DIR-1", title="Delivered", status="Done"),
        PMSTask(project_id=pid, task_key="DIR-2", title="In flight", status="In Progress"),
        PMSTask(project_id=pid, task_key="DIR-3", title="Removed", status="Done", deleted_at=datetime.utcnow()),
    ])
    removed = PMSProject(organization_id=1, workspace_id=wid, name="Removed project", project_key="DIR-REMOVED", deleted_at=datetime.utcnow())
    db.add(removed)
    db.flush()
    db.add(PMSTask(project_id=removed.id, task_key="DIR-4", title="Hidden project task", status="Done"))
    db.commit()
    response = client.get(BASE + "/workspaces", headers=member_headers)
    assert response.status_code == 200, response.text
    row = next(row for row in response.json() if row["id"] == wid)
    overview = client.get(f"{BASE}/workspaces/{wid}/overview", headers=member_headers).json()
    assert row["project_count"] == len(overview["projects"]) == 1
    assert row["task_count"] == len(overview["tasks"]) == 2
    assert row["completed_task_count"] == 1
    assert row["owners"] == [owner.email]
    assert client.get(BASE + "/workspaces", headers=outsider_headers).json() == []
    membership = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=member.id).one()
    db.delete(membership)
    db.commit()
    assert client.get(BASE + "/workspaces", headers=member_headers).json() == []
    assert client.get(f"{BASE}/workspaces/{wid}/overview", headers=member_headers).status_code == 404
