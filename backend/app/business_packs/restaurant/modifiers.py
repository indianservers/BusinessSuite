"""Strict additive menu choices backed by existing native catalog products.

This module does not grant catalog access or assign prices. Callers must resolve
all selected products through the normal Restaurant native catalog boundary.
"""
from pydantic import Field, StrictInt, field_validator, model_validator
from .schemas import StrictInput, ID, ModifierSelection


class ModifierOption(StrictInput):
    product_id: ID
    max_quantity: StrictInt = Field(default=1, ge=1, le=20)


class ModifierGroup(StrictInput):
    key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    label: str = Field(min_length=1, max_length=80)
    min_choices: StrictInt = Field(default=0, ge=0, le=20)
    max_choices: StrictInt = Field(default=1, ge=1, le=20)
    options: list[ModifierOption] = Field(min_length=1, max_length=20)

    @field_validator('label')
    @classmethod
    def printable(cls, value):
        if value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('Use a printable modifier group label')
        return value

    @model_validator(mode='after')
    def limits(self):
        if self.min_choices > self.max_choices or self.max_choices > sum(o.max_quantity for o in self.options):
            raise ValueError('Modifier group limits exceed the available choices')
        if len({o.product_id for o in self.options}) != len(self.options):
            raise ValueError('Each modifier product must occur once in its group')
        return self


class ModifierCatalog(StrictInput):
    version: StrictInt = Field(default=1, ge=1, le=1)
    groups: list[ModifierGroup] = Field(default_factory=list, max_length=10)

    @model_validator(mode='after')
    def unique_groups(self):
        if len({g.key for g in self.groups}) != len(self.groups):
            raise ValueError('Modifier group keys must be unique')
        if sum(len(group.options) for group in self.groups) > 40:
            raise ValueError('A menu product supports at most 40 modifier options')
        return self


def selections(catalog, selected, *, base_product_id):
    """Return exact approved option quantities per one base item, no prices."""
    groups = {group.key: group for group in catalog.groups}
    seen, counts, result = set(), {}, []
    for item in selected:
        pair = (item.group, item.product_id)
        group = groups.get(item.group)
        option = next((o for o in group.options if o.product_id == item.product_id), None) if group else None
        if pair in seen or option is None or item.product_id == base_product_id or item.quantity > option.max_quantity:
            raise ValueError('The selected modifier is not an available unique option')
        seen.add(pair)
        counts[item.group] = counts.get(item.group, 0) + item.quantity
        result.append((group, option, item.quantity))
    for group in catalog.groups:
        if not group.min_choices <= counts.get(group.key, 0) <= group.max_choices:
            raise ValueError('The selected modifier quantities do not satisfy the menu group')
    return result


def catalog(product):
    """Use only the native product's explicitly namespaced definition."""
    raw = (product.metadata_json or {}).get('restaurant_modifiers')
    return ModifierCatalog.model_validate(raw if raw is not None else {})


# The exact new native lines can be read before their immutable command exists,
# solely while producing that command in this same transaction/session.
from contextlib import contextmanager
from weakref import WeakKeyDictionary
from copy import deepcopy
from sqlalchemy import select

_issuances = WeakKeyDictionary()


@contextmanager
def issuance(db, actor, scope, epoch, order, lines, data):
    from .tabs import _native_epoch
    from .service import authority, fail
    if db in _issuances or authority(db, actor, 'orders.create', write=True) is not scope or _native_epoch(db, actor, scope) != epoch:
        fail('Modifier issuance authority changed')
    from sqlalchemy import inspect
    from app.apps.srm.models import SRMSalesOrderLine
    for row in lines:
        state = inspect(row)
        marker = (row.metadata_json or {}).get('restaurant_modifier')
        if (type(row) is not SRMSalesOrderLine or state.session is not db or not state.persistent or
                row.sales_order_id != order.sales_order_id):
            fail('Modifier issuance requires actual lines of this same native order')
        if marker is not None and (marker.get('request_key') != str(data.request_key) or
                type(marker.get('base_slot')) is not int or not 0 <= marker['base_slot'] < len(data.lines) or
                marker.get('base_product_id') != data.lines[marker['base_slot']].product_id):
            fail('Modifier issuance differs from its exact command source')
    proof = [{'line_id': row.id, 'modifier': deepcopy((row.metadata_json or {}).get('restaurant_modifier'))}
             for row in lines if (row.metadata_json or {}).get('restaurant_modifier') is not None]
    lease = (actor, scope, epoch, order.id, deepcopy(proof))
    _issuances[db] = lease
    try:
        yield proof
    finally:
        _issuances.pop(db, None)


def validate_source(db, actor, scope, order, lines):
    from .models import RestaurantCommand
    from .service import fail
    from .tabs import _native_epoch
    command = RestaurantCommand.__table__
    results = db.connection().execute(select(command.c.result).where(
        command.c.organization_id == scope.company_id, command.c.branch_id == scope.branch_id,
        command.c.pack_context_id == scope.context_id, command.c.service_order_id == order.id,
        command.c.action.in_(('tab.create', 'tab.add')))).scalars().all()
    proofs = [entry for result in results for entry in result.get('modifier_sources', [])]
    lease = _issuances.get(db)
    if lease is not None:
        owner, installed, epoch, ident, pending = lease
        if owner is not actor or installed is not scope or ident != order.id or _native_epoch(db, actor, scope) != epoch:
            fail('Modifier source certificate changed')
        proofs += pending
    by_id = {}
    for entry in proofs:
        if (not isinstance(entry, dict) or set(entry) != {'line_id', 'modifier'} or
                type(entry['line_id']) is not int or entry['line_id'] in by_id or not isinstance(entry['modifier'], dict)):
            fail('Modifier command provenance is invalid', 409)
        by_id[entry['line_id']] = entry['modifier']
    actual = {row['id']: (row['metadata_json'] or {}).get('restaurant_modifier') for row in lines}
    if any(ident not in actual for ident in by_id) or any(value != by_id.get(ident) for ident, value in actual.items()):
        fail('Issued modifier source differs from its immutable command', 409)


def validate_catalog(db, actor, scope, base_product_id, currency, definition):
    """Called only after the canonical catalog's native write authorization.

    Returns normalized definition primitives. This helper confers no mutation
    authority, does not enroll/adopt a master, and never stores option prices.
    """
    from .tabs import _product
    from .service import fail
    if scope.pack_key != 'restaurant' or db.info.get('business_pack_scope') is not scope:
        fail('Modifier configuration requires the exact Restaurant catalog context')
    value = ModifierCatalog.model_validate(definition)
    for group in value.groups:
        for option in group.options:
            if option.product_id == base_product_id:
                fail('A modifier option cannot be its own menu product', 422)
            product, _, _ = _product(db, actor, scope, option.product_id, currency)
            if catalog(product).groups:
                fail('Nested modifier menus are unsupported', 422)
    return value.model_dump(mode='json')


def menu_groups(db, actor, scope, product, currency):
    from pydantic import ValidationError
    from fastapi import HTTPException
    from .tabs import _product
    from .service import fail
    try:
        definition = catalog(product)
    except ValidationError:
        fail('Menu modifier definition requires correction', 409)
    result = []
    for group in definition.groups:
        options = []
        for option in group.options:
            try:
                value, _, _ = _product(db, actor, scope, option.product_id, currency)
                if value.id == product.id or catalog(value).groups:
                    fail('Modifier option is unavailable', 409)
            except (HTTPException, ValidationError):
                fail('Menu modifier options are unavailable in this context', 409)
            options.append({'product_id': value.id, 'name': value.item_name, 'price': str(value.sales_rate or 0),
                'currency': value.currency, 'max_quantity': option.max_quantity})
        result.append({'key': group.key, 'label': group.label, 'min_choices': group.min_choices,
            'max_choices': group.max_choices, 'options': options})
    return result
