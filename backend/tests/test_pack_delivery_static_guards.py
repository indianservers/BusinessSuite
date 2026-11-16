"""Actual SQL only: no ORM listener, fake authority flag or application import."""
from datetime import datetime, timedelta
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
import importlib.util
from pathlib import Path
_spec=importlib.util.spec_from_file_location('static_delivery_121',Path(__file__).parents[1]/'alembic_postgresql/versions/pg_20261116_121_delivery_sources.py')
_migration=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_migration)
install_delivery_guards,SPECS=_migration.install_delivery_guards,_migration.SPECS


def schema(connection):
    metadata = sa.MetaData()
    companies = sa.Table('companies', metadata, sa.Column('id', sa.Integer, primary_key=True))
    users = sa.Table('users', metadata, sa.Column('id', sa.Integer, primary_key=True))
    branches = sa.Table('branches', metadata, sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('company_id', sa.Integer, sa.ForeignKey('companies.id', ondelete='CASCADE')))
    contexts = sa.Table('business_pack_contexts', metadata, sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('company_id', sa.Integer, sa.ForeignKey('companies.id', ondelete='RESTRICT')),
        sa.Column('branch_id', sa.Integer, sa.ForeignKey('branches.id', ondelete='RESTRICT')),
        sa.UniqueConstraint('id', 'company_id', 'branch_id'))
    integers = {'id','company_id','branch_id','context_id','revision','pack_version','email_outbox_id',
        'notification_id','actor_user_id','recipient_user_id','organization_id','user_id','related_entity_id','attempts'}
    dates = {'created_at','accepted_at','read_at'}
    booleans = {'is_html','is_read'}
    tables = {}
    for name, _, frozen, mutable, _ in SPECS:
        columns = []
        for field in frozen + mutable:
            kind = sa.Integer if field in integers else sa.DateTime if field in dates else sa.Boolean if field in booleans else sa.JSON if field == 'channels' else sa.Text
            fk = None
            if name == 'notifications':
                fk = {'company_id': ('companies.id','SET NULL'), 'user_id': ('users.id','CASCADE')}.get(field)
            elif name == 'business_pack_record_ownership':
                fk = {'company_id': ('companies.id','RESTRICT'), 'branch_id': ('branches.id','RESTRICT')}.get(field)
            elif name == 'business_pack_delivery_sources':
                fk = {'email_outbox_id': ('email_outbox.id','RESTRICT'), 'notification_id': ('notifications.id','RESTRICT'),
                    'actor_user_id': ('users.id','RESTRICT'), 'recipient_user_id': ('users.id','RESTRICT')}.get(field)
            args = [sa.ForeignKey(fk[0], ondelete=fk[1])] if fk else []
            columns.append(sa.Column(field, kind, *args, primary_key=field == 'id'))
        if name in {'business_pack_record_ownership','business_pack_delivery_sources'}:
            columns.append(sa.ForeignKeyConstraint(['context_id','company_id','branch_id'],
                ['business_pack_contexts.id','business_pack_contexts.company_id','business_pack_contexts.branch_id'],ondelete='RESTRICT'))
        tables[name] = sa.Table(name, metadata, *columns)
    metadata.create_all(connection)
    for table in (companies, users):
        connection.execute(table.insert(), [{'id':1},{'id':2}])
    connection.execute(branches.insert(), [{'id':1,'company_id':1},{'id':2,'company_id':2}])
    connection.execute(contexts.insert(), [{'id':1,'company_id':1,'branch_id':1},{'id':2,'company_id':2,'branch_id':2}])
    now = datetime(2026,11,16,0,0)
    for name in ('email_outbox','notifications'):
        row = {column.name: (now if column.name in dates else 1 if column.name in integers else
            False if column.name in booleans else ['in_app'] if column.name == 'channels' else 'Original private payload')
            for column in tables[name].columns}
        row.update(id=1)
        if name == 'email_outbox':
            row.update(status='queued', attempts=0, accepted_at=None)
        else:
            row.update(is_read=False, read_at=None)
        connection.execute(tables[name].insert().values(**row))
        legacy = {**row, 'id':2}
        legacy.update({'organization_id':2} if name=='email_outbox' else {'company_id':2,'user_id':2})
        connection.execute(tables[name].insert().values(**legacy))
    source = dict(id=1,company_id=1,branch_id=1,context_id=1,resource_table='appointments',
        resource_key='501',source='created',revision=1,created_at=now)
    connection.execute(tables['business_pack_record_ownership'].insert().values(**source))
    certificate = dict(id=1,email_outbox_id=1,notification_id=None,company_id=1,branch_id=1,context_id=1,
        pack_key='hospital',pack_version=1,source_table='appointments',source_key='501',source_kind='assignment',
        module='srm',actor_user_id=1,recipient_user_id=1,recipient_email='patient@example.invalid',payload_sha256='a'*64,created_at=now)
    connection.execute(tables['business_pack_delivery_sources'].insert(),
        [certificate,{**certificate,'id':2,'email_outbox_id':None,'notification_id':1}])
    return metadata, tables


@pytest.fixture
def sql():
    engine = sa.create_engine('sqlite://')
    @sa.event.listens_for(engine, 'connect')
    def fk(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
    with engine.begin() as connection:
        metadata, tables = schema(connection)
        install_delivery_guards(connection)
        install_delivery_guards(connection)
        yield connection, metadata, tables
    engine.dispose()


@pytest.mark.parametrize('table,field', [(table, field) for table,_,fields,_,_ in SPECS for field in fields])
def test_raw_sql_cannot_change_any_certified_field(sql, table, field):
    connection, _, tables = sql
    target = tables[table]
    kind = target.c[field].type
    value = datetime(2026,11,17) if isinstance(kind,sa.DateTime) else True if isinstance(kind,sa.Boolean) else 99 if isinstance(kind,sa.Integer) else ['email'] if isinstance(kind,sa.JSON) else 'Changed source or body'
    with pytest.raises(IntegrityError, match='immutable'), connection.begin_nested():
        connection.execute(target.update().where(target.c.id==1).values(**{field:value}))


@pytest.mark.parametrize('table', [table for table,*_ in SPECS])
def test_raw_sql_cannot_delete_certified_target_or_anchor(sql, table):
    connection, _, tables = sql
    with pytest.raises(IntegrityError, match='retained'), connection.begin_nested():
        connection.execute(tables[table].delete().where(tables[table].c.id==1))


@pytest.mark.parametrize('parent', ['users','companies','branches','business_pack_contexts'])
def test_original_native_parent_cascade_or_nulling_cannot_erase_history(sql, parent):
    connection, metadata, _ = sql
    table = metadata.tables[parent]
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(table.delete().where(table.c.id==1))


def test_legitimate_provider_ack_and_notification_reads_remain_native(sql):
    connection, _, tables = sql
    email, note = tables['email_outbox'], tables['notifications']
    now = datetime(2026,11,16,1,0)
    connection.execute(email.update().where(email.c.id==1).values(status='accepted',provider_message_id='provider-ack',
        attempts=2,error=None,accepted_at=now))
    connection.execute(note.update().where(note.c.id==1).values(is_read=True,read_at=now))
    assert connection.execute(sa.select(email.c.status,email.c.body).where(email.c.id==1)).one()==('accepted','Original private payload')
    assert connection.execute(sa.select(note.c.is_read,note.c.read_at).where(note.c.id==1)).one()==(True,now)


def test_genuinely_unowned_legacy_rows_can_change_and_delete(sql):
    connection, _, tables = sql
    for name, field in [('email_outbox','body'),('notifications','message')]:
        table=tables[name]
        connection.execute(table.update().where(table.c.id==2).values(**{field:'Native legacy update'}))
        connection.execute(table.delete().where(table.c.id==2))
        assert connection.scalar(sa.select(sa.func.count()).select_from(table).where(table.c.id==2))==0


def test_guard_install_does_not_rewrite_old_payloads_or_anchors(sql):
    connection, _, tables = sql
    before={name:list(connection.execute(sa.select(table)).mappings()) for name,table in tables.items()}
    install_delivery_guards(connection)
    after={name:list(connection.execute(sa.select(table)).mappings()) for name,table in tables.items()}
    assert before==after
