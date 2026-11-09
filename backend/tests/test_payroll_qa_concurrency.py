from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import uuid
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import event, text
from app.crud import crud_payroll
from app.models.payroll import PayrollRun, PayrollRecord
from tests.test_payroll_qa_remaining import setup_employee

@pytest.mark.parametrize('workers',[2,4])
def test_postgresql_concurrent_same_scope_generation(db_engine,workers,record_property):
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


def test_postgresql_generation_rechecks_status_after_concurrent_lock(db_engine):
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
