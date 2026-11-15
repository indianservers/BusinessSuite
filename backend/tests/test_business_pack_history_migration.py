from pathlib import Path
import os
import runpy
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

PATH = Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261114_106_pack_history.py'


def test_verified_draft_edit_backfill_and_ambiguous_history_are_distinct():
    engine = sa.create_engine('sqlite://'); metadata = sa.MetaData()
    contexts = sa.Table('business_pack_contexts', metadata, sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('company_id', sa.Integer), sa.Column('branch_id', sa.Integer), sa.Column('activation_id', sa.Integer),
        sa.Column('pack_key', sa.String), sa.Column('pack_version', sa.Integer), sa.Column('state', sa.String), sa.Column('revision', sa.Integer))
    audits = sa.Table('suite_access_audit', metadata, sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('company_id', sa.Integer), sa.Column('operation', sa.String), sa.Column('before_json', sa.JSON), sa.Column('after_json', sa.JSON), sa.Column('outcome', sa.String))
    anchors = sa.Table('business_pack_record_ownership', metadata, sa.Column('id', sa.Integer, primary_key=True), sa.Column('context_id', sa.Integer))
    metadata.create_all(engine)
    migration = runpy.run_path(str(PATH))
    with engine.begin() as connection:
        rows = [dict(id=i, company_id=1, branch_id=11, activation_id=1, pack_key='hospital', pack_version=1,
            state='active' if i == 4 else 'draft', revision=3 if i in (1, 2, 6) else 1) for i in range(1, 8)]
        connection.execute(contexts.insert(), rows)
        creation = {**rows[0], 'state': 'draft', 'revision': 1}
        changes = [dict(company_id=1, operation='settings.business-packs.context.drafted', before_json=None, after_json=creation, outcome='success')]
        for old in (1, 2):
            changes.append(dict(company_id=1, operation='settings.business-packs.master.shared', before_json={'context_revision': old},
                after_json={'context_revision': old + 1, 'availability': {'company_id': 1, 'branch_id': 11, 'context_id': 1, 'resource_table': 'employees'}}, outcome='success'))
        changes.append(dict(company_id=1, operation='settings.business-packs.context.activated', before_json=None, after_json={'id': 5}, outcome='success'))
        connection.execute(audits.insert(), changes)
        connection.execute(anchors.insert().values(context_id=7))
        with Operations.context(MigrationContext.configure(connection)):
            migration['upgrade']()
            result = dict(connection.exec_driver_sql('SELECT id,ever_activated FROM business_pack_contexts').all())
            assert result == {1: 0, 2: 1, 3: 0, 4: 1, 5: 1, 6: 1, 7: 1}
            # Future draft configuration is not reinterpreted on repeated upgrade.
            connection.exec_driver_sql("UPDATE business_pack_contexts SET revision=9 WHERE id=3")
            migration['upgrade']()
            assert connection.exec_driver_sql('SELECT ever_activated FROM business_pack_contexts WHERE id=3').scalar_one() == 0
        connection.exec_driver_sql("UPDATE business_pack_contexts SET state='active' WHERE id=3")
        connection.exec_driver_sql("UPDATE business_pack_contexts SET state='draft' WHERE id=3")
        assert connection.exec_driver_sql('SELECT ever_activated FROM business_pack_contexts WHERE id=3').scalar_one() == 1
        with pytest.raises(IntegrityError):
            with connection.begin_nested(): connection.exec_driver_sql('UPDATE business_pack_contexts SET ever_activated=0 WHERE id=3')
        with pytest.raises(IntegrityError):
            with connection.begin_nested(): connection.exec_driver_sql('UPDATE business_pack_contexts SET ever_activated=2 WHERE id=3')
    engine.dispose()


def test_actual_postgresql_core_transition_cannot_erase_activation_history(request):
    if not os.environ.get('TEST_DATABASE_URL'):
        pytest.skip('Disposable PostgreSQL migration chain required')
    db = request.getfixturevalue('db')
    from app.models.company import Branch
    from app.business_packs.models import PackActivation, PackContext
    connection = db.connection()
    assert connection.dialect.name == 'postgresql'
    branch = connection.execute(Branch.__table__.insert().values(company_id=1, name='History trigger fixture').returning(Branch.id)).scalar_one()
    activation = connection.execute(PackActivation.__table__.insert().values(company_id=1, pack_key='hospital', pack_version=1, state='active').returning(PackActivation.id)).scalar_one()
    ident = connection.execute(PackContext.__table__.insert().values(company_id=1, branch_id=branch, activation_id=activation,
        pack_key='hospital', pack_version=1, state='draft').returning(PackContext.id)).scalar_one()
    table = PackContext.__table__
    connection.execute(table.update().where(table.c.id == ident).values(state='active'))
    connection.execute(table.update().where(table.c.id == ident).values(state='draft'))
    assert connection.execute(sa.select(table.c.ever_activated).where(table.c.id == ident)).scalar_one() is True
    with pytest.raises(sa.exc.DBAPIError):
        with connection.begin_nested(): connection.execute(table.update().where(table.c.id == ident).values(ever_activated=False))
