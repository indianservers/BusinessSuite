"""Due-account scheduler, isolated by database, owner, organization and branch."""
from contextlib import contextmanager, ExitStack
from datetime import timedelta
from starlette.requests import Request
from fastapi import HTTPException
from sqlalchemy import or_
from app.shared.accounting_sync.models import SyncConnection
from app.shared.accounting_sync import service

@contextmanager
def owner_scope(db, connection):
    from app.models.user import User
    from app.models.company import Company
    from app.access.service import bind_authorization
    from app.core.tenant_boundary import install as tenant_boundary
    from app.branches.service import context
    from app.branches.boundary import install as branch_boundary
    from app.shared.import_api import finance_context
    from app.core.audit_context import set_audit_actor
    user=db.get(User,connection.created_by)
    company=db.get(Company,connection.organization_id)
    if not user or not user.is_active or not company or not company.is_active:
        raise HTTPException(403,"Sync owner or company is inactive")
    # Re-resolve current grants on every run; saved credentials confer no permissions.
    request=Request({"type":"http","method":"POST","path":"/api/v1/imports/fam/connections",
        "headers":[(b"x-suite-organization",str(connection.organization_id).encode()),
                   (b"x-suite-branch",str(connection.branch_id).encode())],"query_string":b""})
    with ExitStack() as stack:
        previous=db.info.get("security_write_request")
        db.info["security_write_request"]=True
        stack.callback(lambda:db.info.pop("security_write_request",None) if previous is None else db.info.update(security_write_request=previous))
        stack.callback(bind_authorization(db,user,request))
        stack.callback(tenant_boundary(db,user,connection.organization_id))
        ctx=context(db,user,connection.organization_id,str(connection.branch_id))
        stack.callback(branch_boundary(db,user,ctx))
        from app.shared.record_360 import module_access
        module_access(db,user,"fam")
        finance_context(db,user,request)
        # Verify ownership under the installed row guards, not just the discovery query.
        visible=db.query(SyncConnection).filter_by(id=connection.id,organization_id=ctx.company_id,branch_id=ctx.branch_id,created_by=user.id).first()
        if visible is None: raise HTTPException(403,"Sync account is no longer accessible")
        set_audit_actor(user)
        yield user


def process_due(factory, limit=10):
    stamp=service.now()
    with factory() as discovery:
        identities=[row.id for row in discovery.query(SyncConnection).filter(
            SyncConnection.enabled.is_(True),SyncConnection.auto_sync.is_(True),
            SyncConnection.provider.in_(["zoho","quickbooks"]),SyncConnection.next_sync_at<=stamp,
            or_(SyncConnection.lease_until.is_(None),SyncConnection.lease_until<stamp)
        ).order_by(SyncConnection.next_sync_at,SyncConnection.id).limit(limit)]
    result={"completed":0,"failed":0,"blocked":0,"skipped":0}
    for identity in identities:
        # Each account gets its own authorization listeners and independent transaction.
        with factory() as db:
            connection=db.get(SyncConnection,identity)
            if connection is None: result["skipped"]+=1; continue
            try:
                with owner_scope(db,connection):
                    run=service.execute(db,connection,scheduled=True)
                    result[run.status if run.status in result else "failed"]+=1
            except HTTPException as exc:
                db.rollback()
                if exc.status_code==409:
                    result["skipped"]+=1; continue
                row=db.get(SyncConnection,identity)
                if row:
                    row.schedule_error="Background sync blocked: check owner permissions, membership and branch access"
                    row.next_sync_at=service.now()+timedelta(hours=1)
                    db.commit()
                result["blocked"]+=1
            except Exception:
                db.rollback()
                row=db.get(SyncConnection,identity)
                if row:
                    row.schedule_error="Background sync could not start; retry scheduled in one hour"
                    row.next_sync_at=service.now()+timedelta(hours=1)
                    db.commit()
                result["failed"]+=1
    return result


def dispatch_due(limit=10):
    from app.db.session import SessionLocal
    from app.db.tenant import run_for_company_databases, current_tenant
    from app.module_registry import is_app_enabled
    if not is_app_enabled("fam"):return {"disabled":True}
    if current_tenant.get():return process_due(SessionLocal,limit)
    results=[]
    run_for_company_databases(lambda:results.append(process_due(SessionLocal,limit)))
    return {"databases_processed":len(results),"results":results}


def start_worker():
    import logging
    import threading
    stop=threading.Event()
    def loop():
        while not stop.is_set():
            try:dispatch_due()
            except Exception:logging.getLogger(__name__).warning("accounting_sync_tick_failed; check migrations and account settings")
            stop.wait(60)
    thread=threading.Thread(target=loop,daemon=True,name="suite-accounting-sync")
    thread.start()
    return stop,thread
