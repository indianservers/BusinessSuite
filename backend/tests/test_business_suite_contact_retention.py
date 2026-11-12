"""Polymorphic references may use text identifiers; deletion must still fail closed."""
from tests.test_contact_directory import directory_identity, new_contact, ROOT
from app.apps.business_os.models import BOSLifecycleEvent


def test_tc075_text_identity_history_prevents_permanent_deletion(client, db, superuser_headers):
    row = new_contact(client, superuser_headers, email='retained-history@example.com')
    db.add(BOSLifecycleEvent(company_id=1, module_key='crm', entity_type='contact',
                             entity_id=str(row['id']), event_name='qa_history'))
    db.commit()
    trashed = client.post(ROOT+'/bulk', headers=superuser_headers, json={'ids':[row['id']], 'action':'trash'})
    assert trashed.status_code == 200, trashed.text
    response = client.delete(f"{ROOT}/{row['id']}/permanent", headers=superuser_headers)
    assert response.status_code == 409, response.text
    assert db.query(BOSLifecycleEvent).filter_by(entity_id=str(row['id'])).count() == 1
