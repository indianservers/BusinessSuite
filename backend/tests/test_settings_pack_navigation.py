"""Settings discovery consolidation retains legacy authorization boundaries."""
import pytest

from tests.test_settings_hub import actor, BASE


@pytest.mark.parametrize('admin', [True, False])
def test_pack_discovery_hides_legacy_profile_without_changing_legacy_guards(client, db, admin):
    headers, _ = actor(db, admin=admin)
    response = client.get(BASE, headers=headers)
    assert response.status_code == 200, response.text
    ids = [option['id'] for option in response.json()['options']]
    assert 'business-profile' not in ids
    assert ids.count('business-packs') == int(admin)
    assert {'account', 'preferences'} <= set(ids)
    for key in ('business-profile', 'business-packs'):
        metadata = client.get(BASE + '/options/' + key, headers=headers)
        assert metadata.status_code == (200 if admin else 403), metadata.text
        if admin:
            assert metadata.json()['id'] == key
    legacy = client.get(BASE + '/business-profile/configuration', headers=headers)
    assert legacy.status_code == (200 if admin else 403), legacy.text
