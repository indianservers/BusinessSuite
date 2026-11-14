import pytest
from app.models.company import Company, Branch
from app.shared.business_profile import effective, resolve
from tests.test_settings_hub import actor, BASE

URL = BASE + '/business-profile/configuration'


def test_profile_round_trip_reset_and_stale_write(client, db):
    headers, _ = actor(db, superuser=True)
    first = client.get(URL, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()['effective']['terms']['provider'] == ['Service provider', 'Service providers']
    values = {'business_type': 'hospital', 'terms': {'provider': ['Clinician', 'Clinicians']}}
    saved = client.put(URL, headers=headers, json={'version': 0, 'values': values})
    assert saved.status_code == 200, saved.text
    result = client.get(URL, headers=headers).json()
    assert result['overrides'] == values
    assert result['effective']['terms']['customer'] == ['Patient', 'Patients']
    assert result['effective']['terms']['employee'] == ['Employee', 'Employees']
    history = client.get(BASE + '/history/business-profile', headers=headers)
    assert history.status_code == 200, history.text
    assert 'business_type' in history.json()['items'][0]['fields']
    assert client.put(URL, headers=headers, json={'version': 0, 'values': {}}).status_code == 409
    assert client.put(URL, headers=headers, json={'version': 1, 'values': {}}).status_code == 200
    assert effective(db, 1)['business_type'] == 'general'


def test_branch_inheritance_and_company_isolation(client, db):
    headers, _ = actor(db, superuser=True)
    branch = Branch(company_id=1, name='Clinic', is_active=True)
    other = Company(name='Other business')
    db.add_all([branch, other]); db.flush()
    foreign = Branch(company_id=other.id, name='Foreign', is_active=True)
    db.add(foreign); db.commit()
    for params, values in [({}, {'business_type': 'salon', 'terms': {'customer': ['Guest', 'Guests']}}), ({'branch_id': branch.id}, {'business_type': 'hospital'})]:
        response = client.put(URL, params=params, headers=headers, json={'version': 0, 'values': values})
        assert response.status_code == 200, response.text
    resolved = effective(db, 1, branch.id)
    assert resolved['terms']['provider'][0] == 'Doctor'
    assert resolved['terms']['customer'][0] == 'Guest'
    assert effective(db, 1)['terms']['provider'][0] == 'Stylist'
    assert effective(db, other.id)['business_type'] == 'general'
    assert client.get(URL, params={'branch_id': foreign.id}, headers=headers).status_code in (403, 422)


@pytest.mark.parametrize('values', [
    {'business_type': 'invalid'}, {'business_type': []}, {'pipeline': 1},
    {'terms': {'unknown': ['One', 'Many']}}, {'terms': {'customer': ['Patient']}},
    {'terms': {'provider': ['', 'Doctors']}}, {'terms': {'provider': ['<b>Doctor</b>', 'Doctors']}},
    {'terms': {'customer': ['Patient\n', 'Patients']}}, {'terms': []},
])
def test_invalid_profiles_are_not_saved(client, db, values):
    headers, _ = actor(db, superuser=True)
    assert client.put(URL, headers=headers, json={'version': 0, 'values': values}).status_code == 422
    assert client.get(URL, headers=headers).json()['version'] == 0


def test_readers_cannot_configure_and_get_company_effective_terms(client, db):
    headers, _ = actor(db, superuser=True)
    assert client.put(URL, headers=headers, json={'version': 0, 'values': {'business_type': 'hospital'}}).status_code == 200
    reader, _ = actor(db, 'profile-reader')
    assert client.get(URL, headers=reader).status_code == 403
    assert client.put(URL, headers=reader, json={'version': 1, 'values': {}}).status_code == 403
    response = client.get(BASE + '/business-profile/effective', headers=reader)
    assert response.status_code == 200, response.text
    assert response.json()['terms']['provider'][0] == 'Doctor'


def test_profile_switch_only_changes_template_terms():
    profile = resolve([{'business_type': 'salon', 'terms': {'customer': ['Guest', 'Guests']}}, {'business_type': 'hospital'}])
    assert profile['terms']['provider'][0] == 'Doctor'
    assert profile['terms']['customer'][0] == 'Guest'


def test_profile_changes_do_not_mutate_pipelines(client, db):
    from app.apps.crm.models import CRMPipeline, CRMPipelineStage
    headers, _ = actor(db, superuser=True)
    pipeline = CRMPipeline(organization_id=1, name='Existing sales pipeline', active=True)
    db.add(pipeline); db.flush()
    stage = CRMPipelineStage(pipeline_id=pipeline.id, name='Qualified', stage_type='open', active=True)
    db.add(stage); db.commit()
    ids = pipeline.id, stage.id
    for version, business_type in enumerate(['hospital', 'salon', 'construction']):
        response = client.put(URL, headers=headers, json={'version': version, 'values': {'business_type': business_type}})
        assert response.status_code == 200, response.text
    db.expire_all()
    assert db.get(CRMPipeline, ids[0]).name == 'Existing sales pipeline'
    assert db.get(CRMPipelineStage, ids[1]).name == 'Qualified'
    assert db.get(CRMPipelineStage, ids[1]).pipeline_id == ids[0]
