"""Verify every migrated suite/Inventory table and column on PostgreSQL."""
import argparse
import json
from alembic.config import Config
from alembic.script import ScriptDirectory
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.db.session import engine


def verify(*, suite_only=False):
    root = Path(__file__).resolve().parents[2]
    coverage = json.loads((root / "backend/alembic_postgresql/schema/coverage.json").read_text())
    extensions = json.loads((root / "backend/alembic_postgresql/schema/extensions.json").read_text())
    coverage["target_tables"] = list(set(coverage["target_tables"]) | set(extensions))
    coverage["columns"].update(extensions)
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Application is not connected to PostgreSQL")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    # Batch reflection avoids one remote catalog round trip per application table.
    reflected_columns = {
        name: {column['name'] for column in columns}
        for (_, name), columns in inspector.get_multi_columns(filter_names=sorted(tables)).items()
    }
    missing = sorted(set(coverage["target_tables"]) - tables)
    missing_columns = {t: sorted(set(cols) - reflected_columns[t])
                       for t, cols in coverage['columns'].items() if t in tables}
    missing_columns = {t: cols for t, cols in missing_columns.items() if cols}
    with engine.connect() as conn:
        result = {"database": engine.url.database, "dialect": engine.dialect.name,
                  "version": conn.execute(text("SELECT version()")).scalar(),
                  "table_count": len(tables), "expected_application_tables": len(coverage["target_tables"]),
                  "missing_tables": missing, "missing_columns": missing_columns,
                  "migration_revision": conn.execute(text("SELECT version_num FROM alembic_version")).scalar(),
                  "constraints": conn.execute(text("SELECT count(*) FROM pg_constraint WHERE connamespace='public'::regnamespace")).scalar(),
                  "indexes": conn.execute(text("SELECT count(*) FROM pg_indexes WHERE schemaname='public'")).scalar(),
                  "data_migration": "none; schema only, application bootstrap is separate"}
        result['fresh_business_rows'] = {t: conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar() for t in ('employees','crm_leads','pms_projects','pms_tasks','srm_sales_orders','fam_vouchers')}
    missing_inventory = []
    missing_inventory_columns = {}
    if suite_only:
        result["inventory"] = {"checked": False, "reason": "Standalone Inventory excluded by --suite-only"}
    else:
        inventory_url = (make_url(os.environ['INVENTORY_DATABASE_URL']).set(drivername='postgresql+psycopg')
                         if os.environ.get('INVENTORY_DATABASE_URL') else engine.url.set(database=os.environ.get('INVENTORY_POSTGRES_DB','business_suite_inventory')))
        inventory = create_engine(inventory_url)
        try:
            ii = inspect(inventory)
            inventory_tables = set(ii.get_table_names())
            inventory_columns = {
                name: {column['name'] for column in columns}
                for (_, name), columns in ii.get_multi_columns(filter_names=sorted(inventory_tables)).items()
            }
            expected_inventory = json.loads((root / 'backend/app/apps/inventory/vyapara_erp/migrations_postgresql/schema/coverage.json').read_text())['tables']
            missing_inventory = sorted(set(expected_inventory) - inventory_tables)
            missing_inventory_columns = {t: sorted(set(cols) - inventory_columns[t]) for t,cols in expected_inventory.items() if t in inventory_tables}
            missing_inventory_columns = {t:cols for t,cols in missing_inventory_columns.items() if cols}
            result['inventory'] = {"database": inventory_url.database, "tables": len(inventory_tables),
                                   "business_tables": len(inventory_tables - {'alembic_version'}),
                                   "missing_tables": missing_inventory, "missing_columns": missing_inventory_columns}
        finally:
            inventory.dispose()
    expected = ScriptDirectory.from_config(Config(str(root / "backend/alembic.ini"))).get_current_head()
    with engine.connect() as conn:
        revisions = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    result["expected_revision"] = expected
    result["revision_current"] = revisions == [expected]
    result['passed'] = result["revision_current"] and not missing and not missing_columns and not missing_inventory and not missing_inventory_columns
    out = root / 'docs/migrations/postgresql-verification.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    print(json.dumps(result,indent=2,default=str))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-only", action="store_true", help="Exclude the separately deployed legacy Inventory database")
    verify(suite_only=parser.parse_args().suite_only)
