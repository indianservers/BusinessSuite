"""Keep kitchen commands separate from financial and identity authority."""
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.business_packs.restaurant.schemas import KitchenSubmit, TableCreate, TicketTransition, VoidOrder


def ticket(**changes):
    return dict(request_key=str(uuid4()), service_order_id=4, expected_revision=1,
                lines=[dict(sales_order_line_id=8, quantity='1.25')], **changes)


@pytest.mark.parametrize('injected', [
    {'company_id': 99}, {'context_id': 99}, {'created_by': 99},
    {'total': '1'}, {'payments': []}, {'customer_id': 99}, {'status': 'ready'},
])
def test_kitchen_cannot_supply_identity_money_or_state(injected):
    with pytest.raises(ValidationError):
        KitchenSubmit.model_validate(ticket(**injected))


@pytest.mark.parametrize('quantity', ['NaN', 'Infinity', '-1', '0', '0.001'])
def test_invalid_source_quantity_is_rejected(quantity):
    data = ticket()
    data['lines'][0]['quantity'] = quantity
    with pytest.raises(ValidationError):
        KitchenSubmit.model_validate(data)


def test_duplicate_sources_cannot_hide_combined_overissue():
    data = ticket()
    data['lines'] *= 2
    with pytest.raises(ValidationError):
        KitchenSubmit.model_validate(data)


@pytest.mark.parametrize('revision', [True, '1', 0, -1])
def test_transition_requires_exact_positive_revision(revision):
    with pytest.raises(ValidationError):
        TicketTransition(request_key=uuid4(), expected_revision=revision)


@pytest.mark.parametrize('name', ['   ', 'A\nB', 'A\x7fB'])
def test_invalid_table_labels_are_rejected(name):
    with pytest.raises(ValidationError):
        TableCreate(request_key=uuid4(), name=name, capacity=4)


def test_valid_kitchen_instructions_and_table_label_are_preserved():
    data = ticket()
    data['lines'][0]['instruction'] = 'No peanuts; allergy'
    assert KitchenSubmit.model_validate(data).lines[0].instruction == 'No peanuts; allergy'
    assert TableCreate(request_key=uuid4(), name=' Terrace 2 ', capacity=4).name == 'Terrace 2'
    with pytest.raises(ValidationError):
        VoidOrder(request_key=uuid4(), expected_revision=1, reason='   ')
