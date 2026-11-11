"""Standalone durable operator worker; no Redis required. Run from backend."""
import argparse
import sys
import time
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.base import Base  # noqa: F401 - register configured application models
from app.db.session import SessionLocal
from app.ai_operator.jobs import process_batch


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--suite-only", action="store_true",help="Process only explicitly approved suite actions; do not dispatch unrelated scheduled jobs")
    args = parser.parse_args()
    while True:
        with SessionLocal() as db:
            result = [] if args.suite_only else process_batch(db, limit=max(1, min(args.batch_size, 100)))
        from app.ai_operator.suite import process_suite_batch
        from app.main import app
        with SessionLocal() as db:
            suite_count = asyncio.run(process_suite_batch(db, app, limit=max(1, min(args.batch_size, 100))))
        if suite_count:
            print({'suite_processed': suite_count}, flush=True)
        if args.suite_only:
            from app.ai_operator.workflows import process_suite_children
            with SessionLocal() as db:
                children=process_suite_children(db,limit=max(1,min(args.batch_size,100)))
            if children:print({'suite_child_jobs':children},flush=True)
        # Explicitly activated agent schedules only prepare scoped conversations.
        # They cannot approve or enqueue their proposed business changes.
        from app.ai_operator.agent_schedules import dispatch as schedule_agents
        with SessionLocal() as db:
            scheduled=asyncio.run(schedule_agents(db,app,limit=5))
        if scheduled['processed']:print({'agent_schedules_prepared':scheduled['processed']},flush=True)
        from app.ai_operator.agent_workflows import dispatch as orchestrate_agents
        with SessionLocal() as db:
            orchestrated=asyncio.run(orchestrate_agents(db,app,limit=5))
        if orchestrated['processed']:print({'agent_workflows_prepared':orchestrated['processed']},flush=True)
        if not args.suite_only:
            from app.ai_operator.training import process_training
            with SessionLocal() as db:
                training=process_training(db)
            if training['processed']:
                print({'nlp_training_processed':training['processed']},flush=True)
        if result:
            print(result, flush=True)  # Counts only; never commands or credentials.
        if args.once:
            break
        time.sleep(2)
