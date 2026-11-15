"""Fresh name-only schema probes without PostgreSQL type/domain reflection."""
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.exc import NoSuchTableError


def table_columns(connection, names):
    names = tuple(dict.fromkeys(names))
    if not names:
        return {}
    if connection.dialect.name == 'postgresql':
        # Match unqualified ORM/Inspector visibility, including search_path and
        # temporary relations. LEFT JOIN preserves a present zero-column table.
        statement = text('''
            SELECT c.relname, a.attname
            FROM pg_catalog.pg_class AS c
            LEFT JOIN pg_catalog.pg_attribute AS a
              ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
            WHERE c.relname IN :names
              AND c.relkind IN ('r', 'p', 'f', 'v', 'm')
              AND pg_catalog.pg_table_is_visible(c.oid)
        ''').bindparams(bindparam('names', expanding=True))
        result = {}
        for table, column in connection.execute(statement, {'names': names}):
            columns = result.setdefault(table, set())
            if column is not None:
                columns.add(column)
        return result
    inspector = inspect(connection)
    result = {}
    for name in names:
        try:
            result[name] = {column['name'] for column in inspector.get_columns(name)}
        except NoSuchTableError:
            continue
    return result
