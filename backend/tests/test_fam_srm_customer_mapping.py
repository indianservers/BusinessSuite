from app.apps.fam.models import FAMParty, FAMSRMMapping
from tests.test_fam_srm_invoice_posting import create_sent_srm_invoice


def test_fam_creates_srm_customer_party_and_reuses_mapping(client, db, superuser_headers):
    first = create_sent_srm_invoice(client, superuser_headers, customer_id=1001)
    second = create_sent_srm_invoice(client, superuser_headers, customer_id=1001)

    first_post = client.post(f"/api/v1/fam/integrations/srm/post-invoice/{first['id']}", headers=superuser_headers).json()
    second_post = client.post(f"/api/v1/fam/integrations/srm/post-invoice/{second['id']}", headers=superuser_headers).json()

    assert first_post["party"]["id"] == second_post["party"]["id"]
    assert db.query(FAMParty).filter(FAMParty.party_code == "SRM-CUST-1001").count() == 1
    assert db.query(FAMSRMMapping).filter(FAMSRMMapping.srm_record_type == "customer", FAMSRMMapping.srm_record_id == 1001, FAMSRMMapping.fam_record_type == "party").count() == 1

