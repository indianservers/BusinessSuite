import pytest
from tests.test_contact_directory import directory_identity
from app.apps.crm.contact_identity import ContactIdentityLink


@pytest.mark.parametrize('kind',['Company','Individual'])
def test_relationship_hub_customer_kind_follows_linked_account_details(client,db,superuser_headers,directory_identity,kind):
    created=client.post('/api/v1/master-data/companies',headers=superuser_headers,json={'name':'QA Hub '+kind,'entityKind':kind,'businessType':'Individual' if kind=='Company' else 'Private Limited','roles':['Customer']})
    assert created.status_code==201,created.text
    account=created.json();link=db.query(ContactIdentityLink).filter_by(account_id=account['id'],organization_id=1).one()
    contact_id=link.contact_id
    def assert_kind(expected):
        listed=client.get('/api/v1/crm/contact-directory',headers=superuser_headers,params={'search':account['name']})
        assert listed.status_code==200,listed.text
        row=next(row for row in listed.json()['items'] if row['id']==contact_id)
        assert row['entityKind']==expected
        detail=client.get('/api/v1/crm/contact-directory/'+str(contact_id),headers=superuser_headers)
        assert detail.status_code==200,detail.text
        assert detail.json()['entityKind']==expected
    assert_kind(kind)
    other='Individual' if kind=='Company' else 'Company'
    changed=client.patch('/api/v1/master-data/companies/'+str(account['id']),headers=superuser_headers,json={'name':account['name'],'entityKind':other,'businessType':'Individual','version':account['version'],'roles':['Customer']})
    assert changed.status_code==200,changed.text
    assert db.query(ContactIdentityLink).filter_by(account_id=account['id']).one().contact_id==contact_id
    assert_kind(other)
