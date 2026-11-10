"""Conversion stage self-joins retain ordinary company/branch authorization."""
from app.apps.crm.models import CRMPipelineStage
from tests.test_authorization_audit import identity
from tests.test_crm_deal_workspace import create, BASE


def test_non_superuser_conversion_uses_scoped_stage_selectables(client, db, superuser_headers):
    actor, headers = identity(db, "conversion_viewer", ["crm_view", "crm_manage", "crm_deals_view", "crm_reports_view"])
    record = create(client, db, superuser_headers, owner_id=actor.id, amount=125)
    initial = db.get(CRMPipelineStage, record["stage_id"])
    following = CRMPipelineStage(name="Authorized proposal", organization_id=1,
        pipeline_id=record["pipeline_id"], position=(initial.position or 0) + 1,
        probability=60, active=True)
    foreign = CRMPipelineStage(name="OTHER COMPANY STAGE", organization_id=999,
        pipeline_id=record["pipeline_id"], position=50, active=True)
    db.add_all([following, foreign]); db.commit()
    moved = client.patch(f"/api/v1/crm/deals/{record['id']}", headers=superuser_headers,
                         json={"stage_id": following.id, "expected_version": 1})
    assert moved.status_code == 200, moved.text
    response = client.get(BASE + "/conversion", headers=headers)
    assert response.status_code == 200, response.text
    assert "OTHER COMPANY STAGE" not in response.text
    discovery = next(row for row in response.json()["items"] if row["stage_id"] == initial.id)
    assert discovery["entries"] == discovery["progressed"] == 1
    assert discovery["conversion_rate"] == 100
