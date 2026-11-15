"""Modifier constraints carry quantities and catalog identities, never prices."""
import pytest
from pydantic import ValidationError
from app.business_packs.restaurant.modifiers import ModifierCatalog, ModifierSelection, selections


def catalog(**changes):
    group = dict(key='extras', label='Extras', min_choices=1, max_choices=3,
        options=[dict(product_id=2, max_quantity=2), dict(product_id=3)])
    group.update(changes)
    return ModifierCatalog(groups=[group])


def test_additive_choice_quantities_are_per_base_item():
    result = selections(catalog(), [ModifierSelection(group='extras', product_id=2, quantity=2)], base_product_id=1)
    assert [(g.key, o.product_id, q) for g,o,q in result] == [('extras', 2, 2)]


@pytest.mark.parametrize('selected', [[],
    [dict(group='unknown', product_id=2)],
    [dict(group='extras', product_id=99)],
    [dict(group='extras', product_id=2, quantity=3)],
    [dict(group='extras', product_id=2)] * 2,
    [dict(group='extras', product_id=2, quantity=2), dict(group='extras', product_id=3, quantity=2)]])
def test_missing_unknown_duplicate_and_excess_quantities_fail(selected):
    with pytest.raises(ValueError):
        selections(catalog(), [ModifierSelection(**v) for v in selected], base_product_id=1)


@pytest.mark.parametrize('change', [dict(min_choices=4), dict(max_choices=4),
    dict(options=[dict(product_id=2)]*2), dict(label=' Extras'), dict(label='X\nY'),
    dict(min_choices=True), dict(options=[dict(product_id=True)])])
def test_invalid_native_metadata_definitions_fail_closed(change):
    with pytest.raises(ValidationError):
        catalog(**change)


@pytest.mark.parametrize('override', [dict(price='0'), dict(tax='0'), dict(warehouse_id=2),
    dict(customer_id=2), dict(quantity=True), dict(quantity='1'), dict(quantity=0)])
def test_selection_cannot_override_native_financial_or_identity_fields(override):
    with pytest.raises(ValidationError):
        ModifierSelection(**(dict(group='extras', product_id=2) | override))


def test_self_reference_and_duplicate_group_are_rejected():
    with pytest.raises(ValueError):
        selections(catalog(), [ModifierSelection(group='extras', product_id=2)], base_product_id=2)
    with pytest.raises(ValidationError):
        ModifierCatalog(groups=catalog().groups * 2)
