"""Cross-module snapshots and dated activity using the same scoped source queries as the apps."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import Date, String, and_, cast, func

from app.services.metrics import queries as q
from app.services.metrics.registry import REGISTRY, allowed, crm_query, open_deals


def business_overview(db, user, days=30):
    from app.apps.crm.models import CRMLead, CRMDeal, CRMContact
    from app.models.employee import Employee
    from app.apps.project_management.models import PMSTask
    from app.apps.project_management.access import accessible_project_query
    from app.apps.srm.access import sales_order_query
    from app.apps.srm.services.commercial import invoice_query
    from app.apps.srm.models import SRMSalesOrder, SRMInvoice
    from app.apps.fam.models import FAMVoucher, FAMLedger
    from app.branches.models import BranchOwnership
    from app.models.company import Branch

    context = q.business_context(db, user)
    zone = ZoneInfo(context["timezone"])
    today = datetime.fromisoformat(context["business_date"]).date()
    start = today - timedelta(days=days - 1)
    previous_start = start - timedelta(days=days)
    end = today + timedelta(days=1)
    branch_context = db.info.get("branch_context")
    branch_ids = ({branch_context.branch_id} if branch_context.branch_id else set(branch_context.allowed)) if branch_context else set()
    branches = db.query(Branch).filter(Branch.company_id == context["organization_id"], Branch.id.in_(branch_ids)).order_by(Branch.name).all()
    branch_rows = {branch.id: {"id": branch.id, "name": branch.name, "active": branch.is_active, "counts": {}} for branch in branches}
    points = { (start + timedelta(days=i)).isoformat(): {"date": (start + timedelta(days=i)).isoformat(), "previous_date": (previous_start + timedelta(days=i)).isoformat(), "current": {}, "previous": {}} for i in range(days) }

    def permitted(code):
        return allowed(db, user, REGISTRY[code])

    definitions = [
        ("crm", "CRM", "Leads", "crm.leads.total", CRMLead, lambda: crm_query(db, user, "leads"), CRMLead.created_at, "/crm/leads"),
        ("hrms", "HRMS", "Employees", "employees.total", Employee, lambda: q.employee_records(db, user), Employee.created_at, "/employees"),
        ("pms", "PMS", "Tasks", "pms.tasks.total", PMSTask, lambda: q.task_query(db, user), PMSTask.created_at, "/pms/tasks"),
        ("sales", "Sales", "Sales orders", "srm.orders.total", SRMSalesOrder, lambda: sales_order_query(db, user), SRMSalesOrder.created_at, "/srm/sales-orders"),
        ("finance", "Finance", "Posted vouchers", "fam.ledgers.active", FAMVoucher, lambda: db.query(FAMVoucher).filter(FAMVoucher.company_id == context["organization_id"], FAMVoucher.status == "posted"), FAMVoucher.voucher_date, "/fam/vouchers"),
    ]
    modules = []
    for key, name, label, permission, model, query_factory, timestamp, path in definitions:
        if not permitted(permission):
            modules.append({"key": key, "name": name, "label": label, "status": "restricted", "total": None, "current": None, "previous": None, "path": path, "details": {}})
            continue
        query = query_factory()
        total = q.unique_count(query, model.id)
        is_date = isinstance(timestamp.type, Date) and not hasattr(timestamp.type, "timezone")
        lower = previous_start if is_date else datetime.combine(previous_start, time.min, zone).astimezone(timezone.utc)
        upper = end if is_date else datetime.combine(end, time.min, zone).astimezone(timezone.utc)
        recent = query.filter(timestamp >= lower, timestamp < upper)
        # PostgreSQL groups instants in the organization's timezone. SQLite is
        # only the test dialect; convert its timestamps in Python for exact parity.
        if db.get_bind().dialect.name == "postgresql" or is_date:
            day = func.date(timestamp if is_date else func.timezone(context["timezone"], timestamp))
            dated = recent.order_by(None).with_entities(model.id.label("identity"), day.label("day")).distinct().subquery()
            daily = {str(day): count for day, count in db.query(dated.c.day, func.count()).group_by(dated.c.day).all()}
        else:
            daily = {}
            for _, instant in recent.order_by(None).with_entities(model.id, timestamp).distinct().all():
                day = instant.replace(tzinfo=instant.tzinfo or timezone.utc).astimezone(zone).date().isoformat()
                daily[day] = daily.get(day, 0) + 1
        current = sum(count for day, count in daily.items() if start.isoformat() <= day < end.isoformat())
        previous = sum(count for day, count in daily.items() if previous_start.isoformat() <= day < start.isoformat())
        for point in points.values():
            point["current"][key] = daily.get(point["date"], 0)
            point["previous"][key] = daily.get(point["previous_date"], 0)
        grouped = query.join(BranchOwnership, and_(BranchOwnership.resource_table == model.__tablename__, BranchOwnership.resource_key == cast(model.id, String), BranchOwnership.company_id == context["organization_id"], BranchOwnership.branch_id.in_(branch_ids))).order_by(None).with_entities(BranchOwnership.branch_id, func.count(func.distinct(model.id))).group_by(BranchOwnership.branch_id).all()
        assigned = 0
        for branch_id, count in grouped:
            if branch_id in branch_rows:
                branch_rows[branch_id]["counts"][key] = count
                assigned += count
        if total > assigned:
            branch_rows.setdefault(None, {"id": None, "name": "Unassigned / legacy records", "active": True, "counts": {}})["counts"][key] = total - assigned
        modules.append({"key": key, "name": name, "label": label, "status": "available", "total": total, "current": current, "previous": previous, "path": path, "details": {}})

    by_key = {item["key"]: item for item in modules}
    if by_key["crm"]["status"] == "available":
        by_key["crm"]["details"] = {"Contacts": q.unique_count(crm_query(db, user, "contacts"), CRMContact.id), "Open deals": q.unique_count(open_deals(db, user), CRMDeal.id)}
    if by_key["hrms"]["status"] == "available":
        by_key["hrms"]["details"] = {"Active / probation": q.unique_count(q.employee_records(db, user).filter(Employee.status.in_(q.EMPLOYED)), Employee.id)}
    if by_key["pms"]["status"] == "available":
        from app.apps.project_management.models import PMSProject
        by_key["pms"]["details"] = {"Projects": q.unique_count(accessible_project_query(db, user), PMSProject.id), "Completed tasks": q.unique_count(q.task_query(db, user).filter(PMSTask.status.in_(q.COMPLETED)), PMSTask.id)}
    money = {}
    if by_key["sales"]["status"] == "available":
        invoices = invoice_query(db, user)
        by_key["sales"]["details"] = {"Invoices": q.unique_count(invoices, SRMInvoice.id)}
        from app.apps.analytics.api.router import _financial_allowed
        if _financial_allowed(user):
            issued = invoices.filter(SRMInvoice.status.notin_(["draft", "pending_approval", "cancelled", "void"]))
            money = {"invoiced": q.amounts_by_currency(issued, SRMInvoice.currency, SRMInvoice.total_amount), "collected": q.amounts_by_currency(issued, SRMInvoice.currency, SRMInvoice.paid_amount), "outstanding": q.amounts_by_currency(issued, SRMInvoice.currency, SRMInvoice.balance_amount)}
    if by_key["finance"]["status"] == "available":
        by_key["finance"]["details"] = {"Active ledgers": db.query(FAMLedger).filter(FAMLedger.company_id == context["organization_id"], FAMLedger.active.is_(True)).count()}

    context.update(branch_scope="all" if branch_context and branch_context.branch_id is None else "selected", branch_count=len(branches), branch_id=branch_context.branch_id if branch_context else None)
    return {"context": context, "period": {"days": days, "start": start.isoformat(), "end": today.isoformat()}, "modules": modules, "series": list(points.values()), "branches": list(branch_rows.values()), "money": money, "definition": "Cards show current live record totals. The chart counts newly created leads, employee records, tasks and sales orders, and posted vouchers by voucher date. Deleted/archived records and permission-inaccessible data are excluded by source query. Currency amounts are current issued-invoice snapshots, never mixed across currencies."}
