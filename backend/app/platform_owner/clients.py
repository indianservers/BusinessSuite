"""Owner-only account intelligence, based on saved aggregate usage snapshots."""
from datetime import datetime, timedelta
import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db
from app.platform_owner.auth import current_platform_admin
from app.platform_owner.models import PlatformTenant, PlatformRecord, PlatformTenantDatabase, PlatformDatabaseServer
from app.platform_owner.session import get_platform_db
from app.platform_owner import service as s

router = APIRouter()


def timestamp(value):
    try:
        return s.aware(datetime.fromisoformat(value)) if value else None
    except (ValueError, TypeError):
        return None


def account_view(row, database=None):
    result = s.encode(row)
    config, usage = row.config or {}, row.usage or {}
    profile = config.get("account_profile", {})
    current = s.now()
    flags = []
    end = timestamp(config.get("trial_ends_at")) if row.status == "trial" else None
    renewal = timestamp(profile.get("renewal_at"))
    review = timestamp(profile.get("next_review_at"))
    recorded = timestamp(usage.get("recorded_at"))
    if row.status in {"suspended", "cancelled", "offboarded"}: flags.append(row.status)
    if not usage.get("activated") and not config.get("activated_at"): flags.append("activation_pending")
    if end and end <= current: flags.append("trial_expired")
    elif end and end <= current + timedelta(days=7): flags.append("trial_ending")
    if renewal and renewal <= current + timedelta(days=30): flags.append("renewal_due")
    if review and review <= current: flags.append("review_due")
    if not recorded or recorded < current - timedelta(days=2): flags.append("usage_stale")
    if recorded and usage.get("activated") and not usage.get("active_30d"): flags.append("inactive")
    seats = usage.get("seats", 0)
    seat_limit = config.get("seats", 0)
    storage_limit = config.get("storage_mib", 0) * 1048576
    seat_percent = round(100 * seats / seat_limit, 1) if seat_limit and "seats" in usage else None
    storage_percent = round(100 * usage.get("storage_bytes", 0) / storage_limit, 1) if storage_limit and "storage_bytes" in usage else None
    if seat_percent is not None and seat_percent >= 80: flags.append("seat_capacity")
    if storage_percent is not None and storage_percent >= 80: flags.append("storage_capacity")
    result.update(profile=profile, flags=flags, seat_percent=seat_percent, storage_percent=storage_percent,
                  database=database, trial_days_left=(end-current).days if end else None)
    return result


def directory(db, actor, search="", status="", attention="", module="", priority=""):
    s.require(actor, "tenant.read")
    query = s.scoped(db.query(PlatformTenant).filter(PlatformTenant.status != "removed"), actor, PlatformTenant)
    if status: query = query.filter(PlatformTenant.status == status)
    # Only owner metadata is read here. Never connect to every company on page load.
    tenants = query.order_by(PlatformTenant.id.desc()).all()
    signup_ids = [r.signup_id for r in tenants]
    databases = {}
    if signup_ids:
        for d, server in db.query(PlatformTenantDatabase, PlatformDatabaseServer).join(
            PlatformDatabaseServer, PlatformDatabaseServer.id == PlatformTenantDatabase.server_id
        ).filter(PlatformTenantDatabase.signup_id.in_(signup_ids)):
            databases[d.signup_id] = {"workspace": d.workspace_code, "state": d.status,
                "server": server.name, "database_name": d.database_name, "routing_version": d.routing_version}
    items = [account_view(r, databases.get(r.signup_id)) for r in tenants]
    if search:
        term = search.casefold()
        items = [r for r in items if term in " ".join([r["name"], r["admin_email"], str(r["id"]),
            r["database"]["workspace"] if r["database"] else "", " ".join(r["profile"].get("tags", []))]).casefold()]
    if module: items = [r for r in items if module in r["config"].get("modules", [])]
    if priority: items = [r for r in items if r["profile"].get("priority", "normal") == priority]
    if attention: items = [r for r in items if r["flags"] and (attention == "any" or attention in r["flags"])]
    return items


def summarize(items):
    currencies, statuses, modules = {}, {}, {}
    for r in items:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        for module in r["config"].get("modules", []): modules[module] = modules.get(module, 0) + 1
        if r["status"] == "active":
            currency = r["config"].get("currency", "INR")
            currencies[currency] = currencies.get(currency, 0) + r["config"].get("monthly_price_minor", 0)
    return {"total": len(items), "statuses": statuses, "modules": modules, "mrr_by_currency": currencies,
        "attention": sum(bool(r["flags"]) for r in items),
        "seats": sum(r["usage"].get("seats", 0) for r in items),
        "active_30d": sum(r["usage"].get("active_30d", 0) for r in items),
        "storage_bytes": sum(r["usage"].get("storage_bytes", 0) for r in items),
        "unsynced": sum(not r["usage"].get("recorded_at") for r in items)}


@router.get("/client-directory")
def client_directory(search: str = Query("", max_length=150), status: str = "", attention: str = "", module: str = "",
                     priority: str = "", sort: Literal["newest", "name", "seats", "attention", "last_login"] = "newest",
                     page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                     actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    items = directory(db, actor, search, status, attention, module, priority)
    summary = summarize(items)
    keys = {"newest": lambda r: -r["id"], "name": lambda r: r["name"].casefold(),
        "seats": lambda r: -r["usage"].get("seats", 0), "attention": lambda r: -len(r["flags"]),
        "last_login": lambda r: r["usage"].get("last_login_at") or ""}
    items.sort(key=keys[sort], reverse=sort == "last_login")
    return {"items": items[(page-1)*page_size:page*page_size], "total": len(items), "page": page,
            "page_size": page_size, "summary": summary}


@router.get("/client-directory/export")
def client_export(search: str = Query("", max_length=150), status: str = "", attention: str = "", module: str = "",
                  priority: str = "", actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    rows = directory(db, actor, search, status, attention, module, priority)
    stream = io.StringIO(); writer = csv.writer(stream)
    writer.writerow(["Client ID", "Business", "Admin email", "Status", "Workspace", "Priority", "Tags", "Used seats", "Licensed seats", "Active users 30d", "Last login", "Usage synced", "Attention"])
    for r in rows:
        writer.writerow([s.safe_csv(v) for v in [r["id"], r["name"], r["admin_email"], r["status"],
            r["database"]["workspace"] if r["database"] else "shared", r["profile"].get("priority", "normal"),
            ", ".join(r["profile"].get("tags", [])), r["usage"].get("seats"), r["config"].get("seats"),
            r["usage"].get("active_30d"), r["usage"].get("last_login_at"), r["usage"].get("recorded_at"), ", ".join(r["flags"])]])
    return Response(stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="clients.csv"'})


class AccountProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    version: int = Field(0, ge=0, strict=True)
    priority: Literal["normal", "high", "critical"] = "normal"
    stage: Literal["onboarding", "adopting", "established", "at_risk"] = "onboarding"
    contact_name: str = Field("", max_length=120)
    contact_phone: str = Field("", max_length=40)
    industry: str = Field("", max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=20)
    next_review_at: datetime | None = None
    renewal_at: datetime | None = None
    reason: str = Field(min_length=3, max_length=1000)


@router.patch("/clients/{ident}/profile")
def save_profile(ident: int, data: AccountProfile, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    row = s.tenant_for(db, actor, ident, "tenant.manage", lock=True)
    before = row.config.get("account_profile", {})
    if data.version != before.get("version", 0): raise HTTPException(409, "Account profile changed. Refresh before saving.")
    tags = list(dict.fromkeys(t.strip() for t in data.tags if t.strip()))
    if any(len(t) > 50 for t in tags): raise HTTPException(422, "Tags must be 50 characters or fewer")
    profile = data.model_dump(mode="json", exclude={"reason"})
    profile.update(tags=tags, version=data.version+1, updated_at=s.now().isoformat())
    row.config = {**row.config, "account_profile": profile}
    s.event(db, actor, "tenant.profile_updated", "tenant", row.id, data.reason, before, profile)
    db.commit()
    return profile


@router.get("/clients/{ident}/statistics")
def client_statistics(ident: int, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    row = s.tenant_for(db, actor, ident)
    samples = db.query(PlatformRecord).filter_by(kind="usage_snapshot", tenant_id=ident).order_by(PlatformRecord.id.desc()).limit(30).all()
    database = db.query(PlatformTenantDatabase).filter_by(signup_id=row.signup_id).first()
    placement = None
    if database:
        server = db.get(PlatformDatabaseServer, database.server_id)
        placement = {"workspace": database.workspace_code, "database_name": database.database_name,
            "state": database.status, "server": server.name if server else "Unavailable", "routing_version": database.routing_version}
    return {"usage": row.usage, "database": placement, "snapshots": [{"id": x.id, "recorded_at": x.created_at.isoformat(), "usage": x.data} for x in reversed(samples)]}


def save_usage(db, row, usage):
    row.usage = usage
    db.add(PlatformRecord(kind="usage_snapshot", title="Aggregate client usage", tenant_id=row.id, state="recorded", data=usage))
    db.flush()
    old = db.query(PlatformRecord.id).filter_by(kind="usage_snapshot", tenant_id=row.id).order_by(PlatformRecord.id.desc()).offset(30).all()
    if old: db.query(PlatformRecord).filter(PlatformRecord.id.in_([x[0] for x in old])).delete(synchronize_session=False)


class UsageBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[Annotated[int, Field(strict=True, gt=0, le=2147483647)]] = Field(min_length=1, max_length=10)


@router.post("/client-usage-refresh")
def refresh_usage(data: UsageBatch, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db), business: Session = Depends(get_db)):
    from app.platform_owner import bridge
    # Authorize the whole selection before doing any work.
    ids = list(dict.fromkeys(data.ids))
    for ident in ids: s.tenant_for(db, actor, ident, "tenant.manage")
    result = []
    for ident in ids:
        try:
            with db.begin_nested():
                row = s.tenant_for(db, actor, ident, "tenant.manage", lock=True)
                save_usage(db, row, bridge.usage(business, row))
                if row.usage.get("activated") and not row.config.get("activated_at"):
                    row.config = {**row.config, "activated_at": s.now().isoformat()}
                if row.usage.get("activated"):
                    for invitation in db.query(PlatformRecord).filter_by(kind="customer_invitation", signup_id=row.signup_id):
                        invitation.state = "accepted"
                s.event(db, actor, "tenant.sync_usage", "tenant", row.id, "Selected-client aggregate usage refresh")
            db.commit()
            result.append({"id": ident, "ok": True})
        except Exception:
            db.rollback()
            business.rollback()
            result.append({"id": ident, "ok": False, "error": "Usage could not be read. Check this company's database and retry."})
    return {"items": result}
