"""Read-only local-company record fingerprints for browser lifecycle QA.

Run with backend/venv/Scripts/python.exe qa/company_sample_preservation.py before
and again with after. Stores hashes only, never raw business record contents.
"""
from pathlib import Path
import ast,json,hashlib,sys
from sqlalchemy import select,inspect
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import os
os.chdir(ROOT / "backend")
from app.db.base import Base
from app.db.session import engine
from app.platform_owner.session import platform_factory
from app.platform_owner.models import PlatformTenantDatabase
from app.db.tenant import lookup_route,tenant_engine
root=ROOT
names=sorted({n.args[0].value for n in ast.walk(ast.parse((root/'backend/app/shared/sample_data.py').read_text())) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='add' and n.args and isinstance(n.args[0],ast.Constant)}|{'companies','branches','suite_branch_ownership','security_resource_ownership'})
out=root/'outputs/company-sample-browser';out.mkdir(parents=True,exist_ok=True)
mode=sys.argv[1]
if mode=='before':
    with platform_factory()() as db: workspaces=list(db.scalars(select(PlatformTenantDatabase.tenant_uuid).where(PlatformTenantDatabase.status=='ready')))
    (out/'baseline-workspaces.json').write_text(json.dumps(workspaces))
else:workspaces=json.loads((out/'baseline-workspaces.json').read_text())
result={}
for label,eng in [('legacy',engine)]+[(w,tenant_engine(lookup_route(w))) for w in workspaces]:
    if eng.url.host not in {'localhost','127.0.0.1','::1'}:raise RuntimeError('Only local databases permitted')
    data={}
    with eng.connect() as connection:
        connection.exec_driver_sql('SET TRANSACTION READ ONLY')
        available=set(inspect(connection).get_table_names())
        for name in names:
            if name not in available:continue
            table=Base.metadata.tables[name]
            records={}
            for row in connection.execute(select(table)).mappings():
                key=json.dumps([str(row[c.name]) for c in table.primary_key.columns])
                records[key]=hashlib.sha256(json.dumps(dict(row),sort_keys=True,default=str).encode()).hexdigest()
            data[name]=records
    result[label]=data
(out/f'{mode}.json').write_text(json.dumps(result))
if mode=='before':print(json.dumps({'databases_baselined':len(result),'tables_per_database':len(names),'existing_records_hashed':sum(len(rows) for data in result.values() for rows in data.values())}))
else:
    original=json.loads((out/'before.json').read_text());diff=[]
    for database,tables in original.items():
        for table,rows in tables.items():
            current=result[database][table]
            removed=set(rows)-set(current);added=set(current)-set(rows);changed=[k for k in rows.keys()&current.keys() if rows[k]!=current[k]]
            if removed or added or changed:diff.append({'database':database,'table':table,'removed':len(removed),'added':len(added),'changed':len(changed)})
    summary={'databases_checked':len(result),'differences':diff,'unchanged':not diff}
    (out/'preservation-result.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
