"""Structured PostgreSQL CRUD only; no user SQL or application credentials."""

import json
import re
import threading
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from app.apps.power_apps.integrations.contracts import DBInput, IntegrationFailure
from app.apps.power_apps.integrations.transport import scrub

POOLS = {}
LOCK = threading.Lock()


def engine_for(conn, credential, values, policy):
    target = policy.resolve(
        "postgresql://" + conn.config["hosts"][0],
        database=True,
        port=conn.config.get("port", 5432),
    )
    key = (
        conn.organization_id,
        conn.environment,
        conn.id,
        credential.version,
        conn.config["hosts"][0],
        conn.config["database"],
        values["username"],
        target.address,
        target.port,
    )
    import certifi
    from app.core.config import settings

    url = URL.create(
        "postgresql+psycopg",
        username=values["username"],
        password=values["password"],
        host=target.host,
        port=target.port,
        database=conn.config["database"],
    )
    with LOCK:
        for old in list(POOLS):
            if old[:3] == key[:3] and old != key:
                POOLS.pop(old).dispose()
        if key not in POOLS:
            POOLS[key] = create_engine(
                url,
                connect_args={
                    "hostaddr": target.address,
                    "sslmode": "verify-full",
                    "sslrootcert": getattr(settings, "POWER_CONNECTOR_PG_CA", "")
                    or certifi.where(),
                    "connect_timeout": 5,
                },
                pool_size=2,
                max_overflow=0,
                pool_timeout=5,
                pool_recycle=60,
                hide_parameters=True,
            )
        return POOLS[key]


def execute(conn, credential, values, action, data, policy):
    from psycopg import sql
    from psycopg.types.json import Jsonb

    data = DBInput.model_validate(data)
    allowed = set(conn.config.get("tables", []))
    if (
        action not in {"test", "inspect"}
        and f"{data.schema_name}.{data.table}" not in allowed
    ):
        raise IntegrationFailure(
            "database_policy", "Table is outside the approved allowlist"
        )
    for name in [
        data.schema_name,
        data.table,
        *data.columns,
        *data.where,
        *data.values,
    ]:
        if name and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", name):
            raise IntegrationFailure("database_policy", "Invalid database identifier")
    if action in {"insert", "update", "delete"} and not conn.writes_enabled:
        raise IntegrationFailure("permission", "Database writes are not enabled")
    engine = engine_for(conn, credential, values, policy)
    committing = False
    try:
        with engine.connect() as session:
            session.begin()
            raw = session.connection.driver_connection
            with raw.cursor() as cursor:
                cursor.execute(
                    "SET TRANSACTION READ ONLY"
                    if action in {"test", "inspect", "read"}
                    else "SET TRANSACTION READ WRITE"
                )
                cursor.execute(
                    "SELECT set_config('statement_timeout',%s,true)", ("5000",)
                )
                cursor.execute(
                    "SELECT rolsuper,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user"
                )
                privileges = cursor.fetchone()
                if not privileges or any(privileges):
                    raise IntegrationFailure(
                        "database_role",
                        "Use a dedicated non-administrative database role",
                    )
                if action == "test":
                    cursor.execute("SELECT current_database(),current_user")
                    row = cursor.fetchone()
                    return {
                        "database": row[0],
                        "role": row[1],
                        "read_only_default": True,
                    }
                cursor.execute(
                    "SELECT table_schema,table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE (table_schema || %s || table_name) = ANY(%s) ORDER BY table_schema,table_name,ordinal_position LIMIT 1501",
                    (".", sorted(allowed)),
                )
                metadata = cursor.fetchall()
                if len(metadata) > 1500:
                    raise IntegrationFailure(
                        "database_policy",
                        "Approved schema exceeds 1500 columns; narrow the table allowlist",
                    )
                if action == "inspect":
                    return {
                        "columns": [
                            dict(
                                zip(
                                    ["schema", "table", "column", "type", "nullable"], r
                                )
                            )
                            for r in metadata[:500]
                        ]
                    }
                columns = {
                    r[2]
                    for r in metadata
                    if r[0] == data.schema_name and r[1] == data.table
                }
                if (
                    not columns
                    or set(data.columns + list(data.where) + list(data.values))
                    - columns
                ):
                    raise IntegrationFailure(
                        "database_policy", "Unknown or inaccessible column"
                    )
                table = sql.Identifier(data.schema_name, data.table)
                params = []
                predicates = []
                for name, value in data.where.items():
                    if isinstance(value, (dict, list)):
                        raise IntegrationFailure(
                            "database_policy",
                            "Filters use typed scalar equality; arbitrary predicates are not accepted",
                        )
                    predicates.append(
                        sql.SQL("{} IS NULL").format(sql.Identifier(name))
                        if value is None
                        else sql.SQL("{} = %s").format(sql.Identifier(name))
                    )
                    if value is not None:
                        params.append(value)
                where = (
                    sql.SQL(" AND ").join(predicates) if predicates else sql.SQL("TRUE")
                )
                if action == "read":
                    selected = sql.SQL(",").join(
                        sql.Identifier(c) for c in (data.columns or sorted(columns))
                    )
                    statement = sql.SQL(
                        "SELECT {} FROM {} WHERE {} ORDER BY {} LIMIT %s OFFSET %s"
                    ).format(selected, table, where, sql.Identifier(sorted(columns)[0]))
                    cursor.execute(statement, [*params, data.limit + 1, data.offset])
                    rows = cursor.fetchall()
                    names = [d.name for d in cursor.description]
                    output = {
                        "records": [dict(zip(names, r)) for r in rows[: data.limit]],
                        "next_offset": (
                            data.offset + data.limit if len(rows) > data.limit else None
                        ),
                    }
                else:
                    if action in {"update", "delete"} and not data.where:
                        raise IntegrationFailure(
                            "database_policy",
                            "Update and delete require an explicit equality filter",
                        )
                    if action in {"insert", "update"} and not data.values:
                        raise IntegrationFailure(
                            "database_policy", "Write values are required"
                        )
                    adapted = [
                        Jsonb(v) if isinstance(v, (dict, list)) else v
                        for v in data.values.values()
                    ]
                    if action == "insert":
                        statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                            table,
                            sql.SQL(",").join(map(sql.Identifier, data.values)),
                            sql.SQL(",").join(sql.Placeholder() for _ in data.values),
                        )
                        cursor.execute(statement, adapted)
                    elif action == "update":
                        statement = sql.SQL("UPDATE {} SET {} WHERE {}").format(
                            table,
                            sql.SQL(",").join(
                                sql.SQL("{}=%s").format(sql.Identifier(c))
                                for c in data.values
                            ),
                            where,
                        )
                        cursor.execute(statement, [*adapted, *params])
                    elif action == "delete":
                        cursor.execute(
                            sql.SQL("DELETE FROM {} WHERE {}").format(table, where),
                            params,
                        )
                    else:
                        raise IntegrationFailure(
                            "action", "Unsupported database action"
                        )
                    if cursor.rowcount > 200:
                        raise IntegrationFailure(
                            "row_limit",
                            "Write matched more than 200 rows and was rolled back",
                        )
                    output = {"affected_rows": cursor.rowcount, "committed": True}
            if action in {"insert", "update", "delete"}:
                committing = True
                session.commit()
            return scrub(json.loads(json.dumps(output, default=str)))
    except IntegrationFailure:
        raise
    except Exception:
        raise IntegrationFailure(
            "database",
            "Database operation failed; inspect the dedicated role and server policy",
            uncertain=committing,
        ) from None
