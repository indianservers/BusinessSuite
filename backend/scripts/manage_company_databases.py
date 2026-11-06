"""Local company operations: list/check/upgrade/move. Never deletes source databases."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
import json
import subprocess
import tempfile
import time
from dataclasses import replace
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from app.platform_owner.session import platform_factory
from app.platform_owner.models import PlatformTenantDatabase as D,PlatformDatabaseServer as S,PlatformEvent
from app.platform_owner.tenant_provisioning import admin_url,pg_connection,pg_tool,pg_env,prepare_template
from app.db.tenant import cipher,lookup_route,tenant_session


def grant_runtime(connection,role):
    connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    for query in ["GRANT USAGE ON SCHEMA public TO {}","GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {}",
        "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}","REVOKE INSERT,UPDATE,DELETE ON suite_tenant_identity FROM {}"]:
        connection.execute(sql.SQL(query).format(sql.Identifier(role)))


def drain(url,row):
    with pg_connection(url) as conn:
        conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {}").format(sql.Identifier(row.database_name),sql.Identifier(row.runtime_role)))
        # Registry maintenance stops new application sessions. Terminate only
        # this tenant's restricted role, never another company's sessions.
        conn.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND usename=%s AND pid<>pg_backend_pid()",(row.database_name,row.runtime_role))


def counts(url):
    with pg_connection(url) as conn:
        tables=conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
        return {name:conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))).fetchone()[0] for name, in tables}


def move(workspace,destination_code):
    route=lookup_route(workspace)
    with platform_factory()() as registry:
        row=registry.query(D).filter_by(tenant_uuid=route.tenant_uuid).with_for_update().one()
        if row.status!="ready":raise RuntimeError("Company is not ready for a move")
        source=registry.get(S,row.server_id);destination=registry.query(S).filter_by(code=destination_code,active=True).one()
        if destination.id!=source.id and registry.query(D).filter_by(server_id=destination.id).count()>=destination.max_databases:
            raise RuntimeError("Destination server has no placement capacity")
        src,dst=admin_url(source),admin_url(destination)
        old_database=row.database_name
        new_database=old_database+"_v"+str(row.routing_version+1)
        if len(new_database)>63:raise RuntimeError("Destination database name is too long")
        row.status="moving";registry.commit()
        switched=False;created_target=False
        try:
            drain(src,row)
            with pg_connection(dst) as connection:
                if connection.execute("SELECT 1 FROM pg_database WHERE datname=%s",(new_database,)).fetchone():raise RuntimeError("Destination already exists; inspect before retrying")
                if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",(row.runtime_role,)).fetchone():
                    password=cipher().decrypt(row.encrypted_password.encode()).decode()
                    connection.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT 12").format(sql.Identifier(row.runtime_role),sql.Literal(password)))
                connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(new_database)))
                created_target=True
                connection.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(new_database)))
            with tempfile.TemporaryDirectory(prefix="suite-company-move-") as folder:
                archive=Path(folder)/"company.dump"
                subprocess.run([pg_tool("pg_dump"),"--no-owner","--no-acl","-Fc","-f",str(archive)],env=pg_env(src.set(database=old_database)),capture_output=True,check=True,timeout=1800)
                subprocess.run([pg_tool("pg_restore"),"--no-owner","--no-acl","--exit-on-error","-d",new_database,str(archive)],env=pg_env(dst.set(database=new_database)),capture_output=True,check=True,timeout=1800)
            if counts(src.set(database=old_database))!=counts(dst.set(database=new_database)):raise RuntimeError("Restored table counts differ")
            with pg_connection(dst.set(database=new_database)) as connection:grant_runtime(connection,row.runtime_role)
            with pg_connection(dst) as connection:connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(new_database),sql.Identifier(row.runtime_role)))
            moved=replace(route,host=destination.host,port=destination.port,database_name=new_database,version=route.version+1)
            with tenant_session(moved):pass
            row.server_id,row.database_name,row.routing_version,row.status=destination.id,new_database,route.version+1,"ready"
            row.last_error=None
            registry.add(PlatformEvent(action="database.moved",entity="database",entity_id=row.id,reason="Operator CLI maintenance move",
                before={"database":old_database,"server_id":source.id,"routing_version":route.version},
                after={"database":new_database,"server_id":destination.id,"routing_version":route.version+1,"source_retained":True}))
            registry.commit();switched=True
            with pg_connection(src) as connection:connection.execute(sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS false").format(sql.Identifier(old_database)))
            print(json.dumps({"workspace":workspace,"server":destination.code,"database":new_database,"routing_version":row.routing_version,"source_retained":True}))
        except Exception:
            if not switched:
                if created_target:
                    with pg_connection(dst) as connection:
                        connection.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {}").format(sql.Identifier(new_database),sql.Identifier(row.runtime_role)))
                        connection.execute(sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS false").format(sql.Identifier(new_database)))
                with pg_connection(src) as connection:connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(old_database),sql.Identifier(row.runtime_role)))
                row.status="ready";row.last_error="Move failed before cutover; source restored";registry.commit()
            raise


def upgrade(workspace):
    route=lookup_route(workspace)
    with platform_factory()() as registry:
        row=registry.query(D).filter_by(tenant_uuid=route.tenant_uuid).with_for_update().one()
        server=registry.get(S,row.server_id);url=admin_url(server)
        row.status="maintenance";registry.commit()
        try:
            drain(url,row)
            engine=create_engine(url.set(database=row.database_name),poolclass=NullPool)
            cfg=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))
            with engine.connect() as connection:
                cfg.attributes["connection"]=connection;command.upgrade(cfg,"head")
            engine.dispose()
            with pg_connection(url.set(database=row.database_name)) as connection:
                grant_runtime(connection,row.runtime_role)
                row.schema_version=",".join(x[0] for x in connection.execute("SELECT version_num FROM alembic_version"))
            row.status,row.last_error="ready",None;registry.commit()
        except Exception:
            row.status,row.last_error="failed","Schema upgrade failed; inspect before retrying";registry.commit();raise
        finally:
            with pg_connection(url) as connection:connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(row.database_name),sql.Identifier(row.runtime_role)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["list","check","upgrade","move","refresh-template"])
    parser.add_argument("--workspace");parser.add_argument("--server")
    parser.add_argument("--all",action="store_true",help="Upgrade ready company databases sequentially with per-company status")
    args=parser.parse_args()
    if args.action=="list":
        with platform_factory()() as db:
            print(json.dumps([{"workspace":r.workspace_code,"database":r.database_name,"server_id":r.server_id,"status":r.status,"version":r.routing_version} for r in db.query(D)],indent=2));return
    if args.action=="refresh-template":
        if not args.server:parser.error("--server is required")
        import secrets
        with platform_factory()() as db:
            server=db.query(S).filter_by(code=args.server).one()
            # Prepare a NEW empty template, then switch placement. Retain the
            # prior template; refresh never drops databases or touches users.
            previous=server.template_database
            server.template_database="suite_template_"+secrets.token_hex(8)
            try:prepare_template(server)
            except Exception:server.template_database=previous;raise
            db.commit();print("New schema-only template prepared; future approvals use it")
        return
    if args.action=="upgrade" and args.all:
        with platform_factory()() as db:workspaces=[r.workspace_code for r in db.query(D).filter_by(status="ready").order_by(D.id)]
        for workspace in workspaces:
            upgrade(workspace);print("Upgraded",workspace,flush=True)
        return
    if not args.workspace:parser.error("--workspace is required")
    if args.action=="move":
        if not args.server:parser.error("--server is required")
        move(args.workspace,args.server)
    elif args.action=="upgrade":upgrade(args.workspace)
    else:
        route=lookup_route(args.workspace)
        with tenant_session(route):print("Company database identity and runtime connection verified")


if __name__=="__main__":main()
