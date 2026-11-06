from datetime import datetime, timedelta, timezone
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import or_
from fastapi import HTTPException
from app.shared.accounting_sync.models import SyncConnection, SyncRecord, SyncRun
from app.shared.accounting_sync.providers import ENTITIES, ProviderError, pull, money, MAX_RECORDS
from app.shared.import_service import digest
from app.shared.import_models import ImportConnection

def now(): return datetime.now(timezone.utc)

def acquire(db, connection, scheduled=False):
    stamp = now(); run_id = str(uuid4())
    query = db.query(SyncConnection).filter(SyncConnection.id == connection.id, SyncConnection.enabled.is_(True), or_(SyncConnection.lease_until.is_(None), SyncConnection.lease_until < stamp))
    if scheduled:
        query = query.filter(SyncConnection.auto_sync.is_(True), SyncConnection.next_sync_at <= stamp)
    claimed = query.update({"lease_until":stamp+timedelta(hours=1), "active_token":run_id,
        "next_sync_at":stamp+timedelta(minutes=connection.interval_minutes or 15)}, synchronize_session=False)
    if not claimed: raise HTTPException(409, "A sync is running or this connection is paused")
    db.query(SyncRun).filter(SyncRun.connection_id == connection.id, SyncRun.status == "running").update({"status":"interrupted", "completed_at":stamp, "error":"Previous sync lease expired"}, synchronize_session=False)
    run = SyncRun(id=run_id, connection_id=connection.id,status="running",started_at=stamp,counts={})
    db.add(run); db.commit()
    return run_id

def validate(snapshot):
    if set(snapshot) != set(ENTITIES): raise ProviderError("A complete customers, invoices and payments snapshot is required")
    for entity, records in snapshot.items():
        if not isinstance(records,list) or len(records)>MAX_RECORDS: raise ProviderError("Invalid snapshot size")
        ids = set()
        for row in records:
            ident = row.get("external_id")
            if not isinstance(ident,str) or not ident or len(ident)>160 or ident in ids: raise ProviderError("Snapshot contains missing or duplicate provider IDs")
            ids.add(ident)
            if entity != "customers":
                if not row.get("customer_external_id") or not row.get("currency"): raise ProviderError("Transaction customer and currency are required")
                row["amount"] = money(row.get("amount"))
                if entity == "invoices": row["outstanding"] = money(row.get("outstanding"))

def apply_snapshot(db, connection, run_id, snapshot):
    validate(snapshot)
    # Lock and verify fencing token before publishing a complete snapshot.
    lock = db.query(SyncConnection).filter_by(id=connection.id, active_token=run_id, enabled=True).populate_existing().with_for_update().first()
    if lock is None: raise ProviderError("Sync lease was replaced or connection paused")
    counts = {"created":0,"updated":0,"unchanged":0,"missing":0}
    existing = {(r.entity,r.external_id):r for r in db.query(SyncRecord).filter_by(connection_id=connection.id).all()}
    for entity in ENTITIES:
        for data in snapshot[entity]:
            key = (entity,data["external_id"]); fingerprint = digest(data); row = existing.pop(key,None)
            if row is None:
                row = SyncRecord(id=str(uuid4()),connection_id=connection.id,entity=entity,external_id=key[1],data=data,fingerprint=fingerprint,present=True,seen_run_id=run_id)
                db.add(row); counts["created"]+=1
            else:
                changed = row.fingerprint != fingerprint or not row.present
                counts["updated" if changed else "unchanged"]+=1
                if changed: row.data=data; row.fingerprint=fingerprint
                row.present=True; row.seen_run_id=run_id
    for row in existing.values():
        if row.present: row.present=False; counts["missing"]+=1
    stamp=now(); lock.last_success_at=stamp; lock.lease_until=None; lock.active_token=None
    lock.consecutive_failures=0; lock.schedule_error=None
    lock.next_sync_at=stamp+timedelta(minutes=lock.interval_minutes or 15) if lock.auto_sync else None
    run=db.get(SyncRun,run_id); run.status="completed"; run.completed_at=stamp; run.counts=counts
    db.commit()
    return run

def execute(db, connection, snapshot=None, scheduled=False):
    identity=connection.id; run_id=acquire(db,connection,scheduled=scheduled)
    try:
        if snapshot is None:
            if connection.provider == "tally": raise ProviderError("Tally sync requires a snapshot from the local agent")
            source=db.query(ImportConnection).filter_by(id=connection.source_connection_id,organization_id=connection.organization_id,branch_id=connection.branch_id,created_by=connection.created_by).with_for_update().first()
            if source is None: raise ProviderError("Accounting account is disconnected; reconnect before syncing")
            snapshot=pull(db,connection,source)
        return apply_snapshot(db,connection,run_id,snapshot)
    except Exception as exc:
        db.rollback()
        db.query(SyncConnection).filter_by(id=identity,active_token=run_id).update({"active_token":None,"lease_until":None},synchronize_session=False)
        run=db.get(SyncRun,run_id); run.status="failed"; run.completed_at=now()
        run.error=str(exc)[:300] if isinstance(exc,ProviderError) else "Sync failed; previous successful snapshot was preserved"
        row=db.query(SyncConnection).filter_by(id=identity).populate_existing().first()
        if row is not None and not row.active_token:
            row.consecutive_failures=(row.consecutive_failures or 0)+1
            row.schedule_error=run.error
            delay=min(360,max(5,row.interval_minutes or 15)*2**min(row.consecutive_failures-1,6))
            row.next_sync_at=now()+timedelta(minutes=delay) if row.auto_sync else None
        db.commit()
        return run

def balances(db, connection_id):
    # Do not subtract payments again: invoice outstanding already includes allocations.
    totals={}
    for record in db.query(SyncRecord).filter_by(connection_id=connection_id,entity="invoices",present=True):
        data=record.data
        if data.get("status") in {"draft","void","cancelled"}: continue
        key=(data["customer_external_id"],data["currency"])
        totals[key]=totals.get(key,Decimal(0))+Decimal(data["outstanding"])
    return [{"customer_external_id":customer,"currency":currency,"outstanding":str(amount)} for (customer,currency),amount in sorted(totals.items())]
