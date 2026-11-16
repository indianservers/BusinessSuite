"""Opt-in Telegram-only worker sharing the API process and its application.

Each tick owns its database session; no request session crosses into this thread.
"""
import logging
import os
import socket
import threading
from dataclasses import dataclass

logger = logging.getLogger('businesssuite.power.telegram_worker')
_start_lock = threading.Lock()


@dataclass
class WorkerHandle:
    stop: threading.Event
    thread: threading.Thread


def start_worker(application, *, poll_seconds=3, error_backoff_seconds=5):
    """Start at most one live loop for this application instance."""
    if not 0.05 <= poll_seconds <= 60 or not 0.05 <= error_backoff_seconds <= 60:
        raise ValueError('Worker intervals must be between 0.05 and 60 seconds')
    with _start_lock:
        current = getattr(application.state, 'telegram_worker', None)
        if current and current.thread.is_alive():
            return current
        stop = threading.Event()
        worker_id = f'{socket.gethostname()}:{os.getpid()}:telegram-api'

        def loop():
            from app.db.session import SessionLocal
            from app.db.tenant import all_company_job
            from app.apps.power_apps.worker import worker_tick
            while not stop.is_set():
                failed = False

                def one_database():
                    nonlocal failed
                    if stop.is_set():
                        return False
                    try:
                        with SessionLocal() as db:
                            try:
                                return worker_tick(db, worker_id, telegram_only=True, application=application)
                            except Exception:
                                db.rollback()
                                raise
                    except Exception as exc:
                        failed = True
                        logger.warning('Telegram worker tick failed error_type=%s', type(exc).__name__)
                        return False

                try:
                    outcome = all_company_job(one_database)()
                    worked = any(outcome['results']) if isinstance(outcome, dict) else outcome
                except Exception as exc:
                    failed, worked = True, False
                    logger.warning('Telegram worker routing failed error_type=%s', type(exc).__name__)
                stop.wait(error_backoff_seconds if failed else 0.05 if worked else poll_seconds)

        thread = threading.Thread(target=loop, daemon=True, name='businesssuite-telegram')
        handle = WorkerHandle(stop, thread)
        application.state.telegram_worker = handle
        thread.start()
        return handle


def stop_worker(handle, *, timeout=75):
    """Request drain within the shutdown budget; never replay an unfinished tick."""
    if not 0 <= timeout <= 75:
        raise ValueError('Shutdown timeout must be between 0 and 75 seconds')
    handle.stop.set()
    handle.thread.join(timeout=timeout)
    drained = not handle.thread.is_alive()
    if not drained:
        logger.warning('Telegram worker did not drain within shutdown budget; in-flight work requires reconciliation')
    return drained
