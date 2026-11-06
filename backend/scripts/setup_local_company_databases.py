"""Configure LOCAL per-company PostgreSQL databases; no customer data is copied."""
from pathlib import Path
import secrets
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cryptography.fernet import Fernet
from sqlalchemy.engine import URL,make_url
from alembic import command
from alembic.config import Config
from psycopg import sql
from app.core.config import settings
from app.platform_owner.session import platform_factory
from app.platform_owner.models import PlatformDatabaseServer
from app.platform_owner.tenant_provisioning import pg_connection,prepare_template


def main():
    if settings.POSTGRES_SERVER not in {"127.0.0.1","localhost"}:raise RuntimeError("Local PostgreSQL only")
    backend=Path(__file__).resolve().parents[1]
    admin=URL.create("postgresql+psycopg",username=settings.POSTGRES_USER,password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_SERVER,port=settings.POSTGRES_PORT,database="postgres")
    settings.TENANT_PROVISIONING_URL=admin.render_as_string(hide_password=False)
    settings.TENANT_SECRET_KEY=settings.TENANT_SECRET_KEY or Fernet.generate_key().decode()
    command.upgrade(Config(str(backend/"alembic_platform.ini")),"head")
    with platform_factory()() as registry:
        server=registry.query(PlatformDatabaseServer).filter_by(code="local-01").first()
        if not server:
            server=PlatformDatabaseServer(code="local-01",name="Local PostgreSQL 01",host=settings.POSTGRES_SERVER,
                port=settings.POSTGRES_PORT,template_database=settings.TENANT_TEMPLATE_DATABASE,max_databases=200)
            registry.add(server);registry.commit()
        role="suite_tenant_router";password=secrets.token_urlsafe(36)
        with pg_connection(admin) as connection:
            if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",(role,)).fetchone():
                connection.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT").format(sql.Identifier(role)))
            connection.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(role),sql.Literal(password)))
            platform_url=make_url(settings.PLATFORM_DATABASE_URL)
            connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(platform_url.database),sql.Identifier(role)))
        with pg_connection(admin.set(database=platform_url.database)) as connection:
            connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
            connection.execute(sql.SQL("GRANT SELECT ON platform_tenant_databases,platform_database_servers TO {}").format(sql.Identifier(role)))
        settings.TENANT_REGISTRY_URL=platform_url.set(username=role,password=password).render_as_string(hide_password=False)
        changes={"TENANT_SECRET_KEY":settings.TENANT_SECRET_KEY,"TENANT_REGISTRY_URL":settings.TENANT_REGISTRY_URL,
            "TENANT_PROVISIONING_URL":settings.TENANT_PROVISIONING_URL,"TENANT_DATABASES_ENABLED":"false"}
        env_path=backend/".env";lines=env_path.read_text().splitlines()
        for key,value in changes.items():
            lines=[line for line in lines if not line.startswith(key+"=")];lines.append(key+"='"+value+"'")
        env_path.write_text("\n".join(lines)+"\n")
        prepare_template(server)
        env_path.write_text(env_path.read_text().replace("TENANT_DATABASES_ENABLED='false'","TENANT_DATABASES_ENABLED='true'"))
        print("Local server registered; pristine schema template ready; restricted registry role configured. Per-company provisioning enabled after backend restart.")


if __name__=="__main__":main()
