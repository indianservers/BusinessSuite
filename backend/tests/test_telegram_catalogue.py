from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.access.service import background_scope
from app.apps.power_apps import telegram_catalogue as catalogue
from app.apps.power_apps.telegram_experience import ExperienceConfiguration
from app.apps.power_apps.runtime import now
from app.apps.srm.models import SRMProduct
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot
from tests.test_telegram_booking_flow import appointment_setup


def test_natural_dates_and_after_time():
    today = date(2026, 11, 16)
    assert catalogue.requested_day('tomorrow', today) == date(2026, 11, 17)
    assert catalogue.requested_day('day after tomorrow', today) == date(2026, 11, 18)
    assert catalogue.requested_day('friday', today) == date(2026, 11, 20)
    assert catalogue.earliest_hour('after 4 pm') == 16 * 60
    assert catalogue.earliest_hour('after 12:30 am') == 30
    with pytest.raises(HTTPException):
        catalogue.requested_day('2026-02-30', today)


def test_catalogue_ids_are_explicit_unique_positive():
    for values in ([1, 1], [0], [-1]):
        with pytest.raises(ValidationError):
            ExperienceConfiguration(catalogue_product_ids=values)


def test_public_catalogue_reads_live_price_and_native_slots_without_customer_identity(client, db, actors, bot, appointment_setup):
    resource, trigger, owner, branch, _ = bot
    _, service, _, _ = appointment_setup
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        private = SRMProduct(organization_id=1, sku='PRIVATE-SKU', item_name='Unpublished internal product', sales_rate=999)
        public = SRMProduct(organization_id=1, sku='PUBLIC-SKU', item_name='Published shampoo', sales_rate=120, purchase_rate=83, current_quantity=47)
        db.add_all([private, public]); db.flush()
        trigger.config = {**trigger.config, 'experience': {**trigger.config['experience'], 'catalogue_product_ids': [public.id]}}
        db.commit()
    text = catalogue.answer(db, resource, trigger, owner, 'Show products and services')
    assert 'Consultation' in text and '500' in text and 'Published shampoo' in text
    assert 'Unpublished' not in text and '83' not in text and '47' not in text and 'PRIVATE-SKU' not in text
    result = catalogue.answer(db, resource, trigger, owner, 'Consultation availability tomorrow after 4 pm')
    assert (now() + timedelta(days=1)).date().isoformat() in result
    assert '16:00' in result and '09:00' not in result
    assert 'UTC' in result and 'no appointment has been created' in result
    with background_scope(db, owner, 'power_apps', 'create', branch_id=branch.id):
        service.sales_rate = 650
        db.commit()
    assert '650' in catalogue.answer(db, resource, trigger, owner, 'Consultation price')
    assert catalogue.answer(db, resource, trigger, owner, 'hello') is None


def test_availability_excludes_native_booked_slot(client, db, actors, bot, appointment_setup):
    resource, trigger, owner, _, _ = bot
    buyer, service, resources, headers = appointment_setup
    day = (now() + timedelta(days=1)).date().isoformat()
    response = client.post('/api/v1/srm/industry/appointments', headers=headers, json={
        'request_id': str(uuid4()), 'title': 'Private customer appointment title',
        'customer_id': buyer.id, 'service_id': service.id, 'resource_ids': resources,
        'starts_at': day + 'T16:00:00+00:00', 'duration_minutes': 30})
    assert response.status_code == 201, response.text
    result = catalogue.answer(db, resource, trigger, owner, 'Consultation available tomorrow after 4 pm')
    assert '16:00' not in result and '16:30' in result
    assert 'Private customer appointment' not in result and buyer.name not in result
