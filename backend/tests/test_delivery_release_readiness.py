"""Real SQLite DDL and prepared native migration tampering; no producer mocks."""
from pathlib import Path
import importlib.util
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.business_packs.delivery_release_readiness import installation_reasons, release_status, _check_tree
from app.business_packs.models import PackActivation, PackContext, PackUserGrant, PackRecordOwnership, PackMasterAvailability
from app.models.email_outbox import EmailOutbox
from app.models.notification import Notification

PATH=Path(__file__).parents[1]/'alembic_postgresql/versions/pg_20261116_121_delivery_sources.py'
SPEC=importlib.util.spec_from_file_location('frozen_release_121',PATH)
MIGRATION=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MIGRATION)
FOUNDATIONS=(PackActivation,PackContext,PackUserGrant,PackRecordOwnership,PackMasterAvailability,EmailOutbox,Notification)


@pytest.fixture
def sqlite_release():
    engine=sa.create_engine('sqlite://')
    @sa.event.listens_for(engine,'connect')
    def enforce(connection,record):connection.execute('PRAGMA foreign_keys=ON')
    metadata=sa.MetaData()
    sa.Table('companies',metadata,sa.Column('id',sa.Integer,primary_key=True))
    sa.Table('users',metadata,sa.Column('id',sa.Integer,primary_key=True))
    sa.Table('branches',metadata,sa.Column('id',sa.Integer,primary_key=True))
    for model in FOUNDATIONS:model.__table__.to_metadata(metadata)
    with engine.connect() as connection:
        metadata.create_all(connection)
        with Operations.context(MigrationContext.configure(connection)):MIGRATION.upgrade()
        connection.commit()
        yield connection
    engine.dispose()


def test_actual_sqlite_migration_repeat_has_complete_read_only_release_proof(sqlite_release):
    connection=sqlite_release
    assert installation_reasons(connection)==[]
    before=tuple(connection.execute(sa.text("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")))
    assert release_status(connection)['ready'] is True
    assert tuple(connection.execute(sa.text("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")))==before
    with Operations.context(MigrationContext.configure(connection)):MIGRATION.upgrade();MIGRATION.upgrade()
    assert installation_reasons(connection)==[]


@pytest.mark.parametrize('fault',['missing','actor_column','actor_nullable','actor_type','primary_key','actor_fk','recipient_fk','context_fk','target_fk','target_unique','xor','positive_actor','payload'])
def test_sqlite_real_weakened_schema_never_qualifies(sqlite_release,fault):
    connection=sqlite_release
    assert installation_reasons(connection)==[]
    connection.exec_driver_sql('DROP TABLE business_pack_delivery_sources')
    if fault!='missing':
        ddl=MIGRATION.DDL['sqlite']
        edits={
            'actor_column':('\tactor_user_id INTEGER NOT NULL,','\tobsolete_actor INTEGER NOT NULL,'),
            'actor_nullable':('actor_user_id INTEGER NOT NULL','actor_user_id INTEGER'),
            'actor_type':('actor_user_id INTEGER NOT NULL','actor_user_id VARCHAR(80) NOT NULL'),
            'primary_key':('PRIMARY KEY (id),',''),
            'actor_fk':('FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT','FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE CASCADE'),
            'recipient_fk':('FOREIGN KEY(recipient_user_id) REFERENCES users (id) ON DELETE RESTRICT','FOREIGN KEY(recipient_user_id) REFERENCES users (id) ON DELETE CASCADE'),
            'context_fk':('REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT','REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE CASCADE'),
            'target_fk':('FOREIGN KEY(email_outbox_id) REFERENCES email_outbox (id) ON DELETE RESTRICT','FOREIGN KEY(email_outbox_id) REFERENCES email_outbox (id) ON DELETE CASCADE'),
            'target_unique':('CONSTRAINT uq_pack_delivery_email UNIQUE (email_outbox_id),',''),
            'xor':('(email_outbox_id IS NOT NULL AND notification_id IS NULL) OR (email_outbox_id IS NULL AND notification_id IS NOT NULL)','TRUE'),
            'positive_actor':(' AND actor_user_id > 0',''),
            'payload':('length(payload_sha256)=64','length(payload_sha256)=1'),
        }
        old,new=edits[fault];assert old in ddl;ddl=ddl.replace(old,new)
        if fault=='actor_column':ddl=ddl.replace(' AND actor_user_id > 0','').replace('FOREIGN KEY(actor_user_id)','FOREIGN KEY(obsolete_actor)')
        connection.exec_driver_sql(ddl)
        if fault!='actor_column':MIGRATION.install_delivery_guards(connection)
    assert installation_reasons(connection)
    assert release_status(connection)['ready'] is False


@pytest.mark.parametrize('prefix',['suite_pack_anchor','suite_pack_delivery','suite_private_email','suite_private_notice'])
@pytest.mark.parametrize('suffix',['immutable','retained'])
def test_sqlite_missing_or_name_matching_noop_guard_is_not_ready(sqlite_release,prefix,suffix):
    connection=sqlite_release;name=prefix+'_'+suffix
    table=next(spec[0] for spec in MIGRATION.SPECS if spec[1]==prefix)
    connection.exec_driver_sql('DROP TRIGGER '+name)
    assert installation_reasons(connection)
    connection.exec_driver_sql('CREATE TRIGGER '+name+' BEFORE UPDATE ON '+table+' BEGIN SELECT 1; END')
    assert installation_reasons(connection)


def test_sqlite_disabled_foreign_key_enforcement_is_not_ready(sqlite_release):
    # PRAGMA changes require leaving the fixture's empty metadata transaction.
    connection=sqlite_release;connection.commit();connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
    assert connection.scalar(sa.text('PRAGMA foreign_keys'))==0
    assert release_status(connection)['ready'] is False


def test_check_grammar_preserves_precedence_and_postgresql_pretty_print():
    xor='(email_outbox_id IS NOT NULL AND notification_id IS NULL) OR (email_outbox_id IS NULL AND notification_id IS NOT NULL)'
    assert _check_tree(xor)==_check_tree('((email_outbox_id IS NOT NULL) AND (notification_id IS NULL)) OR ((email_outbox_id IS NULL) AND (notification_id IS NOT NULL))')
    assert _check_tree(xor)!=_check_tree(xor+' OR actor_user_id > 0')
    assert _check_tree('length(payload_sha256)=64 AND length(source_key)>0')==_check_tree('((length((payload_sha256)::text) = 64) AND (length((source_key)::text) > 0))')
    assert _check_tree("state IN ('draft','active')")==_check_tree("((state)::text = ANY ((ARRAY['draft'::character varying, 'active'::character varying])::text[]))")
    assert _check_tree('length(trim(resource_table)) BETWEEN 1 AND 120')==_check_tree('length(btrim(resource_table::text)) >= 1 AND length(btrim(resource_table::text)) <= 120')
    assert _check_tree('length(trim(resource_table)) BETWEEN 1 AND 120')==_check_tree('length(TRIM(BOTH FROM resource_table)) >= 1 AND length(TRIM(BOTH FROM resource_table)) <= 120')
    assert _check_tree('trim(resource_table)')==_check_tree("TRIM(BOTH ' ' FROM resource_table)")
    assert _check_tree("TRIM(BOTH 'x' FROM resource_table)") is None
    assert _check_tree('TRIM(LEADING FROM resource_table)') is None
    assert _check_tree('actor_user_id::boolean::integer > 0') is None


def _native(db):
    if db.connection().dialect.name!='postgresql':pytest.skip('Actual guarded PostgreSQL migration/guard qualification')
    url=db.get_bind().engine.url
    assert url.host in {'127.0.0.1','localhost','::1'}
    assert url.database.startswith('business_suite_') and url.database.endswith('_test')
    return db.connection()


def test_native_actual_migration_and_repeat_release_proof(db):
    connection=_native(db)
    assert connection.scalar(sa.text('SELECT version_num FROM alembic_version'))==MIGRATION.revision
    assert installation_reasons(connection)==[]
    with Operations.context(MigrationContext.configure(connection)):MIGRATION.upgrade();MIGRATION.upgrade()
    assert release_status(connection)['ready'] is True


@pytest.mark.parametrize('fault',['missing_column','actor_nullable','actor_type','missing_actor_fk','not_valid_actor_fk','cascade_actor_fk','missing_unique','weak_xor','weak_positive','weak_payload'])
def test_native_actual_schema_tamper_fails_closed(db,fault):
    connection=_native(db);assert installation_reasons(connection)==[]
    scope=connection.begin_nested()
    try:
        table='business_pack_delivery_sources'
        constraints=sa.inspect(connection).get_foreign_keys(table)
        actor=next(item['name'] for item in constraints if item['constrained_columns']==['actor_user_id'])
        quoted=connection.dialect.identifier_preparer.quote(actor)
        commands={
            'missing_column':'ALTER TABLE business_pack_delivery_sources DROP COLUMN actor_user_id CASCADE',
            'actor_nullable':'ALTER TABLE business_pack_delivery_sources ALTER COLUMN actor_user_id DROP NOT NULL',
            'actor_type':'ALTER TABLE business_pack_delivery_sources ALTER COLUMN source_key TYPE TEXT',
            'missing_actor_fk':'ALTER TABLE business_pack_delivery_sources DROP CONSTRAINT '+quoted,
            'missing_unique':'ALTER TABLE business_pack_delivery_sources DROP CONSTRAINT uq_pack_delivery_email',
            'weak_xor':'ALTER TABLE business_pack_delivery_sources DROP CONSTRAINT ck_pack_delivery_target',
            'weak_positive':'ALTER TABLE business_pack_delivery_sources DROP CONSTRAINT ck_pack_delivery_scope',
            'weak_payload':'ALTER TABLE business_pack_delivery_sources DROP CONSTRAINT ck_pack_delivery_payload',
        }
        if fault in ('not_valid_actor_fk','cascade_actor_fk'):
            connection.exec_driver_sql('ALTER TABLE '+table+' DROP CONSTRAINT '+quoted)
            ending='ON DELETE RESTRICT NOT VALID' if fault=='not_valid_actor_fk' else 'ON DELETE CASCADE'
            connection.exec_driver_sql('ALTER TABLE '+table+' ADD CONSTRAINT '+quoted+' FOREIGN KEY(actor_user_id) REFERENCES users(id) '+ending)
        else:connection.exec_driver_sql(commands[fault])
        for key,name in (('weak_xor','ck_pack_delivery_target'),('weak_positive','ck_pack_delivery_scope'),('weak_payload','ck_pack_delivery_payload')):
            if fault==key:connection.exec_driver_sql('ALTER TABLE '+table+' ADD CONSTRAINT '+name+' CHECK(TRUE)')
        assert installation_reasons(connection)
    finally:scope.rollback()
    assert installation_reasons(connection)==[]


@pytest.mark.parametrize('prefix',['suite_pack_anchor','suite_pack_delivery','suite_private_email','suite_private_notice'])
@pytest.mark.parametrize('fault',['disabled','noop','when_false','missing_truncate'])
def test_native_named_guard_tamper_is_not_ready(db,prefix,fault):
    connection=_native(db);assert installation_reasons(connection)==[]
    table=next(spec[0] for spec in MIGRATION.SPECS if spec[1]==prefix);scope=connection.begin_nested()
    try:
        if fault=='disabled':connection.exec_driver_sql('ALTER TABLE '+table+' DISABLE TRIGGER '+prefix+'_identity')
        elif fault=='missing_truncate':connection.exec_driver_sql('DROP TRIGGER '+prefix+'_truncate ON '+table)
        elif fault=='noop':connection.exec_driver_sql('CREATE OR REPLACE FUNCTION '+prefix+'_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END; $$')
        else:
            connection.exec_driver_sql('DROP TRIGGER '+prefix+'_identity ON '+table)
            connection.exec_driver_sql('CREATE TRIGGER '+prefix+'_identity BEFORE UPDATE OR DELETE ON '+table+' FOR EACH ROW WHEN(FALSE) EXECUTE FUNCTION '+prefix+'_guard()')
        assert installation_reasons(connection)
    finally:scope.rollback()
    assert installation_reasons(connection)==[]
