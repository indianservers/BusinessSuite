"""Native workspace/site/customer/WBS/resources/dependency UI through real HTTP."""
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from app.apps.project_management.models import PMSProject, PMSTask, PMSTaskAssignee, PMSTaskDependency, PMSWorkspace, PMSWorkspaceMember
from app.apps.crm.models import CRMCompany
from app.apps.srm.commercial_models import ProjectCommercial
from tests.test_construction_commercial import commercial
from tests.test_business_pack_construction import construction, construction_approver, scenario, catalog, directory_identity


def test_new_construction_site_commercial_and_canonical_wbs_ui(client, db, commercial, catalog, monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    case = commercial
    headers = case['headers']
    actor, branch, context_id, project_id = case['actor'], case['branch'], case['context'], case['project']
    from app.apps.srm.models import SRMWarehouse, SRMInventoryMovement
    from app.business_packs.models import PackMasterAvailability
    warehouse_id = catalog[1]
    db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context_id, resource_table='srm_warehouses', resource_key=str(warehouse_id), active=True))
    db.commit()
    warehouse_name = db.get(SRMWarehouse, warehouse_id).warehouse_name
    before_movements = db.query(SRMInventoryMovement).count()
    before_workspaces = db.query(PMSWorkspace).count()
    before_projects = db.query(PMSProject).count()
    before_customers = db.query(CRMCompany).count()
    site_name, site_key = 'Browser-created canonical site', 'UI-'+uuid4().hex[:10]
    customer_name = db.get(CRMCompany, 101).name
    identity = client.get('/api/v1/auth/me', headers=headers)
    access = client.get('/api/v1/access/me', headers=headers)
    assert identity.status_code == access.status_code == 200
    user = identity.json()
    primary = user['role'] if isinstance(user['role'], str) else (user['role'] or {}).get('name')
    user.update(role=primary, primary_role=primary, access=access.json())
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'construction-definition-native.cjs')
    with tempfile.TemporaryDirectory(prefix='construction-definition-browser-') as temporary:
        auth_file = Path(temporary) / 'identity.json'
        auth_file.write_text(json.dumps({'token': headers['Authorization'].split(' ', 1)[1], 'user': user,
            'branch': str(branch), 'context': str(context_id), 'project': project_id, 'workspace_name': 'Browser canonical Construction workspace', 'site_name': site_name, 'site_key': site_key, 'customer_name': customer_name, 'warehouse_name': warehouse_name, 'warehouse_id': warehouse_id, 'resource': actor.id}), encoding='utf-8')
        monkeypatch.setenv('SUITE_QA_AUTH_FILE', str(auth_file))
        test_control_center_real_browser(client, db, None, headers)
    db.expire_all()
    assert db.query(PMSProject).count() == before_projects + 1
    assert db.query(CRMCompany).count() == before_customers
    assert db.query(SRMInventoryMovement).count() == before_movements
    proof = json.loads((Path(__file__).resolve().parents[2] / '.local' / 'construction-definition-browser-proof.json').read_text(encoding='utf-8'))
    assert proof['stage'] == 'complete'
    site = db.get(PMSProject, proof['site_id'])
    assert site.project_key == site_key.strip().upper()
    assert site.name == site_name
    assert db.query(PMSWorkspace).count() == before_workspaces + 1
    workspace = db.get(PMSWorkspace, site.workspace_id)
    assert workspace.name == 'Browser canonical Construction workspace'
    owner = db.query(PMSWorkspaceMember).filter_by(workspace_id=workspace.id, user_id=actor.id).one()
    assert owner.role == 'Owner'
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackRecordOwnership
    native = db.get(BranchOwnership, (PMSWorkspace.__tablename__, str(workspace.id)))
    pack = db.query(PackRecordOwnership).filter_by(resource_table=PMSWorkspace.__tablename__, resource_key=str(workspace.id)).one()
    assert (native.company_id, native.branch_id, pack.company_id, pack.branch_id, pack.context_id) == (1, branch, 1, branch, context_id)
    assert db.get(ProjectCommercial, site.id).customer_id == 101
    tasks = db.query(PMSTask).filter_by(project_id=site.id).order_by(PMSTask.id).all()
    assert [task.id for task in tasks] == proof['task_ids']
    assert len(tasks) == 3 and tasks[2].parent_task_id == tasks[0].id
    assert db.query(PMSTaskAssignee).filter(PMSTaskAssignee.task_id.in_([task.id for task in tasks])).count() == 3
    dependency = db.query(PMSTaskDependency).filter_by(task_id=tasks[1].id).one()
    assert dependency.depends_on_task_id == tasks[0].id and dependency.lag_days == 1
