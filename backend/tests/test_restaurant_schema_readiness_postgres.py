"""Queued only: actual migrated owned PostgreSQL catalog proof, no pack activation."""
import os
import pytest
from sqlalchemy import text
from app.business_packs.restaurant.schema_readiness import installation_reasons

@pytest.fixture
def owned_native_engine(db_engine):
    if db_engine.dialect.name!='postgresql':pytest.skip('Actual PostgreSQL catalog proof')
    url=db_engine.url
    assert os.getenv('TEST_DATABASE_URL') and url.host in {'127.0.0.1','localhost'}
    assert url.database.startswith('business_suite_') and url.database.endswith('_test')
    return db_engine


def test_actual_migrated_restaurant117_catalog_is_complete_and_readonly(owned_native_engine):
    with owned_native_engine.connect() as connection:
        transaction=connection.begin()
        try:
            connection.exec_driver_sql('SET TRANSACTION READ ONLY')
            assert connection.scalar(text("SELECT current_setting('transaction_read_only')"))=='on'
            assert installation_reasons(connection)==[]
            assert connection.scalar(text("SELECT current_setting('transaction_read_only')"))=='on'
        finally:transaction.rollback()


def test_actual_pg_missing117_provenance_guard_fails_closed(owned_native_engine):
    with owned_native_engine.connect() as connection:
        transaction=connection.begin()
        try:
            connection.exec_driver_sql('ALTER TABLE business_restaurant_tab_lines DROP CONSTRAINT ck_restaurant_tab_original_identity')
            reasons=installation_reasons(connection)
            assert any('117' in reason for reason in reasons)
        finally:transaction.rollback()


def test_actual_pg_disabled107_trigger_fails_closed(owned_native_engine):
    with owned_native_engine.connect() as connection:
        transaction=connection.begin()
        try:
            connection.exec_driver_sql('ALTER TABLE suite_branch_ownership DISABLE TRIGGER suite_pack_branch_identity')
            reasons=installation_reasons(connection)
            assert any('107' in reason for reason in reasons)
        finally:transaction.rollback()
