"""Standalone durable operator worker; no Redis required. Run from backend."""
import argparse
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.base import Base  # noqa: F401 - register configured application models
from app.db.session import SessionLocal
from app.ai_operator.jobs import process_batch


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()
    while True:
        with SessionLocal() as db:
            result = process_batch(db, limit=max(1, min(args.batch_size, 100)))
        if result:
            print(result, flush=True)  # Counts only; never commands or credentials.
        if args.once:
            break
        time.sleep(2)
