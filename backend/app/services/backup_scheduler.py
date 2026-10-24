"""Optional long-running deployment worker; serverless uses an external scheduler."""

import logging
import threading
from .data_backups import run_full_due

logger = logging.getLogger(__name__)


def start_scheduler():
    stop = threading.Event()

    def loop():
        from app.db.session import SessionLocal
        from app.apps.project_management.recovery import run_due

        while not stop.is_set():
            try:
                with SessionLocal() as db:
                    run_due(db)
            except Exception:
                logger.exception("Automatic workspace savepoint failed")
            try:
                run_full_due()
            except Exception:
                logger.exception("Automatic full-system backup failed")
            stop.wait(60)

    worker = threading.Thread(target=loop, daemon=True, name="businesssuite-backups")
    worker.start()
    return stop, worker
