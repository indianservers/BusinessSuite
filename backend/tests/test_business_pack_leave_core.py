"""Canonical leave works independently of operational pack selection."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.test_business_pack_common_core import core_case, select_pack


@pytest.fixture
def leave_case(core_case):
    from app.models.user import Permission
    from app.models.leave import LeaveType, LeaveBalance
    from app.models.employee import Employee
    from app.access.models import AccessPolicy
    n = core_case
    names = ['leave_apply', 'leave_approve', 'leave_manage']
    for name in names:
        permission = n.db.query(Permission).filter_by(name=name).first()
        if permission is None:
            permission = Permission(name=name, module='hrms', description=name)
            n.db.add(permission); n.db.flush()
        if permission not in n.admin.role.permissions: n.admin.role.permissions.append(permission)
        if name == 'leave_apply' and permission not in n.user.role.permissions: n.user.role.permissions.append(permission)
    for user in (n.user, n.admin):
        policy = n.db.query(AccessPolicy).filter_by(user_id=user.id, company_id=1).one()
        grants = dict(policy.grants)
        grants['hrms'] = {**grants['hrms'], 'permissions': [*grants['hrms']['permissions'],
            *(['leave_apply'] if user is n.user else names)]}
        policy.grants = grants
    manager = Employee(employee_id=uuid4().hex, first_name='Leave', last_name='Reviewer', status='Active',
        date_of_joining=date(2020, 1, 1), user_id=n.admin.id, branch_id=n.branch.id)
    n.db.add(manager); n.db.flush()
    n.employee.reporting_manager_id = manager.id
    from app.branches.migration import backfill
    backfill(n.db.connection(), 1)
    n.db.commit()
    created = n.client.post('/api/v1/leave/types', headers=n.admin_headers,
        json={'name':'Canonical annual leave','code':uuid4().hex[:18],'days_allowed':'20'})
    assert created.status_code == 201, created.text
    kind = n.db.get(LeaveType, created.json()['id'])
    allocated = n.client.post('/api/v1/leave/balance/allocate', headers=n.admin_headers,
        params={'employee_id':n.employee.id,'leave_type_id':kind.id,'year':date.today().year,'days':20})
    assert allocated.status_code == 200, allocated.text
    balance = n.db.get(LeaveBalance, allocated.json()['id'])
    n.kind, n.balance, n.manager = kind, balance, manager
    return n


def apply(n, headers=None, offset=2):
    day = date.today() + timedelta(days=offset)
    return n.client.post('/api/v1/leave/apply', headers=headers or n.headers,
        json={'leave_type_id': n.kind.id, 'from_date': day.isoformat(), 'to_date': day.isoformat(), 'reason': 'Native leave request'})


@pytest.mark.parametrize('pack', ['hospital', 'salon'])
def test_native_leave_same_records_across_pack_selectors_and_review(leave_case, pack):
    from app.models.leave import LeaveRequest, LeaveBalanceLedger
    from app.models.notification import Notification, NotificationDeliveryLog
    n = leave_case
    context = select_pack(n, pack)
    headers = {**n.headers, 'X-Suite-Pack-Context': str(context.id)}
    response = apply(n, headers)
    assert response.status_code == 201, response.text
    identity = response.json()['id']
    for selector in (str(context.id), '99999999', 'invalid-selector'):
        result = n.client.get('/api/v1/leave/my-requests', headers={**n.headers, 'X-Suite-Pack-Context': selector})
        assert result.status_code == 200, result.text
        assert [item['id'] for item in result.json()] == [identity]
    for path in ('types', 'balance', 'ledger'):
        result = n.client.get('/api/v1/leave/' + path, headers=headers)
        assert result.status_code == 200, result.text
        assert len(result.json()) == (2 if path == 'ledger' else 1)
    calendar = n.client.get('/api/v1/leave/calendar', headers=headers, params={
        'from_date': date.today().isoformat(), 'to_date': (date.today()+timedelta(days=7)).isoformat(), 'scope': 'mine'})
    assert calendar.status_code == 200, calendar.text
    assert calendar.json()['total_leave_days'] == 1
    result = n.client.put(f'/api/v1/leave/requests/{identity}/approve', headers=n.admin_headers,
        json={'status': 'Approved', 'review_remarks': 'Native reviewed'})
    assert result.status_code == 200, result.text
    n.db.expire_all()
    assert n.db.get(LeaveRequest, identity).status == 'Approved'
    assert n.db.get(type(n.balance), n.balance.id).used == Decimal('1')
    assert n.db.query(LeaveBalanceLedger).filter_by(leave_request_id=identity).count() == 2
    notifications = n.db.query(Notification).filter_by(related_entity_id=identity, module='leave').order_by(Notification.id).all()
    # Native Own record scope also masks the manager lookup during submission;
    # leave must not widen that scope merely to send an optional notification.
    assert [(row.user_id, row.event_type, row.channels) for row in notifications] == [
        (n.user.id, 'leave_approved', ['in_app'])]
    assert all(row.company_id == 1 and row.related_entity_type == 'leave_request' for row in notifications)
    delivery = n.db.query(NotificationDeliveryLog).filter(NotificationDeliveryLog.notification_id.in_([row.id for row in notifications])).all()
    assert [(row.channel, row.status, row.recipient) for row in delivery] == [('in_app', 'delivered', None)]
    from app.shared.models import ServiceEvent
    events = n.db.query(ServiceEvent).filter_by(entity_type='leave', entity_id=identity).order_by(ServiceEvent.id).all()
    assert [(row.organization_id, row.actor_id, row.module_key, row.event_type) for row in events] == [
        (1, n.user.id, 'hrms', 'record.created'), (1, n.admin.id, 'hrms', 'status.changed')]
    assert all(row.payload_json == {'depth': 0, 'data': {}} and row.status == 'pending' for row in events)


def test_pack_doctor_never_grants_leave_review_and_own_scope_hides_others(leave_case):
    n = leave_case
    context = select_pack(n)
    response = apply(n)
    assert response.status_code == 201, response.text
    identity = response.json()['id']
    result = n.client.put(f'/api/v1/leave/requests/{identity}/approve',
        headers={**n.headers, 'X-Suite-Pack-Context': str(context.id)}, json={'status': 'Approved'})
    assert result.status_code == 403, result.text
    result = n.client.get(f'/api/v1/leave/balance/{n.manager.id}', headers=n.headers)
    assert result.status_code == 403, result.text
    result = n.client.put(f'/api/v1/leave/requests/{identity}/cancel', headers=n.headers)
    assert result.status_code == 200, result.text


@pytest.mark.parametrize('denial', ['policy', 'branch', 'legacy-branch', 'revoked'])
def test_native_leave_writes_respect_explicit_denials(leave_case, denial):
    from app.access.models import AccessPolicy
    from app.branches.models import BranchGrant
    from app.models.leave import LeaveRequest
    n = leave_case
    select_pack(n)
    policy = n.db.query(AccessPolicy).filter_by(user_id=n.user.id, company_id=1).one()
    if denial == 'policy':
        policy.grants = {'hrms': {**policy.grants['hrms'], 'actions': ['view']}}
    elif denial in {'branch', 'legacy-branch'}:
        if denial == 'legacy-branch':
            n.db.delete(policy)
            n.user.role.permissions = []
        n.db.query(BranchGrant).filter_by(user_id=n.user.id, branch_id=n.branch.id).one().can_write = False
    else:
        policy.status = 'suspended'
    n.db.commit()
    before = n.db.query(LeaveRequest).count()
    result = apply(n)
    assert result.status_code == 403, result.text
    assert n.db.query(LeaveRequest).count() == before


def test_original_empty_native_role_retains_only_own_leave_self_service(leave_case):
    from app.access.models import AccessPolicy
    n = leave_case
    context = select_pack(n, 'salon')
    n.db.query(AccessPolicy).filter_by(user_id=n.user.id, company_id=1).delete()
    n.user.role.permissions = []
    n.db.commit()
    headers = {**n.headers, 'X-Suite-Pack-Context': str(context.id)}
    response = apply(n, headers)
    assert response.status_code == 201, response.text
    identity = response.json()['id']
    for path in ('types', 'balance', 'ledger', 'my-requests'):
        result = n.client.get('/api/v1/leave/' + path, headers=headers)
        assert result.status_code == 200, result.text
    result = n.client.put(f'/api/v1/leave/requests/{identity}/approve', headers=headers, json={'status': 'Approved'})
    assert result.status_code == 403, result.text
    result = n.client.put(f'/api/v1/leave/requests/{identity}/cancel', headers=headers)
    assert result.status_code == 200, result.text


def test_native_visible_manager_receives_only_matching_in_app_submission(leave_case):
    from app.access.models import AccessPolicy
    from app.models.notification import Notification, NotificationDeliveryLog
    n = leave_case
    select_pack(n, 'salon')
    policy = n.db.query(AccessPolicy).filter_by(user_id=n.user.id, company_id=1).one()
    policy.grants = {'hrms': {**policy.grants['hrms'], 'scope': 'organization'}}
    n.db.commit()
    response = apply(n)
    assert response.status_code == 201, response.text
    notification = n.db.query(Notification).filter_by(module='leave', related_entity_id=response.json()['id']).one()
    assert (notification.user_id, notification.company_id, notification.event_type, notification.channels) == (
        n.admin.id, 1, 'leave_submitted', ['in_app'])
    delivery = n.db.query(NotificationDeliveryLog).filter_by(notification_id=notification.id).one()
    assert (delivery.channel, delivery.status, delivery.recipient, delivery.provider_message_id) == ('in_app', 'delivered', None, None)


def test_native_team_reviewer_can_reject_only_its_canonical_report(leave_case):
    from app.access.models import AccessPolicy
    from app.models.leave import LeaveRequest
    from app.models.employee import Employee
    from app.branches.models import BranchOwnership
    n = leave_case
    select_pack(n, 'salon')
    policy = n.db.query(AccessPolicy).filter_by(user_id=n.admin.id, company_id=1).one()
    policy.grants = {'hrms': {**policy.grants['hrms'], 'scope': 'team'}}
    stranger = Employee(employee_id=uuid4().hex, first_name='Outside', last_name='Reporting line',
        date_of_joining=date(2020, 1, 1), branch_id=n.branch.id, status='Active')
    n.db.add(stranger); n.db.flush()
    day = date.today() + timedelta(days=9)
    outside = LeaveRequest(company_id=1, employee_id=stranger.id, leave_type_id=n.kind.id,
        from_date=day, to_date=day, days_count=1, status='Pending')
    n.db.add(outside); n.db.flush()
    for row in (stranger, outside):
        n.db.add(BranchOwnership(company_id=1, branch_id=n.branch.id, resource_table=row.__tablename__,
            resource_key=str(row.id), source='verified-native-team-test'))
    n.db.commit()
    submitted = apply(n)
    assert submitted.status_code == 201, submitted.text
    result = n.client.put(f"/api/v1/leave/requests/{submitted.json()['id']}/approve", headers=n.admin_headers,
        json={'status':'Rejected', 'review_remarks':'Native team review'})
    assert result.status_code == 200, result.text
    n.db.expire_all()
    assert n.db.get(LeaveRequest, submitted.json()['id']).status == 'Rejected'
    assert n.db.get(type(n.balance), n.balance.id).pending == 0
    result = n.client.put(f'/api/v1/leave/requests/{outside.id}/approve', headers=n.admin_headers,
        json={'status':'Approved'})
    assert result.status_code == 404, result.text
    n.db.expire_all()
    assert n.db.get(LeaveRequest, outside.id).status == 'Pending'


def test_leave_core_never_adopts_pack_private_requests_or_other_employees(leave_case):
    from app.models.leave import LeaveRequest
    from app.business_packs.models import PackRecordOwnership
    from app.branches.models import BranchOwnership
    n = leave_case
    context = select_pack(n)
    day = date.today() + timedelta(days=9)
    other = LeaveRequest(company_id=1, employee_id=n.manager.id, leave_type_id=n.kind.id,
        from_date=day, to_date=day, days_count=1, status='Pending')
    private = LeaveRequest(company_id=1, employee_id=n.employee.id, leave_type_id=n.kind.id,
        from_date=day, to_date=day, days_count=1, status='Pending')
    n.db.add_all([other, private]); n.db.flush()
    for row in (other, private):
        n.db.add(BranchOwnership(company_id=1, branch_id=n.branch.id, resource_table='leave_requests',
            resource_key=str(row.id), source='verified-native-test-parent'))
    n.db.add(PackRecordOwnership(company_id=1, branch_id=n.branch.id, context_id=context.id,
        resource_table='leave_requests', resource_key=str(private.id)))
    n.db.commit()
    for identity in (other.id, private.id):
        response = n.client.get(f'/api/v1/leave/requests/{identity}', headers=n.headers)
        assert response.status_code == 404, response.text
    response = n.client.get('/api/v1/leave/my-requests', headers=n.headers)
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_leave_definition_cannot_cross_native_company(leave_case):
    from app.models.company import Company
    from app.models.leave import LeaveType
    from app.models.security_boundary import SecurityResourceOwnership
    n = leave_case
    n.db.add(Company(id=77, name='Other native company')); n.db.flush()
    foreign = LeaveType(name='Foreign confidential leave type', code=uuid4().hex[:18], days_allowed=20)
    n.db.add(foreign); n.db.flush()
    n.db.add(SecurityResourceOwnership(resource_table='leave_types', resource_id=foreign.id, company_id=77))
    n.db.commit()
    select_pack(n, 'salon')
    response = n.client.get('/api/v1/leave/types', headers=n.headers)
    assert response.status_code == 200, response.text
    assert foreign.id not in {row['id'] for row in response.json()}
    response = n.client.get('/api/v1/leave/types', headers={**n.headers, 'X-Suite-Organization':'77'})
    assert response.status_code == 403, response.text


def test_leave_mid_request_native_revocation_prevents_any_application(leave_case, monkeypatch):
    from sqlalchemy import update
    from app.access.models import AccessPolicy
    from app.crud import crud_leave
    from app.models.leave import LeaveRequest
    n = leave_case
    select_pack(n)
    original = crud_leave.create_leave_request
    def revoke(db, *args, **kwargs):
        db.connection().execute(update(AccessPolicy).where(AccessPolicy.user_id == n.user.id,
            AccessPolicy.company_id == 1).values(version=AccessPolicy.version + 1))
        return original(db, *args, **kwargs)
    monkeypatch.setattr(crud_leave, 'create_leave_request', revoke)
    before = n.db.query(LeaveRequest).count()
    response = apply(n)
    assert response.status_code == 403, response.text
    assert n.db.query(LeaveRequest).count() == before


@pytest.mark.parametrize('operation', ['events-read', 'events-write', 'raw', 'bulk'])
def test_leave_native_graph_rejects_unreviewed_sources_and_bypasses(leave_case, monkeypatch, operation):
    from sqlalchemy import text
    from app.crud import crud_leave
    from app.models.leave import LeaveRequest
    from app.shared.models import ServiceEvent
    n = leave_case
    select_pack(n)
    def unreviewed(db):
        if operation == 'events-read': return db.query(ServiceEvent).all()
        if operation == 'raw': return db.execute(text('SELECT 1')).all()
        if operation == 'bulk': return db.query(LeaveRequest).delete()
        db.add(ServiceEvent(organization_id=1, actor_id=n.user.id, module_key='hrms',
            entity_type='leave', entity_id=999999, event_type='record.created', request_key=str(uuid4()),
            payload_json={'depth':0,'data':{}}, status='pending'))
        db.flush()
        return []
    monkeypatch.setattr(crud_leave, 'get_all_leave_types', unreviewed)
    before = n.db.query(ServiceEvent).count()
    response = n.client.get('/api/v1/leave/types', headers=n.headers)
    assert response.status_code == 403, response.text
    assert n.db.query(ServiceEvent).count() == before



@pytest.mark.parametrize('tamper',['valid','signature','foreign-user','foreign-company','foreign-session',
    'missing-origin','extra-data','extra-origin','wrong-operation','stale-origin','non-ai-origin'])
def test_actual_native_leave_event_requires_current_exact_ai_provenance(leave_case,monkeypatch,tamper):
    from copy import deepcopy
    from datetime import datetime,timezone
    from sqlalchemy import update
    from app.models.user import UserSession
    from app.models.leave import LeaveRequest,LeaveBalanceLedger
    from app.shared.models import ServiceEvent,ServicePolicy
    from app.crud import crud_leave
    from app.ai_agents.security import seal,signature,verify_provenance
    n=leave_case
    login=UserSession(user_id=n.user.id,session_token_hash=uuid4().hex,status='Active',expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
    n.db.add(login)
    epoch=n.db.query(ServicePolicy).filter_by(scope_key='company:1:ai_acl_epoch',kind='ai_acl_epoch').first()
    if epoch is None:
        epoch=ServicePolicy(organization_id=1,scope_key='company:1:ai_acl_epoch',kind='ai_acl_epoch',version=1,values_json={},updated_by=n.admin.id)
        n.db.add(epoch)
    n.db.commit();session_id=login.id;epoch_id=epoch.id
    # A genuine cryptographic seal alone cannot turn an ordinary request into AI.
    historical=seal(n.db,n.user,session_id=session_id,tenant=1) if tamper=='non-ai-origin' else None
    select_pack(n)
    create=crud_leave.create_leave_request
    def actual_ai_request(db,*args,**kwargs):
        if tamper!='non-ai-origin':
            previous=db.info.get('ai_request_context') or {}
            db.info['ai_request_context']={**previous,'user_id':n.user.id,'company_id':1,'session_id':session_id,'is_ai':True}
        return create(db,*args,**kwargs)
    monkeypatch.setattr(crud_leave,'create_leave_request',actual_ai_request)
    constructor=ServiceEvent.__init__
    def mutate(row,**kwargs):
        if kwargs.get('entity_type')=='leave':
            payload=deepcopy(kwargs['payload_json'])
            if tamper=='non-ai-origin':payload['ai_origin']=historical
            elif tamper=='missing-origin':payload.pop('ai_origin')
            elif tamper=='extra-data':payload['data']={'private':'unreviewed'}
            elif tamper=='stale-origin':
                n.db.connection().execute(update(ServicePolicy).where(ServicePolicy.id==epoch_id).values(version=ServicePolicy.version+1))
            elif tamper not in {'valid'}:
                origin=payload['ai_origin']
                if tamper=='signature':origin['signature']='0'*64
                else:
                    if tamper=='foreign-user':origin['user_id']=n.admin.id
                    elif tamper=='foreign-company':origin['company_id']=77
                    elif tamper=='foreign-session':origin['session_id']=session_id+1
                    elif tamper=='extra-origin':origin['private']='unreviewed'
                    elif tamper=='wrong-operation':origin['operation']='f'*64
                    origin['signature']=signature({key:value for key,value in origin.items() if key!='signature'})
            kwargs['payload_json']=payload
        constructor(row,**kwargs)
    monkeypatch.setattr(ServiceEvent,'__init__',mutate)
    before=(n.db.query(LeaveRequest).count(),n.db.query(ServiceEvent).count(),n.db.query(LeaveBalanceLedger).count())
    result=apply(n)
    if tamper=='valid':
        assert result.status_code==201,result.text
        event=n.db.query(ServiceEvent).filter_by(entity_type='leave',entity_id=result.json()['id']).one()
        assert event.actor_id==n.user.id and event.organization_id==1 and event.event_type=='record.created'
        assert set(event.payload_json)=={'depth','data','ai_origin'}
        assert verify_provenance(n.user,event.payload_json['ai_origin'])['session_id']==session_id
    else:
        assert result.status_code in {403,409},result.text
        assert (n.db.query(LeaveRequest).count(),n.db.query(ServiceEvent).count(),n.db.query(LeaveBalanceLedger).count())==before
        n.db.refresh(n.balance);assert n.balance.pending==0
