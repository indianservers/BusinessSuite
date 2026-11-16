"""Assigned service plans stay private and never become actual worked hours."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.company import Company, Branch
from app.models.employee import Employee
from app.models.user import User, Role, Permission
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.attendance import Attendance
from app.models.audit import AuditLog
from app.access.models import AccessMembership, AccessPolicy
from app.branches.service import context as branch_context
from app.business_packs.models import PackActivation, PackContext, PackUserGrant, PackRecordOwnership, PackMasterAvailability
from app.business_packs.access import resolve_context
from app.apps.srm.industry_models import IndustryRecord
from app.services.planned_services import planned_services


START = datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc)


@pytest.fixture
def plans(db):
    if not db.get(Company, 1):
        db.add(Company(id=1, name='Planned work company', default_timezone='Asia/Kolkata'))
    db.add(Company(id=2, name='Foreign planned work company'))
    db.flush()
    branches = [Branch(company_id=1, name='Service branch'), Branch(company_id=1, name='Other branch'), Branch(company_id=2, name='Foreign branch')]
    db.add_all(branches); db.flush()
    permission = db.query(Permission).filter_by(name='timesheet_view').first()
    if not permission:
        permission = Permission(name='timesheet_view', module='hrms'); db.add(permission); db.flush()
    role = Role(name='planned-worker-' + uuid4().hex, permissions=[permission])
    db.add(role); db.flush()
    users, employees = {}, {}
    for index, name in enumerate(['specialist', 'coworker', 'reception', 'foreign']):
        user = User(email=name + '-' + uuid4().hex + '@example.test', hashed_password='unused', is_active=True, is_superuser=False, role_id=role.id)
        db.add(user); db.flush()
        branch = branches[2] if name == 'foreign' else branches[0]
        user.organization_id = branch.company_id
        db.add(AccessMembership(user_id=user.id, company_id=branch.company_id, active=True))
        employee = Employee(employee_id='PLAN-' + uuid4().hex[:12], user_id=user.id,
            first_name=name, last_name='QA', branch_id=branch.id, date_of_joining=date(2024, 1, 1), status='Active')
        db.add(employee); db.flush()
        users[name], employees[name] = user, employee
    db.commit()

    def provider(employee=None, *, branch=None, user_only=False, resource_type='doctor'):
        employee = employee or employees['specialist']
        selected = branch or employee.branch_id
        row = IndustryRecord(organization_id=2 if selected == branches[2].id else 1, branch_id=selected,
            kind='resource', title='QA provider', request_id=str(uuid4()), status='active',
            created_by=users['reception'].id, data={'resource_type': resource_type, 'employee_id': None if user_only else employee.id,
                'user_id': employee.user_id, 'timezone': 'Asia/Kolkata'})
        db.add(row); db.flush(); return row

    default_provider = provider()

    def appointment(resources=None, *, starts=START, minutes=60, status='booked', branch=None):
        selected = branch or branches[0].id
        row = IndustryRecord(organization_id=2 if selected == branches[2].id else 1, branch_id=selected,
            kind='appointment', title='QA appointment', status=status, request_id=str(uuid4()),
            starts_at=starts, ends_at=starts + timedelta(minutes=minutes), created_by=users['reception'].id,
            data={'resource_ids': [item.id for item in (resources or [default_provider])],
                'service_id': 17, 'service_name': 'Scheduled consultation', 'duration_minutes': minutes,
                'notes': 'PRIVATE NOTE', 'customer_name': 'PRIVATE CUSTOMER', '_payment_requests': {'private': {'receipt_id': 99}}})
        db.add(row); db.flush(); return row

    def read(employee=None, *, actor=None, context=None, scope=None, **kwargs):
        actor = actor or users['specialist']
        employee = employee or employees['specialist']
        context = context or branch_context(db, actor, actor.organization_id, branches[0].id)
        return planned_services(db, actor, context, employee.id, kwargs.pop('from_at', START - timedelta(days=1)),
            kwargs.pop('until_at', START + timedelta(days=2)), scope, **kwargs)

    def pack(pack='hospital', role='doctor', *, state='active'):
        activation = PackActivation(company_id=1, pack_key=pack, pack_version=1, state=state)
        db.add(activation); db.flush()
        context = PackContext(company_id=1, branch_id=branches[0].id, activation_id=activation.id, pack_key=pack, pack_version=1, state=state)
        db.add(context); db.flush()
        grant = PackUserGrant(company_id=1, branch_id=branches[0].id, context_id=context.id, user_id=users['specialist'].id, role=role)
        db.add(grant); db.flush()
        return context, grant

    def anchor(row, context):
        db.add(PackRecordOwnership(company_id=context.company_id, branch_id=context.branch_id,
            context_id=context.id, resource_table='srm_industry_records', resource_key=str(row.id)))
        db.flush()

    return SimpleNamespace(db=db, branches=branches, users=users, employees=employees, role=role,
        provider=provider, default_provider=default_provider, appointment=appointment, read=read, pack=pack, anchor=anchor)


def denied(call, code=403):
    with pytest.raises(HTTPException) as error:
        call()
    assert error.value.status_code == code, error.value.detail


def test_reception_created_assignment_is_visible_without_broad_sales_rights_and_reads_never_write(plans):
    p = plans
    row = p.appointment()
    p.db.commit()
    before = p.db.connection().execute(select(IndustryRecord.id, IndustryRecord.data, IndustryRecord.updated_at)).all()
    counts = [p.db.query(model).count() for model in (Timesheet, TimesheetEntry, Attendance, AuditLog)]
    response = p.read()
    assert response['employee_id'] == p.employees['specialist'].id
    assert response['timezone'] == 'Asia/Kolkata'
    assert response['items'] == [{'appointment_id': row.id, 'revision': row.revision, 'service_id': 17,
        'service_name': 'Scheduled consultation', 'starts_at': START.isoformat(),
        'ends_at': (START + timedelta(hours=1)).isoformat(), 'planned_minutes': 60,
        'status': 'booked', 'blocks_availability': True, 'resources': [], 'employee_categories': []}]
    assert response['next_cursor'] is None
    assert not any(key in str(response) for key in ['PRIVATE', 'customer_name', 'payment_requests', 'actual_hours', 'paid_amount'])
    assert p.db.connection().execute(select(IndustryRecord.id, IndustryRecord.data, IndustryRecord.updated_at)).all() == before
    assert [p.db.query(model).count() for model in (Timesheet, TimesheetEntry, Attendance, AuditLog)] == counts
    assert not p.db.new and not p.db.dirty and not p.db.deleted


def test_own_schedule_excludes_coworker_and_foreign_branch_or_company(plans):
    p = plans
    own = p.appointment()
    p.appointment([p.provider(p.employees['coworker'])])
    p.appointment([p.default_provider], branch=p.branches[1].id)
    p.appointment([p.provider(p.employees['foreign'])], branch=p.branches[2].id)
    p.db.commit()
    assert [row['appointment_id'] for row in p.read()['items']] == [own.id]
    denied(lambda: p.read(p.employees['coworker']), 404)
    denied(lambda: p.read(p.employees['foreign']), 404)


def test_resource_aliases_deduplicate_and_legacy_user_link_is_verified(plans):
    p = plans
    alias = p.provider(user_only=True)
    row = p.appointment([p.default_provider, alias])
    room = p.provider(resource_type='room')
    p.appointment([room])
    p.db.commit()
    assert [item['appointment_id'] for item in p.read()['items']] == [row.id]


@pytest.mark.parametrize('status,blocking', [('booked', True), ('checked_in', True), ('in_service', True), ('completed', False), ('cancelled', False), ('no_show', False)])
def test_visit_status_does_not_convert_planned_duration_to_worked_hours(plans, status, blocking):
    p = plans
    p.appointment(status=status, minutes=45)
    p.db.commit()
    item = p.read(statuses=[status])['items'][0]
    assert item['planned_minutes'] == 45 and item['blocks_availability'] is blocking
    assert p.db.query(TimesheetEntry).count() == 0


def test_half_open_overlap_range_and_signed_pagination(plans):
    p = plans
    before = p.appointment(starts=START - timedelta(hours=1))
    rows = [p.appointment(starts=START, minutes=30) for _ in range(3)]
    p.appointment(starts=START + timedelta(hours=1))
    p.db.commit()
    kwargs = {'from_at': START, 'until_at': START + timedelta(hours=1), 'limit': 1}
    first = p.read(**kwargs)
    second = p.read(**kwargs, cursor=first['next_cursor'])
    third = p.read(**kwargs, cursor=second['next_cursor'])
    assert [page['items'][0]['appointment_id'] for page in [first, second, third]] == [row.id for row in rows]
    assert third['next_cursor'] is None and before.id not in [item['appointment_id'] for item in first['items']]
    denied(lambda: p.read(**kwargs, cursor=first['next_cursor'] + 'tampered'), 422)
    denied(lambda: p.read(from_at=START, until_at=START + timedelta(hours=2), cursor=first['next_cursor']), 422)


@pytest.mark.parametrize('changes', [{'limit': 0}, {'limit': 101}, {'limit': True}, {'from_at': START.replace(tzinfo=None)}, {'until_at': START - timedelta(days=2)}, {'until_at': START + timedelta(days=94)}, {'statuses': ['unknown']}, {'statuses': 'booked'}])
def test_invalid_or_unbounded_requests_fail(plans, changes):
    denied(lambda: plans.read(**changes), 422)


def test_native_permission_and_managed_team_scope_are_enforced(plans):
    p = plans
    coworker = p.employees['coworker']
    coworker.reporting_manager_id = p.employees['specialist'].id
    p.appointment([p.provider(coworker)])
    policy = AccessPolicy(company_id=1, user_id=p.users['specialist'].id, status='active', grants={'hrms': {
        'enabled': True, 'permissions': ['timesheet_view'], 'actions': ['view'], 'scope': 'team'}})
    p.db.add(policy); p.db.commit()
    assert len(p.read(coworker)['items']) == 1
    policy.grants = {'hrms': {'enabled': True, 'permissions': ['timesheet_view', 'hr_admin'], 'actions': ['view'], 'scope': 'own'}}
    p.db.commit()
    denied(lambda: p.read(coworker), 404)
    policy.status = 'suspended'; p.db.commit()
    denied(lambda: p.read())


def test_native_permission_cannot_be_replaced_by_an_employee_relationship(plans):
    plans.appointment(); plans.role.permissions = []; plans.db.commit()
    denied(lambda: plans.read())


def test_legacy_permission_revocation_is_not_hidden_by_cached_role_relationship(plans):
    from app.models.user import role_permissions
    p = plans
    p.appointment(); p.db.commit()
    assert p.users['specialist'].role.permissions
    assert p.read()['items']
    p.db.connection().execute(role_permissions.delete().where(role_permissions.c.role_id == p.role.id))
    p.db.commit()
    denied(lambda: p.read())


def test_disabled_source_module_fails_without_creating_actual_time(plans):
    from app.apps.business_os.models import BOSEnabledModule
    p = plans
    p.db.add(BOSEnabledModule(company_id=1, module_key='srm', display_name='Sales', enabled=False)); p.db.commit()
    denied(lambda: p.read())
    assert p.db.query(TimesheetEntry).count() == 0


def test_missing_source_schema_fails_safely_for_hrms_only(plans, monkeypatch):
    from app import module_registry
    installed = module_registry.is_app_enabled
    monkeypatch.setattr(module_registry, 'is_app_enabled', lambda key: False if key == 'srm' else installed(key))
    denied(lambda: plans.read(), 404)


def test_legacy_projection_excludes_anchored_appointment_and_aliased_provider(plans):
    p = plans
    legacy = p.appointment()
    context, _ = p.pack(state='draft')
    anchored_appointment = p.appointment(); p.anchor(anchored_appointment, context)
    anchored_provider = p.provider(); p.anchor(anchored_provider, context)
    p.appointment([anchored_provider])
    p.db.commit()
    assert [item['appointment_id'] for item in p.read()['items']] == [legacy.id]


def test_pack_projection_uses_canonical_anchor_table_for_provider_alias_and_rechecks_grant(plans):
    p = plans
    context, grant = p.pack()
    row = p.appointment(); p.anchor(row, context); p.anchor(p.default_provider, context)
    wrong_context, _ = p.pack('restaurant', 'chef')
    wrong_provider = p.provider(); p.anchor(wrong_provider, wrong_context)
    wrong = p.appointment([wrong_provider]); p.anchor(wrong, wrong_context)
    p.appointment()  # An unanchored legacy row must not be relabeled into the pack.
    p.db.commit()
    branch = branch_context(p.db, p.users['specialist'], 1, p.branches[0].id)
    scope = resolve_context(p.db, p.users['specialist'], branch, context.id)
    assert [item['appointment_id'] for item in p.read(scope=scope)['items']] == [row.id]
    grant.active = False; p.db.commit()
    denied(lambda: p.read(scope=scope))


def test_pack_master_availability_is_explicit_and_chef_role_has_no_appointment_access(plans):
    p = plans
    context, _ = p.pack()
    row = p.appointment(); p.anchor(row, context)
    p.db.add(PackMasterAvailability(company_id=1, branch_id=p.branches[0].id, context_id=context.id,
        resource_table='srm_industry_records', resource_key=str(p.default_provider.id), active=True))
    chef_context, _ = p.pack('restaurant', 'chef')
    p.db.commit()
    branch = branch_context(p.db, p.users['specialist'], 1, p.branches[0].id)
    scope = resolve_context(p.db, p.users['specialist'], branch, context.id)
    assert [item['appointment_id'] for item in p.read(scope=scope)['items']] == [row.id]
    chef = resolve_context(p.db, p.users['specialist'], branch, chef_context.id)
    denied(lambda: p.read(scope=chef))


def test_booking_room_details_exclude_foreign_branch_and_context_resources(plans):
    p = plans
    room = p.provider(resource_type='room'); room.title = 'Room A'
    foreign = p.provider(branch=p.branches[1].id, resource_type='room'); foreign.title = 'HIDDEN FOREIGN ROOM'
    anchored = p.provider(resource_type='equipment'); anchored.title = 'HIDDEN PACK EQUIPMENT'
    context, _ = p.pack()
    other_context, _ = p.pack('salon', 'stylist')
    p.anchor(anchored, other_context)
    p.anchor(p.default_provider, context); p.anchor(room, context)
    p.employees['specialist'].work_categories = ['Consultant', 'Senior']
    booking = p.appointment([p.default_provider, room, foreign, anchored]); p.anchor(booking, context)
    p.db.commit()
    branch = branch_context(p.db, p.users['specialist'], 1, p.branches[0].id)
    scope = resolve_context(p.db, p.users['specialist'], branch, context.id)
    item = p.read(scope=scope)['items'][0]
    assert item['resources'] == [{'id': room.id, 'name': 'Room A', 'resource_type': 'room'}]
    assert item['employee_categories'] == ['Consultant', 'Senior']
    assert 'HIDDEN' not in str(item)
