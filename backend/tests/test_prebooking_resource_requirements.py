from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.apps.srm.models import SRMProduct, SRMInvoice, SRMSalesOrder, SRMReceipt
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.industry_api import appointment_operation, appointment_detail, reschedule_operation, Reschedule
from datetime import timedelta
from app.apps.srm.service_checkout import save_policy, checkout
from app.apps.srm.service_checkout_schemas import PolicyInput
from app.apps.srm.service_checkout_options import service_options, scheduling_availability, validate_prebooking
from tests.test_prebooking_shared_selection import selection
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


def configure(db, user, product_id, booking, required):
    return save_policy(PolicyInput(service_product_id=product_id, expected_revision=booking.expected_policy_revision,
        default_duration_minutes=30, min_duration_minutes=5, max_duration_minutes=120,
        required_resource_types=required), db, user)


def room(db, user, branch):
    row = IndustryRecord(organization_id=1, branch_id=branch, kind='resource', title='Required room', status='active',
        request_id=str(uuid4()), created_by=user.id, data={'resource_type':'room','timezone':'UTC',
            'weekdays':list(range(7)),'opens':'00:00:00','closes':'23:59:00'})
    db.add(row)
    db.commit()
    return row


def test_resource_rules_are_per_policy_preserved_and_revisioned_once(db, scenario):
    user, branch, source, basket = scenario
    booking = basket(False).lines[1].booking
    with native_writer(db,user,branch):
        product = db.get(SRMProduct,source[2][1])
        product.metadata_json = {**(product.metadata_json or {}),'service_resource_requirements':{'999999':['equipment']}}
        db.commit()
        saved = configure(db,user,product.id,booking,['room'])
        assert saved['revision'] == booking.expected_policy_revision + 1
        assert product.metadata_json['service_resource_requirements']['999999'] == ['equipment']
        options = service_options(db,user,product.id)
        assert options['policy']['required_resource_types'] == ['room']
        assert options['can_configure'] is True
        # An older POS editor which omits the new field must preserve requirements.
        save_policy(PolicyInput(service_product_id=product.id,expected_revision=saved['revision'],
            default_duration_minutes=30,min_duration_minutes=5,max_duration_minutes=120),db,user)
        assert service_options(db,user,product.id)['policy']['required_resource_types'] == ['room']
        policy = service_options(db,user,product.id)['policy']
        changed = save_policy(PolicyInput(service_product_id=product.id,expected_revision=policy['revision'],
            default_duration_minutes=45,min_duration_minutes=15,max_duration_minutes=120,
            required_resource_types=['room','equipment']),db,user)
        assert changed['revision'] == policy['revision'] + 1
        assert service_options(db,user,product.id)['policy']['required_resource_types'] == ['equipment','room']
        unconfigured = SRMProduct(organization_id=1,sku='UNCONFIGURED-'+uuid4().hex,item_name='Unconfigured service',
            product_type='service',sales_rate=100,active=True,track_inventory=False)
        db.add(unconfigured)
        db.commit()
        unconfigured_options = service_options(db,user,unconfigured.id)
        assert unconfigured_options['policy'] is None
        assert unconfigured_options['can_configure'] is True


def test_missing_resources_block_advisory_prebooking_and_final_checkout(db, scenario):
    user, branch, source, basket = scenario
    draft = selection(basket)
    with native_writer(db,user,branch):
        saved = configure(db,user,draft.service_id,draft.booking,['room'])
        draft.booking.expected_policy_revision = saved['revision']
        resource = room(db,user,branch)
        state = scheduling_availability(db,user,draft.service_id,draft.booking.eligibility_id,
            draft.starts_at.date(),draft.duration_minutes,starts_at=draft.starts_at)
        assert state['selection_available'] is False
        assert state['missing_resource_types'] == ['room']
        assert state['slots'] == []
        with pytest.raises(HTTPException):
            validate_prebooking(db,user,draft)
        data = basket(False)
        for line in data.lines:
            if line.booking:
                line.booking.expected_policy_revision = saved['revision']
        with pytest.raises(HTTPException,match='Required service resources missing'):
            checkout(data,db,user)
        assert [db.query(model).count() for model in (SRMInvoice,SRMSalesOrder,SRMReceipt)] == [0,0,0]
        draft.booking.additional_resource_ids = [resource.id]
        draft.resource_ids.append(resource.id)
        validate_prebooking(db,user,draft)
        created = appointment_operation(draft,db,user)
        assert created['status'] == 'booked'
        assert appointment_detail(created['id'],db,user)['id'] == created['id']
        assert [db.query(model).count() for model in (SRMInvoice,SRMSalesOrder,SRMReceipt)] == [0,0,0]
        legacy = draft.model_copy(deep=True)
        legacy.request_id = uuid4()
        legacy.booking = None
        legacy.starts_at += timedelta(hours=3)
        legacy.resource_ids = [draft.booking.provider_resource_id]
        with pytest.raises(HTTPException,match='Required service resources missing'):
            appointment_operation(legacy,db,user)
        with pytest.raises(HTTPException,match='Required service resources missing'):
            reschedule_operation(created['id'],Reschedule(expected_revision=created['revision'],
                starts_at=draft.starts_at+timedelta(hours=2),duration_minutes=30,
                resource_ids=[draft.booking.provider_resource_id]),db,user)
        assert appointment_detail(created['id'],db,user)['revision'] == created['revision']


def test_checkout_accepts_required_resource_and_rejects_duplicate_type_rules(db, scenario):
    user,branch,source,basket=scenario
    data=basket(False)
    with native_writer(db,user,branch):
        saved=configure(db,user,source[2][1],data.lines[1].booking,['room'])
        resource=room(db,user,branch)
        for line in data.lines:
            if line.booking:
                line.booking.expected_policy_revision=saved['revision']
                line.booking.additional_resource_ids=[resource.id]
        assert checkout(data,db,user)['state'] == 'committed'
    with pytest.raises(ValidationError):
        PolicyInput(service_product_id=1,default_duration_minutes=30,min_duration_minutes=5,max_duration_minutes=120,
            required_resource_types=['room','room'])
