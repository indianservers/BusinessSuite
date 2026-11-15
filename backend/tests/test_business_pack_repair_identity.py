"""Pack configuration failures cannot trap native identity or common HRMS."""
from fastapi import HTTPException


def test_partial_pack_configuration_keeps_native_identity_and_core(client, superuser_headers, monkeypatch):
    def unavailable(*args, **kwargs):
        raise HTTPException(503, 'Pack configuration upgrade required')
    monkeypatch.setattr('app.business_packs.discovery._installed', unavailable)
    monkeypatch.setattr('app.business_packs.legacy_boundary.installation', unavailable)
    headers = {**superuser_headers, 'X-Suite-Pack-Context': 'stale-context'}
    identity = client.get('/api/v1/auth/me', headers=headers)
    assert identity.status_code == 200, identity.text
    access = client.get('/api/v1/access/me', headers=headers)
    assert access.status_code == 200, access.text
    assert access.json()['businessPacks']['state'] == 'unavailable'
    assert access.json()['businessPacks']['reason'] == 'schema_unavailable'
    core = client.get('/api/v1/timesheets/', headers=headers)
    assert core.status_code == 200, core.text
    assert core.json() == []


def test_core_label_cannot_select_a_native_realm_for_private_sales(client, superuser_headers):
    headers = {**superuser_headers, 'X-Suite-Pack-Context': 'core'}
    core = client.get('/api/v1/timesheets/', headers=headers)
    assert core.status_code == 200, core.text
    private = client.get('/api/v1/srm/invoices', headers=headers)
    assert private.status_code == 403, private.text
    assert set(private.json()) == {'detail'}
