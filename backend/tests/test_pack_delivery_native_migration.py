"""Real deployed119 -> Restaurant120 -> common121 on a guarded native DB."""
from pathlib import Path
import hashlib,json,runpy
import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_pack_delivery_sources import queued,retail_setup,scenario,catalog,directory_identity
from app.business_packs.models import PackRecordOwnership
from app.business_packs.delivery_source_models import PackDeliverySource
from app.models.email_outbox import EmailOutbox

ROOT=Path(__file__).parents[1]
REV119='pg_20261116_119_cash_intent'
REV121='pg_20261116_121_delivery_sources'


def _native(engine):
    if engine.dialect.name!='postgresql':pytest.skip('Actual PostgreSQL migration/trigger proof')
    url=make_url(engine.url if hasattr(engine,'url') else engine.engine.url)
    assert url.host in {'localhost','127.0.0.1','::1'}
    assert url.database.startswith('business_suite_') and url.database.endswith('_test')


def _fingerprints(connection,excluded):
    inspector=sa.inspect(connection);result={};columns_by_table=inspector.get_multi_columns()
    for name in inspector.get_table_names():
        if name in excluded:continue
        columns=[(row['name'],str(row['type']),row['nullable'],str(row.get('default'))) for row in columns_by_table[(None,name)]]
        quoted=connection.dialect.identifier_preparer.quote(name)
        rows=sorted(json.dumps(dict(row),sort_keys=True,default=str) for row in connection.exec_driver_sql('SELECT * FROM '+quoted).mappings())
        result[name]=(columns,hashlib.sha256(json.dumps(rows).encode()).hexdigest())
    return result


def test_actual_full_native_119_120_121_upgrade_repeat_preserves_original_rows(db):
    _native(db.get_bind())
    assert (ROOT/'alembic_postgresql/versions/pg_20261116_120_rest_split.py').exists()
    restaurant=runpy.run_path(str(ROOT/'alembic_postgresql/versions/pg_20261116_120_rest_split.py'))
    excluded={name for name,_,_ in restaurant['_DDL']['postgresql']}|{'business_pack_delivery_sources','alembic_version'}
    connection=db.connection()
    transaction=connection.begin_nested()
    try:
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM business_pack_record_ownership'))==0
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM business_pack_delivery_sources'))==0
        config=Config(str(ROOT/'alembic.ini'));config.attributes['connection']=connection
        command.downgrade(config,REV119)
        assert connection.scalar(sa.text('SELECT version_num FROM alembic_version'))==REV119
        before=_fingerprints(connection,excluded)
        command.upgrade(config,REV121)
        assert connection.scalar(sa.text('SELECT version_num FROM alembic_version'))==REV121
        command.upgrade(config,REV121)
        migration=runpy.run_path(str(ROOT/'alembic_postgresql/versions/pg_20261116_121_delivery_sources.py'))
        with Operations.context(MigrationContext.configure(connection)):
            migration['upgrade']();migration['upgrade']()
        assert _fingerprints(connection,excluded)==before
        inspector=sa.inspect(connection)
        assert inspector.has_table('business_pack_delivery_sources')
        foreign_keys=inspector.get_foreign_keys('business_pack_delivery_sources')
        assert any(row['constrained_columns']==['actor_user_id'] and row['referred_table']=='users'
            and row['options'].get('ondelete')=='RESTRICT' for row in foreign_keys)
        assert any(row['constrained_columns']==['context_id','company_id','branch_id']
            and row['referred_table']=='business_pack_contexts' for row in foreign_keys)
        assert {tuple(row['column_names']) for row in inspector.get_unique_constraints('business_pack_delivery_sources')} >= {('email_outbox_id',),('notification_id',)}
        assert 'ck_pack_delivery_target' in {row['name'] for row in inspector.get_check_constraints('business_pack_delivery_sources')}
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM business_pack_delivery_sources'))==0
        assert len(before)>800
    finally:transaction.rollback()


def test_actual_private_native_producer_has_retained_db_guard_and_dispatch(db,queued,monkeypatch):
    _native(db.get_bind())
    setup,rows=queued
    assert len(rows)==5
    ids=[row.id for row in rows]
    assert db.query(PackDeliverySource).filter(PackDeliverySource.email_outbox_id.in_(ids)).count()==5
    target=rows[0]
    from app.models.user import User
    issuer=db.query(PackDeliverySource.actor_user_id).filter_by(email_outbox_id=target.id).one()[0]
    other=db.query(User.id).filter(User.id!=issuer).first()[0]
    notice=db.query(PackDeliverySource).filter(PackDeliverySource.notification_id.is_not(None)).first()
    assert notice is not None
    attempts=[('DELETE FROM business_pack_record_ownership WHERE resource_table=\'email_outbox\' AND resource_key=:key',{'key':str(target.id)}),
        ('UPDATE business_pack_delivery_sources SET source_key=\'999999\' WHERE email_outbox_id=:id',{'id':target.id}),
        ('UPDATE business_pack_delivery_sources SET actor_user_id=:actor WHERE email_outbox_id=:id',{'actor':other,'id':target.id}),
        ('UPDATE email_outbox SET body=\'Counterfeit payload\' WHERE id=:id',{'id':target.id}),
        ('UPDATE notifications SET message=\'Counterfeit preview\' WHERE id=:id',{'id':notice.notification_id}),
        ('UPDATE notifications SET channels=CAST(\'["email"]\' AS JSON) WHERE id=:id',{'id':notice.notification_id}),
        ('DELETE FROM notifications WHERE id=:id',{'id':notice.notification_id}),
        ('TRUNCATE business_pack_delivery_sources',{})]
    for sql,params in attempts:
        with pytest.raises(DBAPIError):
            with db.begin_nested():db.connection().execute(sa.text(sql),params)
    db.connection().execute(sa.text('UPDATE notifications SET is_read=true,read_at=CURRENT_TIMESTAMP WHERE id=:id'),{'id':notice.notification_id})
    migration=runpy.run_path(str(ROOT/'alembic_postgresql/versions/pg_20261116_121_delivery_sources.py'))
    with Operations.context(MigrationContext.configure(db.connection())):
        with pytest.raises(RuntimeError,match='Retained private origin'):migration['downgrade']()
        migration['upgrade']()
    sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(1) or 'fake-provider')
    from app.services.email_dispatch import _deliver
    for row in rows:_deliver(db,row)
    assert len(sent)==5 and all(row.status=='accepted' for row in rows)
    assert db.query(PackDeliverySource).filter(PackDeliverySource.email_outbox_id.in_(ids)).count()==5
