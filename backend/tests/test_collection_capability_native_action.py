"""Collection hints must match the native payment approval action."""
import pytest

from tests.test_business_pack_http_integration import native_actor
from tests.test_service_checkout import scenario, catalog, directory_identity


@pytest.mark.parametrize('actions,expected', [
    (('view', 'create'), False),
    (('view', 'approve'), True),
    (('view',), False),
])
def test_legacy_collection_hint_requires_native_approval_not_generic_create(client, db, scenario, actions, expected):
    _, branch, _, _ = scenario
    headers, actor = native_actor(db, branch, actions=actions)
    assert not actor.is_superuser
    response = client.get('/api/v1/srm/business/collection-invoices', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['can_record'] is expected
    assert db.info.get('business_pack_scope') is None
