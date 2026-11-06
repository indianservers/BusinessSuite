"""Company database provisioner; privileged connections are limited to DDL/setup."""
from contextlib import contextmanager
from pathlib import Path
import os
import secrets
import subprocess
import tempfile
import uuid

from fastapi import HTTPException
from psycopg import connect, sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.platform_owner.session import platform_factory
from app.platform_owner.models import PlatformTenantDatabase as D, PlatformDatabaseServer as S
from app.db.tenant import cipher, tenant_session, lookup_route


def admin_url(server):
    value=getattr(settings,server.provisioning_env,None) or settings.TENANT_SERVER_URLS.get(server.provisioning_env) or os.environ.get(server.provisioning_env,"")
    if not value:raise HTTPException(503,"Database server provisioning credentials are not configured")
    url=make_url(value)
    if (url.host,url.port or 5432)!=(server.host,server.port):
        raise HTTPException(503,"Local provisioning server configuration mismatch")
    if url.host not in {"127.0.0.1","localhost","::1"} and (not settings.TENANT_ALLOW_REMOTE_OPERATIONS or url.query.get("sslmode")!="verify-full"):
        raise HTTPException(503,"Remote database operations require explicit configuration and verified TLS")
    return url


def pg_connection(url):
    return connect(url.set(drivername="postgresql").render_as_string(hide_password=False),autocommit=True)


def pg_tool(name):
    if settings.TENANT_PG_BIN:
        return str(Path(settings.TENANT_PG_BIN)/(name+(".exe" if os.name=="nt" else "")))
    from importlib.util import spec_from_file_location,module_from_spec
    spec=spec_from_file_location("suite_pg_tools",Path(__file__).resolve().parents[2]/"scripts/postgres_backup.py")
    helper=module_from_spec(spec);spec.loader.exec_module(helper)
    return helper.postgres_tool(name)


def pg_env(url):
    env=dict(os.environ)
    env.update(PGHOST=url.host,PGPORT=str(url.port or 5432),PGUSER=url.username,PGPASSWORD=url.password or "",PGDATABASE=url.database)
    return env


def prepare_template(server):
    """Copy schema ONLY. Never clone the populated legacy business database."""
    url=admin_url(server)
    from app.db.base import Base  # Register all enabled relationship targets.
    with pg_connection(url) as connection:
        connection.execute("SELECT pg_advisory_lock(1092348981)")
        existing=connection.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s",(server.template_database,)).fetchone()
        if existing and existing[0]=="suite_pristine_template_v1":return
        if existing:connection.execute(sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS true").format(sql.Identifier(server.template_database)))
        with tempfile.TemporaryDirectory(prefix="suite-empty-schema-") as folder:
            archive=Path(folder)/"schema.dump"
            source=make_url(settings.TENANT_PROVISIONING_URL).set(database=make_url(settings.SQLALCHEMY_DATABASE_URI).database)
            target=url.set(database=server.template_database)
            if not existing:
                subprocess.run([pg_tool("pg_dump"),"--schema-only","--no-owner","--no-acl","-Fc","-f",str(archive)],
                    env=pg_env(source),capture_output=True,check=True,timeout=300)
                connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(server.template_database)))
                connection.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(server.template_database)))
                subprocess.run([pg_tool("pg_restore"),"--no-owner","--no-acl","--exit-on-error","-d",server.template_database,str(archive)],
                    env=pg_env(target),capture_output=True,check=True,timeout=300)
            engine=create_engine(target,poolclass=NullPool)
            with engine.begin() as db:
                db.execute(text("CREATE TABLE IF NOT EXISTS suite_tenant_identity (singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton), tenant_uuid varchar(36) NOT NULL, company_id integer NOT NULL)"))
            # Only application permission/role definitions are seeded. No users,
            # contacts, transactions, signup queues or bootstrap admin are copied.
            from app.db.init_db import SYSTEM_PERMISSIONS,SYSTEM_ROLES
            from app.apps.power_apps.registry import PERMISSIONS
            from app.models.user import Permission,Role
            with Session(engine) as db:
                from app.models.user import User
                from app.models.company import Company
                if db.query(User).count() or db.query(Company).count():raise RuntimeError("Template contains customer data")
                permissions={}
                for name,description,module in SYSTEM_PERMISSIONS:
                    if name in permissions:continue
                    item=Permission(name=name,description=description,module=module);db.add(item);permissions[name]=item
                for name in PERMISSIONS:
                    if name not in permissions:db.add(Permission(name=name,description=name,module="power_apps"))
                for definition in SYSTEM_ROLES:
                    db.add(Role(name=definition["name"],description=definition["description"],is_system=True,
                        permissions=[permissions[n] for n in dict.fromkeys(definition["permissions"]) if n in permissions]))
                db.commit()
            # Preserve the schema migration receipt, not any other source data.
            with create_engine(source,poolclass=NullPool).connect() as db:versions=db.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            with engine.begin() as db:
                for version in versions:db.execute(text("INSERT INTO alembic_version(version_num) VALUES (:v) ON CONFLICT DO NOTHING"),{"v":version})
            engine.dispose()
            connection.execute(sql.SQL("COMMENT ON DATABASE {} IS 'suite_pristine_template_v1'").format(sql.Identifier(server.template_database)))
            connection.execute(sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS false").format(sql.Identifier(server.template_database)))


def ensure_database(signup_id):
    with platform_factory()() as registry:
        row=registry.query(D).filter_by(signup_id=signup_id).first()
        if not row:
            # Serialize placement accounting; capacity is an owner-controlled
            # limit, not a promise that a server can handle a fixed tenant count.
            servers=registry.query(S).filter_by(active=True).order_by(S.id).with_for_update().all()
            server=next((s for s in servers if registry.query(D).filter_by(server_id=s.id).count()<s.max_databases),None)
            if not server:raise HTTPException(503,"No company database server has free placement capacity")
            ident=str(uuid.uuid4())
            row=D(signup_id=signup_id,tenant_uuid=ident,workspace_code=f"company-{signup_id}",company_id=1_000_000_000+signup_id,
                server_id=server.id,database_name="suite_c_"+ident.replace("-",""),runtime_role="suite_r_"+ident.replace("-",""),
                encrypted_password=cipher().encrypt(secrets.token_urlsafe(36).encode()).decode(),status="provisioning")
            registry.add(row);registry.commit()
        server=registry.get(S,row.server_id)
        if row.status=="ready":return row.tenant_uuid
        try:
            prepare_template(server)
            url=admin_url(server)
            password=cipher().decrypt(row.encrypted_password.encode()).decode()
            with pg_connection(url) as connection:
                connection.execute("SELECT pg_advisory_lock(%s)",(row.company_id,))
                if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",(row.runtime_role,)).fetchone():
                    connection.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT 12").format(sql.Identifier(row.runtime_role),sql.Literal(password)))
                if not connection.execute("SELECT 1 FROM pg_database WHERE datname=%s",(row.database_name,)).fetchone():
                    connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(row.database_name),sql.Identifier(server.template_database)))
                connection.execute(sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS true").format(sql.Identifier(row.database_name)))
                connection.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(row.database_name)))
                connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(row.database_name),sql.Identifier(row.runtime_role)))
            with pg_connection(url.set(database=row.database_name)) as connection:
                existing=connection.execute("SELECT tenant_uuid,company_id FROM suite_tenant_identity").fetchone()
                if existing and existing!=(row.tenant_uuid,row.company_id):raise RuntimeError("Existing database identity mismatch")
                if not existing:connection.execute("INSERT INTO suite_tenant_identity(tenant_uuid,company_id) VALUES (%s,%s)",(row.tenant_uuid,row.company_id))
                if not connection.execute("SELECT 1 FROM pg_constraint WHERE conname='suite_single_company'").fetchone():
                    connection.execute(sql.SQL("ALTER TABLE companies ADD CONSTRAINT suite_single_company CHECK(id={})").format(sql.Literal(row.company_id)))
                connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
                connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(row.runtime_role)))
                connection.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(row.runtime_role)))
                connection.execute(sql.SQL("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(sql.Identifier(row.runtime_role)))
                connection.execute(sql.SQL("REVOKE INSERT,UPDATE,DELETE ON suite_tenant_identity FROM {}").format(sql.Identifier(row.runtime_role)))
                versions=connection.execute("SELECT version_num FROM alembic_version").fetchall()
            row.status,row.last_error,row.schema_version="ready",None,",".join(v[0] for v in versions)
            registry.commit()
            return row.tenant_uuid
        except Exception as exc:
            row.status,row.last_error="failed",type(exc).__name__+": company database provisioning failed"
            registry.commit()
            raise HTTPException(503,"Company database provisioning failed; inspect the owner database directory and retry") from None


def provision_company(row,data):
    from app.db.base import Base
    from app.access.signup import provision_signup
    workspace=ensure_database(row.id)
    route=lookup_route(workspace)
    with tenant_session(route) as db:
        result=provision_signup(row,data,db,company_id=route.company_id)
        if not result.get("invitation_url"):
            from types import SimpleNamespace
            from app.platform_owner.bridge import invitation
            from app.models.user import User
            user=db.get(User,result["user_id"])
            if user and not user.is_active:
                result["invitation_url"]=invitation(db,SimpleNamespace(signup_id=row.id,company_id=route.company_id,admin_email=row.email))
        from app.apps.business_os.services.module_service import ensure_business_os_seed
        ensure_business_os_seed(db,route.company_id);db.commit()
    if result.get("invitation_url"):result["invitation_url"]+="&tenant="+route.workspace_code
    return {**result,"tenant_uuid":workspace,"workspace_code":route.workspace_code,"database_name":route.database_name}


@contextmanager
def company_business_session(tenant,fallback):
    """Owner service bridge: explicit destination, never request-header routing."""
    if not settings.TENANT_DATABASES_ENABLED or fallback.info.get("tenant_company_id")==tenant.company_id:
        yield fallback;return
    with platform_factory()() as registry:
        row=registry.query(D).filter_by(signup_id=tenant.signup_id).first()
        workspace=row.tenant_uuid if row else None
    if workspace:
        with tenant_session(lookup_route(workspace)) as db:yield db
    else:yield fallback  # Explicit compatibility for pre-existing shared customers.
