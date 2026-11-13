from types import SimpleNamespace as NS
from datetime import datetime, timezone
import json
import pytest
from app.apps.power_apps.integrations import account_identity as accounts, service
from app.ai_operator.agent_connector_status import actions, account


def connection(**extra):
    return NS(id=1, revision=2, connector_id='outlook', connector_version=1,
        organization_id=1, environment='development', owner_user_id=7, config={},
        scopes=extra.pop('scopes', ['User.Read']), enabled=extra.pop('enabled', True),
        writes_enabled=extra.pop('writes_enabled', False), expires_at=extra.pop('expires_at', None), **extra)


def credential():
    return NS(id=3, version=1, revoked_at=None)


@pytest.mark.parametrize('provider,output,expected', [
    ('gmail', {'emailAddress':'reader@example.com','historyId':'private'}, {'email':'reader@example.com'}),
    ('outlook', {'id':'u-1','displayName':'Reader','access_token':'private'}, {'id':'u-1','label':'Reader'}),
    ('github', {'id':12,'login':'reader','bio':'private'}, {'id':'12','label':'reader'}),
    ('slack', {'ok':True,'user_id':'U1','user':'reader','team':'Team','team_id':'T1','url':'private'}, {'id':'U1','label':'reader','workspace':'Team','workspace_id':'T1'}),
    ('dropbox', {'account_id':'dbid-1','name':{'display_name':'Reader'},'email':'reader@example.com'}, {'id':'dbid-1','label':'Reader','email':'reader@example.com'}),
    ('box', {'id':'1','name':'Reader','login':'reader@example.com'}, {'id':'1','label':'Reader','email':'reader@example.com'}),
    ('jira', {'accountId':'u-1','displayName':'Reader','emailAddress':'reader@example.com'}, {'id':'u-1','label':'Reader','email':'reader@example.com'}),
])
def test_only_provider_specific_verification_fields_are_retained(provider, output, expected):
    assert accounts.extract(provider, output) == expected
    assert 'private' not in json.dumps(accounts.extract(provider, output))


@pytest.mark.parametrize('provider,output', [('google_sheets',{'id':'sheet','name':'Private sheet'}),
    ('gmail',{'emailAddress':'not an email'}), ('slack',{'ok':False,'user_id':'U1'}),
    ('outlook',{'id':'Bearer private'}), ('outlook',{'id':'line\nbreak'}), ('outlook',{'id':'[REDACTED]'})])
def test_resource_tests_and_invalid_identity_do_not_become_accounts(provider, output):
    assert accounts.extract(provider, output) is None


def test_native_provider_envelope_is_allowlisted_without_persisting_its_other_fields():
    assert accounts.extract('gmail', {'data': {'emailAddress':'reader@example.com','private':'ignored'},
        'http_status':200,'delivery':'read'}) == {'email':'reader@example.com'}


def test_account_proof_is_bound_to_current_configuration_and_authorization():
    conn=connection();cred=credential()
    audit=NS(details={'binding':accounts.binding(conn,cred),'identity':{'id':'u-1','access_token':'private'},
                      'verified_at':'2026-11-13T00:00:00+00:00','operation_id':12})
    assert account(conn,cred,audit,True)['identity']=={'id':'u-1'}
    for field,value in [('revision',3),('config',{'label':'changed'}),('scopes',[]),('environment','production')]:
        previous=getattr(conn,field);setattr(conn,field,value)
        assert account(conn,cred,audit,True)=={'status':'verification_required'}
        setattr(conn,field,previous)
    cred.version+=1
    assert account(conn,cred,audit,True)=={'status':'verification_required'}
    assert account(conn,cred,None,False)=={'status':'verification_required'}


def test_action_readiness_uses_native_scopes_opt_in_and_separate_review():
    conn=connection();cred=credential()
    by_id={a['id']:a for a in actions(conn,cred,True,True)}
    assert by_id['test']['status']=='ready_to_read'
    assert by_id['send_mail']['status']=='missing_scopes'
    conn.scopes.append('Mail.Send')
    assert next(a for a in actions(conn,cred,True,True) if a['id']=='send_mail')['status']=='writes_disabled'
    conn.writes_enabled=True
    send=next(a for a in actions(conn,cred,True,True) if a['id']=='send_mail')
    assert send['status']=='ready_for_review' and send['requires_approval'] and send['requires_agent_binding']
    conn.expires_at=datetime(2020,1,1,tzinfo=timezone.utc)
    assert all(a['status'] in {'authorization_expired','native_workflow_required'} for a in actions(conn,cred,True,True))
    assert all(a['status'] in {'permission_required','native_workflow_required'} for a in actions(conn,cred,True,False))


def test_scope_aliases_remain_identical_to_execution_and_native_only_actions_stay_restricted():
    conn=connection();conn.connector_id='google_sheets';conn.scopes=['https://www.googleapis.com/auth/spreadsheets']
    assert 'https://www.googleapis.com/auth/spreadsheets.readonly' in service.effective_scopes(conn)
    read=next(a for a in actions(conn,credential(),True,True) if a['id']=='read_values')
    assert read['status']=='ready_to_read' and read['missing_scopes']==[]
    conn.connector_id='http'
    assert all(a['status']=='native_workflow_required' for a in actions(conn,credential(),True,True))
