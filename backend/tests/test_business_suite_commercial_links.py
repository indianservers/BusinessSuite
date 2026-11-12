"""Contract creation must be exercised with a real shared customer, not a dummy ID."""
from tests.test_contact_directory import directory_identity
from app.apps.crm.models import CRMCompany
from app.apps.srm.models import SRMContract


def test_tc061_contract_reuses_existing_canonical_customer(client, db, superuser_headers):
    buyer = client.post('/api/v1/master-data/companies',headers=superuser_headers,
                        json={'name':'QA AMC customer','roles':['Customer']})
    assert buyer.status_code == 201, buyer.text
    buyer_id = buyer.json()['id']
    response = client.post('/api/v1/srm/contracts',headers=superuser_headers,json={
        'title':'QA annual maintenance coverage','customer_id':buyer_id,'contract_value':1000,
        'effective_date':'2026-11-12','expiry_date':'2027-11-11','currency':'INR',
    })
    assert response.status_code == 201, response.text
    assert response.json()['customer_id'] == buyer_id
    assert db.query(CRMCompany).filter_by(name='QA AMC customer').count() == 1
    assert db.get(SRMContract,response.json()['id']).customer_id == buyer_id
