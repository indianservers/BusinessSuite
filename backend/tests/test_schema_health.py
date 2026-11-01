"""A current revision marker must not hide missing ORM fields at deployment."""
import pytest
import sqlalchemy as sa
from app.db.schema_health import model_schema_report, require_model_schema


def test_schema_guard_detects_new_fields_on_an_existing_table():
    old = sa.MetaData()
    sa.Table('work', old, sa.Column('id', sa.Integer, primary_key=True), sa.Column('title', sa.String))
    runtime = sa.MetaData()
    sa.Table('work', runtime, sa.Column('id', sa.Integer, primary_key=True), sa.Column('title', sa.String), sa.Column('is_general', sa.Boolean))
    engine = sa.create_engine('sqlite://')
    old.create_all(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO work VALUES (1,'Preserved')"))
        report = model_schema_report(connection, runtime)
        assert report['missing_columns'] == {'work': ['is_general']}
        with pytest.raises(RuntimeError, match='work.*is_general'):
            require_model_schema(connection, runtime)
        connection.execute(sa.text('ALTER TABLE work ADD COLUMN is_general BOOLEAN DEFAULT 0'))
        assert require_model_schema(connection, runtime)['missing_columns'] == {}
        assert connection.execute(sa.text('SELECT title FROM work')).scalar_one() == 'Preserved'


def test_schema_guard_allows_historical_fields_but_rejects_missing_tables():
    runtime = sa.MetaData()
    sa.Table('live', runtime, sa.Column('id', sa.Integer, primary_key=True))
    sa.Table('new_feature', runtime, sa.Column('id', sa.Integer, primary_key=True))
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(sa.text('CREATE TABLE live (id INTEGER PRIMARY KEY, legacy_field TEXT)'))
        report = model_schema_report(connection, runtime)
        assert report['missing_tables'] == ['new_feature']
        assert report['missing_columns'] == {}
        with pytest.raises(RuntimeError, match='new_feature'):
            require_model_schema(connection, runtime)
        connection.execute(sa.text('CREATE TABLE new_feature (id INTEGER PRIMARY KEY)'))
        assert require_model_schema(connection, runtime)['checked_tables'] == 2


def test_schema_guard_postgresql_schema_isolation(db_engine):
    if db_engine.dialect.name != 'postgresql':
        pytest.skip('Real PostgreSQL reflection integration')
    assert db_engine.url.database.endswith('_test')
    from uuid import uuid4
    schema = 'schema_health_' + uuid4().hex
    runtime = sa.MetaData(schema=schema)
    sa.Table('items', runtime, sa.Column('id', sa.Integer, primary_key=True), sa.Column('new_field', sa.String))
    with db_engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
        try:
            connection.execute(sa.text(f'CREATE TABLE "{schema}".items (id INTEGER PRIMARY KEY)'))
            report = model_schema_report(connection, runtime)
            assert report['missing_columns'] == {f'{schema}.items': ['new_field']}
            with pytest.raises(RuntimeError, match='new_field'):
                require_model_schema(connection, runtime)
            connection.execute(sa.text(f'ALTER TABLE "{schema}".items ADD COLUMN new_field VARCHAR'))
            assert require_model_schema(connection, runtime)['missing_columns'] == {}
        finally:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
