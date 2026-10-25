from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pytest
from sqlalchemy.orm import Session
from app.core.config import settings, Settings
from app.models.employee import Employee
from app.models.leave import LeaveType, LeaveBalanceLedger
from app.models.deployment import CollaborationEvent, ScheduledJobRun
from app.apps.project_management.event_feed import append_event, read_events
from app.services.scheduled_jobs import run_cron_batch


@pytest.fixture
def private_storage(monkeypatch, tmp_path):
    from moto import mock_aws
    from app.core.storage import s3_client
    with mock_aws():
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(settings, "S3_BUCKET", "private-suite-test")
        monkeypatch.setattr(settings, "S3_REGION", "us-east-1")
        monkeypatch.setattr(settings, "S3_ENDPOINT_URL", None)
        monkeypatch.setattr(settings, "S3_ACCESS_KEY_ID", "testing")
        monkeypatch.setattr(settings, "S3_SECRET_ACCESS_KEY", "testing")
        s3_client.cache_clear()
        s3_client().create_bucket(Bucket=settings.S3_BUCKET)
        yield tmp_path
        s3_client.cache_clear()


def test_private_files_survive_local_loss_and_reject_traversal(private_storage):
    from app.core.storage import persist_file, upload_exists, materialize_file, FileResponse, storage_key
    target = private_storage / "employee_docs" / "one.pdf"
    target.parent.mkdir()
    target.write_bytes(b"private PDF content")
    persist_file(str(target))
    target.unlink()  # Simulate an unrelated serverless instance with no disk cache.
    assert upload_exists(str(target))
    response = FileResponse(str(target))
    assert response.status_code == 307
    assert "/api/v1/files/blob?token=" in response.headers["location"]
    materialize_file(str(target))
    assert target.read_bytes() == b"private PDF content"
    from app.core.storage import normalize_upload_references, sign_upload_references
    link = sign_upload_references("/uploads/employee_docs/one.pdf")
    assert normalize_upload_references(link) == "/uploads/employee_docs/one.pdf"
    with pytest.raises(Exception):
        storage_key(str(private_storage / ".." / "escape"))


def test_employee_upload_is_durable_and_links_are_private(client, db, superuser_headers, private_storage):
    employee = Employee(employee_id="CLOUD-FILE", first_name="Cloud", last_name="File", date_of_joining=date.today())
    db.add(employee)
    db.commit()
    response = client.post(f"/api/v1/employees/{employee.id}/documents", headers=superuser_headers,
        data={"document_type": "Identity", "document_name": "Identity PDF"},
        files={"file": ("identity.pdf", b"private content", "application/pdf")})
    assert response.status_code in {200, 201}, response.text
    assert "/api/v1/files/blob?token=" in response.json()["file_url"]
    from app.core.storage import s3_client
    objects = s3_client().list_objects_v2(Bucket=settings.S3_BUCKET)["Contents"]
    assert s3_client().get_object(Bucket=settings.S3_BUCKET, Key=objects[0]["Key"])["Body"].read() == b"private content"
    photo = client.post(f"/api/v1/employees/{employee.id}/photo", headers=superuser_headers,
                        files={"file": ("photo.png", b"PNG", "image/png")})
    assert photo.status_code == 200, photo.text
    edited = client.put(f"/api/v1/employees/{employee.id}", headers=superuser_headers,
                        json={"profile_photo_url": photo.json()["url"]})
    assert edited.status_code == 200, edited.text
    db.refresh(employee)
    assert employee.profile_photo_url.startswith("/uploads/")
    assert client.post(f"/api/v1/employees/{employee.id}/documents", data={"document_type": "Identity", "document_name": "Blocked"}, files={"file": ("blocked.pdf", b"blocked", "application/pdf")}).status_code in {401, 403}


def test_event_feed_cross_connection_and_access_revocation(db_engine):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Real PostgreSQL integration")
    try:
        with Session(db_engine) as receiver:
            cursor = read_events(receiver, {900001})["cursor"]
        with Session(db_engine) as sender:
            append_event(sender, {"type": "task.updated", "projectId": 900001, "taskId": 5})
            append_event(sender, {"type": "task.updated", "projectId": 900002, "taskId": 6})
        with Session(db_engine) as receiver:
            result = read_events(receiver, {900001}, cursor)
            assert [event["taskId"] for event in result["events"]] == [5]
            assert read_events(receiver, set(), cursor)["events"] == []
    finally:
        with Session(db_engine) as db:
            db.query(CollaborationEvent).filter(CollaborationEvent.project_id.in_([900001, 900002])).delete()
            db.commit()


def test_cron_requires_secret_and_is_not_public(client, monkeypatch):
    monkeypatch.setattr(settings, "CRON_SECRET", "a" * 40)
    assert client.get("/api/v1/internal/cron").status_code == 401
    assert client.get("/api/v1/internal/cron", headers={"Authorization": "Bearer incorrect"}).status_code == 401
    assert client.get("/api/v1/internal/jobs").status_code in {401, 403}


def test_scheduler_resumes_batches_and_does_not_credit_twice(db):
    if db.get_bind().dialect.name != "postgresql":
        pytest.skip("PostgreSQL claim integration")
    db.add_all([Employee(employee_id=f"JOB-{i}", first_name="Scheduled", last_name=str(i), date_of_joining=date(2025, 1, 1), status="Active") for i in range(3)])
    db.add(LeaveType(name="Cloud earned leave", code="CLOUD-EL", days_allowed=12, accrual_frequency="monthly", is_active=True))
    db.commit()
    now = datetime(2026, 11, 1, 2, tzinfo=timezone.utc)
    first = run_cron_batch(db, now=now, batch_size=2)
    assert first["status"] == "pending"
    assert run_cron_batch(db, now=now, batch_size=2)["status"] == "completed"
    assert run_cron_batch(db, now=now, batch_size=2)["status"] == "already_running_or_completed"
    assert db.query(LeaveBalanceLedger).filter_by(transaction_type="scheduled_accrual").count() == 3


def test_scheduler_retries_failed_and_expired_leases(db_engine, monkeypatch):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL claim integration")
    with Session(db_engine) as db:
        import app.services.scheduled_jobs as jobs
        now = datetime(2026, 11, 2, 2, tzinfo=timezone.utc)
        original = jobs.run_scheduled_leave_accruals
        def fail(*args, **kwargs):
            raise RuntimeError("Simulated provider failure")
        monkeypatch.setattr(jobs, "run_scheduled_leave_accruals", fail)
        with pytest.raises(RuntimeError):
            jobs.run_cron_batch(db, now=now)
        row = db.query(ScheduledJobRun).one()
        assert row.status == "failed"
        monkeypatch.setattr(jobs, "run_scheduled_leave_accruals", original)
        assert jobs.run_cron_batch(db, now=now)["status"] == "completed"
        row.status = "running"
        row.lease_until = now + timedelta(minutes=2)
        db.commit()
        assert jobs.run_cron_batch(db, now=now)["status"] == "already_running_or_completed"
        assert jobs.run_cron_batch(db, now=now + timedelta(minutes=3))["status"] == "completed"
        db.query(ScheduledJobRun).delete()
        db.commit()


def test_neon_pooled_connections_do_not_send_session_startup_options():
    config = Settings(_env_file=None, DATABASE_URL="postgresql://u:p@ep-test-pooler.us-east-2.aws.neon.tech/db?sslmode=require")
    assert "options" not in config.SQLALCHEMY_CONNECT_ARGS
    assert config.SQLALCHEMY_CONNECT_ARGS["prepare_threshold"] is None


def test_serverless_requires_explicit_stable_secrets():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(_env_file=None, SERVERLESS=True, DATABASE_AUTO_MIGRATE=False, SECRET_KEY="short")


def test_serverless_startup_does_not_migrate_or_seed(monkeypatch):
    import asyncio
    from app.main import app, lifespan
    monkeypatch.setattr(settings, "SERVERLESS", True)
    def forbidden(*args, **kwargs):
        raise AssertionError("Cold starts must not provision infrastructure")
    monkeypatch.setattr("app.main.os.makedirs", forbidden)
    monkeypatch.setattr("app.db.migrations.upgrade_schema", forbidden)
    async def run():
        async with lifespan(app):
            pass
    asyncio.run(run())
