import json
from datetime import timedelta
from urllib.parse import urlsplit,parse_qs
from types import SimpleNamespace
import pytest
from tests.test_power_apps import actors
from tests.test_marketplace_provider_authorization import CASES
from app.apps.power_apps.integrations import marketplace_oauth as mo,oauth,vault,adapters
from app.apps.power_apps.integrations.registry import REGISTRY
from app.apps.power_apps.integrations.models import Connection,Credential
from app.apps.power_apps.runtime import now
from app.core.config import settings


@pytest.mark.parametrize('provider',list(mo.PROVIDERS))
def test_authorize_callback_replay_refresh_and_provider_headers(client,db,actors,monkeypatch,provider):
    spec=mo.PROVIDERS[provider]
    monkeypatch.setattr(settings,'POWER_'+spec['name'].upper()+'_CLIENT_ID','qa-client')
    monkeypatch.setattr(settings,'POWER_'+spec['name'].upper()+'_CLIENT_SECRET','qa-client-secret')
    monkeypatch.setattr(settings,'BACKEND_PUBLIC_URL','https://backend.example.test')
    monkeypatch.setattr(settings,'POWER_OAUTH_REDIRECT_URI','https://backend.example.test/api/v1/power-apps/integrations/oauth/callback')
    case=next(c for c in CASES if c[0]==provider)
    root='/api/v1/power-apps/integrations';scopes=REGISTRY[provider].oauth_scopes
    made=client.post(root+'/connections',headers=actors[0],json={'connector_id':provider,'name':'OAuth QA','auth_type':'oauth2','config':case[1],'secrets':{},'scopes':scopes})
    assert made.status_code==201,made.text
    ident=made.json()['id'];requests=[]
    class Transport:
        def __init__(self,*args):pass
        def request(self,method,url,headers=None,body=None,**kwargs):
            requests.append((method,url,headers,body))
            if url.endswith('/metadata'): result={'dc':'us21'}
            elif url.endswith('/userinfo'): result={'accounts':[{'account_id':'qa-account','is_default':True,'base_uri':'https://demo.docusign.net'}]}
            else:
                result={'access_token':'qa-new-token','scope':' '.join(scopes)}
                if provider not in {'mailchimp','facebook_lead_ads'}:result.update(expires_in=3600,refresh_token='qa-refresh-token')
                elif provider=='facebook_lead_ads':result.update(expires_in=3600)
            return SimpleNamespace(status=200,headers={},body=json.dumps(result).encode())
    monkeypatch.setattr(mo,'HttpTransport',Transport)
    start=client.post(f'{root}/connections/{ident}/oauth',headers=actors[0],json={'scopes':scopes})
    assert start.status_code==200,start.text
    url=urlsplit(start.json()['authorization_url'])
    query=parse_qs(url.query or url.fragment.split('?',1)[1])
    assert query['client_id']==['qa-client'] and 'qa-client-secret' not in start.text
    assert ('code_challenge' in query)==spec['pkce']
    state=query['state'][0]
    done=client.get(root+'/oauth/callback',params={'state':state,'code':'qa-code'})
    assert done.status_code==200,done.text
    assert client.get(root+'/oauth/callback',params={'state':state,'code':'qa-code'}).status_code==400
    conn=db.get(Connection,ident);db.refresh(conn);credential=db.get(Credential,conn.credential_id)
    assert 'qa-new-token' not in credential.encrypted_value
    if provider=='mailchimp': assert conn.config['provider_host']=='us21.api.mailchimp.com' and conn.expires_at is None
    if provider=='docusign': assert conn.config['account_id']=='qa-account' and conn.config['api_host']=='demo.docusign.net'
    token_call=next(r for r in requests if r[1].endswith('/token') or r[1].endswith('/tokens') or r[1].endswith('/accessToken') or r[1].endswith('/access_token'))
    if spec.get('basic'):
        assert token_call[2]['Authorization'].startswith('Basic ') and b'qa-client-secret' not in token_call[3]
    if spec.get('json'): assert token_call[2]['Content-Type']=='application/json'
    count=len(requests)
    if provider not in {'mailchimp','facebook_lead_ads'}:
        conn.expires_at=now()-timedelta(seconds=1);db.commit()
    values=oauth.access_values(db,conn,credential,vault.CredentialVault.decrypt(credential))
    assert values['access_token']=='qa-new-token'
    assert len(requests)==count+(0 if provider in {'mailchimp','facebook_lead_ads'} else 1)
    class ProviderTransport:
        def request(self,method,url,**kwargs):
            assert kwargs['headers']['Authorization']=='Bearer qa-new-token'
            if provider in {'apollo','klaviyo'}:assert 'x-api-key' not in kwargs['headers']
            return SimpleNamespace(status=200,headers={},body=b'{"ok":true,"id":"qa"}')
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:ProviderTransport())
    response=client.post(root+'/execute',headers=actors[0],json={'connection_id':ident,'action_id':'test','input':case[2],'request_id':'oauth-provider-check-123'})
    assert response.status_code==200,response.text
    assert 'qa-new-token' not in client.get(root+'/connections',headers=actors[0]).text
    if provider=='facebook_lead_ads':
        conn.expires_at=now()-timedelta(seconds=1);db.commit()
        from app.apps.power_apps.integrations.contracts import IntegrationFailure
        with pytest.raises(IntegrationFailure):
            oauth.access_values(db,conn,credential,vault.CredentialVault.decrypt(credential))


def test_missing_oauth_configuration_is_explicit():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error: mo.config('mailchimp')
    assert error.value.status_code==503


def test_provider_downscoping_does_not_enable_requested_write_permissions():
    from app.apps.power_apps.integrations.contracts import IntegrationFailure
    conn=SimpleNamespace(connector_id='klaviyo')
    with pytest.raises(IntegrationFailure):
        oauth.store_tokens(None,conn,None,{'access_token':'qa-token','scope':'profiles:read'},['profiles:read','profiles:write'])
