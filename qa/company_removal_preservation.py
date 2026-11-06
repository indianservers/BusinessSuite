"""Read-only checksums of every table in other local company databases.

Run from the repository with backend/venv/Scripts/python.exe and before/after.
Only company-38 (the lifecycle QA company) is excluded. Stores counts and hashes.
"""
from pathlib import Path
import json
import os
import sys
from sqlalchemy import inspect, text, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
from app.db.session import engine
from app.db.tenant import lookup_route, tenant_engine
from app.platform_owner.models import PlatformTenantDatabase
from app.platform_owner.session import platform_factory

out = ROOT / "outputs/company-removal-browser"
out.mkdir(parents=True, exist_ok=True)
mode = sys.argv[1]
if mode == "before":
    with platform_factory()() as db:
        workspaces = list(db.scalars(select(PlatformTenantDatabase.workspace_code).where(
            PlatformTenantDatabase.status == "ready", PlatformTenantDatabase.workspace_code != "company-38")))
    (out / "workspaces.json").write_text(json.dumps(workspaces))
else:
    workspaces = json.loads((out / "workspaces.json").read_text())

result = {}
for label, eng in [("legacy", engine)] + [(w, tenant_engine(lookup_route(w))) for w in workspaces]:
    assert eng.url.host in {"localhost", "127.0.0.1", "::1"}, "Local QA only"
    tables = {}
    with eng.connect() as connection:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        connection.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
        oid = connection.exec_driver_sql("SELECT oid FROM pg_database WHERE datname=current_database()").scalar_one()
        for name in inspect(connection).get_table_names(schema="public"):
            quoted = connection.dialect.identifier_preparer.quote(name)
            count, checksum = connection.exec_driver_sql(
                f"SELECT count(*), md5(coalesce(string_agg(md5(row_to_json(t)::text), '' ORDER BY md5(row_to_json(t)::text)),'')) FROM public.{quoted} t").one()
            tables[name] = {"count": count, "checksum": checksum}
    result[label] = {"oid": oid, "tables": tables}
with engine.connect() as connection:
    result["cluster"] = {"databases": dict(connection.execute(text("SELECT datname,oid FROM pg_database WHERE NOT datistemplate")).all()),
                         "roles": list(connection.execute(text("SELECT rolname FROM pg_roles WHERE rolname LIKE 'suite_r_%' ORDER BY rolname")).scalars())}
(out / f"{mode}.json").write_text(json.dumps(result, indent=2))
if mode == "before":
    print(json.dumps({"other_databases": len(workspaces)+1, "tables": sum(len(v["tables"]) for k,v in result.items() if k!="cluster"),
        "rows": sum(t["count"] for k,v in result.items() if k!="cluster" for t in v["tables"].values())}))
else:
    before = json.loads((out / "before.json").read_text())
    changes = []
    for database, value in before.items():
        if database == "cluster": continue
        for table, checksum in value["tables"].items():
            if result[database]["tables"].get(table) != checksum:
                changes.append({"database": database, "table": table, "before": checksum, "after": result[database]["tables"].get(table)})
    removed = {k:v for k,v in before["cluster"]["databases"].items() if k not in result["cluster"]["databases"]}
    summary = {"other_databases_checked": len(workspaces)+1, "changed_tables": changes,
        "databases_removed": removed, "roles_removed": sorted(set(before["cluster"]["roles"])-set(result["cluster"]["roles"]))}
    (out / "comparison.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
