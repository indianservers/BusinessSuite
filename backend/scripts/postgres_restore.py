"""Restore a PostgreSQL backup into the configured empty target database."""
import argparse
from pathlib import Path
import subprocess
from postgres_backup import postgres_environment, postgres_tool


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()
    if not args.backup.is_file():
        parser.error("Backup does not exist")
    env = postgres_environment()
    subprocess.run([postgres_tool("pg_restore"), "--no-owner", "--no-acl", "--exit-on-error", "--single-transaction", "--dbname", env["PGDATABASE"], str(args.backup)],
                   env=env, check=True)
    print("PostgreSQL restore complete")


if __name__ == "__main__":
    main()
