from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import uuid
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import event, text,create_engine,select,func
from pathlib import Path
from app.crud import crud_payroll
from app.models.payroll import PayrollRun, PayrollRecord
from tests.test_payroll_qa_remaining import setup_employee



@pytest.fixture
def payroll_engine(db_engine):
    """Independent commits may never leak demo roles/runs into later tests.

    Use a genuinely fresh owned database and the deployed migration chain. No
    connection to the suite's shared source database is terminated or cloned.
    """
    source=db_engine.url
    if source.get_backend_name()!='postgresql':pytest.skip('Requires independent PostgreSQL connections')
    if (source.host not in {'localhost','127.0.0.1','::1'} or not (source.database or '').startswith('business_suite_')
            or not source.database.endswith('_test')):
        raise RuntimeError('Payroll concurrency requires the guarded local disposable test database')
    from app.models.user import User,Role
    models=(Role,User,PayrollRun)
    def source_counts():
        with db_engine.connect() as connection:
            return tuple(connection.scalar(select(func.count()).select_from(model.__table__)) for model in models)
    before=source_counts()
    name='business_suite_payroll_race_'+uuid.uuid4().hex+'_test'
    assert name!=source.database
    admin=create_engine(source.set(database='postgres'),isolation_level='AUTOCOMMIT',hide_parameters=True)
    target=create_engine(source.set(database=name),connect_args={'options':'-c timezone=UTC -c lock_timeout=20000 -c statement_timeout=30000'},hide_parameters=True)
    created=False
    try:
        with admin.connect() as connection:
            quoted=connection.dialect.identifier_preparer.quote_identifier(name)
            connection.exec_driver_sql(f'CREATE DATABASE {quoted}')
            created=True
        from alembic import command
        from alembic.config import Config
        config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
        # Alembic owns its transaction, including the frozen baseline's
        # required autocommit block; never wrap migration in an outer BEGIN.
        with target.connect() as connection:
            config.attributes['connection']=connection
            command.upgrade(config,'head')
            # Match the native shared test baseline without borrowing its rows.
            from app.models.company import Company
            connection.execute(Company.__table__.insert().values(id=1,name='Integration Test Company'))
            connection.exec_driver_sql("SELECT setval(pg_get_serial_sequence('companies','id'),1,true)")
            connection.commit()
        yield target
    finally:
        target.dispose()
        if created:
            with admin.connect() as connection:
                quoted=connection.dialect.identifier_preparer.quote_identifier(name)
                connection.exec_driver_sql(f'DROP DATABASE {quoted} WITH (FORCE)')
        admin.dispose()
        assert source_counts()==before,'Independent payroll commits escaped into shared role/user/run tables'


@pytest.mark.parametrize('workers',[2,4])
def test_postgresql_concurrent_same_scope_generation(payroll_engine,workers,record_property):
    db_engine=payroll_engine
    if db_engine.dialect.name!='postgresql':pytest.skip('Requires independent PostgreSQL connections')
    category='QA-CONCURRENT-'+uuid.uuid4().hex[:10]
    # These rows are committed only inside the runner's new disposable database.
    with Session(db_engine) as seed:
        employee,period,actor=setup_employee(seed,category)
        employee_id,actor_id=employee.id,actor.id
    start=Barrier(workers)
    def generate(_):
        with Session(db_engine) as session:
            start.wait(timeout=20)
            backend=session.scalar(text('SELECT pg_backend_pid()'))
            run=crud_payroll.run_payroll(session,5,2026,actor_id,force_run=True,employee_category=category)
            return run.id,backend
    with ThreadPoolExecutor(max_workers=workers) as pool: results=list(pool.map(generate,range(workers)))
    record_property('actual',str(results));record_property('expected','One shared run ID, one payroll record')
    with Session(db_engine) as verify:
        ids=[value[0] for value in results]
        assert len(set(ids))==1
        assert len({value[1] for value in results})==workers
        assert verify.query(PayrollRun).filter_by(employee_category=category).count()==1
        assert verify.query(PayrollRecord).filter_by(payroll_run_id=ids[0],employee_id=employee_id).count()==1


def test_postgresql_generation_rechecks_status_after_concurrent_lock(payroll_engine):
    db_engine=payroll_engine
    if db_engine.dialect.name!='postgresql':pytest.skip('Requires independent PostgreSQL connections')
    category='QA-LOCK-RACE-'+uuid.uuid4().hex[:10]
    with Session(db_engine) as seed:
        employee,period,actor=setup_employee(seed,category)
        actor_id=actor.id
        run=crud_payroll.run_payroll(seed,5,2026,actor_id,force_run=True,employee_category=category)
        run_id=run.id
    entered=Event()
    def observe(conn,cursor,statement,parameters,context,executemany):
        if 'FROM payroll_runs' in statement and 'FOR UPDATE' in statement:entered.set()
    with Session(db_engine) as owner:
        locked=owner.query(PayrollRun).filter_by(id=run_id).with_for_update().one()
        event.listen(db_engine,'before_cursor_execute',observe)
        try:
            def regenerate():
                with Session(db_engine) as contender:
                    return crud_payroll.run_payroll(contender,5,2026,actor_id,force_run=True,employee_category=category)
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(regenerate)
                assert entered.wait(timeout=20)
                locked.status='locked';owner.commit()
                with pytest.raises(ValueError,match='cannot be recalculated'):pending.result(timeout=20)
        finally:event.remove(db_engine,'before_cursor_execute',observe)
    with Session(db_engine) as verify:assert verify.get(PayrollRun,run_id).status=='locked'
