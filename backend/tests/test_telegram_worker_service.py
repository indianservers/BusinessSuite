import threading
import time
import asyncio
from contextvars import ContextVar

import pytest
from fastapi import FastAPI

from app.apps.power_apps import telegram_worker_service as service


def sessions(monkeypatch):
    opened = []

    class Session:
        def __init__(self):
            self.closed = False
            self.rolled_back = False
            opened.append(self)

        def __enter__(self):
            return self

        def rollback(self):
            self.rolled_back = True

        def __exit__(self, *_):
            self.closed = True

    monkeypatch.setattr('app.db.session.SessionLocal', Session)
    return opened


def test_one_shared_application_loop_drains_and_stops_without_second_tick(monkeypatch):
    app = FastAPI()
    opened = sessions(monkeypatch)
    entered, release = threading.Event(), threading.Event()
    calls = []
    monkeypatch.setattr('app.db.tenant.all_company_job', lambda callback: callback)

    def tick(db, worker_id, *, telegram_only, application):
        calls.append((db, worker_id, telegram_only, application))
        entered.set()
        assert release.wait(5)
        return True

    monkeypatch.setattr('app.apps.power_apps.worker.worker_tick', tick)
    handle = service.start_worker(app)
    try:
        assert entered.wait(5)
        assert service.start_worker(app) is handle
        handle.stop.set()
        assert handle.thread.is_alive()  # Current tick drains before shutdown.
    finally:
        release.set()
        service.stop_worker(handle)
    assert not handle.thread.is_alive()
    assert len(calls) == 1 and calls[0][2:] == (True, app)
    assert len(opened) == 1 and opened[0].closed


def test_errors_are_sanitized_retried_and_each_tick_gets_its_own_session(monkeypatch, caplog):
    app = FastAPI()
    opened = sessions(monkeypatch)
    monkeypatch.setattr('app.db.tenant.all_company_job', lambda callback: callback)
    attempts = []

    def tick(db, worker_id, **kwargs):
        attempts.append(db)
        if len(attempts) == 1:
            raise RuntimeError('sensitive-provider-url-and-token')
        app.state.telegram_worker.stop.set()
        return False

    monkeypatch.setattr('app.apps.power_apps.worker.worker_tick', tick)
    handle = service.start_worker(app, poll_seconds=0.05, error_backoff_seconds=0.05)
    handle.thread.join(5)
    try:
        assert not handle.thread.is_alive()
        assert len(opened) == 2 and opened[0] is not opened[1]
        assert all(db.closed for db in opened)
        assert opened[0].rolled_back and not opened[1].rolled_back
        assert 'error_type=RuntimeError' in caplog.text
        assert 'sensitive-provider' not in caplog.text
    finally:
        service.stop_worker(handle)


def test_tenant_router_owns_context_and_sessions_for_each_database(monkeypatch):
    app = FastAPI()
    opened = sessions(monkeypatch)
    tenant = ContextVar('test_telegram_worker_tenant', default=None)
    routed, seen = [], []

    def all_company_job(callback):
        def run():
            results = []
            for workspace in ['legacy', 'customer-workspace']:
                token = tenant.set(workspace)
                try:
                    routed.append(workspace)
                    results.append(callback())
                finally:
                    tenant.reset(token)
            return {'results': results}
        return run

    def tick(db, worker_id, **kwargs):
        seen.append((tenant.get(), db))
        if len(seen) == 2:
            app.state.telegram_worker.stop.set()
        return False

    monkeypatch.setattr('app.db.tenant.all_company_job', all_company_job)
    monkeypatch.setattr('app.apps.power_apps.worker.worker_tick', tick)
    handle = service.start_worker(app)
    handle.thread.join(5)
    try:
        assert not handle.thread.is_alive()
        assert routed == ['legacy', 'customer-workspace']
        assert [name for name, _ in seen] == routed
        assert len(opened) == 2 and seen[0][1] is not seen[1][1]
        assert all(db.closed for db in opened) and tenant.get() is None
    finally:
        service.stop_worker(handle)


def test_shutdown_budget_returns_while_stuck_tick_remains_and_does_not_start_replacement(monkeypatch, caplog):
    app = FastAPI()
    opened = sessions(monkeypatch)
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setattr('app.db.tenant.all_company_job', lambda callback: callback)

    def tick(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return True

    monkeypatch.setattr('app.apps.power_apps.worker.worker_tick', tick)
    handle = service.start_worker(app)
    try:
        assert entered.wait(5)
        started = time.monotonic()
        assert service.stop_worker(handle, timeout=0.05) is False
        assert time.monotonic() - started < 1
        assert handle.stop.is_set() and handle.thread.is_alive()
        assert service.start_worker(app) is handle
        assert 'in-flight work requires reconciliation' in caplog.text
    finally:
        release.set()
        assert service.stop_worker(handle, timeout=5) is True
    assert len(opened) == 1 and opened[0].closed


@pytest.mark.parametrize('enabled', [False, True])
def test_api_lifespan_opt_in_works_without_a_power_apps_app_module(monkeypatch, tmp_path, enabled):
    from app.main import lifespan
    from app.core.config import settings
    for key, value in {'ENVIRONMENT': 'production', 'SERVERLESS': False,
            'DATABASE_AUTO_MIGRATE': False, 'POWER_TELEGRAM_WORKER_ENABLED': enabled,
            'EMAIL_WORKER_ENABLED': False, 'CALENDAR_SYNC_WORKER_ENABLED': False,
            'ACCOUNTING_SYNC_WORKER_ENABLED': False, 'BUSINESSSUITE_BACKUP_SCHEDULER': False,
            'UPLOAD_DIR': str(tmp_path)}.items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr('app.main.is_app_enabled', lambda module: False)

    class Session:
        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr('app.db.session.SessionLocal', Session)
    for path in ['app.db.init_common_db.init_common_db',
            'app.apps.business_os.services.module_service.ensure_business_os_seed',
            'app.apps.automation.schema.ensure_automation_schema',
            'app.apps.customization.schema.ensure_customization_schema',
            'app.apps.communication.schema.ensure_communication_schema',
            'app.apps.analytics.schema.ensure_analytics_schema',
            'app.apps.ai_copilot.schema.ensure_ai_copilot_schema',
            'app.ai_agents.services.registry.AiAgentRegistryService.ensure_seed_data',
            'app.ai_agents.tools.ai_tool_registry_service.AiToolRegistryService.ensure_seed_data']:
        monkeypatch.setattr(path, lambda *args, **kwargs: None)

    async def platform_checks():
        await asyncio.Event().wait()

    monkeypatch.setattr('app.platform_owner.worker.run', platform_checks)
    app = FastAPI()
    marker, started, stopped = object(), [], []
    monkeypatch.setattr(service, 'start_worker', lambda application: started.append(application) or marker)
    monkeypatch.setattr(service, 'stop_worker', lambda handle: stopped.append(handle) or True)

    async def run():
        async with lifespan(app):
            assert started == ([app] if enabled else [])
            assert not stopped

    asyncio.run(run())
    assert stopped == ([marker] if enabled else [])
