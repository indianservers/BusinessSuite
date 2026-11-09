import pytest
from fastapi import HTTPException
from app.apps.power_apps.integrations import oauth


@pytest.mark.parametrize('environment,base,accepted', [
    ('development', 'http://localhost:1534', True),
    ('development', 'http://127.0.0.1:1534', True),
    ('development', 'http://example.com', False),
    ('production', 'http://localhost:1534', False),
    ('production', 'https://suite.example.com', True),
])
def test_callback_transport_boundary(monkeypatch, environment, base, accepted):
    monkeypatch.setattr(oauth.settings, 'ENVIRONMENT', environment)
    monkeypatch.setattr(oauth.settings, 'BACKEND_PUBLIC_URL', base)
    monkeypatch.setattr(oauth.settings, 'POWER_GOOGLE_CLIENT_ID', 'test-client')
    monkeypatch.setattr(oauth.settings, 'POWER_GOOGLE_CLIENT_SECRET', 'test-secret')
    monkeypatch.setattr(oauth.settings, 'POWER_OAUTH_REDIRECT_URI', base + '/api/v1/power-apps/integrations/oauth/callback')
    if accepted:
        assert oauth.app_config('google_calendar')['client_id'] == 'test-client'
    else:
        with pytest.raises(HTTPException) as error:
            oauth.app_config('google_calendar')
        assert error.value.status_code == 503


def test_callback_must_match_backend(monkeypatch):
    monkeypatch.setattr(oauth.settings, 'ENVIRONMENT', 'development')
    monkeypatch.setattr(oauth.settings, 'BACKEND_PUBLIC_URL', 'http://localhost:1534')
    monkeypatch.setattr(oauth.settings, 'POWER_GOOGLE_CLIENT_ID', 'test-client')
    monkeypatch.setattr(oauth.settings, 'POWER_GOOGLE_CLIENT_SECRET', 'test-secret')
    monkeypatch.setattr(oauth.settings, 'POWER_OAUTH_REDIRECT_URI', 'http://localhost:1534/wrong')
    with pytest.raises(HTTPException):
        oauth.app_config('google_calendar')
