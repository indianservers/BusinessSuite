"""Isolated new-table contracts; run with --noconftest, no application startup."""
import os
from pathlib import Path
import runpy
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, create_engine, event, insert, select, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from app.db.base_class import Base

from app.business_packs.models import (
    PackActivation, PackContext, PackIdentityError, PackMasterAvailability,
    PackRecordOwnership, PackRevisionError, PackUserGrant,
)


MODELS = (PackActivation, PackContext, PackUserGrant, PackRecordOwnership, PackMasterAvailability)
MIGRATION_PATH = Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261114_102_business_pack_foundation.py'


@pytest.fixture(params=('models', 'migration'))
def pack_db(request):
    # Isolated --noconftest runs intentionally do not import the application's
    # Company/Branch/User models. Resolve the mapped FK names using bare stubs;
    # full application test runs already have their real metadata definitions.
    for name in ('companies', 'branches', 'users'):
        if name not in Base.metadata.tables:
            Table(name, Base.metadata, Column('id', Integer, primary_key=True))
    metadata = MetaData()
    companies = Table('companies', metadata, Column('id', Integer, primary_key=True))
    branches = Table('branches', metadata, Column('id', Integer, primary_key=True), Column('company_id', Integer, ForeignKey('companies.id'), nullable=False))
    users = Table('users', metadata, Column('id', Integer, primary_key=True))
    for model in MODELS:
        model.__table__.to_metadata(metadata)
    engine = create_engine('sqlite://')
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
    if request.param == 'models':
        metadata.create_all(engine)
    else:
        metadata.create_all(engine, tables=[companies, branches, users])
        migration = runpy.run_path(str(MIGRATION_PATH))
        with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            migration['upgrade']()
            migration['upgrade']()
            migration['downgrade']()
            history = runpy.run_path(str(MIGRATION_PATH.with_name('pg_20261114_106_pack_history.py')))
            history['upgrade'](); history['upgrade']()
            assert all(connection.execute(select(model.__table__.c.id)).first() is None for model in MODELS)
    with engine.begin() as connection:
        connection.execute(companies.insert(), [{'id': 1}, {'id': 2}])
        connection.execute(branches.insert(), [{'id': 11, 'company_id': 1}, {'id': 12, 'company_id': 1}, {'id': 22, 'company_id': 2}])
        connection.execute(users.insert(), [{'id': 101}, {'id': 102}])
    with Session(engine) as session:
        first = PackActivation(company_id=1, pack_key='hospital', pack_version=1, state='active')
        other = PackActivation(company_id=2, pack_key='restaurant', pack_version=1, state='active')
        session.add_all([first, other]); session.flush()
        context = PackContext(company_id=1, branch_id=11, activation_id=first.id, pack_key='hospital', pack_version=1, state='active')
        foreign = PackContext(company_id=2, branch_id=22, activation_id=other.id, pack_key='restaurant', pack_version=1, state='active')
        session.add_all([context, foreign]); session.commit()
        yield session, first.id, context.id, foreign.id
    engine.dispose()


def test_new_models_only_reference_existing_identity_and_new_configuration_tables(pack_db):
    db, activation_id, context_id, _ = pack_db
    assert db.get(PackActivation, activation_id).revision == 1
    assert db.get(PackContext, context_id).pack_version == 1

    assert 'is_primary' not in PackContext.__table__.c
    assert set(db.get_bind().dialect.get_table_names(db.connection())) == {
        'companies', 'branches', 'users', *(model.__tablename__ for model in MODELS),
    }
    inspector = inspect(db.connection())
    for model in MODELS:
        table = model.__table__
        assert {column['name'] for column in inspector.get_columns(table.name)} == set(table.c.keys())
        actual = {(tuple(fk['constrained_columns']), fk['referred_table'], tuple(fk['referred_columns'])) for fk in inspector.get_foreign_keys(table.name)}
        expected = {(tuple(element.parent.name for element in fk.elements), fk.referred_table.name, tuple(element.column.name for element in fk.elements)) for fk in table.foreign_key_constraints}
        assert actual == expected



def test_activation_history_stays_true_after_state_reset_and_cannot_be_cleared(pack_db):
    db, _, context_id, _ = pack_db
    row = db.get(PackContext, context_id)
    assert row.ever_activated is True
    row.state = 'draft'; db.commit()
    assert row.ever_activated is True
    row.ever_activated = False
    with pytest.raises(PackIdentityError): db.commit()

@pytest.mark.parametrize('changes', [{'company_id': 2}, {'pack_key': 'restaurant'}, {'pack_version': 2}])
def test_context_activation_composite_fk_rejects_cross_company_or_version(pack_db, changes):
    db, activation_id, _, _ = pack_db
    values = dict(company_id=1, branch_id=12, activation_id=activation_id, pack_key='hospital', pack_version=1)
    values.update(changes)
    with pytest.raises(IntegrityError):
        db.execute(insert(PackContext.__table__).values(**values)); db.flush()


@pytest.mark.parametrize('model,extra', [
    (PackUserGrant, {'user_id': 101, 'role': 'doctor'}),
    (PackRecordOwnership, {'resource_table': 'srm_industry_records', 'resource_key': '73'}),
    (PackMasterAvailability, {'resource_table': 'srm_products', 'resource_key': '9'}),
])
@pytest.mark.parametrize('changes', [{'company_id': 2}, {'branch_id': 12}, {'context_id': 2}])
def test_exact_context_fk_rejects_mismatched_grant_anchor_or_master(pack_db, model, extra, changes):
    db, _, context_id, foreign_id = pack_db
    values = dict(company_id=1, branch_id=11, context_id=context_id, **extra)
    values.update({'context_id': foreign_id} if 'context_id' in changes else changes)
    with pytest.raises(IntegrityError):
        db.execute(insert(model.__table__).values(**values)); db.flush()


@pytest.mark.parametrize('model,values', [
    (PackActivation, {'company_id': 1, 'pack_key': 'hospital', 'pack_version': 1}),
    (PackContext, {'company_id': 1, 'branch_id': 11, 'activation_id': 1, 'pack_key': 'hospital', 'pack_version': 1}),
    (PackUserGrant, {'company_id': 1, 'branch_id': 11, 'context_id': 1, 'user_id': 101, 'role': 'doctor'}),
    (PackRecordOwnership, {'company_id': 1, 'branch_id': 11, 'context_id': 1, 'resource_table': 'srm_industry_records', 'resource_key': '73'}),
    (PackMasterAvailability, {'company_id': 1, 'branch_id': 11, 'context_id': 1, 'resource_table': 'srm_products', 'resource_key': '9'}),
])
def test_duplicate_configuration_or_native_anchor_is_rejected(pack_db, model, values):
    db, _, _, _ = pack_db
    if model not in (PackActivation, PackContext):
        db.add(model(**values)); db.commit()
    with pytest.raises(IntegrityError):
        db.execute(insert(model.__table__).values(**values)); db.flush()


def test_same_native_record_cannot_be_reanchored_in_another_valid_pack(pack_db):
    db, _, context_id, foreign_id = pack_db
    db.add(PackRecordOwnership(company_id=1, branch_id=11, context_id=context_id, resource_table='srm_industry_records', resource_key='73'))
    db.commit()
    with pytest.raises(IntegrityError):
        db.execute(insert(PackRecordOwnership.__table__).values(company_id=2, branch_id=22, context_id=foreign_id, resource_table='srm_industry_records', resource_key='73'))


def test_shared_master_requires_separate_explicit_availability_rows(pack_db):
    db, activation_id, context_id, _ = pack_db
    second = PackContext(company_id=1, branch_id=12, activation_id=activation_id, pack_key='hospital', pack_version=1)
    db.add(second); db.flush()
    db.add_all([PackMasterAvailability(company_id=1, branch_id=branch, context_id=context, resource_table='srm_products', resource_key='9')
                for branch, context in [(11, context_id), (12, second.id)]])
    db.commit()
    assert len(db.scalars(select(PackMasterAvailability)).all()) == 2


@pytest.mark.parametrize('column,value', [('state', 'enabled'), ('pack_version', 0), ('revision', 0)])
def test_database_enforces_state_and_positive_versions(pack_db, column, value):
    db, _, _, _ = pack_db
    values = dict(company_id=1, pack_key='retail', pack_version=1)
    values[column] = value
    with pytest.raises(IntegrityError):
        db.execute(insert(PackActivation.__table__).values(**values))


@pytest.mark.parametrize('values', [{'pack_key': 'Hospital'}, {'pack_key': '*'}, {'pack_version': True}, {'pack_version': 1.5}, {'revision': -1}, {'state': 'enabled'}])
def test_orm_rejects_malformed_activation_fields(values):
    base = dict(company_id=1, pack_key='hospital', pack_version=1)
    base.update(values)
    with pytest.raises(ValueError):
        PackActivation(**base)


@pytest.mark.parametrize('field,value', [('company_id', 2), ('pack_key', 'restaurant'), ('pack_version', 2), ('branch_id', 12), ('activation_id', 2)])
def test_context_identity_cannot_be_retagged_even_after_expiration(pack_db, field, value):
    db, _, context_id, _ = pack_db
    row = db.get(PackContext, context_id)
    db.expire(row)
    setattr(row, field, value)
    with pytest.raises(PackIdentityError):
        db.commit()


def test_activation_identity_cannot_be_retagged(pack_db):
    db, activation_id, _, _ = pack_db
    db.get(PackActivation, activation_id).pack_key = 'restaurant'
    with pytest.raises(PackIdentityError):
        db.commit()


def test_grant_can_be_revoked_but_cannot_move_to_another_identity(pack_db):
    db, _, context_id, _ = pack_db
    row = PackUserGrant(company_id=1, branch_id=11, context_id=context_id, user_id=101, role='doctor')
    db.add(row); db.commit()
    row.active = False; db.commit()
    assert row.revision == 2
    row.user_id = 102
    with pytest.raises(PackIdentityError):
        db.commit()


def test_record_anchor_cannot_be_updated_or_deleted(pack_db):
    db, _, context_id, _ = pack_db
    row = PackRecordOwnership(company_id=1, branch_id=11, context_id=context_id, resource_table='srm_industry_records', resource_key='73')
    db.add(row); db.commit()
    identity = row.id
    row.resource_key = '74'
    with pytest.raises(PackIdentityError):
        db.commit()
    db.rollback()
    db.delete(db.get(PackRecordOwnership, identity))
    with pytest.raises(PackIdentityError):
        db.commit()


def test_revision_optimistic_locking_rejects_stale_writer(pack_db):
    db, activation_id, _, _ = pack_db
    first = db.get(PackActivation, activation_id)
    with Session(db.get_bind()) as other:
        stale = other.get(PackActivation, activation_id)
        first.state = 'suspended'; db.commit()
        assert first.revision == 2
        stale.state = 'retired'
        with pytest.raises(StaleDataError):
            other.commit()


def test_revision_cannot_be_reset_or_skipped(pack_db):
    db, activation_id, _, _ = pack_db
    row = db.get(PackActivation, activation_id)
    row.revision = 8
    with pytest.raises(PackRevisionError):
        db.commit()


def test_actual_postgresql_migration_is_repeatable_and_enforces_context_pair(request):
    if not os.environ.get('TEST_DATABASE_URL'):
        pytest.skip('Opt-in disposable PostgreSQL test database required')
    db = request.getfixturevalue('db')
    connection = db.connection()
    assert connection.dialect.name == 'postgresql'
    from app.models.company import Company, Branch
    for identity in (1, 2):
        if connection.execute(select(Company.id).where(Company.id == identity)).first() is None:
            connection.execute(Company.__table__.insert().values(id=identity, name=f'Pack fixture {identity}'))
    branch_id = connection.execute(Branch.__table__.insert().values(company_id=1, name='Pack PostgreSQL fixture').returning(Branch.id)).scalar_one()
    migration = runpy.run_path(str(MIGRATION_PATH))
    with Operations.context(MigrationContext.configure(connection)):
        migration['upgrade']()
        migration['upgrade']()
    activation = connection.execute(insert(PackActivation.__table__).values(company_id=1, pack_key='hospital').returning(PackActivation.id)).scalar_one()
    context = connection.execute(insert(PackContext.__table__).values(company_id=1, branch_id=branch_id, activation_id=activation, pack_key='hospital', pack_version=1).returning(PackContext.id)).scalar_one()
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert(PackMasterAvailability.__table__).values(company_id=2, branch_id=branch_id, context_id=context, resource_table='srm_products', resource_key='73'))
    connection.execute(insert(PackMasterAvailability.__table__).values(company_id=1, branch_id=branch_id, context_id=context, resource_table='srm_products', resource_key='73'))
