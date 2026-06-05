from app.apps.srm.models import SRMEngagementLink

from tests.test_srm_crm_won_handoff import create_won_deal_with_quote


def test_srm_engagement_creation_links_crm_srm_records(client, db, superuser_headers):
    deal, quote = create_won_deal_with_quote(db, "Engagement Link Deal")

    response = client.post(f"/api/v1/srm/from-crm/deals/{deal.id}/create-sales-order", headers=superuser_headers)
    assert response.status_code == 201, response.text
    engagement = response.json()["engagement"]
    sales_order = response.json()["sales_order"]
    contract = response.json()["contract"]

    links = db.query(SRMEngagementLink).filter(SRMEngagementLink.engagement_id == engagement["id"]).all()
    link_keys = {(link.linked_module, link.linked_entity_type, link.linked_entity_id) for link in links}
    assert ("crm", "deal", deal.id) in link_keys
    assert ("crm", "quote", quote.id) in link_keys
    assert ("srm", "sales_order", sales_order["id"]) in link_keys
    assert ("srm", "contract", contract["id"]) in link_keys

    lifecycle = client.get(f"/api/v1/srm/engagements/{engagement['id']}/lifecycle", headers=superuser_headers)
    assert lifecycle.status_code == 200, lifecycle.text
    assert lifecycle.json()["sales_order"]["id"] == sales_order["id"]
    assert lifecycle.json()["billing_plan"]["engagement_id"] == engagement["id"]
