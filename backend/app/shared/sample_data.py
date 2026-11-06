"""Explicitly requested fictional records, with an exact, guarded deletion manifest.

Core inserts intentionally avoid email, invitation and integration ORM listeners.
No users, permissions, real payments or posted accounting vouchers are created.
"""
from collections import Counter
from datetime import date, timedelta
from uuid import uuid4
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import inspect, select

from app.shared.import_models import ImportBatch
from app.shared.import_service import digest, json_value, now

MODULES = {"crm", "hrms", "project_management", "srm", "fam"}


def context(db, user, request):
    from app.access.models import AccessMembership
    from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
    from app.apps.srm.services.commercial import tenant
    from app.branches.service import context as branch_context
    company = tenant(user)
    # Lock the durable company membership to serialize imports and deletion.
    membership = db.query(AccessMembership).filter_by(company_id=company, user_id=user.id, active=True, is_admin=True).with_for_update().first()
    if not membership:
        raise HTTPException(403, "Only the company administrator can manage sample data")
    # Subscription setup is company control data and has no branch stamp.
    p, s = TenantSubscriptionPlan.__table__, TenantSubscription.__table__
    record = db.connection().execute(select(p.c.id, p.c.config_json).select_from(p.join(s, s.c.plan_id == p.c.id))
        .where(s.c.company_id == company, p.c.code.like("platform-signup-%")).with_for_update()).mappings().first()
    plan = SimpleNamespace(**record) if record else None
    if not plan or not (plan.config_json or {}).get("company_signup"):
        raise HTTPException(403, "Sample data is available after company signup approval")
    ctx = branch_context(db, user, company, request.headers.get("X-Suite-Branch"))
    if ctx.branch_id is None or ctx.branch_id not in ctx.writable:
        raise HTTPException(403, "Choose a writable branch")
    return ctx, plan


def status(db, ctx, plan):
    table = ImportBatch.__table__
    record = db.connection().execute(select(table).where(table.c.organization_id == ctx.company_id,
        table.c.source == "company_sample", table.c.status == "imported")).mappings().first()
    batch = SimpleNamespace(**record) if record else None
    return {"requested": bool((plan.config_json or {}).get("sample_data_requested")),
            "modules": sorted(set((plan.config_json or {}).get("modules", [])) & MODULES),
            "batch": {"id": batch.id, "branch_id": batch.branch_id, "counts": batch.preview_json["counts"],
                      "total": len(batch.changes_json)} if batch else None}


def populate(db, ctx, user, modules):
    from app.db.base import Base
    from app.branches.catalog import SHARED, resource_key
    from app.models.security_boundary import SecurityResourceOwnership
    tables = Base.metadata.tables
    manifest, counts = [], Counter()
    token = uuid4().hex[:8]
    prefix = f"S{token}"
    today = date.today()

    def add(table_name, **values):
        name = table_name
        table = tables[table_name]
        for key, value in {"organization_id": ctx.company_id, "company_id": ctx.company_id,
                           "branch_id": ctx.branch_id, "created_by": user.id,
                           "created_by_user_id": user.id, "owner_user_id": user.id}.items():
            if key in table.c:
                # CRM company_id denotes a customer, not tenant ownership.
                if key == "company_id" and "organization_id" in table.c:
                    continue
                values.setdefault(key, value)
        ident = db.connection().execute(table.insert().values(**values).returning(table.c.id)).scalar_one()
        if name not in SHARED:
            db.connection().execute(tables["suite_branch_ownership"].insert().values(resource_table=name,
                resource_key=resource_key(table, dict(values, id=ident)), company_id=ctx.company_id,
                branch_id=ctx.branch_id, source="company_sample"))
        # Legacy roots (employees, salaries etc.) need tenant ownership as well.
        db.connection().execute(SecurityResourceOwnership.__table__.insert().values(resource_table=name, resource_id=ident, company_id=ctx.company_id))
        snapshot = db.connection().execute(select(table).where(table.c.id == ident)).mappings().one()
        manifest.append({"table": name, "id": ident, "after": {k: json_value(v) for k, v in snapshot.items()}})
        counts[name] += 1
        return ident

    if "hrms" in modules:
        for i in range(40):
            employee = add("employees", employee_id=f"{prefix}-E{i:03}", first_name=["Asha", "Ravi", "Maya", "Arjun"][i % 4],
                last_name=f"Sample {i+1}", work_email=f"employee.{i}@{token}.example.com", date_of_joining=today-timedelta(days=60+i),
                employment_type="Full-time", status="Active", work_location=["Office", "Hybrid", "Remote"][i % 3])
            add("employee_salaries", employee_id=employee, ctc=600000+i*12000, basic=25000+i*500, hra=12500, effective_from=today.replace(day=1), is_active=True)
            add("expense_claims", employee_id=employee, claim_number=f"{prefix}-EXP{i}", claim_type=["Travel","Meals","Internet"][i%3],
                expense_date=today-timedelta(days=i%14), amount=500+i*50, description="Fictional sample expense", status="Draft", submitted_by=user.id)
            for j in range(6):
                add("attendances", employee_id=employee, attendance_date=today-timedelta(days=j),
                    status=["Present", "Absent", "Present"][j % 3], total_hours=0 if j % 3 == 1 else 8, source="Manual", remarks="Sample attendance")

    if "crm" in modules:
        pipeline = add("crm_pipelines", name="Sample sales pipeline", is_default=False)
        stages = [add("crm_pipeline_stages", pipeline_id=pipeline, name=name, probability=prob, position=i,
                      is_won=name == "Won", is_lost=name == "Lost")
                  for i, (name, prob) in enumerate([("Qualification", 20), ("Proposal", 50), ("Negotiation", 75), ("Won", 100), ("Lost", 0)])]
        for i in range(40):
            account = add("crm_companies", name=f"Sample {['Aster','Cedar','Meridian','Prism'][i%4]} {i+1}",
                email=f"accounts.{i}@{token}.example.com", account_type="Customer", status="Active", city=["Hyderabad","Chennai","Bengaluru"][i%3])
            contact = add("crm_contacts", company_id=account, full_name=f"Sample Buyer {i+1}", first_name="Sample", last_name=f"Buyer {i+1}", email=f"buyer.{i}@{token}.example.com")
            lead = add("crm_leads", full_name=f"Sample Lead {i+1}", first_name="Sample", email=f"lead.{i}@{token}.example.com",
                status=["New","Contacted","Qualified"][i%3], source=["Website","Referral","Trade Show"][i%3], rating=["Hot","Warm","Cold"][i%3])
            deal = add("crm_deals", company_id=account, contact_id=contact, pipeline_id=pipeline, stage_id=stages[i%5], name=f"Sample rollout {i+1}",
                amount=50000+i*1000, currency="INR", probability=[20,50,75,100,0][i%5], status="Won" if i%5 == 3 else "Lost" if i%5 == 4 else "Open", expected_close_date=today+timedelta(days=i-10))
            for j in range(4):
                add("crm_activities", lead_id=lead, company_id=account, contact_id=contact, deal_id=deal,
                    entity_type="lead", entity_id=lead, activity_type=["Call","Meeting","Task","Email"][j],
                    title=f"Sample follow-up {j+1}", subject=f"Sample follow-up {j+1}", status="Planned", description="Fictional sample activity; no message is sent.")

    if "project_management" in modules:
        workspace = add("pms_workspaces", name="Sample delivery workspace")
        add("pms_workspace_members", workspace_id=workspace, user_id=user.id, role="Admin")
        for i in range(10):
            project = add("pms_projects", workspace_id=workspace, name=f"Sample delivery project {i+1}", project_key=f"{prefix}P{i}",
                manager_user_id=user.id, status=["Active","Planned","On Hold","Completed"][i%4], priority=["High","Medium","Low"][i%3],
                start_date=today-timedelta(days=30), due_date=today+timedelta(days=i-3), budget_amount=100000+i*5000)
            add("pms_project_members", project_id=project, user_id=user.id, role="Manager", allocation_percent=20)
            for j in range(16):
                task = add("pms_tasks", project_id=project, task_key=f"{prefix}P{i}-{j+1}", title=f"Sample {['Discovery','Design','Implementation','Testing'][j%4]} {j+1}",
                    reporter_user_id=user.id, status=["To Do","In Progress","In Review","Done"][j%4], priority=["High","Medium","Low"][j%3], due_date=today+timedelta(days=j-5))
                add("pms_time_logs", project_id=project, task_id=task, user_id=user.id, log_date=today-timedelta(days=j%7),
                    duration_minutes=60+j*5, description="Sample delivery work", approval_status="Pending", is_billable=j%2 == 0)

    if "srm" in modules:
        warehouse = add("srm_warehouses", warehouse_code=f"{prefix}-WH", warehouse_name="Sample warehouse")
        for i in range(40):
            product = add("srm_products", sku=f"{prefix}-{i:03}", item_name=f"Sample {['Laptop','Monitor','Router','Support service'][i%4]} {i+1}",
                product_type="service" if i%4 == 3 else "goods", unit_code="NOS", sales_rate=1000, purchase_rate=700, gst_rate=[0,5,12,18][i%4], default_warehouse_id=warehouse)
            if i%4 != 3:
                product_table = tables["srm_products"]
                db.connection().execute(product_table.update().where(product_table.c.id == product).values(current_quantity=20, average_cost=700))
                row = db.connection().execute(select(product_table).where(product_table.c.id == product)).mappings().one()
                manifest[-1]["after"] = {k:json_value(v) for k,v in row.items()}
                add("srm_inventory_balances", product_id=product, warehouse_id=warehouse, quantity=20, average_cost=700)
                add("srm_inventory_movements", movement_number=f"{prefix}-OPEN{i}", movement_type="opening_stock", movement_date=today,
                    product_id=product, warehouse_id=warehouse, quantity_in=20, quantity_out=0, rate=700, value=14000, notes="Fictional sample opening stock")
            order = add("srm_sales_orders", order_number=f"{prefix}-SO{i}", title=f"Sample order {i+1}", status="draft", subtotal=1000, total_amount=1000)
            add("srm_sales_order_lines", sales_order_id=order, product_id=product, description="Sample item", quantity=1, unit_price=1000, line_total=1000)
            invoice = add("srm_invoices", invoice_number=f"{prefix}-INV{i}", sales_order_id=order, status="draft", issue_date=today,
                due_date=today+timedelta(days=30), subtotal=1000, total_amount=1000, paid_amount=0, balance_amount=1000)
            add("srm_invoice_lines", invoice_id=invoice, description="Sample item", quantity=1, unit_price=1000, line_total=1000)
            for j in range(3):
                add("srm_engagements", engagement_number=f"{prefix}-ENG{i}-{j}", sales_order_id=order, name=f"Sample delivery phase {j+1}", status="planned", billing_type="fixed", budget_amount=1000)

    if "fam" in modules:
        groups = {nature: add("fam_ledger_groups", group_code=f"{prefix}-{nature}", group_name=f"Sample {nature}", nature=nature)
                  for nature in ["asset","liability","income","expense"]}
        for i in range(40):
            nature = ["asset","liability","income","expense"][i%4]
            ledger = add("fam_ledgers", ledger_code=f"{prefix}-L{i}", ledger_name=f"Sample {nature} account {i+1}", ledger_group_id=groups[nature], nature=nature)
            if i == 0:
                bank = add("fam_bank_accounts", ledger_id=ledger, bank_name="Sample Bank", account_number_masked="SAMPLE-XXXX-0001")
                statement = add("fam_bank_statements", bank_account_id=bank, statement_period_start=today-timedelta(days=30), statement_period_end=today,
                    imported_file_name="Fictional sample statement", imported_file_hash=prefix, imported_by=user.id)
                for j in range(30):
                    add("fam_bank_statement_lines", statement_id=statement, transaction_date=today-timedelta(days=29-j), description=f"Sample receipt {j+1}",
                        reference_number=f"{prefix}-TX{j}", credit_amount=1000, debit_amount=0, balance=1000*(j+1), line_hash=f"{prefix}-{j}", matched_status="unmatched")
            party = add("fam_parties", party_code=f"{prefix}-C{i}", legal_name=f"Sample trading company {i+1}", party_type="customer" if i%2 == 0 else "supplier", email=f"finance.{i}@{token}.example.com")
            add("fam_cost_centers", code=f"{prefix}-CC{i}", name=f"Sample cost center {i+1}")
            for j in range(5):
                add("fam_bill_references", party_id=party, ledger_id=ledger, bill_number=f"{prefix}-B{i}-{j}",
                    bill_date=today-timedelta(days=j*10), due_date=today+timedelta(days=30-j*10), bill_type="invoice" if i%2 == 0 else "bill",
                    original_amount=1000, outstanding_amount=1000, status="open")
    return manifest, dict(counts)


def remove(db, batch):
    """Check every snapshot and inbound FK before deleting in reverse order."""
    from app.db.base import Base
    from app.branches.catalog import resource_key
    tables = Base.metadata.tables
    changes = batch.changes_json or []
    inbound = {}
    # Optional connectors can register models without installing their tables
    # in every dedicated company database. Inspect the actual destination.
    installed = set(inspect(db.connection()).get_table_names())
    from app.branches.catalog import INFERRED
    for child in tables.values():
        if child.name not in installed:
            continue
        for column in child.c:
            targets = {fk.column.table.name for fk in column.foreign_keys if fk.column.name == "id"}
            if column.name in INFERRED:
                targets.add(INFERRED[column.name])
            if child.name.startswith("srm_") and column.name == "customer_id":
                targets.add("crm_companies")
            for target in targets:
                inbound.setdefault(target, []).append(column)
    for item in changes:
        table = tables[item["table"]]
        row = db.connection().execute(select(table).where(table.c.id == item["id"]).with_for_update()).mappings().first()
        if row is None or digest({k:json_value(v) for k,v in row.items()}) != digest(item["after"]):
            raise HTTPException(409, "Sample records were changed or removed. No sample data was deleted.")
    for item in reversed(changes):
        table, ident = tables[item["table"]], item["id"]
        for column in inbound.get(table.name, []):
            if db.connection().execute(select(column).where(column == ident).limit(1)).first():
                raise HTTPException(409, "Other records use the sample data. Remove those dependencies first; no sample data was deleted.")
        db.connection().execute(table.delete().where(table.c.id == ident))
        ownership = tables["suite_branch_ownership"]
        db.connection().execute(ownership.delete().where(ownership.c.resource_table == table.name,
            ownership.c.resource_key == resource_key(table, {"id": ident}), ownership.c.company_id == batch.organization_id))
        # Remove tenant registry entries using the same manifest, never a name prefix.
        from app.models.security_boundary import SecurityResourceOwnership
        registry = SecurityResourceOwnership.__table__
        db.connection().execute(registry.delete().where(registry.c.resource_table == table.name, registry.c.resource_id == ident, registry.c.company_id == batch.organization_id))
    batch.status, batch.revoked_at = "revoked", now()
    batch.version += 1
