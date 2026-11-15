from dataclasses import replace
import pytest
from fastapi import HTTPException
from tests.test_business_pack_access import packs, denied
from app.business_packs.access import resolve_context
from app.business_packs.operations import require, capabilities, for_record_read, for_transition
from app.apps.srm import industry_api
from tests.test_service_checkout import scenario, catalog, directory_identity, enable_pack
from tests.test_srm_native_transaction_operations import native_writer


@pytest.fixture
def operation(packs):
    p = packs
    p.db.info['business_pack_scope'] = resolve_context(p.db, p.users['doctor'], p.ctx())
    return p


def test_doctor_can_only_read_and_run_visit_actions(operation):
    p = operation; actor = p.users['doctor']
    for_record_read(p.db, actor, 'appointment')
    for_transition(p.db, actor, 'appointment', 'in_service')
    for_transition(p.db, actor, 'appointment', 'completed')
    for status in ('checked_in', 'cancelled', 'no_show', 'invalid'):
        denied(lambda: for_transition(p.db, actor, 'appointment', status))
    for kind in ('resource', 'boq', 'measurement', 'site_diary', 'subcontract', 'material_issue'):
        denied(lambda: for_record_read(p.db, actor, kind))
    denied(lambda: require(p.db, actor, 'payments.record'))
    denied(lambda: require(p.db, actor, 'appointments.schedule'))


def test_chef_cannot_read_or_operate_appointments(packs):
    p = packs; actor = p.users['chef']
    p.db.info['business_pack_scope'] = resolve_context(p.db, actor, p.ctx(), p.contexts['chef'].id)
    denied(lambda: for_record_read(p.db, actor, 'appointment'))
    denied(lambda: for_transition(p.db, actor, 'appointment', 'in_service'))
    denied(lambda: require(p.db, actor, 'billing.prepare'))
    require(p.db, actor, 'kitchen.prepare')


def test_engineer_can_prepare_only_its_construction_actions(packs):
    p = packs; actor = p.users['builder']
    p.db.info['business_pack_scope'] = resolve_context(p.db, actor, p.ctx('b'))
    for_record_read(p.db, actor, 'boq')
    require(p.db, actor, 'diary.record')
    denied(lambda: for_record_read(p.db, actor, 'appointment'))
    denied(lambda: for_transition(p.db, actor, 'measurement', 'approved'))
    denied(lambda: require(p.db, actor, 'payments.record'))


def test_actor_scope_forgery_and_revocation_are_rejected(operation):
    p = operation
    denied(lambda: capabilities(p.db, p.users['chef']))
    p.db.info['business_pack_scope'] = replace(p.db.info['business_pack_scope'], capabilities=frozenset({'hospital.payments.record'}))
    denied(lambda: require(p.db, p.users['doctor'], 'payments.record'))
    p.db.info['business_pack_scope'] = resolve_context(p.db, p.users['doctor'], p.ctx())
    p.grants['doctor'].active = False; p.db.commit()
    denied(lambda: for_record_read(p.db, p.users['doctor'], 'appointment'))


def test_native_industry_entrypoints_reject_other_pack_actions_before_writes(operation):
    p = operation; actor = p.users['doctor']
    # Native action authorization remains mandatory; the pack guard can reject
    # a forbidden operation even before resolving a submitted record/project ID.
    with pytest.raises(HTTPException) as error:
        industry_api.invoice(999999, None, p.db, actor)
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        industry_api.project_options('', 0, p.db, actor)
    assert error.value.status_code == 403


def test_genuinely_legacy_calls_keep_native_domain_validation(packs):
    p = packs
    assert capabilities(p.db, p.users['doctor']) is None
    require(p.db, p.users['doctor'], 'payments.record')


def test_native_broad_permission_metadata_is_intersected_with_doctor_role(db, scenario):
    user, branch, source, _ = scenario
    enable_pack(db, user, branch, source, role='doctor')
    with native_writer(db, user, branch):
        db.info['business_pack_scope'] = resolve_context(db, user, db.info['branch_context'])
        try:
            data = industry_api.capabilities(None, db, user)
            assert data['collect'] is data['billing'] is data['invoice'] is data['approve_invoice'] is False
            assert data['manage'] is data['self_approve'] is False
            assert data['appointment_actions'] == ['start', 'complete']
        finally:
            db.info.pop('business_pack_scope', None)
