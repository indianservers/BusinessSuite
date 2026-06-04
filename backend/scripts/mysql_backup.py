"""Create a timestamped MySQL SQL backup using app database settings."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings


def _connect(database: str | None = None):
    return pymysql.connect(
        host=settings.MYSQL_SERVER,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=database,
        charset="utf8mb4",
    )


def _quote_identifier(name: str) -> str:
    return f"`{name.replace('`', '``')}`"


def _row_insert(cursor, table_name: str, columns: list[str], row: tuple) -> str:
    column_sql = ", ".join(_quote_identifier(column) for column in columns)
    value_sql = ", ".join(["%s"] * len(columns))
    return cursor.mogrify(f"INSERT INTO {_quote_identifier(table_name)} ({column_sql}) VALUES ({value_sql});", row)


def create_backup(database: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = output_dir / f"{database}_backup_{timestamp}.sql"

    connection = _connect(database)
    try:
        with connection.cursor() as cursor, backup_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("-- Business Suite MySQL backup\n")
            handle.write(f"-- Database: {database}\n")
            handle.write(f"-- Created at: {datetime.now().isoformat(timespec='seconds')}\n\n")
            handle.write("SET FOREIGN_KEY_CHECKS=0;\n")
            handle.write("SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\n\n")

            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]

            for table_name in reversed(tables):
                handle.write(f"DROP TABLE IF EXISTS {_quote_identifier(table_name)};\n")
            handle.write("\n")

            for table_name in tables:
                cursor.execute(f"SHOW CREATE TABLE {_quote_identifier(table_name)}")
                create_sql = cursor.fetchone()[1]
                handle.write(f"{create_sql};\n\n")

                cursor.execute(f"SELECT * FROM {_quote_identifier(table_name)}")
                columns = [description[0] for description in cursor.description or []]
                for row in cursor.fetchall():
                    handle.write(_row_insert(cursor, table_name, columns, row))
                    handle.write("\n")
                handle.write("\n")

            handle.write("SET FOREIGN_KEY_CHECKS=1;\n")
    finally:
        connection.close()

    return backup_path


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Create a timestamped MySQL backup.")
    parser.add_argument("--database", default=settings.MYSQL_DB, help="Database name to back up.")
    parser.add_argument("--output-dir", default="backups", help="Directory for generated SQL backup files.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    backup_path = create_backup(args.database, Path(args.output_dir))
    print(backup_path)


if __name__ == "__main__":
    main()
