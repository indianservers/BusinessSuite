from types import SimpleNamespace
import pytest
from app.apps.power_apps.integrations.marketplace import APPS, discovery
from app.apps.power_apps.integrations import providers
from app.apps.power_apps.integrations.registry import REGISTRY
from tests.test_power_apps import actors


def test_discovery_reuses_connectors_without_duplicate_provider_cards():
    items = discovery()
    ids = [item['id'] for item in items]
    assert len(ids) == len(set(ids))
    assert set(REGISTRY) <= set(ids)
    assert len(APPS) == 25
    assert ids.count('mailchimp') == 1
    assert next(i for i in items if i['id']=='slack')['implemented']
    pending = next(i for i in items if i['id']=='nova')
    assert pending['destination'] is None and not pending['implemented']
    assert pending['authorization'] == []
    assert next(i for i in items if i['id']=='quickbooks')['destination']=='/fam/import-data'
    assert {i['id'] for i in items if not i['implemented']} == {'dedupely','nova'}
    for item in items:
        assert item['modules']
        if item['id'] in {'dedupely','nova'}:
            assert item['blocked_reason']


@pytest.mark.parametrize('key,host,path,prefix',[
    ('calendly','api.calendly.com','/users/me','Bearer'),
    ('zoom','api.zoom.us','/v2/users/me','Bearer'),
    ('pandadoc','api.pandadoc.com','/public/v1/documents','API-Key'),
])
def test_provider_authorization_probe_is_read_only_and_uses_pinned_origin(key,host,path,prefix):
    calls=[]
    class Transport:
        def request(self,method,url,**kwargs):
            calls.append((method,url,kwargs))
            return SimpleNamespace(status=200,body=b'{"ok":true}',headers={})
    providers.execute(SimpleNamespace(connector_id=key),'test',{},Transport(),{},
        {'access_token':'synthetic-secret'},'synthetic-operation')
    method,url,kwargs=calls[0]
    assert method=='GET' and url=='https://'+host+path
    assert kwargs['headers']['Authorization']==prefix+' synthetic-secret'
    assert kwargs['body'] is None
    assert not next(a for a in REGISTRY[key].actions if a.id=='test').mutates


def test_discovery_requires_authentication(client, superuser_headers):
    path='/api/v1/power-apps/integrations/discovery'
    assert client.get(path).status_code in (401,403)
    response=client.get(path,headers=superuser_headers)
    assert response.status_code==200,response.text
    assert response.json()['items']
    assert 'secrets' not in response.text and 'access_token' not in response.text


def test_authorized_connection_uses_existing_vault_and_permissions(client, db, actors, monkeypatch):
    from app.apps.power_apps.integrations.models import Credential
    from app.apps.power_apps.integrations import adapters
    calls=[]
    class Transport:
        def request(self,method,url,**kwargs):
            calls.append(url)
            return SimpleNamespace(status=200,body=b'{"resource":{"name":"QA user"}}',headers={})
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    root='/api/v1/power-apps/integrations'
    payload={'connector_id':'calendly','name':'QA Calendly','auth_type':'bearer',
        'secrets':{'access_token':'synthetic-calendar-token'},'scopes':[],'config':{}}
    denied=client.post(root+'/connections',headers=actors[2],json=payload)
    assert denied.status_code==403
    made=client.post(root+'/connections',headers=actors[0],json=payload)
    assert made.status_code==201,made.text
    assert 'synthetic-calendar-token' not in made.text
    assert 'synthetic-calendar-token' not in db.query(Credential).one().encrypted_value
    ident=made.json()['id']
    probe={'connection_id':ident,'action_id':'test','input':{},'request_id':'marketplace-probe-123'}
    result=client.post(root+'/execute',headers=actors[0],json=probe)
    assert result.status_code==200,result.text
    assert calls==['https://api.calendly.com/users/me']
    assert client.post(root+'/execute',headers=actors[1],json={**probe,'request_id':'cross-company-123'}).status_code in (403,404)
    assert len(calls)==1
