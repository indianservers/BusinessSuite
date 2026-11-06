"""Verified request/job database routing. Never derive a DSN from client input."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache
from threading import RLock
import re

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine, select, or_, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings


@dataclass(frozen=True)
class TenantRoute:
    tenant_uuid: str
    workspace_code: str
    company_id: int
    host: str
    port: int
    database_name: str
    runtime_role: str
    encrypted_password: str
    version: int


current_tenant: ContextVar[TenantRoute | None] = ContextVar("suite_database_tenant", default=None)
_engines = OrderedDict()
_lock = RLock()


def cipher():
    if not settings.TENANT_SECRET_KEY:
        raise HTTPException(503,"Company database secret key is not configured")
    return Fernet(settings.TENANT_SECRET_KEY.encode())


@lru_cache(maxsize=1)
def registry_factory():
    if not settings.TENANT_REGISTRY_URL:
        raise HTTPException(503,"Company database registry is not configured")
    engine=create_engine(settings.TENANT_REGISTRY_URL,pool_pre_ping=True,pool_size=2,max_overflow=2,
        connect_args={"connect_timeout":5,"options":"-c statement_timeout=3000"})
    return sessionmaker(bind=engine)


def lookup_route(workspace):
    from app.platform_owner.models import PlatformTenantDatabase as D, PlatformDatabaseServer as S
    if not isinstance(workspace,str) or not re.fullmatch(r"[a-z0-9-]{3,64}",workspace):
        raise HTTPException(401,"Invalid company workspace")
    try:
        with registry_factory()() as db:
            result=db.execute(select(D,S).join(S,S.id==D.server_id).where(or_(D.tenant_uuid==workspace,D.workspace_code==workspace))).first()
            if result and result[0].status == "removed":
                raise HTTPException(410,"This company workspace has been removed")
            if result and result[0].status == "deleting":
                raise HTTPException(423,"This company workspace is being removed")
            if not result or result[0].status!="ready":
                raise HTTPException(503,"Company database is not ready or is under maintenance")
            d,s=result
            return TenantRoute(d.tenant_uuid,d.workspace_code,d.company_id,s.host,s.port,d.database_name,d.runtime_role,d.encrypted_password,d.routing_version)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503,"Company database registry is unavailable") from None


def tenant_engine(route):
    # NullPool: idle companies consume zero PostgreSQL connections. Production
    # endpoints may point at PgBouncer; never create an unbounded pool per tenant.
    key=(route.tenant_uuid,route.version,route.host,route.port,route.database_name,route.encrypted_password)
    with _lock:
        if key in _engines:
            _engines.move_to_end(key);return _engines[key]
        password=cipher().decrypt(route.encrypted_password.encode()).decode()
        remote=route.host not in {"127.0.0.1","localhost","::1"}
        url=URL.create("postgresql+psycopg",username=route.runtime_role,password=password,host=route.host,
            port=route.port,database=route.database_name,query={"sslmode":"verify-full" if remote else "disable"})
        engine=create_engine(url,poolclass=NullPool,pool_pre_ping=True,connect_args={"connect_timeout":5,"prepare_threshold":None})
        _engines[key]=engine
        while len(_engines)>settings.TENANT_ENGINE_CACHE_SIZE:
            _,old=_engines.popitem(last=False);old.dispose()
        return engine


def tenant_session(route):
    db=sessionmaker(bind=tenant_engine(route),autoflush=False)()
    try:
        identity=db.execute(text("SELECT tenant_uuid,company_id,current_database() FROM suite_tenant_identity WHERE singleton=true")).one()
        if tuple(identity)!=(route.tenant_uuid,route.company_id,route.database_name):
            raise RuntimeError("Tenant identity mismatch")
        db.info["tenant_uuid"]=route.tenant_uuid
        db.info["tenant_company_id"]=route.company_id
        return db
    except Exception:
        db.close();raise HTTPException(503,"Company database identity or connection check failed") from None


@contextmanager
def tenant_context(workspace):
    route=lookup_route(workspace)
    token=current_tenant.set(route)
    try: yield route
    finally: current_tenant.reset(token)


def token_tenant_claims():
    route=current_tenant.get()
    return {"tenant":route.tenant_uuid,"workspace":route.workspace_code} if route else {}


def run_for_company_databases(callback):
    """Independent transactions per company; one failure cannot choose a fallback DB."""
    import logging
    from app.platform_owner.models import PlatformTenantDatabase
    try:callback()  # Existing legacy companies remain explicitly in the legacy DB.
    except Exception as exc:logging.getLogger(__name__).warning("Legacy job failed error=%s",type(exc).__name__)
    if not settings.TENANT_DATABASES_ENABLED:return
    with registry_factory()() as db:
        if settings.TENANT_WORKER_SHARD>=settings.TENANT_WORKER_SHARDS:raise RuntimeError("Invalid company worker shard")
        workspaces=db.scalars(select(PlatformTenantDatabase.tenant_uuid).where(PlatformTenantDatabase.status=="ready",
            PlatformTenantDatabase.id % settings.TENANT_WORKER_SHARDS==settings.TENANT_WORKER_SHARD)).all()
    for workspace in workspaces:
        try:
            with tenant_context(workspace):callback()
        except Exception as exc:
            logging.getLogger(__name__).warning("Company job failed tenant=%s error=%s",workspace,type(exc).__name__)


def all_company_job(function):
    from functools import wraps
    @wraps(function)
    def run(*args,**kwargs):
        if not settings.TENANT_DATABASES_ENABLED or current_tenant.get():return function(*args,**kwargs)
        outcomes=[]
        run_for_company_databases(lambda:outcomes.append(function(*args,**kwargs)))
        return {"databases_processed":len(outcomes),"results":outcomes}
    return run
