"""Owner-reviewed removal of exactly one verified dedicated company database.

No shared-database fallback, wildcard SQL, DROP OWNED, or cross-company cleanup.
The durable removal receipt fences routing before non-transactional database DDL.
"""
from datetime import timedelta
import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from psycopg import sql
from sqlalchemy import and_, or_

from app.core.config import settings
from app.platform_owner.auth import current_platform_admin
from app.platform_owner.session import get_platform_db
from app.platform_owner import service as s
from app.platform_owner.models import (PlatformTenantDatabase as Database, PlatformDatabaseServer as Server,
    PlatformSignupRequest as Signup, PlatformRecord, PlatformEvent, PlatformAudit)
from app.platform_owner.tenant_provisioning import admin_url, pg_connection

router = APIRouter(prefix="/customers", tags=["Company removal"])
AUDIENCE = "company-removal-preview"


class RemovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    preview_token: str = Field(max_length=4000)
    confirmation: str = Field(max_length=100)
    reason: str = Field(min_length=5, max_length=500)


def target(db, actor, ident, *, retry=False):
    s.require(actor, "tenant.manage")
    if actor.role != "owner":
        raise HTTPException(403, "Only the platform owner can permanently remove a company")
    tenant = s.tenant_for(db, actor, ident, "tenant.manage", lock=True)
    signup = db.query(Signup).filter_by(id=tenant.signup_id).with_for_update().first()
    database = db.query(Database).filter_by(signup_id=tenant.signup_id).with_for_update().first()
    if not signup or signup.company_id != tenant.company_id or signup.legal_hold:
        raise HTTPException(409, "Company identity is inconsistent or has a legal hold")
    if not database or database.company_id != tenant.company_id:
        raise HTTPException(409, "Removal requires a dedicated company database; shared data cannot be removed here")
    try:
        suffix = uuid.UUID(database.tenant_uuid).hex
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(409, "Company database identity is invalid") from None
    if (database.database_name != "suite_c_"+suffix or database.runtime_role != "suite_r_"+suffix
            or database.workspace_code != f"company-{signup.id}"):
        raise HTTPException(409, "Company database does not match its registered identity")
    server = db.get(Server, database.server_id)
    if not server or database.database_name == server.template_database:
        raise HTTPException(409, "A shared or template database cannot be removed")
    if tenant.status == "removed" and database.status == "removed":
        return tenant, signup, database, server
    if database.status != "ready" and not (retry and database.status == "deleting"):
        raise HTTPException(409, "Company database is not ready for removal")
    if tenant.config.get("retention_until"):
        from datetime import datetime
        if s.aware(datetime.fromisoformat(tenant.config["retention_until"])) > s.now():
            raise HTTPException(409, "Company retention period has not ended")
    # Reject corrupt owner links before doing any DDL; never clean up another
    # company's records just because a signup ID happens to match.
    if db.query(PlatformRecord.id).filter(or_(
        and_(PlatformRecord.tenant_id == tenant.id, PlatformRecord.signup_id.isnot(None), PlatformRecord.signup_id != signup.id),
        and_(PlatformRecord.signup_id == signup.id, PlatformRecord.tenant_id.isnot(None), PlatformRecord.tenant_id != tenant.id),
    )).first():
        raise HTTPException(409, "Owner records have inconsistent company links")
    return tenant, signup, database, server


def identity(database, server):
    return {"signup_id": database.signup_id, "company_id": database.company_id,
        "tenant_uuid": database.tenant_uuid, "workspace": database.workspace_code,
        "database": database.database_name, "role": database.runtime_role,
        "server_id": server.id, "host": server.host, "port": server.port,
        "version": database.routing_version}


def verify_database(database, server):
    url = admin_url(server)
    # The deterministic names above also prevent legacy/control-plane targets.
    with pg_connection(url.set(database=database.database_name)) as connection:
        row = connection.execute("SELECT tenant_uuid,company_id,current_database() FROM suite_tenant_identity WHERE singleton=true").fetchone()
        companies = connection.execute("SELECT id FROM companies ORDER BY id LIMIT 2").fetchall()
        if row != (database.tenant_uuid, database.company_id, database.database_name) or companies != [(database.company_id,)]:
            raise HTTPException(409, "Database contains a different company; nothing was removed")
        return connection.execute("SELECT oid FROM pg_database WHERE datname=current_database()").fetchone()[0]


@router.post("/{ident}/removal/preview")
def preview(ident: int, actor=Depends(current_platform_admin), db=Depends(get_platform_db)):
    tenant, signup, database, server = target(db, actor, ident, retry=True)
    if tenant.status == "removed":
        raise HTTPException(409, "Company has already been removed")
    expected = identity(database, server)
    job = None
    if database.status == "deleting":
        job = db.query(PlatformRecord).filter_by(kind="company_removal",tenant_id=ident).with_for_update().first()
        expected["version"] -= 1
        if not job or job.data.get("target") != expected or not job.data.get("oid"):
            raise HTTPException(409, "Removal receipt does not match this company")
        oid = job.data["oid"]
    else:
        oid = verify_database(database, server)
    payload = {"aud": AUDIENCE, "sub": str(actor.id), "tenant_id": ident,
        "target": expected, "oid": oid, "exp": s.now()+timedelta(minutes=10)}
    token = jwt.encode(payload, settings.PLATFORM_SECRET_KEY, algorithm="HS256")
    if job:
        job.data = {**job.data, "proof_hash": s.digest(token)}
        db.commit()
    return {"company_name": tenant.name, "company_id": tenant.company_id, "workspace": database.workspace_code,
        "confirmation": "REMOVE "+database.workspace_code, "permanent": True,
        "preview_token": token}


def drop_database(database, server, oid):
    """Serialize with provisioning and recheck the physical database before DDL."""
    url = admin_url(server)
    with pg_connection(url) as control:
        control.execute("SELECT pg_advisory_lock(%s)", (database.company_id,))
        found = control.execute("SELECT oid FROM pg_database WHERE datname=%s", (database.database_name,)).fetchone()
        # A durable deleting receipt allows a retry after DDL succeeded but the
        # owner transaction did not. No substitute database is ever selected.
        if found:
            if found[0] != oid or verify_database(database, server) != oid:
                raise HTTPException(409, "Database changed since preview; nothing was removed")
            control.execute(sql.SQL("ALTER ROLE {} NOLOGIN").format(sql.Identifier(database.runtime_role)))
            control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database.database_name)))
        # DROP ROLE fails closed if anything elsewhere references this identity.
        # Never use DROP OWNED to try to resolve such dependencies.
        if control.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (database.runtime_role,)).fetchone():
            control.execute(sql.SQL("ALTER ROLE {} NOLOGIN").format(sql.Identifier(database.runtime_role)))
            control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(database.runtime_role)))


def finalize(db, actor, tenant, signup, database, job, reason):
    own = or_(PlatformRecord.tenant_id == tenant.id, PlatformRecord.signup_id == signup.id)
    ids = [row[0] for row in db.query(PlatformRecord.id).filter(own, PlatformRecord.id != job.id)]
    events = or_(and_(PlatformEvent.entity == "tenant", PlatformEvent.entity_id == tenant.id),
        and_(PlatformEvent.entity == "signup", PlatformEvent.entity_id == signup.id),
        and_(PlatformEvent.entity == "record", PlatformEvent.entity_id.in_(ids)))
    db.query(PlatformEvent).filter(events).update({"before": {}, "after": {}, "reason": "Company removed"}, synchronize_session=False)
    db.query(PlatformAudit).filter_by(signup_id=signup.id).update({"reason": "Company removed"}, synchronize_session=False)
    db.query(PlatformRecord).filter(own, PlatformRecord.id != job.id).delete(synchronize_session=False)
    email = f"removed-company-{tenant.company_id}@example.com"
    signup.name, signup.company_name, signup.email, signup.phone = "Removed company", None, email, ""
    signup.notes, signup.tags, signup.campaign, signup.source = None, [], "", "removed"
    signup.workflow, signup.consent_evidence, signup.review_reason = {}, "Company removed", "Company removed"
    signup.status, signup.deleted_at, signup.user_id = "removed", s.now(), None
    signup.version += 1
    tenant.name, tenant.admin_email, tenant.status = f"Removed company #{tenant.id}", email, "removed"
    tenant.config, tenant.usage = {"removed_at": s.now().isoformat(), "removal_job_id": job.id}, {}
    database.status, database.encrypted_password, database.last_error = "removed", "", None
    job.state, job.title = "completed", "Company removal receipt"
    job.data = {"company_id": database.company_id, "workspace": database.workspace_code, "database_removed": True}
    s.event(db, actor, "tenant.removed", "tenant", tenant.id, reason,
        after={"status": "removed", "workspace": database.workspace_code})
    db.commit()


@router.post("/{ident}/removal")
def remove(ident: int, data: RemovalInput, actor=Depends(current_platform_admin), db=Depends(get_platform_db)):
    try:
        proof = jwt.decode(data.preview_token, settings.PLATFORM_SECRET_KEY, algorithms=["HS256"], audience=AUDIENCE,
            options={"require": ["sub", "exp", "aud"]})
    except jwt.PyJWTError:
        raise HTTPException(409, "Removal preview expired or is invalid; review the company again") from None
    tenant, signup, database, server = target(db, actor, ident, retry=True)
    if proof.get("sub") != str(actor.id) or proof.get("tenant_id") != ident or data.confirmation != "REMOVE "+database.workspace_code:
        raise HTTPException(422, "Preview and typed confirmation must match this company")
    if tenant.status == "removed":
        return {"removed": True, "workspace": database.workspace_code}
    expected = identity(database, server)
    job = db.query(PlatformRecord).filter_by(kind="company_removal", tenant_id=ident).with_for_update().first()
    if database.status == "deleting":
        if not job or job.data.get("proof_hash") != s.digest(data.preview_token):
            raise HTTPException(409, "A different removal is already in progress")
        expected["version"] -= 1
    if proof.get("target") != expected:
        raise HTTPException(409, "Company changed since preview; nothing was removed")
    if database.status != "deleting":
        if verify_database(database, server) != proof["oid"]:
            raise HTTPException(409, "Database changed since preview")
        job = PlatformRecord(kind="company_removal", title="Company removal in progress", state="running", tenant_id=ident,
            signup_id=signup.id, owner_id=actor.id, data={"proof_hash": s.digest(data.preview_token), "target": expected, "oid": proof["oid"]})
        db.add(job)
        database.status, tenant.status = "deleting", "deleting"
        database.routing_version += 1
        db.commit()  # Fence routing before the irreversible DDL, also on retry.
    try:
        db.refresh(database, with_for_update=True)
        db.refresh(server, with_for_update=True)
        fenced = {**proof["target"], "version": proof["target"]["version"]+1}
        if identity(database, server) != fenced or database.status != "deleting":
            raise HTTPException(409, "Removal destination changed; no database was removed")
        drop_database(database, server, proof["oid"])
    except HTTPException:
        raise
    except Exception:
        database.last_error = "Company removal incomplete; retry the same reviewed request"
        db.commit()
        raise HTTPException(503, "Company is blocked from access. Removal is incomplete; retry the reviewed request") from None
    finalize(db, actor, tenant, signup, database, job, data.reason)
    return {"removed": True, "workspace": database.workspace_code}
