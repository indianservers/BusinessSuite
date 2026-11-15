"""Standalone additive data-schema proof; run with --noconftest, SQLite only."""
from decimal import Decimal
import json
from pathlib import Path
import runpy

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError

from app.db.base_class import Base
from app.module_registry import import_model_modules


DOMAIN_TABLES = frozenset('''
business_retail_sale_stock_sources business_retail_returns business_retail_return_lines
business_pharma_batch_availability business_pharma_batch_receipts business_pharma_batch_allocations
business_pharma_batch_controls business_pharma_recalls business_pharma_recall_events
business_pharma_returns business_pharma_return_lines business_pharma_return_lots
business_restaurant_tables business_restaurant_service_orders business_restaurant_kitchen_tickets
business_restaurant_kitchen_lines business_restaurant_commands business_restaurant_tab_lines
business_restaurant_kitchen_issues business_accounts_periods business_accounts_commands
business_accounts_engagement_commands
'''.split())
MIGRATIONS = (
    'pg_20261115_107_pack_branch_guard.py',
    'pg_20261115_108_retail_returns.py',
    'pg_20261115_109_pharma_stock.py',
    'pg_20261115_110_restaurant.py',
    'pg_20261115_111_accounts.py',
    'pg_20261115_112_pharma_recall.py',
    'pg_20261115_113_restaurant_tabs.py',
    'pg_20261115_114_return_precision.py',
    'pg_20261115_115_pharma_returns.py',
    'pg_20261115_116_accounts_engagements.py',
)


def test_schema_inventory_covers_every_domain_model():
    import_model_modules()
    inventory = json.loads((Path(__file__).parents[1] / 'alembic_postgresql/schema/extensions.json').read_text())
    for name in DOMAIN_TABLES:
        assert set(inventory[name]) == set(Base.metadata.tables[name].c.keys()), name


def _snapshot(connection, names):
    return {name: [dict(row) for row in connection.execute(
        select(Base.metadata.tables[name])).mappings()] for name in names}


def _upgrade(connection):
    directory = Path(__file__).parents[1] / 'alembic_postgresql/versions'
    with Operations.context(MigrationContext.configure(connection)):
        for name in MIGRATIONS:
            runpy.run_path(str(directory / name))['upgrade']()


@pytest.fixture
def migrated():
    # No API startup, operational services, application fixtures or configured DB.
    import_model_modules()
    assert len(DOMAIN_TABLES) == 22
    assert DOMAIN_TABLES <= Base.metadata.tables.keys()
    engine = create_engine('sqlite://')
    assert engine.url.drivername == 'sqlite' and engine.url.database is None

    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')

    try:
        Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables
                                                if table.name not in DOMAIN_TABLES])
        with engine.begin() as connection:
            assert not DOMAIN_TABLES.intersection(inspect(connection).get_table_names())
            tables = Base.metadata.tables
            connection.execute(tables['companies'].insert(), [
                {'id': 1, 'name': 'Original company'}, {'id': 2, 'name': 'Other company'}])
            connection.execute(tables['branches'].insert(), [
                {'id': 11, 'name': 'Original branch', 'company_id': 1},
                {'id': 12, 'name': 'Other branch', 'company_id': 1},
                {'id': 21, 'name': 'Other company branch', 'company_id': 2}])
            connection.execute(tables['users'].insert().values(
                id=1, email='schema-proof@example.test', hashed_password='unused-test-hash'))
            connection.execute(tables['crm_companies'].insert().values(
                id=1, organization_id=1, name='Preserved shared customer'))
            connection.execute(tables['srm_invoices'].insert().values(
                id=1, organization_id=1, customer_id=1, invoice_number='SCHEMA-ORIGINAL',
                currency='INR', subtotal=Decimal('123.45'), total_amount=Decimal('145.67'),
                paid_amount=Decimal('45.67'), balance_amount=Decimal('100.00')))
            for identity, company, branch, pack in [(1, 1, 11, 'retail'), (2, 2, 21, 'pharma')]:
                connection.execute(tables['business_pack_activations'].insert().values(
                    id=identity, company_id=company, pack_key=pack, pack_version=1))
                connection.execute(tables['business_pack_contexts'].insert().values(
                    id=identity, company_id=company, branch_id=branch, activation_id=identity,
                    pack_key=pack, pack_version=1))
            connection.execute(tables['business_pack_record_ownership'].insert().values(
                company_id=1, branch_id=11, context_id=1,
                resource_table='srm_invoices', resource_key='1'))
            connection.execute(tables['suite_branch_ownership'].insert().values(
                company_id=1, branch_id=11, resource_table='srm_invoices',
                resource_key='1', source='schema-proof'))
            native_names = ('companies', 'branches', 'users', 'crm_companies', 'srm_invoices',
                            'business_pack_contexts', 'business_pack_record_ownership',
                            'suite_branch_ownership')
            original = _snapshot(connection, native_names)
            _upgrade(connection)
            assert 'business_accounts_engagement_commands' in inspect(connection).get_table_names()
            assert _snapshot(connection, native_names) == original
            # Add real new-domain history before the repeat, so repeatability
            # cannot pass merely because all newly migrated tables are empty.
            connection.execute(tables['business_restaurant_tables'].insert().values(
                id=1, organization_id=1, branch_id=11, pack_context_id=1,
                created_by=1, name='Retained table', capacity=2))
            history = _snapshot(connection, DOMAIN_TABLES)
            _upgrade(connection)
            assert _snapshot(connection, native_names) == original
            assert _snapshot(connection, DOMAIN_TABLES) == history
        yield engine
    finally:
        engine.dispose()


def test_static_107_to_116_creates_exact_model_columns_and_foreign_keys(migrated):
    inspector = inspect(migrated)
    for name in sorted(DOMAIN_TABLES):
        table = Base.metadata.tables[name]
        assert {column['name'] for column in inspector.get_columns(name)} == set(table.c.keys()), name
        expected = {(tuple(element.parent.name for element in constraint.elements),
                     constraint.referred_table.name,
                     tuple(element.column.name for element in constraint.elements))
                    for constraint in table.foreign_key_constraints}
        actual = {(tuple(fk['constrained_columns']), fk['referred_table'],
                   tuple(fk['referred_columns'])) for fk in inspector.get_foreign_keys(name)}
        assert actual == expected, name


def test_private_native_branch_history_cannot_move_or_disappear(migrated):
    table = Base.metadata.tables['suite_branch_ownership']
    for statement in (table.update().where(table.c.resource_key == '1').values(branch_id=12),
                      table.delete().where(table.c.resource_key == '1')):
        with migrated.begin() as connection:
            with pytest.raises(IntegrityError, match='Pack-private'):
                connection.execute(statement)
            assert connection.scalar(select(table.c.branch_id).where(table.c.resource_key == '1')) == 11


def test_new_domain_composite_context_rejects_foreign_company(migrated):
    table = Base.metadata.tables['business_restaurant_tables']
    with migrated.begin() as connection:
        with pytest.raises(IntegrityError, match='FOREIGN KEY'):
            connection.execute(table.insert().values(
                id=2, organization_id=1, branch_id=11, pack_context_id=2,
                created_by=1, name='Rejected context', capacity=2))
        assert connection.scalar(select(table.c.id).where(table.c.id == 2)) is None

