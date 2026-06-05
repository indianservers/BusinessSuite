from tests.srm_test_utils import create_engagement_via_confirm


def test_srm_profitability_snapshot_for_engagement(client, db, superuser_headers):
    engagement, _order = create_engagement_via_confirm(client, superuser_headers)
    response = client.get(f"/api/v1/srm/profitability?engagement_id={engagement['id']}", headers=superuser_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engagement_id"] == engagement["id"]
    assert "gross_margin_amount" in body
