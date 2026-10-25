"""Persisted scheduling adapters. Native records remain the source of truth."""
from app.access.catalog import permission_objects
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.deps import get_db, get_current_user
from app.module_registry import is_app_enabled
from app.apps.business_os.services.module_service import assert_module_enabled
from app.apps.scheduling.models import ScheduleBoard

router = APIRouter(prefix="/scheduling", tags=["Scheduling"])


def fail(detail, code=422):
    raise HTTPException(status_code=code, detail=detail)


def permission(user, names):
    return user.is_superuser or bool(set(names) & {p.name for p in (permission_objects(user))})


def context(db, user, module, source):
    installed = "srm" if module == "inventory" else module
    if installed not in {"crm", "srm", "hrms", "fam"} or not is_app_enabled(installed):
        fail("Scheduling module unavailable", 404)
    if module == "crm":
        from app.apps.crm.api.router import _organization_id
        tenant = _organization_id(db, user)
        view, manage = {"crm_view", "crm_manage", "crm_admin"}, {"crm_manage", "crm_admin"}
        allowed = {"calendar"}
    elif module in {"srm", "inventory"}:
        from app.apps.srm.api.router import _org
        tenant = _org(user)
        view, manage = {"srm_view", "srm_manage", "srm_admin"}, {"srm_manage", "srm_admin"}
        allowed = {"purchase-orders"} if module == "inventory" else {"sales-orders", "contracts", "engagements"}
    elif module == "fam":
        from app.apps.fam.api.router import company_id_for
        from app.apps.fam.access import FAM_VIEW_PERMISSIONS, FAM_SETTINGS_PERMISSIONS
        tenant = company_id_for(user)
        view, manage, allowed = FAM_VIEW_PERMISSIONS, FAM_SETTINGS_PERMISSIONS, {"financial-years"}
    else:
        from app.api.v1.leave import _current_company_id
        tenant = _current_company_id(user)
        view, manage, allowed = set(), {"leave_approve", "hr_admin"}, {"leave"}
    if source not in allowed:
        fail("Unknown schedule source", 404)
    if module != "hrms" and not permission(user, view):
        fail("Schedule access denied", 403)
    assert_module_enabled(db, installed, company_id=tenant or 1)
    return f"{installed}:{tenant if tenant is not None else 'unassigned'}", permission(user, manage)


def resolve(db, user, module, source, key, lock=False):
    """Resolve every id through tenant and record scope, including dependency endpoints."""
    context(db, user, module, source)
    first = last = None
    if module == "crm":
        from app.apps.crm.api.router import _organization_id, _get_resource, _base_query, _apply_record_visibility
        parts = key.split(":")
        fields = {"tasks": (None, "due_date"), "meetings": ("start_time", "end_time"), "activities": ("activity_date", "due_date"), "calls": (None, "call_time"), "deals": (None, "expected_close_date"), "quotations": (None, "expiry_date")}
        if len(parts) != 2 or parts[0] not in fields or not parts[1].isdigit(): fail("Invalid calendar record", 404)
        kind, number = parts[0], int(parts[1]); resource = _get_resource(kind)
        query = _apply_record_visibility(_base_query(db, resource, _organization_id(db, user)), resource, user, db).filter(resource.model.id == number)
        first, last = fields[kind]
    elif module in {"srm", "inventory"}:
        from app.apps.srm.models import SRMSalesOrder, SRMContract, SRMEngagement, SRMPurchaseOrder
        from app.apps.srm.access import sales_order_query, engagement_query
        from app.apps.srm.api.router import _org
        configs = {"sales-orders": (SRMSalesOrder, "expected_start_date", "expected_end_date"), "contracts": (SRMContract, "effective_date", "expiry_date"), "engagements": (SRMEngagement, "planned_start_date", "planned_end_date"), "purchase-orders": (SRMPurchaseOrder, "order_date", "expected_date")}
        model, first, last = configs[source]
        if not key.isdigit(): fail("Invalid record", 404)
        query = sales_order_query(db, user) if source == "sales-orders" else engagement_query(db, user) if source == "engagements" else db.query(model).filter(model.deleted_at.is_(None))
        # Even superusers must use the board's tenant, preventing cross-tenant links.
        from app.apps.srm.services.commercial import scoped
        query = query.filter(scoped(model.organization_id,user), model.id == int(key))
    elif module == "fam":
        from app.apps.fam.models import FAMFinancialYear
        from app.apps.fam.api.router import company_id_for
        if not key.isdigit(): fail("Invalid record", 404)
        query = db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id_for(user), FAMFinancialYear.id == int(key))
        first, last = "start_date", "end_date"
    else:
        from app.models.leave import LeaveRequest
        from app.api.v1.leave import _current_company_id, _is_hr_admin
        if not key.isdigit(): fail("Invalid record", 404)
        query = db.query(LeaveRequest).filter(LeaveRequest.id == int(key), LeaveRequest.deleted_at.is_(None))
        if not user.is_superuser:
            company = _current_company_id(user)
            query = query.filter(LeaveRequest.company_id == company)
            if not _is_hr_admin(user):
                ids = [user.employee.id] if user.employee else []
                if permission(user, {"leave_approve"}) and user.employee:
                    from app.models.employee import Employee
                    ids += [row.id for row in db.query(Employee).filter(Employee.reporting_manager_id == user.employee.id).all()]
                query = query.filter(LeaveRequest.employee_id.in_(ids))
        first, last = "from_date", "to_date"
    item = (query.with_for_update() if lock else query).first()
    if not item: fail("Schedule record not found", 404)
    return item, first, last


def editable(db, user, module, source, key, item):
    _, manage = context(db, user, module, source)
    state = str(getattr(item, "status", "")).lower()
    if module == "hrms":
        from app.api.v1.leave import _is_hr_admin
        manage = manage or _is_hr_admin(user) or bool(user.employee and user.employee.id == item.employee_id)
        return bool(manage and state == "pending")
    if module == "fam":
        from app.apps.fam.models import FAMVoucher, FAMAccountingPeriod
        return bool(manage and state == "open" and not db.query(FAMVoucher.id).filter_by(financial_year_id=item.id).first() and not db.query(FAMAccountingPeriod.id).filter_by(financial_year_id=item.id).first())
    if module == "inventory":
        from app.apps.srm.models import SRMGoodsReceipt
        if db.query(SRMGoodsReceipt.id).filter_by(purchase_order_id=item.id).first():
            return False
    return bool(manage and state not in {"done", "completed", "cancelled", "canceled", "closed", "expired", "terminated", "received", "fulfilled", "rejected", "won", "lost", "accepted"})


def board_query(db, tenant, module, source):
    return db.query(ScheduleBoard).filter_by(tenant_key=tenant, module=module, source=source)


def board_for_write(db, tenant, module, source, revision):
    board = board_query(db, tenant, module, source).with_for_update().first()
    if not board:
        board = ScheduleBoard(tenant_key=tenant, module=module, source=source, revision=0, starts={}, links=[])
        db.add(board)
        try: db.flush()
        except IntegrityError:
            db.rollback(); fail("Schedule changed. Refresh and retry.", 409)
    if board.revision != revision: fail("Schedule changed. Refresh and retry.", 409)
    return board


def day(value):
    return value.date() if isinstance(value, datetime) else value


def dates(item, first, last, key, board):
    end = day(getattr(item, last))
    start = day(getattr(item, first)) if first else (date.fromisoformat(board.starts[key]) if board and key in board.starts else end)
    return start or end, end or start


class SchedulePatch(BaseModel):
    start: date
    end: date
    revision: int = Field(ge=0)
    expected_start: date | None = None
    expected_end: date | None = None


class LinkPatch(BaseModel):
    source_id: str = Field(max_length=100)
    target_id: str = Field(max_length=100)
    type: Literal["FS", "SS", "FF", "SF"] = "FS"
    lag: int = Field(default=0, ge=-3650, le=3650)
    revision: int = Field(ge=0)


@router.get("/{module}/{source}")
def state(module: str, source: str, ids: str = Query("", max_length=20000), db: Session = Depends(get_db), user=Depends(get_current_user)):
    tenant, _ = context(db, user, module, source)
    keys = list(dict.fromkeys(ids.split(","))) if ids else []
    if len(keys) > 500: fail("Load at most 500 schedules at a time")
    board = board_query(db, tenant, module, source).first()
    records = {}
    for key in keys:
        try:
            item, first, last = resolve(db, user, module, source, key)
        except HTTPException as exc:
            if exc.status_code == 404: continue
            raise
        start, end = dates(item, first, last, key, board)
        records[key] = {"can_edit": editable(db, user, module, source, key, item), "start": start, "end": end}
    links = [link for link in (board.links if board else []) if link["source_id"] in records and link["target_id"] in records]
    return {"revision": board.revision if board else 0, "records": records, "dependencies": links}


def native_date(item, field, value):
    previous = getattr(item, field)
    # Preserve time of day for meetings, activities and task deadlines.
    from sqlalchemy import DateTime
    is_datetime = isinstance(item.__table__.columns[field].type, DateTime)
    setattr(item, field, datetime.combine(value, previous.timetz() if isinstance(previous, datetime) else time.min) if is_datetime else value)


def audit_link(db, user, module, source, action, link):
    from app.models.audit import AuditLog
    db.add(AuditLog(user_id=user.id, method="POST" if action == "CREATE" else "DELETE", endpoint=f"/scheduling/{module}/{source}/dependencies", action=f"DEPENDENCY_{action}", status_code=200, description=f"{link['source_id']} -> {link['target_id']} ({link['type']}, {link['lag']} days)"))


def update_leave(db, user, item, start, end):
    from app.crud import crud_leave as crud
    from app.models.leave import LeaveBalance
    if start.year != end.year: fail("Leave must stay within one balance year")
    if item.is_half_day and start != end: fail("Half-day leave must stay on a single day")
    # Lock the employee to serialize overlapping requests as well as balance changes.
    from app.models.employee import Employee
    db.query(Employee).filter_by(id=item.employee_id).with_for_update().first()
    if crud.has_overlapping_leave(db, item.employee_id, start, end, exclude_request_id=item.id): fail("Leave dates overlap another request", 409)
    old = db.query(LeaveBalance).filter_by(employee_id=item.employee_id, leave_type_id=item.leave_type_id, year=item.from_date.year).with_for_update().first()
    new = db.query(LeaveBalance).filter_by(employee_id=item.employee_id, leave_type_id=item.leave_type_id, year=start.year).with_for_update().first()
    if not old or not new: fail("No leave balance allocated for the requested year")
    count = crud.calculate_leave_days(start, end, item.is_half_day)
    available = crud.get_available_balance(new) + (item.days_count if old.id == new.id else Decimal("0"))
    if available < count: fail("Insufficient leave balance")
    old.pending -= item.days_count
    crud.add_ledger_entry(db, balance=old, transaction_type="schedule_released", amount=item.days_count, balance_after=crud.get_available_balance(old), leave_request_id=item.id, created_by=user.id, reason="Leave rescheduled")
    new.pending += count
    crud.add_ledger_entry(db, balance=new, transaction_type="schedule_pending", amount=-count, balance_after=crud.get_available_balance(new), leave_request_id=item.id, created_by=user.id, reason="Leave rescheduled")
    item.days_count = count


@router.patch("/{module}/{source}/records/{key}")
def save(module: str, source: str, key: str, payload: SchedulePatch, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if payload.end < payload.start: fail("End date must be on or after start date")
    tenant, _ = context(db, user, module, source)
    board = board_for_write(db, tenant, module, source, payload.revision)
    item, first, last = resolve(db, user, module, source, key, lock=True)
    if not editable(db, user, module, source, key, item): fail("This record is read-only or locked", 403)
    previous = dates(item, first, last, key, board)
    if previous != (payload.expected_start, payload.expected_end): fail("Record dates changed. Refresh and retry.", 409)
    if module == "hrms": update_leave(db, user, item, payload.start, payload.end)
    if module == "fam":
        from app.apps.fam.models import FAMFinancialYear, FAMVoucher, FAMAccountingPeriod
        # Lock company to serialize year-overlap checks against other scheduling requests.
        from app.models.company import Company
        db.query(Company).filter_by(id=item.company_id).with_for_update().first()
        if payload.start >= payload.end: fail("Financial year end must be after start")
        if db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == item.company_id, FAMFinancialYear.id != item.id, FAMFinancialYear.start_date <= payload.end, FAMFinancialYear.end_date >= payload.start).first(): fail("Financial years cannot overlap", 409)
        if db.query(FAMVoucher).filter(FAMVoucher.financial_year_id == item.id).first() or db.query(FAMAccountingPeriod).filter(FAMAccountingPeriod.financial_year_id == item.id).first(): fail("Year has accounting periods or vouchers; dates cannot be changed", 409)
    native_date(item, last, payload.end)
    if first: native_date(item, first, payload.start)
    else: board.starts = {**board.starts, key: payload.start.isoformat()}
    if module == "crm" and key.startswith("meetings:"):
        if item.end_time <= item.start_time: fail("Meeting end time must be after its start time")
        if item.external_provider: item.sync_status = "pending"
    board.revision += 1
    from app.models.audit import AuditLog
    db.add(AuditLog(user_id=user.id, method="PATCH", endpoint=f"/scheduling/{module}/{source}/records/{key}", action="SCHEDULE", status_code=200, description=f"{previous} -> {payload.start}/{payload.end}"))
    db.commit()
    return {"revision": board.revision, "start": payload.start, "end": payload.end}


@router.post("/{module}/{source}/dependencies", status_code=201)
def create_link(module: str, source: str, payload: LinkPatch, db: Session = Depends(get_db), user=Depends(get_current_user)):
    tenant, _ = context(db, user, module, source)
    board = board_for_write(db, tenant, module, source, payload.revision)
    if payload.source_id == payload.target_id: fail("A record cannot depend on itself")
    for key in (payload.source_id, payload.target_id):
        item, _, _ = resolve(db, user, module, source, key, lock=True)
        if not editable(db, user, module, source, key, item): fail("Both records must be editable", 403)
    if any(link["source_id"] == payload.source_id and link["target_id"] == payload.target_id for link in board.links): fail("Dependency already exists", 409)
    graph = {}
    for link in board.links: graph.setdefault(link["source_id"], []).append(link["target_id"])
    pending, visited = [payload.target_id], set()
    while pending:
        key = pending.pop()
        if key == payload.source_id: fail("Dependency would create a cycle", 409)
        if key not in visited:
            visited.add(key); pending.extend(graph.get(key, []))
    link = {"id": str(uuid4()), **payload.model_dump(exclude={"revision"})}
    board.links = [*board.links, link]; board.revision += 1
    audit_link(db, user, module, source, "CREATE", link)
    db.commit()
    return {"revision": board.revision, "dependency": link}


@router.delete("/{module}/{source}/dependencies/{link_id}")
def delete_link(module: str, source: str, link_id: str, revision: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    tenant, _ = context(db, user, module, source)
    board = board_for_write(db, tenant, module, source, revision)
    link = next((link for link in board.links if link["id"] == link_id), None)
    if not link: fail("Dependency not found", 404)
    for key in (link["source_id"], link["target_id"]):
        item, _, _ = resolve(db, user, module, source, key, lock=True)
        if not editable(db, user, module, source, key, item): fail("Dependency is read-only", 403)
    board.links = [link for link in board.links if link["id"] != link_id]; board.revision += 1
    audit_link(db, user, module, source, "DELETE", link)
    db.commit()
    return {"revision": board.revision}
