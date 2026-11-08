"""HTTP workflow tests; synthetic tokens and controlled provider responses only."""
import base64
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs
import pytest
from tests.test_power_apps import actors
from app.apps.power_apps.integrations import adapters, vault, providers
from app.apps.power_apps.integrations.models import Credential, Connection

CASES = [
    ('facebook_lead_ads',{}, {},'graph.facebook.com','/v24.0/me'),
    ('mailchimp',{'provider_host':'us21.api.mailchimp.com'},{},'us21.api.mailchimp.com','/3.0/ping'),
    ('docusign',{'provider_host':'account-d.docusign.com'},{},'account-d.docusign.com','/oauth/userinfo'),
    ('trello',{}, {},'api.trello.com','/1/members/me'),
    ('zendesk',{'provider_host':'qa.zendesk.com'},{},'qa.zendesk.com','/api/v2/users/me.json'),
    ('activecampaign',{'provider_host':'qa.api-us1.com'},{},'qa.api-us1.com','/api/3/users/me'),
    ('linkedin_lead_forms',{'form_id':'123'},{'form_id':'123'},'api.linkedin.com','/rest/leadForms/123'),
    ('klaviyo',{}, {},'a.klaviyo.com','/api/accounts'),
    ('surfe',{}, {},'api.surfe.com','/v1/credits'),
    ('apollo',{}, {},'api.apollo.io','/api/v1/auth/health'),
    ('cloudtalk',{}, {},'my.cloudtalk.io','/api/contacts/index.json'),
]


@pytest.mark.parametrize('key,config,probe,host,path',CASES,ids=[c[0] for c in CASES])
def test_save_verify_rotate_disable_and_tenant_isolation(client,db,actors,monkeypatch,key,config,probe,host,path):
    calls=[]
    status=[200]
    class Transport:
        def request(self,method,url,**kw):
            calls.append((method,url,kw))
            assert method=='GET' and urlsplit(url).hostname==host and urlsplit(url).path==path
            assert kw['body'] is None
            return SimpleNamespace(status=status[0],headers={},body=b'{"id":"qa-account","ok":true}')
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    auth=providers.PROFILES[key]['auth']
    secrets={'username':'qa-key-id','password':'qa-secret-v1'} if auth=='basic' else {'access_token':'qa-secret-v1'}
    root='/api/v1/power-apps/integrations'
    payload={'connector_id':key,'name':'QA '+key,'auth_type':auth,'secrets':secrets,'config':config,'scopes':[]}
    assert client.post(root+'/connections',headers=actors[2],json=payload).status_code==403
    made=client.post(root+'/connections',headers=actors[0],json=payload)
    assert made.status_code==201,made.text
    ident=made.json()['id']
    assert 'qa-secret-v1' not in made.text
    assert all('qa-secret-v1' not in row.encrypted_value for row in db.query(Credential).all())
    request={'connection_id':ident,'action_id':'test','input':probe,'request_id':key+'-verify-123'}
    assert client.post(root+'/execute',headers=actors[1],json=request).status_code in (403,404)
    assert calls==[]
    result=client.post(root+'/execute',headers=actors[0],json=request)
    assert result.status_code==200,result.text
    assert len(calls)==1
    headers=calls[-1][2]['headers']
    if key=='trello':
        assert headers['Authorization']=='OAuth oauth_consumer_key="qa-key-id", oauth_token="qa-secret-v1"'
    elif auth=='basic':
        assert headers['Authorization']=='Basic '+base64.b64encode(b'qa-key-id:qa-secret-v1').decode()
    elif key in ('apollo','activecampaign'):
        assert headers['x-api-key' if key=='apollo' else 'Api-Token']=='qa-secret-v1'
        assert 'Authorization' not in headers
    else:
        assert headers['Authorization']==('Klaviyo-API-Key' if key=='klaviyo' else 'Bearer')+' qa-secret-v1'
    if key=='cloudtalk': assert headers['User-Agent']=='BusinessSuite-Connector/1.0'
    if key=='klaviyo': assert headers['revision']=='2026-10-15'
    if key=='linkedin_lead_forms': assert headers['LinkedIn-Version']=='202610'
    listed=client.get(root+'/connections',headers=actors[0]).json()['items'][0]
    assert listed['health']=='healthy' and listed['live_verified']
    rotated={k:('qa-key-id' if k=='username' else 'qa-secret-v2') for k in secrets}
    changed=client.post(f'{root}/connections/{ident}/rotate',headers=actors[0],json={'expected_version':listed['revision'],'secrets':rotated})
    assert changed.status_code==200,changed.text
    assert changed.json()['health']=='unverified' and not changed.json()['live_verified']
    status[0]=401
    rejected=client.post(root+'/execute',headers=actors[0],json={**request,'request_id':key+'-invalid-123'})
    assert rejected.status_code==422,rejected.text
    assert 'qa-secret' not in rejected.text
    latest=client.get(root+'/connections',headers=actors[0]).json()['items'][0]
    disabled=client.put(f'{root}/connections/{ident}',headers=actors[0],json={'expected_revision':latest['revision'],'enabled':False})
    assert disabled.status_code==200,disabled.text
    count=len(calls)
    assert client.post(root+'/execute',headers=actors[0],json={**request,'request_id':key+'-disabled-123'}).status_code==422
    assert len(calls)==count
    logs=client.get(root+'/monitor',headers=actors[0])
    assert 'qa-secret' not in logs.text


@pytest.mark.parametrize('key,host',[
    ('mailchimp','us21.api.mailchimp.com.attacker.test'),('zendesk','localhost'),
    ('activecampaign','qa.api-us1.com:443'),('docusign','account.docusign.com@attacker.test'),
    ('mailchimp','https://us21.api.mailchimp.com'),('zendesk','127.0.0.1'),
])
def test_account_host_rejects_credential_exfiltration(key,host):
    from fastapi import HTTPException
    auth=providers.PROFILES[key]['auth']
    secret={'username':'key','password':'token'} if auth=='basic' else {'access_token':'token'}
    with pytest.raises(HTTPException) as error:
        vault.validate_config(key,auth,{'provider_host':host},secret,[],False)
    assert error.value.status_code==422


def test_linkedin_query_encoding_preserves_owner_without_injection():
    calls=[]
    class Transport:
        def request(self,method,url,**kwargs):
            calls.append(url)
            return SimpleNamespace(status=200,headers={},body=b'{"elements":[]}')
    owner='(sponsoredAccount:urn:li:sponsoredAccount:123)'
    providers.execute(SimpleNamespace(connector_id='linkedin_lead_forms'), 'list_responses',
        {'owner':owner,'lead_type':'SPONSORED'},Transport(),{}, {'access_token':'qa-token'},'qa-operation')
    parsed=urlsplit(calls[0])
    assert parsed.hostname=='api.linkedin.com'
    assert parse_qs(parsed.query)['owner']==[owner]
    assert parse_qs(parsed.query)['leadType']==['(leadType:SPONSORED)']


def test_all_eleven_authorization_workflows_over_real_local_tls(client,db,actors,monkeypatch,tmp_path):
    """Exercise API -> encrypted vault -> policy -> TLS socket -> provider response."""
    import ssl, socket, threading, json
    from datetime import datetime, timedelta, timezone
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from app.apps.power_apps.integrations.transport import EgressPolicy,HttpTransport,PinnedHTTPS,Target
    hosts={case[3] for case in CASES}|{'demo.docusign.net'}
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Connector QA')])
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc)+timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(h) for h in hosts]),critical=False)
        .sign(key,hashes.SHA256()))
    certfile=tmp_path/'qa.pem'; keyfile=tmp_path/'qa-key.pem'
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            host=self.headers['Host'].split(':')[0]
            assert host in hosts
            assert self.headers.get('Authorization') or self.headers.get('x-api-key') or self.headers.get('Api-Token')
            received.append((host,urlsplit(self.path).path))
            body=json.dumps({'id':'tls-account','ok':True}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        do_POST=do_GET
        do_PUT=do_GET
        def log_message(self,*args): pass
    server=HTTPServer(('127.0.0.1',0),Handler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(str(certfile),str(keyfile))
    server.socket=context.wrap_socket(server.socket,server_side=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def resolver(host,port,**kw):
        return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8' if host in hosts else '1.1.1.1',port))]
    class FixtureSocket(PinnedHTTPS):
        def __init__(self,target,timeout):
            assert target.host in hosts and target.address=='8.8.8.8'
            super().__init__(Target(target.host,server.server_port,'127.0.0.1',target.url),timeout)
            self._context=ssl.create_default_context(cafile=str(certfile))
    def transport(policy):
        # Only this test redirects the already validated host to its trusted TLS fixture.
        policy.resolver=resolver
        return HttpTransport(policy,connection_factory=FixtureSocket)
    monkeypatch.setattr(adapters,'HTTP_FACTORY',transport)
    root='/api/v1/power-apps/integrations'
    try:
        for provider,config,probe,host,path in CASES:
            auth=providers.PROFILES[provider]['auth']
            secrets={'username':'tls-key','password':'tls-secret'} if auth=='basic' else {'access_token':'tls-secret'}
            response=client.post(root+'/connections',headers=actors[0],json={'connector_id':provider,'name':'TLS '+provider,'auth_type':auth,'secrets':secrets,'config':config,'scopes':[],'writes_enabled':True})
            assert response.status_code==201,response.text
            result=client.post(root+'/execute',headers=actors[0],json={'connection_id':response.json()['id'],'action_id':'test','input':probe,'request_id':'tls-'+provider+'-123'})
            assert result.status_code==200,result.text
            assert received[-1]==(host,path)
            assert result.json()['output']['data']['id']=='tls-account'
            from tests.test_power_provider_actions import sample
            action=next((a for a in providers.PROFILES[provider]['actions'] if a['id'] in {'upsert_contact','create_contact','create_draft','create_ticket','create_card','enrich_person'}),None)
            if action:
                written=client.post(root+'/execute',headers=actors[0],json={'connection_id':response.json()['id'],'action_id':action['id'],'input':sample(action),'confirm_side_effect':True,'request_id':'tls-write-'+provider+'-123'})
                assert written.status_code==200,written.text
                assert written.json()['output']['delivery']=='accepted'
                assert client.post(root+'/execute',headers=actors[0],json={'connection_id':response.json()['id'],'action_id':action['id'],'input':sample(action),'confirm_side_effect':True,'request_id':'tls-write-'+provider+'-123'}).status_code==200
        assert len(received)==20
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
