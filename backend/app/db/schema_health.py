"""Check runtime ORM requirements, independently of Alembic's revision marker."""
from sqlalchemy import inspect
from sqlalchemy.schema import MetaData


def model_schema_report(connection, metadata: MetaData) -> dict:
    inspector = inspect(connection)
    missing_tables = []
    missing_columns = {}
    checked_columns = 0
    schemas = {table.schema for table in metadata.tables.values()}
    for schema in sorted(schemas, key=lambda value: value or ""):
        expected = {table.name: table for table in metadata.tables.values() if table.schema == schema}
        available = set(inspector.get_table_names(schema=schema))
        present = sorted(set(expected) & available)
        actual = {
            name: {column['name'] for column in columns}
            for (_, name), columns in inspector.get_multi_columns(schema=schema, filter_names=present).items()
        } if present else {}
        for name, table in expected.items():
            label = f'{schema}.{name}' if schema else name
            checked_columns += len(table.columns)
            if name not in available:
                missing_tables.append(label)
                continue
            absent = sorted({column.name for column in table.columns} - actual.get(name, set()))
            if absent:
                missing_columns[label] = absent
    return {'checked_tables': len(metadata.tables), 'checked_columns': checked_columns,
            'missing_tables': sorted(missing_tables), 'missing_columns': missing_columns}


def require_model_schema(connection, metadata: MetaData) -> dict:
    report = model_schema_report(connection, metadata)
    if report['missing_tables'] or report['missing_columns']:
        raise RuntimeError(f'Application/database schema mismatch: missing tables={report["missing_tables"]}; missing columns={report["missing_columns"]}')
    return report
