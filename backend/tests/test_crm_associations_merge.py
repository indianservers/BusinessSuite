from tests.rich_text_test_utils import organization_context
"""CRM multi-item associations and non-destructive merge regressions."""
import pytest
from app.models.company import Company, Branch
from app.models.user import User
from app.apps.crm.models import CRMCustomFieldValue
from app.shared.catalog_models import CatalogLink
from test_identity_utils import attach_test_identity
from tests.test_crm_deal_catalog import test_catalog_round_trip_update_clear_and_server_total as test_existing_deal_multi_item_round_trip
from tests.test_crm_rest_api import (
    test_crm_duplicate_detection_and_merge_relinks_related_records as test_existing_related_work_merge,
    test_crm_duplicate_detection_uses_custom_unique_fields_and_merges_values_safely as test_existing_custom_field_merge,
    test_crm_duplicate_detection_never_compares_across_organizations as test_existing_tenant_isolation,
)

@pytest.fixture
def superuser_headers(superuser_headers, db):
    if not db.get(Company, 1):
        db.add(Company(id=1, name='CRM merge regression', is_active=True))
    db.flush()
    branch = Branch(company_id=1, name='CRM test branch', code='CRM-MERGE')
    db.add(branch)
    attach_test_identity(db, db.query(User).filter_by(email='testadmin@test.com').one())
    db.commit()
    return {**superuser_headers, 'X-Suite-Branch': str(branch.id)}


def post(client, headers, path, data):
    response = client.post('/api/v1/' + path, headers=headers, json=data)
    assert response.status_code in (200, 201), response.text
    return response.json()


def offering(client, h, kind, code):
    return post(client, h, 'catalog/items?source=crm', {'kind':kind, 'name':code, 'code':code, 'price':100, 'currency':'INR', 'tax':0})


def line(item):
    return {'kind':item['kind'], 'item_id':item['id'], 'quantity':1, 'unit_price':100, 'discount':0}


def contact(client, h, **values):
    return post(client, h, 'crm/contacts', {'first_name':'Merge', 'full_name':'Merge Person', 'email':'merge@example.com', 'confirmShared':True, 'sharedReason':'Synthetic duplicate for merge regression', **values})


def test_contact_multiple_items_create_edit_remove(client, superuser_headers):
    h = superuser_headers
    p, s = offering(client,h,'product','CRM-P'), offering(client,h,'service','CRM-S')
    record = contact(client,h,catalog_lines=[line(p),line(s)])
    url = f"/api/v1/catalog/links/contact/{record['id']}?source=crm"
    saved = client.get(url,headers=h)
    assert saved.status_code == 200, saved.text
    assert {(r['kind'],r['item_id']) for r in saved.json()['lines']} == {('product',p['id']),('service',s['id'])}
    changed = client.patch(f"/api/v1/crm/contacts/{record['id']}",headers=h,json={'catalog_lines':[line(s)]})
    assert changed.status_code == 200, changed.text
    assert [r['kind'] for r in client.get(url,headers=h).json()['lines']] == ['service']
    removed = client.put(url,headers=h,json={'lines':[]})
    assert removed.status_code == 200, removed.text
    assert client.get(url,headers=h).json()['lines'] == []


def test_merge_fills_all_columns_and_combines_catalog(client, db, superuser_headers):
    h = superuser_headers
    p, s = offering(client,h,'product','MERGE-P'), offering(client,h,'service','MERGE-S')
    winner = contact(client,h,city='Hyderabad',notes='First note',tags_text='Customer',catalog_lines=[line(p)],social_profiles_json={'linkedin':'first'})
    loser = contact(client,h,job_title='Director',address='Office address',website='https://example.com',notes='Second note',tags_text='Partner',catalog_lines=[line(p),line(s)],social_profiles_json={'twitter':'second'})
    payload = {'entityType':'contact','winnerId':winner['id'],'loserIds':[loser['id']]}
    result = post(client,h,'crm/duplicates/merge',payload)
    kept = result['winner']
    assert kept['city'] == 'Hyderabad' and kept['job_title'] == 'Director'
    assert kept['address'] == 'Office address' and kept['website'] == 'https://example.com'
    assert 'First note' in kept['notes'] and 'Second note' in kept['notes']
    assert kept['social_profiles_json'] == {'linkedin':'first','twitter':'second'}
    assert set(kept['tags_text'].split(', ')) == {'Customer','Partner'}
    detail = client.get(f"/api/v1/crm/contacts/{winner['id']}",headers=h)
    assert detail.status_code == 200 and detail.json()['job_title'] == 'Director'
    assert client.get(f"/api/v1/crm/contacts/{loser['id']}",headers=h).status_code == 404
    url = f"/api/v1/catalog/links/contact/{winner['id']}?source=crm"
    links = client.get(url,headers=h)
    assert links.status_code == 200, links.text
    assert len(links.json()['lines']) == 2
    assert not db.query(CatalogLink).filter_by(target_type='contact',target_id=loser['id']).count()
    scan = client.get('/api/v1/crm/duplicates?entityType=contact',headers=h)
    assert scan.status_code == 200 and not scan.json()['items']
    assert client.post('/api/v1/crm/duplicates/merge',headers=h,json=payload).status_code in (403,404)
    assert len(client.get(url,headers=h).json()['lines']) == 2


@pytest.mark.parametrize("archived", [False, True])
def test_explicit_conflict_choice_and_blank_custom_field(client, db, superuser_headers, archived):
    h = superuser_headers
    field = post(client,h,'crm/custom-fields',{'entityType':'contacts','fieldName':'Reference','fieldKey':'merge_ref','fieldType':'text'})
    winner = contact(client,h,city='Hyderabad',customFields={'merge_ref':''})
    loser = contact(client,h,city='Delhi',customFields={'merge_ref':'Filled reference'})
    if archived:
        from datetime import datetime, timezone
        db.query(CRMCustomFieldValue).filter_by(record_id=winner['id'],custom_field_id=field['id']).one().deleted_at = datetime.now(timezone.utc)
        db.commit()
    result = post(client,h,'crm/duplicates/merge',{'entityType':'contact','winnerId':winner['id'],'loserIds':[loser['id']],'fieldValues':{'city':'Delhi'}})
    assert result['winner']['city'] == 'Delhi'
    db.expire_all()
    value = db.query(CRMCustomFieldValue).filter_by(record_id=winner['id'],custom_field_id=field['id'],deleted_at=None).one()
    assert value.value_text == 'Filled reference'


def test_lead_multi_item_capture_and_merge_preserves_operating_details(client, db, superuser_headers):
    from app.apps.crm.lead_models import CRMLeadOperatingState
    from app.apps.crm.models import CRMTimelineEvent
    h = superuser_headers
    p, s = offering(client,h,'product','LEAD-P'), offering(client,h,'service','LEAD-S')
    captured = post(client,h,'crm/lead-management/leads',{'values':{'full_name':'Captured lead','email':'capture@example.com'},'catalog_lines':[line(p),line(s)]})
    url = f"/api/v1/catalog/links/lead/{captured['id']}?source=crm"
    assert len(client.get(url,headers=h).json()['lines']) == 2
    assert client.put(url,headers=h,json={'lines':[]}).status_code == 200
    assert not client.get(url,headers=h).json()['lines']
    first = post(client,h,'crm/lead-management/leads',{'values':{'full_name':'First lead','email':'first@example.com'},'catalog_lines':[line(p)]})
    second = post(client,h,'crm/lead-management/leads',{'values':{'full_name':'Second lead','email':'second@example.com','job_title':'Director'},'catalog_lines':[line(s)]})
    a = db.query(CRMLeadOperatingState).filter_by(lead_id=first['id']).one()
    b = db.query(CRMLeadOperatingState).filter_by(lead_id=second['id']).one()
    a.data_json = {**a.data_json, 'qualification':{'budget':'Agreed'}}
    b.data_json = {**b.data_json, 'qualification':{'need':'Implementation'}}
    db.commit()
    result = post(client,h,'crm/duplicates/merge',{'entityType':'lead','winnerId':first['id'],'loserIds':[second['id']],'allowUndetected':True})
    assert result['winner']['job_title'] == 'Director'
    db.expire_all()
    combined = db.query(CRMLeadOperatingState).filter_by(lead_id=first['id']).one()
    assert combined.data_json['qualification'] == {'budget':'Agreed','need':'Implementation'}
    assert not db.query(CRMTimelineEvent).filter(CRMTimelineEvent.record_type=='lead',CRMTimelineEvent.record_id==second['id'],CRMTimelineEvent.event_type!='duplicate_merge').count()
    assert len(client.get(f"/api/v1/catalog/links/lead/{first['id']}?source=crm",headers=h).json()['lines']) == 2


def test_manual_merge_unmatched_complementary_contacts(client, superuser_headers):
    h = superuser_headers
    first = contact(client,h,full_name='Asha Rao',email='asha@example.com',city='Hyderabad')
    second = contact(client,h,full_name='Asha',email=None,phone='9000012345',phone_country_code='+91',job_title='Director')
    payload = {'entityType':'contact','winnerId':first['id'],'loserIds':[second['id']]}
    assert client.post('/api/v1/crm/duplicates/merge',headers=h,json=payload).status_code == 409
    result = post(client,h,'crm/duplicates/merge',{**payload,'allowUndetected':True})
    assert result['winner']['email'] == 'asha@example.com'
    assert result['winner']['phone'] == '9000012345'
    assert result['winner']['phone_country_code'] == '+91'
    assert result['winner']['job_title'] == 'Director'


def test_invalid_merge_rolls_back_and_invalid_associations_are_atomic(client, db, superuser_headers):
    from app.apps.crm.models import CRMContact
    h = superuser_headers
    first, second = contact(client,h,city='Hyderabad'), contact(client,h,job_title='Director')
    # The shared fixture keeps its session open. Roll back only the failed
    # request's savepoint, matching production get_db without erasing fixtures.
    savepoint = db.begin_nested()
    failed = client.post('/api/v1/crm/duplicates/merge',headers=h,json={'entityType':'contact','winnerId':first['id'],'loserIds':[second['id']],'fieldValues':{'phone':'bad','phone_country_code':'+91'}})
    assert failed.status_code == 422, failed.text
    if savepoint.is_active:
        savepoint.rollback()
    db.expire_all()
    assert db.get(CRMContact,second['id']).deleted_at is None
    assert db.get(CRMContact,first['id']).job_title is None
    savepoint = db.begin_nested()
    invalid = client.post('/api/v1/crm/contacts',headers=h,json={'first_name':'Invalid','full_name':'Invalid association','email':'atomic@example.com','catalog_lines':[{'kind':'product','item_id':999999,'quantity':1}]})
    assert invalid.status_code == 404, invalid.text
    if savepoint.is_active:
        savepoint.rollback()
    assert not db.query(CRMContact).filter_by(email='atomic@example.com').count()


