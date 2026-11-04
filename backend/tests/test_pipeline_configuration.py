"""Horizontal editor transaction, stale-draft and tenant-boundary coverage."""
import pytest
from copy import deepcopy
from tests.rich_text_test_utils import organization_context

from app.apps.crm.models import CRMPipeline, CRMPipelineStage
from app.apps.project_management.models import PMSBoardColumn
from tests.test_pms_workspaces import account
from tests.test_pms_workspaces import middleware_database


@pytest.fixture(autouse=True)
def setup_branch(db, organization_context):
    from app.models.company import Company, Branch
    company = db.get(Company, 1)
    company.country = "India"
    company.email = "pipeline@example.test"
    if not db.query(Branch).filter_by(company_id=1, is_active=True).first():
        db.add(Branch(company_id=1, name="Pipeline branch", code="PIPELINE", is_active=True))
    db.commit()


@pytest.fixture
def company(client, db, setup_branch):
    from app.core.security import create_access_token
    from app.models.user import User
    from tests.tenant_test_utils import assign_company
    from app.models.company import Branch
    owner, headers = account(db, "pipeline-owner@example.test", True)
    branch = db.query(Branch).filter_by(company_id=1, is_active=True).first()
    headers.update({"X-Suite-Organization":"1","X-Suite-Branch":str(branch.id)})
    w = client.post("/api/v1/project-management/workspaces", headers=headers, json={"name":"Pipeline workspace"})
    assert w.status_code in (200,201), w.text
    r = client.post("/api/v1/project-management/projects", headers=headers, json={"name":"Pipeline project","project_key":"PIPE","workspace_id":w.json()["id"]})
    assert r.status_code == 200, r.text
    other = User(email="pipeline-other@example.test", hashed_password="unused", is_superuser=True, is_active=True)
    db.add(other); db.flush(); assign_company(db,other,2)
    foreign_branch = Branch(company_id=2, name="Other pipeline branch", code="OTHER", is_active=True)
    db.add(foreign_branch);db.flush()
    from app.models.company import Company
    db.get(Company,2).country="India";db.get(Company,2).email="other-pipeline@example.test"
    from app.branches.models import BranchGrant
    db.add(BranchGrant(user_id=other.id,company_id=2,branch_id=foreign_branch.id,can_write=True));db.commit()
    return [headers, {}, {"Authorization":"Bearer "+create_access_token(str(other.id)), "X-Suite-Organization":"2", "X-Suite-Branch":str(foreign_branch.id)}], w.json(), r.json()


def crm_draft(client, headers):
    created = client.post("/api/v1/crm/pipelines", headers=headers, json={"name": "Editor pipeline"})
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    stages = []
    for i, name in enumerate(["Discover", "Proposal"]):
        r = client.post(f"/api/v1/crm/pipelines/{pid}/stages", headers=headers, json={"name": name, "position": i + 1, "probability": 20, "color": "#278a48"})
        assert r.status_code == 201, r.text
        stages.append(r.json())
    fields = ("id", "name", "probability", "color", "is_won", "is_lost", "position")
    return pid, {"name": "Renamed pipeline", "expected_name": "Editor pipeline", "expected_stages": [{k: s[k] for k in fields} for s in stages], "stages": [{"id": str(s["id"]), "name": s["name"], "probability": 20, "color": "#278a48", "outcome": "open"} for s in stages], "remap": {}}


def test_crm_configuration_swaps_names_and_rejects_stale_draft(client, db, superuser_headers):
    pid, draft = crm_draft(client, superuser_headers)
    draft["stages"][0]["name"], draft["stages"][1]["name"] = "Proposal", "Discover"
    draft["stages"].reverse()
    draft["expected_stages"].reverse() # Snapshot transport order is not workflow order.
    r = client.put(f"/api/v1/crm/pipelines/{pid}/configuration", headers=superuser_headers, json=draft)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(CRMPipeline, pid).name == "Renamed pipeline"
    rows = db.query(CRMPipelineStage).filter_by(pipeline_id=pid, deleted_at=None).order_by(CRMPipelineStage.position).all()
    assert [s.name for s in rows] == ["Discover", "Proposal"]
    assert client.put(f"/api/v1/crm/pipelines/{pid}/configuration", headers=superuser_headers, json=draft).status_code == 409


def test_crm_configuration_invalid_stage_does_not_partially_rename(client, db, superuser_headers):
    pid, draft = crm_draft(client, superuser_headers)
    invalid = deepcopy(draft)
    invalid["stages"][1]["probability"] = 101
    r = client.put(f"/api/v1/crm/pipelines/{pid}/configuration", headers=superuser_headers, json=invalid)
    assert r.status_code == 422, r.text
    db.expire_all()
    assert db.get(CRMPipeline, pid).name == "Editor pipeline"
    assert [s.name for s in db.query(CRMPipelineStage).filter_by(pipeline_id=pid).order_by(CRMPipelineStage.position)] == ["Discover", "Proposal"]


def test_crm_remap_requires_same_outcome_and_preserves_deals(client, db, superuser_headers):
    from app.apps.crm.models import CRMDeal
    pid, draft = crm_draft(client, superuser_headers)
    source, destination = draft["stages"]
    response = client.post("/api/v1/crm/deals", headers=superuser_headers, json={"name": "Remap opportunity", "pipeline_id": pid, "stage_id": int(source["id"]), "amount": 1000, "currency": "INR"})
    assert response.status_code == 201, response.text
    deal_id = response.json()["id"]
    draft["stages"] = [destination]
    draft["remap"] = {source["id"]: destination["id"]}
    invalid = deepcopy(draft)
    invalid["stages"][0]["outcome"] = "won"
    r = client.put(f"/api/v1/crm/pipelines/{pid}/configuration", headers=superuser_headers, json=invalid)
    assert r.status_code == 409, r.text
    db.expire_all()
    assert db.get(CRMDeal, deal_id).stage_id == int(source["id"])
    r = client.put(f"/api/v1/crm/pipelines/{pid}/configuration", headers=superuser_headers, json=draft)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(CRMDeal, deal_id).stage_id == int(destination["id"])
    assert db.get(CRMDeal, deal_id).status == "Open"
    assert db.get(CRMPipelineStage, int(source["id"])).deleted_at is not None


def test_pms_configuration_preserves_system_status_and_blocks_cross_company(client, db, company):
    headers, _, project = company
    base = f"/api/v1/project-management/projects/{project['id']}/board"
    r = client.get(base, headers=headers[0])
    assert r.status_code == 200, r.text
    board = r.json()
    columns = sorted(board["columns"], key=lambda c: (c["position"], c["id"]))
    draft = {"name": "Delivery pipeline", "expected_name": board["name"], "expected_stages": [{k: c[k] for k in ("id", "name", "status_key", "position")} for c in columns], "stages": [{"id": str(c["id"]), "name": "Quality review" if c["status_key"] == "IN_REVIEW" else c["name"]} for c in columns], "remap": {}}
    denied = client.put(base + "/configuration", headers=headers[2], json=draft)
    assert denied.status_code in (403, 404), denied.text
    r = client.put(base + "/configuration", headers=headers[0], json=draft)
    assert r.status_code == 200, r.text
    db.expire_all()
    review = db.query(PMSBoardColumn).filter_by(board_id=board["id"], status_key="IN_REVIEW").one()
    assert review.name == "Quality review"
    assert client.put(base + "/configuration", headers=headers[0], json=draft).status_code == 409


def test_pms_stage_remap_cannot_complete_blocked_work(client, db, company):
    from app.apps.project_management.models import PMSTask, PMSBoard
    headers, _, project = company
    base = f"/api/v1/project-management/projects/{project['id']}"
    task = client.post(base + "/tasks", headers=headers[0], json={"title": "Blocked work", "task_key": "PIPE-1"})
    assert task.status_code == 200, task.text
    tid = task.json()["id"]
    block = client.post(f"/api/v1/project-management/task-workspace/tasks/{tid}/entries", headers=headers[0], json={"kind": "blocker", "body": "Waiting for access", "revision": 0})
    assert block.status_code == 201, block.text
    board = client.get(base + "/board", headers=headers[0]).json()
    columns = sorted(board["columns"], key=lambda c: (c["position"], c["id"]))
    source = next(c for c in columns if c["status_key"] == "TODO")
    target = next(c for c in columns if c["status_key"] == "DONE")
    draft = {"name": "Should roll back", "expected_name": board["name"], "expected_stages": [{k: c[k] for k in ("id", "name", "status_key", "position")} for c in columns], "stages": [{"id": str(c["id"]), "name": c["name"]} for c in columns if c["id"] != source["id"]], "remap": {str(source["id"]): str(target["id"])}}
    r = client.put(base + "/board/configuration", headers=headers[0], json=draft)
    assert r.status_code == 409, r.text
    db.expire_all()
    assert db.get(PMSTask, tid).status == "To Do"
    assert db.get(PMSBoardColumn, source["id"]) is not None
    assert db.get(PMSBoard, board["id"]).name == board["name"]
