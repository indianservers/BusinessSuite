"""Newborn graph contract, not a substitute for native HTTP authority proofs."""
from types import SimpleNamespace
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.business_packs import anonymous_birth as birth
from app.business_packs import anonymous_definitions as definitions
from app.shared.master_data import CompanyInput


@pytest.fixture
def graph(monkeypatch):
    from app.branches.models import BranchOwnership
    engine = create_engine('sqlite://')
    for model in (*birth._read_models(), BranchOwnership):
        model.__table__.create(engine)
    actor = SimpleNamespace(id=7)
    scope = object()
    monkeypatch.setattr(definitions, '_authority', lambda db, user: (2, 3, scope))
    monkeypatch.setattr('app.apps.srm.services.commercial.lock_tenant', lambda *args: None)
    with Session(engine, expire_on_commit=False) as db:
        db.info['business_pack_scope'] = scope
        payload = CompanyInput(name='Anonymous counter ledger', country='IN', roles=['Customer'], notes='Counter account')
        yield db, actor, payload, scope
    engine.dispose()


def new_root(db, actor, payload):
    company = birth._models()[0]
    row = company(organization_id=2, name=payload.name, owner_user_id=actor.id, created_by_user_id=actor.id)
    db.add(row)
    from app.apps.crm.contact_identity import link_source
    link_source(db, row, 'account')
    return row


def add_remainder(db, actor, root):
    _, _, _, details, relationship, audit = birth._models()
    db.add_all([
        details(account_id=root.id, organization_id=2, addresses=[], tax_registrations=[], version=1),
        relationship(account_id=root.id, organization_id=2, role='Customer'),
        audit(organization_id=2, user_id=actor.id, method='POST', endpoint='/master-data',
              entity_type='company', entity_id=root.id, action='COMPANY_MASTER_SAVED', status_code=200,
              new_values=json.dumps({'roles': ['Customer'], 'sharedReason': None})),
    ])


def flush_graph(db):
    birth.prepare_flush(db)
    for item in tuple(db.new | db.dirty | db.deleted):
        assert birth.allow_write(db, item)
    db.flush()


def test_new_canonical_graph_exact_ids_and_cleanup(graph):
    db, actor, payload, scope = graph
    from app.branches.models import BranchOwnership
    with birth.canonical_account_birth(db, actor, payload):
        assert set(birth.leased_models(db)) == set(birth._read_models())
        root = new_root(db, actor, payload)
        flush_graph(db)
        db.connection().execute(BranchOwnership.__table__.insert().values(
            resource_table=root.__tablename__, resource_key=str(root.id), company_id=2, branch_id=3, source='test'))
        add_remainder(db, actor, root)
        flush_graph(db)
        assert birth.assert_born_account(db, actor, root) is scope
        for model, criterion in birth.read_criteria(db).items():
            assert len(db.execute(select(model).where(criterion)).scalars().all()) == (1 if model in birth._models() else 0)
    assert birth.leased_models(db) == ()
    assert birth.read_criteria(db) == {}
    assert not birth.allow_write(db, root)
    assert db not in birth._active and db not in definitions._leases


@pytest.mark.parametrize('attack', ['personal_contact', 'other_company', 'fake_primary_key',
    'second_root', 'second_contact', 'money', 'employee_link', 'foreign_details',
    'vendor', 'audit_body', 'input_changed', 'scope_replaced', 'delete'])
def test_wrong_source_or_field_rejects_and_savepoint_rolls_back(graph, attack):
    db, actor, payload, scope = graph
    models = birth._models()
    with pytest.raises(HTTPException) as error:
        with db.begin_nested(), birth.canonical_account_birth(db, actor, payload):
            root = new_root(db, actor, payload)
            contact = next(item for item in db.new if type(item) is models[1])
            link = next(item for item in db.new if type(item) is models[2])
            if attack == 'personal_contact': contact.email = 'forged@example.invalid'
            if attack == 'other_company': root.organization_id = 99
            if attack == 'fake_primary_key': root.id = 99
            if attack == 'second_root': new_root(db, actor, payload)
            if attack == 'second_contact':
                db.add(models[1](organization_id=2, first_name='Anonymous', full_name=payload.name, company=root))
            if attack == 'money': root.annual_revenue = 1
            if attack == 'employee_link': link.employee_id = 55
            if attack == 'input_changed': payload.name = 'Swapped payload'
            if attack == 'scope_replaced': db.info['business_pack_scope'] = object()
            flush_graph(db)
            if attack in {'foreign_details', 'vendor', 'audit_body', 'delete'}:
                add_remainder(db, actor, root)
                if attack == 'foreign_details':
                    next(x for x in db.new if type(x) is models[3]).account_id = 999
                if attack == 'vendor':
                    next(x for x in db.new if type(x) is models[4]).role = 'Vendor'
                if attack == 'audit_body':
                    next(x for x in db.new if type(x) is models[5]).new_values = '{}'
                if attack == 'delete': db.delete(root)
                flush_graph(db)
    assert error.value.status_code == 403
    db.info['business_pack_scope'] = scope
    assert db.execute(select(models[0].id)).all() == []
    assert db not in birth._active and db not in definitions._leases


@pytest.mark.parametrize('attack', ['contact_fk', 'account_fk', 'contact_link_fk', 'pk', 'missing_owner', 'foreign_actor'])
def test_persistent_identity_cannot_be_repointed(graph, attack):
    db, actor, payload, _ = graph
    from app.branches.models import BranchOwnership
    with pytest.raises(HTTPException) as error:
        with db.begin_nested(), birth.canonical_account_birth(db, actor, payload):
            root = new_root(db, actor, payload)
            flush_graph(db)
            state = birth._active[db]
            contact, link = (state.objects[model] for model in birth._models()[1:3])
            if attack != 'missing_owner':
                db.connection().execute(BranchOwnership.__table__.insert().values(
                    resource_table=root.__tablename__, resource_key=str(root.id), company_id=2, branch_id=3, source='test'))
            if attack == 'contact_fk': contact.company_id = None
            if attack == 'account_fk': link.account_id = None
            if attack == 'contact_link_fk': link.contact_id = 999
            if attack == 'pk': root.id = 999
            birth.assert_born_account(db, object() if attack == 'foreign_actor' else actor, root)
    assert error.value.status_code == 403
    assert db.execute(select(birth._models()[0].id)).all() == []


def test_existing_account_cannot_be_adopted(graph):
    db, actor, payload, _ = graph
    company = birth._models()[0]
    root = company(organization_id=2, name='Existing unrelated account', owner_user_id=7, created_by_user_id=7)
    db.add(root); db.flush()
    with pytest.raises(HTTPException) as error:
        with birth.canonical_account_birth(db, actor, payload):
            birth.allow_write(db, root)
    assert error.value.status_code == 403


def test_duplicate_name_is_blind_409_before_any_birth(graph):
    db, actor, payload, _ = graph
    company = birth._models()[0]
    existing = company(organization_id=2, name='  ANONYMOUS COUNTER LEDGER  ', owner_user_id=99)
    db.add(existing); db.flush()
    with pytest.raises(HTTPException) as error:
        with birth.canonical_account_birth(db, actor, payload):
            pytest.fail('A duplicate must fail before caller can create records')
    assert error.value.status_code == 409
    assert isinstance(error.value.detail, str)
    assert str(existing.id) not in error.value.detail
    assert db.execute(select(company.id)).scalars().all() == [existing.id]
    assert not db.new
    assert db not in birth._active and db not in definitions._leases


def test_empty_primary_mirror_reads_no_channels_and_channel_writes_stay_denied(graph):
    from app.shared.master_data_models import ContactChannel
    from app.shared.master_data_sync import mirror_primary
    db, actor, payload, _ = graph
    existing = ContactChannel(organization_id=2, account_id=999, kind='email',
                              value='hidden@example.invalid', normalized_value='hidden@example.invalid')
    db.add(existing); db.flush()
    with birth.canonical_account_birth(db, actor, payload):
        root = new_root(db, actor, payload)
        flush_graph(db)
        criterion = birth.read_criteria(db)[ContactChannel]
        assert db.execute(select(ContactChannel).where(criterion)).scalars().all() == []
        mirror_primary(db, root)
        assert not any(type(row) is ContactChannel for row in db.new)
        assert not birth.allow_write(db, existing)
        existing.is_primary = True
        assert not birth.allow_write(db, existing)
        db.delete(existing)
        assert not birth.allow_write(db, existing)
        channel = ContactChannel(organization_id=2, account_id=root.id, kind='email',
                                  value='forged@example.invalid', normalized_value='forged@example.invalid')
        db.add(channel)
        assert not birth.allow_write(db, channel)
        db.expunge(channel)
        db.add(existing); existing.is_primary = False


def test_newborn_has_no_legacy_projection_links_and_all_link_writes_are_denied(graph):
    from app.apps.srm.commercial_models import CustomerLink
    from app.apps.srm.services.customer_identity import refresh_legacy_projections
    from sqlalchemy import event
    from sqlalchemy.orm import with_loader_criteria
    db, actor, payload, _ = graph
    existing = CustomerLink(organization_id=2, source_type='crm_account', source_id=999,
                            customer_id=999, actor_id=7)
    db.add(existing); db.flush()
    with birth.canonical_account_birth(db, actor, payload):
        root = new_root(db, actor, payload)
        flush_graph(db)
        criterion = birth.read_criteria(db)[CustomerLink]
        assert db.execute(select(CustomerLink).where(criterion)).scalars().all() == []
        def scoped(execution):
            if execution.is_select:
                execution.statement = execution.statement.options(with_loader_criteria(CustomerLink, criterion))
        event.listen(db, 'do_orm_execute', scoped)
        try:
            root.notes = payload.notes
            with db.no_autoflush:
                refresh_legacy_projections(db, None, None)
            assert not any(type(row) is CustomerLink for row in db.new)
        finally:
            event.remove(db, 'do_orm_execute', scoped)
        assert not birth.allow_write(db, existing)
        existing.source_id = 998
        assert not birth.allow_write(db, existing)
        db.delete(existing)
        assert not birth.allow_write(db, existing)
        db.add(existing); existing.source_id = 999
        forged = CustomerLink(organization_id=2, source_type='crm_account', source_id=999,
                              customer_id=root.id, actor_id=7)
        db.add(forged)
        assert not birth.allow_write(db, forged)
        db.expunge(forged)
