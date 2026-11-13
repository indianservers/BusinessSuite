"""Native verification -> private agent connection cards, using disposable data."""
import json
from uuid import uuid4
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from tests.test_power_connector_runtime import fixture_transport
from ai_test_utils import auth_headers
from app.apps.power_apps.integrations.models import Connection, Credential, ConnectionAudit, Operation
from app.apps.power_apps.integrations.transport import Response
from app.apps.power_apps.runtime import now, scope_values
from app.apps.power_apps.models import PowerEnvironment
from app.models.user import Permission

NATIVE='/api/v1/power-apps/integrations'
ROOT='/api/v1/ai-operator/suite/agents/connectors'
SCOPES=['https://www.googleapis.com/auth/gmail.metadata']


def setup(client,db):
    values=setup_suite(client,db)
    if not db.query(PowerEnvironment).filter_by(organization_id=1,key='development').first():
        db.add(PowerEnvironment(organization_id=1,key='development',enabled=True));db.commit()
    return values


def connect(client,h):
    response=client.post(NATIVE+'/connections',headers=h,json={'connector_id':'gmail','name':'Synthetic mail account',
        'auth_type':'bearer','secrets':{'access_token':'synthetic-mail-secret'},'scopes':SCOPES,'writes_enabled':False})
    assert response.status_code==201,response.text
    return response.json()


def verify(client,h,conn):
    response=client.post(NATIVE+'/execute',headers=h,json={'connection_id':conn['id'],'action_id':'test',
        'input':{},'request_id':'synthetic-check-'+uuid4().hex})
    assert response.status_code==200,response.text
    return response


def card(client,h,ident):
    response=client.get(ROOT,headers=h)
    assert response.status_code==200,response.text
    assert 'no-store' in response.headers.get('Cache-Control','')
    return next(item for item in response.json()['connections'] if item['id']==ident),response


def test_native_account_verification_rotation_and_private_readiness(client,db,monkeypatch):
    h,user,_,_=setup(client,db);conn=connect(client,h)
    email=['reader@example.com']
    calls=fixture_transport(monkeypatch,lambda *args:Response(200,{},json.dumps({'emailAddress':email[0],
        'access_token':'synthetic-mail-secret','debug':'Private provider debug body'}).encode(),1))
    before,_=card(client,h,conn['id']);assert before['account']['status']=='verification_required'
    verify(client,h,conn)
    value,response=card(client,h,conn['id'])
    assert value['account']['identity']=={'email':'reader@example.com'}
    assert value['account']['status']=='verified' and value['account']['operation_id']
    assert value['last_successful_operation_at'] and value['last_successful_read_at'] is None
    assert next(a for a in value['actions'] if a['id']=='test')['status']=='ready_to_read'
    assert next(a for a in value['actions'] if a['id']=='send_mail')['status']=='missing_scopes'
    assert len(calls)==1 and db.query(ConnectionAudit).filter_by(action='provider_account_verified').count()==1
    assert 'synthetic-mail-secret' not in response.text and 'Private provider debug' not in response.text
    other,_=auth_headers(client,db,email='other-status-'+uuid4().hex+'@example.com',permissions=['ai_assistant','power_apps_view'])
    hidden=client.get(ROOT,headers=other);assert hidden.status_code==200,hidden.text
    assert hidden.json()['connections']==[] and 'reader@example.com' not in hidden.text
    rotated=client.post(NATIVE+f'/connections/{conn["id"]}/rotate',headers=h,json={
        'expected_version':conn['revision'],'secrets':{'access_token':'rotated-synthetic-secret'}})
    assert rotated.status_code==200,rotated.text
    value,response=card(client,h,conn['id'])
    assert value['account']['status']=='verification_required' and 'reader@example.com' not in response.text
    email[0]='new-reader@example.com';verify(client,h,conn)
    value,_=card(client,h,conn['id']);assert value['account']['identity']=={'email':'new-reader@example.com'}
    assert len(calls)==2
    stored=db.get(Connection,conn['id']);credential=db.get(Credential,stored.credential_id)
    credential.revoked_at=now();db.commit()
    value,response=card(client,h,conn['id'])
    assert value['account']['status']=='verification_required' and 'new-reader@example.com' not in response.text
    assert not value['live_verified'] and value['authorization_status']=='unavailable'
    assert all(a['status'] in {'authorization_unavailable','native_workflow_required'} for a in value['actions'])


def test_inflight_authorization_change_does_not_verify_replacement_connection(client,db,monkeypatch):
    h,_,_,_=setup(client,db);conn=connect(client,h)
    def changed(*args):
        row=db.get(Connection,conn['id']);row.revision+=1;row.health='unverified';row.last_verified_at=None;db.commit()
        return Response(200,{},b'{"emailAddress":"old-reader@example.com"}',1)
    fixture_transport(monkeypatch,changed)
    verify(client,h,conn)
    value,response=card(client,h,conn['id'])
    assert value['health']=='unverified' and not value['live_verified']
    assert value['account']['status']=='verification_required' and 'old-reader@example.com' not in response.text
    assert db.query(ConnectionAudit).filter_by(action='provider_account_verified').count()==0
    assert db.query(Operation).one().status=='succeeded'  # Actual response remains an accurate old-operation receipt.


def test_history_is_bounded_and_excludes_other_owners_environments_and_raw_errors(client,db):
    h,user,_,_=setup(client,db);conn=connect(client,h);row=db.get(Connection,conn['id'])
    _,other=auth_headers(client,db,email='journal-other-'+uuid4().hex+'@example.com',permissions=['ai_assistant','power_apps_view'])
    db.add(PowerEnvironment(organization_id=1,key='testing',enabled=True));db.commit()
    for index in range(9):
        db.add(Operation(**scope_values(row),connection_id=row.id,connector_id='gmail',action_id='test',
            operation_key=uuid4().hex,input_hash='f'*64,mutates=False,status='failed',
            correlation_id=uuid4().hex,error_category='rate_limit',error='Private provider failure',finished_at=now()))
    for owner,env in [(other.id,'development'),(user.id,'testing')]:
        db.add(Operation(organization_id=1,environment=env,owner_user_id=owner,connection_id=row.id,
            connector_id='gmail',action_id='send_mail',operation_key=uuid4().hex,input_hash='f'*64,
            mutates=True,status='failed',correlation_id=uuid4().hex,error_category='private_other_error',finished_at=now()))
    db.add(Operation(**scope_values(row),connection_id=row.id,connector_id='gmail',action_id='list_messages',
        operation_key=uuid4().hex,input_hash='f'*64,mutates=False,status='succeeded',correlation_id=uuid4().hex,finished_at=now()))
    db.commit()
    value,response=card(client,h,row.id)
    assert len(value['recent_errors'])==5 and value['last_successful_read_at']
    assert all(e['category']=='rate_limit' for e in value['recent_errors'])
    assert 'Private provider failure' not in response.text and 'private_other_error' not in response.text


def test_view_only_owner_does_not_receive_activity_history_or_execution_readiness(client,db):
    h,user,_,_=setup(client,db);conn=connect(client,h);row=db.get(Connection,conn['id'])
    db.add(Operation(**scope_values(row),connection_id=row.id,connector_id='gmail',action_id='test',
        operation_key=uuid4().hex,input_hash='f'*64,mutates=False,status='failed',
        correlation_id=uuid4().hex,error_category='private_history_category',finished_at=now()))
    permission=db.query(Permission).filter_by(name='power_apps_view').first()
    if not permission:
        permission=Permission(name='power_apps_view',module='power_apps');db.add(permission);db.flush()
    user.role.permissions.append(permission);user.is_superuser=False;db.commit()
    value,response=card(client,h,row.id)
    assert not value['history_visible'] and value['recent_errors']==[]
    assert value['last_successful_operation_at'] is None and 'private_history_category' not in response.text
    assert all(a['status'] in {'permission_required','native_workflow_required'} for a in value['actions'])


def test_nonretained_native_read_does_not_persist_account_identity(client,db,monkeypatch):
    from app.apps.power_apps.integrations import service
    from app.access.service import activate_run_context, release_run_context, background_scope
    from types import SimpleNamespace
    h,user,_,_=setup(client,db);conn=connect(client,h)
    fixture_transport(monkeypatch,lambda *args:Response(200,{},b'{"emailAddress":"private-reader@example.com"}',1))
    activate_run_context(db,user,SimpleNamespace(scope_key='company:1'))
    try:
        with background_scope(db,user,'power_apps','view'):
            service.invoke(db,user,db.get(Connection,conn['id']),'test',{},key=uuid4().hex,retain_output=False)
    finally:
        release_run_context(db)
    assert db.query(Operation).one().output=={'source_read':True,'retained':False}
    assert db.query(ConnectionAudit).filter_by(action='provider_account_verified').count()==0
    value,response=card(client,h,conn['id'])
    assert value['account']['status']=='not_reported' and 'private-reader@example.com' not in response.text
