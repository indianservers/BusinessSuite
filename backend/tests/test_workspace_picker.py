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
