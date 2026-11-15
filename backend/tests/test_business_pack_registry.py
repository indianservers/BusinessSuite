"""Pure definitions only: registry tests require no app, DB or activation."""
from dataclasses import FrozenInstanceError, replace
import pytest

from app.business_packs import (
    PACKS, PACK_ALIASES, NATIVE_MODULE_KEYS, FeatureState, PackManifest,
    PackRegistryError, PackRole, get_pack, get_role, list_packs, resolve_pack_key,
)


KEYS = {'retail', 'construction', 'hospital', 'pharma', 'accounting_firm', 'salon', 'restaurant'}


def test_registry_has_exactly_seven_unique_canonical_manifests():
    assert set(PACKS) == KEYS
    assert len(list_packs()) == 7
    assert len({pack.key for pack in list_packs()}) == 7
    assert all(get_pack(pack.key) is pack for pack in list_packs())


@pytest.mark.parametrize('key, duties', [
    ('retail', {'checkout.create', 'stock.receive', 'appointments.schedule', 'payments.record'}),
    ('construction', {'boq.approve', 'billing.prepare', 'appointments.schedule', 'payments.record'}),
    ('hospital', {'providers.manage', 'appointments.schedule', 'visits.complete', 'payments.record'}),
    ('pharma', {'batches.quarantine', 'checkout.create', 'appointments.schedule', 'payments.record'}),
    ('accounting_firm', {'work.prepare', 'work.review', 'billing.prepare', 'payments.record'}),
    ('salon', {'providers.manage', 'appointments.schedule', 'visits.complete', 'payments.record'}),
    ('restaurant', {'kitchen.prepare', 'orders.create', 'reservations.schedule', 'payments.record'}),
])
def test_explicit_business_owner_covers_only_its_pack_operational_duties(key, duties):
    owner = get_role(key, 'business_owner')
    assert {key + '.' + duty for duty in duties} <= owner.capabilities
    assert owner.grants_company_admin is False
    assert all(capability.startswith(key + '.') for capability in owner.capabilities)
    assert not any(capability.startswith(other + '.') for other in KEYS - {key}
                   for capability in owner.capabilities)


@pytest.mark.parametrize('alias,canonical', [
    ('saloon', 'salon'), ('pharmacy', 'pharma'), ('accounts_company', 'accounting_firm'),
])
def test_only_explicit_pack_aliases_resolve(alias, canonical):
    assert resolve_pack_key(alias) == canonical
    assert get_pack(alias) is get_pack(canonical)


@pytest.mark.parametrize('key', [
    None, True, 1, [], {}, '', ' hospital', 'hospital ', 'Hospital', 'HOSPITAL',
    'hospital/restaurant', 'hospital.doctor', '../hospital', 'hospitаl',
    'consulting', 'consultancy', 'accounts', 'pharmaceutical_manufacturing',
])
def test_unsupported_or_malformed_pack_names_fail_closed(key):
    with pytest.raises(PackRegistryError): get_pack(key)


def test_nested_registry_values_are_immutable():
    pack = get_pack('hospital')
    role = get_role('hospital', 'doctor')
    with pytest.raises(TypeError): PACKS['hospital'] = get_pack('restaurant')
    with pytest.raises(TypeError): PACK_ALIASES['consulting'] = 'accounting_firm'
    with pytest.raises(FrozenInstanceError): pack.key = 'restaurant'
    with pytest.raises(FrozenInstanceError): role.pack_key = 'restaurant'
    with pytest.raises(FrozenInstanceError): pack.workflows[0].state = FeatureState.PLANNED
    assert isinstance(pack.roles, tuple) and isinstance(pack.workflows, tuple)
    assert isinstance(role.capabilities, frozenset)
    with pytest.raises(AttributeError): role.capabilities.add('restaurant.kitchen.view')


def test_dependencies_use_native_modules_without_implicitly_granting_them():
    expected = {
        'retail': {'srm'}, 'pharma': {'srm'},
        'hospital': {'hrms', 'srm'}, 'salon': {'hrms', 'srm'}, 'restaurant': {'hrms', 'srm'},
        'construction': {'crm', 'project_management', 'srm'},
        'accounting_firm': {'crm', 'project_management', 'srm'},
    }
    assert NATIVE_MODULE_KEYS == {'hrms', 'crm', 'project_management', 'srm', 'fam'}
    for pack in list_packs():
        assert pack.required_modules == expected[pack.key]
        assert pack.required_modules | pack.optional_modules <= NATIVE_MODULE_KEYS
        assert not pack.required_modules & pack.optional_modules


@pytest.mark.parametrize('pack_key,role_key', [
    ('hospital', 'chef'), ('hospital', 'site_engineer'),
    ('restaurant', 'doctor'), ('restaurant', 'site_engineer'),
    ('construction', 'doctor'), ('construction', 'chef'),
    ('salon', 'doctor'), ('pharma', 'chef'), ('accounting_firm', 'doctor'),
])
def test_specialist_roles_cannot_be_looked_up_through_another_pack(pack_key, role_key):
    with pytest.raises(PackRegistryError): get_role(pack_key, role_key)


@pytest.mark.parametrize('role', [None, True, 1, {}, '', 'Doctor', ' doctor', 'doctor ', 'hospital.doctor', '*', '../doctor'])
def test_malformed_or_unregistered_role_names_fail_closed(role):
    with pytest.raises(PackRegistryError): get_role('hospital', role)


def test_doctor_chef_and_engineer_have_explicit_distinct_allow_lists():
    assert get_role('hospital', 'doctor').capabilities == {
        'hospital.appointments.view', 'hospital.visits.start', 'hospital.visits.complete',
    }
    assert get_role('restaurant', 'chef').capabilities == {
        'restaurant.kitchen.view', 'restaurant.kitchen.prepare', 'restaurant.kitchen.ready',
    }
    assert get_role('construction', 'site_engineer').capabilities == {
        'construction.sites.view', 'construction.diary.record',
        'construction.measurements.prepare', 'construction.materials.request',
    }
    for pack in list_packs():
        for role in pack.roles:
            assert role.pack_key == pack.key
            assert all(capability.startswith(pack.key + '.') for capability in role.capabilities)
            assert '*' not in ''.join(role.capabilities)


def test_shared_services_do_not_turn_into_unqualified_cross_pack_grants():
    assert 'appointments' in get_pack('hospital').shared_services
    assert 'appointments' in get_pack('salon').shared_services
    assert 'appointments' in get_pack('restaurant').shared_services
    assert 'pos' in get_pack('retail').shared_services & get_pack('pharma').shared_services & get_pack('restaurant').shared_services
    assert get_role('hospital', 'receptionist').capabilities.isdisjoint(get_role('salon', 'receptionist').capabilities)
    assert all(capability.count('.') >= 2 for pack in list_packs() for capability in pack.capabilities)


def test_all_billing_packs_have_an_explicit_role_that_can_collect_payment():
    for pack in list_packs():
        assert any(pack.key + '.payments.record' in role.capabilities and
                   any(pack.key + '.' + action in role.capabilities
                       for action in ('billing.prepare', 'checkout.create'))
                   for role in pack.roles), pack.key
    for pack_key, role_key in [('construction', 'billing_officer'),
                                ('accounting_firm', 'billing_officer'), ('pharma', 'cashier')]:
        role = get_role(pack_key, role_key)
        assert not role.grants_company_admin
        assert not any('.settings.' in cap or '.providers.' in cap or '.kitchen.' in cap
                       or '.visits.' in cap for cap in role.capabilities)


def test_all_businesses_can_explicitly_assign_a_common_service_desk():
    for pack in list_packs():
        role = get_role(pack.key, 'service_desk')
        assert 'appointments' in pack.shared_services
        assert role.capabilities == {pack.key + '.' + action for action in (
            'customers.register', 'appointments.view', 'appointments.schedule', 'appointments.check_in',
            'billing.view', 'billing.prepare', 'payments.record')}
        assert not role.grants_company_admin
        assert not any('.visits.' in capability or '.settings.' in capability
                       or '.providers.' in capability for capability in role.capabilities)
    assert 'hospital.payments.record' not in get_role('hospital', 'doctor').capabilities
    assert 'restaurant.appointments.view' not in get_role('restaurant', 'chef').capabilities
    assert 'construction.appointments.view' not in get_role('construction', 'site_engineer').capabilities


def test_all_packs_have_an_explicit_register_closing_supervisor():
    for pack in list_packs():
        assert any(pack.key + '.sessions.close' in role.capabilities for role in pack.roles), pack.key
        assert pack.key + '.sessions.close' not in get_role(pack.key, 'service_desk').capabilities


def test_pack_managers_never_grant_company_or_platform_administration():
    for pack in list_packs():
        for role in pack.roles:
            assert role.grants_company_admin is False
            assert role.key not in {'company_admin', 'super_admin', 'platform_admin'}
            assert not any('company_admin' in capability or 'platform_admin' in capability for capability in role.capabilities)
    with pytest.raises(TypeError):
        PackRole('hospital', 'doctor', 'Doctor', frozenset({'hospital.visits.start'}), grants_company_admin=True)


def test_scaffolding_reports_missing_activation_and_isolation_honestly():
    for pack in list_packs():
        assert pack.version == 1
        assert pack.foundation_state == 'registry_only'
        assert pack.activation_ready is False and pack.isolation_ready is False and pack.ui_integrated is False
    assert next(workflow for workflow in get_pack('pharma').workflows if workflow.key == 'batch_expiry').state is FeatureState.PLANNED
    assert next(workflow for workflow in get_pack('restaurant').workflows if workflow.key == 'kitchen').state is FeatureState.PLANNED
    assert 'Clinical notes' in get_pack('hospital').exclusions[0]
    assert all(workflow.key not in {'prescriptions', 'admissions', 'labs'} for workflow in get_pack('hospital').workflows)


def test_invalid_code_owned_definitions_are_rejected():
    hospital = get_pack('hospital')
    with pytest.raises(PackRegistryError): replace(hospital, required_modules=frozenset({'hospital'}))
    with pytest.raises(PackRegistryError): replace(hospital, optional_modules=frozenset({'srm'}))
    with pytest.raises(PackRegistryError): replace(hospital, roles=(get_role('restaurant', 'chef'),))
    with pytest.raises(PackRegistryError): replace(hospital, roles=hospital.roles + (hospital.roles[0],))
    with pytest.raises(PackRegistryError): replace(hospital, roles=list(hospital.roles))
    with pytest.raises(PackRegistryError): replace(hospital, workflows=list(hospital.workflows))
    with pytest.raises(PackRegistryError): replace(hospital, exclusions=list(hospital.exclusions))
    for capability in ['restaurant.kitchen.view', 'hospital.*', 'hospital.company_admin.grant']:
        with pytest.raises(PackRegistryError): PackRole('hospital', 'doctor', 'Doctor', frozenset({capability}))
