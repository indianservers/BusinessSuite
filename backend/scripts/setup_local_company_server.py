"""Start/register a second dedicated LOCAL PostgreSQL instance for move testing."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse,json,secrets,subprocess,tempfile,os
from sqlalchemy.engine import URL
from app.core.config import settings
from app.platform_owner.models import PlatformDatabaseServer
from app.platform_owner.session import platform_factory
from app.platform_owner.tenant_provisioning import pg_tool,pg_connection


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--port",type=int,default=55439);args=parser.parse_args()
    if args.port!=55439:raise RuntimeError("This local QA setup reserves port55439 only")
    backend=Path(__file__).resolve().parents[1];folder=backend.parent/".local/company-postgres-02";folder.mkdir(parents=True,exist_ok=True)
    data=folder/"data";secret_key="LOCAL_COMPANY_02"
    url=settings.TENANT_SERVER_URLS.get(secret_key)
    if not (data/"PG_VERSION").exists():
        password=secrets.token_urlsafe(36)
        url=URL.create("postgresql+psycopg",username="suite_company_cluster",password=password,host="127.0.0.1",port=args.port,database="postgres").render_as_string(hide_password=False)
        descriptor,password_file=tempfile.mkstemp(prefix="suite-pg-password-")
        try:
            with os.fdopen(descriptor,"w") as handle:handle.write(password)
            subprocess.run([pg_tool("initdb"),"-D",str(data),"-U","suite_company_cluster","--pwfile",password_file,"--auth-host=scram-sha-256","--auth-local=scram-sha-256","--no-locale","-E","UTF8"],capture_output=True,check=True,timeout=120)
        finally:Path(password_file).unlink(missing_ok=True)
        values={**settings.TENANT_SERVER_URLS,secret_key:url}
        env=backend/".env";lines=[l for l in env.read_text().splitlines() if not l.startswith("TENANT_SERVER_URLS=")]
        lines.append("TENANT_SERVER_URLS='"+json.dumps(values)+"'");env.write_text("\n".join(lines)+"\n")
    if not url:raise RuntimeError("Existing local cluster has no configured secret; inspect before reuse")
    status=subprocess.run([pg_tool("pg_ctl"),"-D",str(data),"status"],capture_output=True)
    if status.returncode:
        subprocess.run([pg_tool("pg_ctl"),"-D",str(data),"-l",str(folder/"postgres.log"),"-o",f"-p {args.port} -h 127.0.0.1","-w","start"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    from sqlalchemy.engine import make_url
    with pg_connection(make_url(url)) as connection:
        if connection.execute("SELECT inet_server_port()").fetchone()[0]!=args.port:raise RuntimeError("Unexpected local server")
    with platform_factory()() as registry:
        if not registry.query(PlatformDatabaseServer).filter_by(code="local-02").first():
            registry.add(PlatformDatabaseServer(code="local-02",name="Local PostgreSQL 02",host="127.0.0.1",port=args.port,
                provisioning_env=secret_key,template_database="suite_company_template_02",max_databases=200,active=True));registry.commit()
    print("Second local PostgreSQL instance registered on127.0.0.1:55439; credentials stored in ignored local configuration.")


if __name__=="__main__":main()
