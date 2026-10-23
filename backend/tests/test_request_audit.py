import json
import pytest
from fastapi import Depends
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from app.main import app
from app.core.deps import get_current_user
from app.models.audit import AuditLog, AuditLogTask
from app.models.user import Role, Permission
from app.apps.project_management.models import PMSWorkspaceMember
from tests.test_pms_workspaces import account, middleware_database, BASE


@pytest.fixture(autouse=True)
def audit_database(db):
    app.state.audit_session_factory=lambda:db
    app.state.audit_close_session=False
    app.state.audit_commit=False
    yield
    del app.state.audit_session_factory
    del app.state.audit_close_session
    del app.state.audit_commit


if not any(getattr(route,'path','')=='/api/v1/_audit-test/error' for route in app.routes):
    @app.get('/api/v1/_audit-test/error')
    def audit_failure(user=Depends(get_current_user)):
        raise ValueError('secret-password-should-not-appear')


def fixture(client,db):
    owner, headers=account(db,'audit-owner@test.com',True)
    member,mh=account(db,'audit-member@test.com')
    wid=client.post(BASE+'/workspaces',headers=headers,json={'name':'Audit workspace'}).json()['id']
    db.add(PMSWorkspaceMember(workspace_id=wid,user_id=member.id,role='Member'))
    pid=client.post(BASE+'/projects',headers=headers,json={'workspace_id':wid,'name':'Audit project','project_key':'AUD'}).json()['id']
    return owner,headers,member,mh,wid,pid


def test_audit_captures_task_actor_ip_and_redacts_queries(client,db):
    owner,headers,member,mh,wid,pid=fixture(client,db)
    role=Role(name='pms_team_member',is_system=True);db.add(role);db.flush();member.role_id=role.id;db.commit()
    response=client.post(f'{BASE}/projects/{pid}/tasks?password=secret-query&token=secret-token&task_id=7',headers={**mh,'X-Request-ID':'audit-test-123','X-Forwarded-For':'198.51.100.20','User-Agent':'Audit browser'},json={'title':'Private title','task_key':'AUD-1'})
    assert response.status_code==200,response.text
    assert response.headers['X-Request-ID']=='audit-test-123'
    task_id=response.json()['id']
    row=db.query(AuditLog).filter_by(request_id='audit-test-123').one()
    assert row.user_id==member.id and row.actor_role=='pms_team_member'
    assert row.actor_authenticated is True
    assert row.task_id==task_id and row.project_id==pid and row.workspace_id==wid
    assert row.forwarded_ip=='198.51.100.20' and row.ip_source=='peer'
    assert row.ip_address!='198.51.100.20'
    assert row.duration_ms>=0 and row.created_at
    assert row.user_agent=='Audit browser'
    assert 'secret-query' not in row.description and 'secret-token' not in row.description and 'Private title' not in row.description
    assert json.loads(row.description)['safe_query']=={'task_id':'7'}
    assert db.query(AuditLogTask).filter_by(audit_log_id=row.id,task_id=task_id).count()==1
    data=client.get('/api/v1/logs/requests',headers=headers,params={'task_id':task_id,'role':'pms_team_member'}).json()
    assert data['total']==1 and data['items'][0]['actor_email']==member.email
    role.name='renamed_role';db.commit()
    assert client.get('/api/v1/logs/requests',headers=headers,params={'task_id':task_id,'role':'pms_team_member'}).json()['total']==1


def test_audit_is_admin_only_and_workspace_scoped(client,db):
    owner,headers,member,mh,wid,pid=fixture(client,db)
    assert client.get('/api/v1/logs/requests',headers=mh).status_code==403
    # Giving a member an old company-management permission must not reveal logs.
    role=Role(name='office_manager',is_system=True);permission=Permission(name='company_manage',module='company');role.permissions=[permission];db.add(role);db.flush();member.role_id=role.id;db.commit()
    assert client.get('/api/v1/logs/audit',headers=mh).status_code==403
    local_admin,ah=account(db,'workspace-auditor@test.com')
    db.add(PMSWorkspaceMember(workspace_id=wid,user_id=local_admin.id,role='Admin'));db.commit()
    other,oh=account(db,'other-admin@test.com',True)
    other_wid=client.post(BASE+'/workspaces',headers=oh,json={'name':'Other workspace'}).json()['id']
    data=client.get('/api/v1/logs/requests',headers=ah).json()
    assert data['scope']=='workspace'
    assert all(row['workspace_id']!=other_wid for row in data['items'])
    assert client.get('/api/v1/logs/requests').status_code in (401,403)


def test_failure_is_retained_without_exception_message(client,db):
    owner,headers=account(db,'audit-error@test.com',True)
    with pytest.raises(Exception):
        client.get('/api/v1/_audit-test/error',headers={**headers,'X-Request-ID':'error-test'})
    row=db.query(AuditLog).filter_by(request_id='error-test').one()
    assert row.status_code==500 and row.error_type=='ValueError'
    assert row.user_id==owner.id
    assert 'secret-password' not in row.description
    assert json.loads(row.description)['error_location']
    response=client.get('/api/v1/logs/requests',headers=headers,params={'outcome':'server_error','request_id':'error-test'})
    assert response.status_code==200
    assert response.json()['total']==1


def test_bulk_actions_link_all_tasks(client,db):
    owner,headers,_,_,wid,pid=fixture(client,db)
    task_ids=[client.post(f'{BASE}/projects/{pid}/tasks',headers=headers,json={'title':f'Task {i}','task_key':f'AUD-{i}'}).json()['id'] for i in range(2)]
    response=client.patch(BASE+'/tasks/bulk',headers={**headers,'X-Request-ID':'bulk-audit'},json={'task_ids':task_ids,'priority':'High'})
    assert response.status_code==200,response.text
    for tid in task_ids:
        result=client.get('/api/v1/logs/requests',headers=headers,params={'task_id':tid,'request_id':'bulk-audit'}).json()
        assert result['total']==1
        assert result['items'][0]['task_ids']==task_ids


@pytest.mark.parametrize('folder,prefix',[('alembic',''),('alembic_postgresql','pg_')])
def test_request_audit_migration_is_repeat_safe(folder,prefix):
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        metadata=MetaData();Table('audit_logs',metadata,Column('id',Integer,primary_key=True));metadata.create_all(connection)
        connection.exec_driver_sql('INSERT INTO audit_logs(id) VALUES (42)')
        file=Path(__file__).parents[1]/folder/'versions'/f'{prefix}20261024_002_request_audit.py'
        spec=spec_from_file_location('audit_migration_'+prefix,file);module=module_from_spec(spec);spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade();module.upgrade()
        assert 'actor_role' in {c['name'] for c in inspect(connection).get_columns('audit_logs')}
        assert inspect(connection).has_table('audit_log_tasks')
        assert connection.exec_driver_sql('SELECT id FROM audit_logs').scalar()==42


def test_proxy_chain_ignores_spoofed_leftmost_hop(monkeypatch):
    from starlette.requests import Request
    from app.core.middleware.audit import client_addresses
    request=Request({'type':'http','method':'GET','path':'/','headers':[(b'x-forwarded-for',b'203.0.113.99, 198.51.100.20, 10.0.0.2')],'client':('10.0.0.1',1234)})
    monkeypatch.setenv('AUDIT_TRUSTED_PROXY_CIDRS','10.0.0.0/8')
    assert client_addresses(request)==('198.51.100.20','trusted_proxy','203.0.113.99')
    monkeypatch.delenv('AUDIT_TRUSTED_PROXY_CIDRS')
    assert client_addresses(request)[0]=='10.0.0.1'


def test_audit_survives_business_transaction_rollback(tmp_path):
    from sqlalchemy.orm import sessionmaker
    from starlette.requests import Request
    from types import SimpleNamespace
    from app.core.middleware.audit import AuditLogMiddleware
    engine=create_engine('sqlite:///'+str(tmp_path/'audit-isolation.db'))
    metadata=MetaData();Table('users',metadata,Column('id',Integer,primary_key=True));Table('business_records',metadata,Column('id',Integer,primary_key=True));metadata.create_all(engine)
    AuditLog.__table__.create(engine);AuditLogTask.__table__.create(engine)
    factory=sessionmaker(bind=engine)
    business=factory();business.execute(metadata.tables['business_records'].insert().values(id=1));business.rollback();business.close()
    request=Request({'type':'http','method':'POST','path':'/api/v1/_audit-test/failure','query_string':b'password=secret','headers':[],'client':('127.0.0.1',1234),'app':SimpleNamespace(state=SimpleNamespace(audit_session_factory=factory))})
    request.state.audit_context={'actor':{'user_id':None,'email':None,'role':None,'authenticated':False}}
    request.state.request_id='rollback-audit'
    AuditLogMiddleware(app)._persist(request,500,12,RuntimeError('secret'))
    with factory() as db:
        assert db.execute(metadata.tables['business_records'].select()).all()==[]
        row=db.query(AuditLog).one()
        assert row.request_id=='rollback-audit' and row.status_code==500
        assert 'secret' not in row.description
