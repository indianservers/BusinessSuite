from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from threading import Barrier
import pytest
from sqlalchemy.orm import Session
from app.models.deployment import ScheduledJobRun
from app.models.employee import Employee
from app.models.leave import LeaveType, LeaveBalanceLedger
from app.services.scheduled_jobs import run_cron_batch


def test_scheduler_claim_is_exclusive_across_connections(db_engine):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL concurrency integration")
    barrier = Barrier(2)
    now = datetime(2099, 1, 2, 2, tzinfo=timezone.utc)
    def invoke():
        with Session(db_engine) as db:
            barrier.wait(timeout=15)
            return run_cron_batch(db, now=now)["status"]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: invoke(), range(2)))
        assert sorted(results) == ["already_running_or_completed", "completed"]
        with Session(db_engine) as db:
            row = db.query(ScheduledJobRun).one()
            assert row.attempts == 1
    finally:
        with Session(db_engine) as db:
            db.query(ScheduledJobRun).delete()
            db.commit()


def test_retry_after_business_commit_does_not_double_credit(db_engine, monkeypatch):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL crash recovery integration")
    import app.services.scheduled_jobs as jobs
    with Session(db_engine) as db:
        employee = Employee(employee_id="CRASH-RECOVERY", first_name="Crash", last_name="Recovery",
                            date_of_joining=date(2025, 1, 1), status="Active")
        leave = LeaveType(name="Crash test leave", code="CRASH", days_allowed=12, accrual_frequency="monthly", is_active=True)
        db.add_all([employee, leave])
        db.commit()
        employee_id, leave_id = employee.id, leave.id
    original = jobs.run_scheduled_leave_accruals
    def crash(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("Crash after business transaction committed")
    now = datetime(2099, 2, 1, 2, tzinfo=timezone.utc)
    try:
        with Session(db_engine) as db:
            monkeypatch.setattr(jobs, "run_scheduled_leave_accruals", crash)
            with pytest.raises(RuntimeError):
                run_cron_batch(db, now=now)
            monkeypatch.setattr(jobs, "run_scheduled_leave_accruals", original)
            assert run_cron_batch(db, now=now)["status"] == "completed"
            assert db.query(LeaveBalanceLedger).filter_by(employee_id=employee_id, transaction_type="scheduled_accrual").count() == 1
    finally:
        from app.models.leave import LeaveBalance
        with Session(db_engine) as db:
            db.query(LeaveBalanceLedger).filter_by(employee_id=employee_id).delete()
            db.query(LeaveBalance).filter_by(employee_id=employee_id).delete()
            db.query(Employee).filter_by(id=employee_id).delete()
            db.query(LeaveType).filter_by(id=leave_id).delete()
            db.query(ScheduledJobRun).delete()
            db.commit()
