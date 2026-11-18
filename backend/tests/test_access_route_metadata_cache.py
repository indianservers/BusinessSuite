from app.access import catalog


def test_cached_action_metadata_tracks_live_route_registry(monkeypatch):
    key = 'test_route_metadata'
    route = (900001, '/test-metadata', 'GET')
    monkeypatch.setitem(catalog.ROUTES, route, key)
    assert catalog.module_actions(key) == ['view']
    # Returned lists are caller-owned, and a warm result cannot retain removed
    # routes or miss a newly registered write operation.
    catalog.module_actions(key).append('delete')
    assert catalog.module_actions(key) == ['view']
    post = (900002, '/test-metadata', 'POST')
    monkeypatch.setitem(catalog.ROUTES, post, key)
    assert 'create' in catalog.module_actions(key)
    monkeypatch.delitem(catalog.ROUTES, post)
    assert catalog.module_actions(key) == ['view']
