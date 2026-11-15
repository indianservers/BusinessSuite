"""Finite projection/lease contract; native setup authority is tested by HTTP."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.business_packs import anonymous_definitions as adapter
from app.apps.crm.models import CRMCustomField
from app.shared.master_data import CompanyInput


@pytest.fixture
def projection(monkeypatch):
    engine = create_engine('sqlite://')
    CRMCustomField.__table__.create(engine)
    scope = object()
    actor = SimpleNamespace(id=7)
    with Session(engine) as db:
        monkeypatch.setattr(adapter, '_authority', lambda session, user: (2, 3, scope))
        monkeypatch.setattr('app.apps.srm.services.commercial.lock_tenant', lambda *args: None)
        payload = CompanyInput(name='Counter ledger', country='IN', roles=['Customer'])
        yield db, actor, payload
    engine.dispose()


def seed(db, **values):
    row = CRMCustomField(organization_id=2, entity='companies', field_key='required',
                         label='Required account field', field_type='text',
                         is_active=True, is_required=True, is_visible=False, **values)
    db.add(row)
    db.flush()
    return row


def test_required_hidden_definition_reaches_original_validator_without_writes(projection):
    db, actor, payload = projection
    seed(db)
    from app.apps.crm.custom_field_config import validate_values
    before = db.scalar(select(func.count()).select_from(CRMCustomField))
    with adapter.anonymous_company_birth(db, actor, payload):
        adapter.assert_company_birth_input(db, actor, 'srm', payload, None)
        with pytest.raises(HTTPException) as error:
            validate_values(db, 'companies', 2, {})
        assert error.value.status_code == 422
        assert error.value.detail == 'Required account field is required'
        assert adapter.definitions_for_birth(db, 'companies', 2, include_hidden=False) == ()
    assert db.scalar(select(func.count()).select_from(CRMCustomField)) == before
    assert db not in adapter._leases


def test_foreign_null_inactive_deleted_and_other_entity_definitions_are_excluded(projection):
    db, actor, payload = projection
    for index, changes in enumerate(({'organization_id': 3}, {'organization_id': None},
                                    {'is_active': False}, {'entity': 'contacts'})):
        values = dict(organization_id=2, entity='companies', field_key=str(index),
                      label='Excluded', field_type='text', is_required=True)
        values.update(changes)
        db.add(CRMCustomField(**values))
    from datetime import datetime, timezone
    db.add(CRMCustomField(organization_id=2, entity='companies', field_key='deleted',
                         label='Deleted', is_required=True, deleted_at=datetime.now(timezone.utc)))
    db.flush()
    with adapter.anonymous_company_birth(db, actor, payload):
        assert adapter.definitions_for_birth(db, 'companies', 2) == ()
    assert adapter.definitions_for_birth(db, 'companies', 2) is None
    adapter.assert_company_birth_input(db, object(), 'crm', object(), object())


@pytest.mark.parametrize('variant', ['payload', 'actor', 'source', 'row', 'mutation', 'entity', 'company', 'nested'])
def test_lease_cannot_be_borrowed_or_retargeted_and_cleans_up(projection, variant):
    db, actor, payload = projection
    with pytest.raises(HTTPException) as error:
        with adapter.anonymous_company_birth(db, actor, payload):
            if variant == 'entity':
                adapter.definitions_for_birth(db, 'contacts', 2)
            elif variant == 'company':
                adapter.definitions_for_birth(db, 'companies', 3)
            elif variant == 'nested':
                with adapter.anonymous_company_birth(db, actor, payload):
                    pass
            else:
                candidate = payload.model_copy() if variant == 'payload' else payload
                if variant == 'mutation':
                    payload.name = 'Changed after certification'
                adapter.assert_company_birth_input(db, object() if variant == 'actor' else actor,
                    'crm' if variant == 'source' else 'srm', candidate,
                    object() if variant == 'row' else None)
    assert error.value.status_code == 403
    assert db not in adapter._leases


def test_outside_lease_canonical_reader_retains_native_orm_fallback(projection):
    db, _, _ = projection
    row = seed(db)
    from app.apps.crm.api.router import _custom_field_definitions
    result = _custom_field_definitions(db, 'companies', 2)
    assert len(result) == 1 and result[0] is row
