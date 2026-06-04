"""Restore a Business Suite MySQL SQL backup into a target database."""

from __future__ import annotations

import argparse
import sys
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


def _split_sql(sql_text: str) -> list[str]:
    sql_text = "\n".join(line for line in sql_text.splitlines() if not line.lstrip().startswith("--"))
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    escaped = False

    for char in sql_text:
        current.append(char)
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == ";" and not in_single and not in_double:
            statement = "".join(current).strip()
            current = []
            if statement and not statement.startswith("--"):
                statements.append(statement[:-1].strip())

    tail = "".join(current).strip()
    if tail and not tail.startswith("--"):
        statements.append(tail)
    return statements


def restore_backup(database: str, backup_file: Path, recreate: bool = False) -> int:
    if not backup_file.exists():
        raise FileNotFoundError(backup_file)

    admin = _connect()
    try:
        with admin.cursor() as cursor:
            if recreate:
                cursor.execute(f"DROP DATABASE IF EXISTS {_quote_identifier(database)}")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {_quote_identifier(database)} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        admin.commit()
    finally:
        admin.close()

    sql_text = backup_file.read_text(encoding="utf-8")
    statements = _split_sql(sql_text)
    connection = _connect(database)
    executed = 0
    try:
        with connection.cursor() as cursor:
            for statement in statements:
                if not statement:
                    continue
                cursor.execute(statement)
                executed += 1
        connection.commit()
    finally:
        connection.close()
    return executed


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Restore a MySQL backup into a target database.")
    parser.add_argument("--database", required=True, help="Target database name.")
    parser.add_argument("--file", required=True, help="Backup SQL file to restore.")
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate the target database first.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    count = restore_backup(args.database, Path(args.file), recreate=args.recreate)
    print(f"restored_statements={count}")


if __name__ == "__main__":
    main()
