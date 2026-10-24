"""Backup worker and verified offline recovery. Suitable for cron / Task Scheduler."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run_once():
    # Register all installed model modules before ORM relationships are resolved.
    from app.db.base import Base  # noqa: F401
    from app.db.session import SessionLocal
    from app.apps.project_management.recovery import run_due
    from app.services.data_backups import run_full_due

    import logging

    errors = []
    points, archive = [], None
    try:
        with SessionLocal() as db:
            points = run_due(db)
    except Exception:
        logging.exception("Scheduled workspace savepoint cycle failed")
        errors.append("workspace savepoints")
    try:
        archive = run_full_due()
    except Exception:
        logging.exception("Scheduled full-system archive cycle failed")
        errors.append("full-system archives")
    if errors:
        raise RuntimeError(
            "Backup worker failures: " + ", ".join(errors) + ". Inspect worker logs."
        )
    return {"workspace_savepoints": points, "full_backup": archive}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--due",
        action="store_true",
        help="Create due workspace/full backups; schedule every 5 minutes",
    )
    action.add_argument(
        "--backup", action="store_true", help="Create a manual full-system archive"
    )
    action.add_argument("--verify", type=Path)
    action.add_argument("--restore", type=Path)
    parser.add_argument(
        "--target-directory",
        type=Path,
        help="New offline destination; existing directories are refused",
    )
    args = parser.parse_args()
    from app.services.data_backups import (
        create_archive,
        verify_archive,
        extract_archive,
    )

    if args.due:
        print(run_once())
    elif args.backup:
        print(create_archive())
    elif args.verify:
        manifest = verify_archive(args.verify)
        print({"verified": True, "id": manifest["id"], "files": manifest["file_count"]})
    elif args.restore:
        if not args.target_directory:
            parser.error(
                "--restore requires --target-directory (a new offline directory)"
            )
        print(
            "Verified recovery files written to",
            extract_archive(args.restore, args.target_directory),
        )
        print(
            "For PostgreSQL, restore database.dump into an EMPTY database using scripts/postgres_restore.py. For SQLite, use database.sqlite3. Stop application writers before switching databases and upload directories together."
        )


if __name__ == "__main__":
    main()
