"""Run with python -m app.apps.power_apps.worker; SIGINT/SIGTERM drain the current local step."""

import argparse
import logging
import os
import signal
import socket
import time
from datetime import timedelta
from app.db.session import SessionLocal
from app.apps.power_apps.runtime import claim, process, tick, now
from app.apps.power_apps.runtime_triggers import scheduler_tick
from app.apps.power_apps.runtime_models import AutomationWorker
from app.db.base import Base  # load registered metadata

logger = logging.getLogger("businesssuite.power.runtime")
STOP = False


def stop(*_):
    global STOP
    STOP = True


def worker_tick(db, worker_id):
    record = db.get(AutomationWorker, worker_id)
    if not record:
        record = AutomationWorker(id=worker_id, heartbeat_at=now(), processed=0)
        db.add(record)
    record.heartbeat_at = now()
    record.status = "running"
    db.commit()
    if not record.scheduler_at or now() - record.scheduler_at.replace(
        tzinfo=record.scheduler_at.tzinfo or now().tzinfo
    ) > timedelta(seconds=5):
        tick(db)
        scheduler_tick(db)
        from app.apps.power_apps.runtime_retention import purge_payloads

        purge_payloads(db)
        record.scheduler_at = now()
        db.commit()
    work = claim(db, worker_id)
    if not work:
        return False
    result = process(db, *work)
    record = db.get(AutomationWorker, worker_id)
    record.processed += 1
    record.heartbeat_at = now()
    db.commit()
    logger.info(
        "power_automation_job",
        extra={"job_id": work[0], "result": result, "worker": worker_id},
    )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poll-seconds", type=float, default=1)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not 0.05 <= args.poll_seconds <= 60:
        parser.error("poll interval must be 0.05–60 seconds")
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    while not STOP:
        with SessionLocal() as db:
            try:
                worked = worker_tick(db, worker_id)
            except Exception as exc:
                db.rollback()
                logger.error(
                    "power_automation_worker_failure error_type=%s", type(exc).__name__
                )
                worked = False
                if args.once:
                    raise SystemExit(1)
        if args.once:
            break
        if not worked:
            time.sleep(args.poll_seconds)
    with SessionLocal() as db:
        record = db.get(AutomationWorker, worker_id)
        if record:
            record.status = "stopped"
            record.heartbeat_at = now()
            db.commit()


if __name__ == "__main__":
    main()
