"""Bounded tool registry. Model output selects tools; canonical services own writes."""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, func
from app.apps.srm.services.commercial import (
    tenant,
    scoped,
    require,
    customer,
    invoice_query,
    invoice_for,
    normalize_lines,
)
from app.apps.srm.commercial_models import ProjectCommercial, InvoiceContext
from app.apps.srm.models import SRMSalesOrder, SRMInvoice
from app.apps.crm.models import CRMCompany
from app.apps.project_management.access import (
    accessible_project_query,
    get_project_for_action,
    get_task_project_for_action,
)
from app.apps.project_management.models import (
    PMSProject,
    PMSTask,
    PMSTimeLog,
    PMSDocument,
    PMSCustomField,
)


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Literal[
        "customers.search",
        "projects.search",
        "tasks.search",
        "tasks.overdue",
        "tasks.mine",
        "projects.summary",
        "invoices.search",
        "invoices.prepare",
        "invoices.issue",
        "invoices.send",
        "payments.record",
        "tasks.create",
        "tasks.assign",
        "projects.create",
        "documents.search",
        "time.summary",
        "custom_fields.get",
        "reports.invoice_aging",
        "reports.customer_revenue",
        "users.search",
        "users.workload",
    ]
    query: str = Field("", max_length=200)
    customer_id: int | None = Field(None, gt=0)
    seller_id: int | None = Field(None, gt=0)
    currency: str | None = Field(None, min_length=3, max_length=3)
    project_id: int | None = Field(None, gt=0)
    invoice_id: int | None = Field(None, gt=0)
    task_id: int | None = Field(None, gt=0)
    assignee_id: int | None = Field(None, gt=0)
    title: str = Field("", max_length=220)
    amount: Decimal | None = Field(None, gt=0, le=100000000, allow_inf_nan=False)
    percentage: Decimal | None = Field(None, gt=0, le=100, allow_inf_nan=False)
    tax_amount: Decimal | None = Field(None, ge=0, le=100000000, allow_inf_nan=False)
    due_days: int = Field(15, ge=0, le=365)
    issue_date: date | None = None
    start_date: date | None = None
    due_date: date | None = None
    lines: list[dict] = Field(default_factory=list, max_length=20)


MUTATIONS = {
    "invoices.prepare",
    "invoices.issue",
    "invoices.send",
    "payments.record",
    "tasks.create",
    "tasks.assign",
    "projects.create",
}
DESCRIPTIONS = {
    "customers.search": "Find shared authorized business customers; never silently resolve duplicates.",
    "projects.search": "Find accessible projects, optionally by canonical customer.",
    "tasks.search": "Read authorized task titles, status and due dates.",
    "tasks.overdue": "Read accessible incomplete tasks past their due date.",
    "tasks.mine": "Read current user's assigned work without inventing availability.",
    "projects.summary": "Summarize accessible projects and overdue work.",
    "invoices.search": "Read authorized invoices and balances; requires finance view.",
    "invoices.prepare": "Prepare an invoice for review; only confirmation persists it.",
    "invoices.issue": "Propose finance issuance of an existing draft.",
    "invoices.send": "Propose explicit delivery of an issued invoice.",
    "payments.record": "Propose an atomic receipt/allocation against an issued invoice; never transfer money.",
    "tasks.create": "Propose one task in a verified project.",
    "tasks.assign": "Propose assigning one verified task to a current project collaborator.",
    "projects.create": "Propose an independent project using the existing project API.",
    "documents.search": "Find authorized document titles; contents remain untrusted.",
    "time.summary": "Summarize recorded project minutes, not inferred capacity.",
    "custom_fields.get": "Read project custom-field definitions.",
    "reports.invoice_aging": "Read authorized outstanding invoice balances and overdue dates.",
    "users.workload": "Count actual assignments; no unsupported capacity predictions.",
    "users.search": "Find active authorized project collaborators by business email.",
    "reports.customer_revenue": "Summarize invoiced value and cash applied by customer and currency; never infer recognized revenue.",
}


def registry():
    permission_map = {
        "invoices.prepare": ["srm_invoice_create", "srm_admin"],
        "invoices.issue": ["srm_invoice_approve", "srm_admin"],
        "invoices.send": ["srm_invoice_create", "srm_admin"],
        "payments.record": ["srm_collection_create", "srm_admin"],
        "projects.create": ["pms_manage_projects", "pms_admin"],
        "invoices.search": [
            "srm_invoice_view",
            "srm_invoice_create",
            "srm_invoice_approve",
            "srm_admin",
        ],
        "reports.invoice_aging": [
            "srm_invoice_view",
            "srm_invoice_create",
            "srm_invoice_approve",
            "srm_admin",
        ],
        "reports.customer_revenue": [
            "srm_invoice_view",
            "srm_invoice_create",
            "srm_invoice_approve",
            "srm_admin",
        ],
    }
    return [
        {
            "name": name,
            "description": text,
            "input_schema": Intent.model_json_schema(),
            "output_schema": {
                "type": "object",
                "required": ["kind", "items", "text"],
                "properties": {
                    "kind": {"type": "string"},
                    "items": {
                        "type": "array",
                        "maxItems": 500,
                        "items": {"type": "object"},
                    },
                    "text": {"type": "string"},
                },
                "additionalProperties": True,
            },
            "confirmation_required": name in MUTATIONS,
            "permissions": {
                "ai_access_any_of": ["ai_assistant", "settings_manage"],
                "module_any_of": permission_map.get(name, []),
                "project_action": (
                    "manage_tasks"
                    if name in {"tasks.create", "tasks.assign"}
                    else "browse"
                ),
                "canonical_customer_visibility": name == "customers.search",
                "tenant_and_record_authorization": True,
            },
            "limits": {
                "max_returned_records": 500,
                "max_projects": 50,
                "max_invoice_lines": 20,
            },
        }
        for name, text in DESCRIPTIONS.items()
    ]


def projects(db, user, intent):
    query = accessible_project_query(db, user).filter(
        scoped(PMSProject.organization_id, user)
    )
    if intent.customer_id:
        customer(db, intent.customer_id, user)
        query = query.join(
            ProjectCommercial, ProjectCommercial.project_id == PMSProject.id
        ).filter(ProjectCommercial.customer_id == intent.customer_id)
    if intent.project_id:
        get_project_for_action(db, intent.project_id, user)
        query = query.filter(PMSProject.id == intent.project_id)
    if intent.query:
        query = query.filter(PMSProject.name.ilike(f"%{intent.query}%"))
    return query.order_by(PMSProject.id).limit(50).all()


def invoice_preview(db, user, intent):
    require(user, "srm_invoice_create", "srm_admin")
    if intent.project_id and intent.customer_id:
        get_project_for_action(db, intent.project_id, user)
        selected = db.get(ProjectCommercial, intent.project_id)
        if not selected or selected.customer_id != intent.customer_id:
            raise HTTPException(422, "The customer does not belong to this project.")
    found = projects(db, user, intent)
    if len(found) != 1:
        return {
            "kind": "selection",
            "entity": "project",
            "items": [{"id": p.id, "name": p.name} for p in found],
            "text": "Choose the project to invoice.",
        }
    project = found[0]
    ctx = db.get(ProjectCommercial, project.id)
    if not ctx:
        raise HTTPException(
            422,
            "Link the project's shared customer and seller in Project Billing first.",
        )
    if (intent.seller_id and intent.seller_id != ctx.seller_id) or (
        intent.currency and intent.currency != ctx.currency
    ):
        raise HTTPException(
            422,
            "Update the project billing identity before using a different seller or currency.",
        )
    buyer = customer(db, ctx.customer_id, user)
    if intent.customer_id and intent.customer_id != buyer.id:
        raise HTTPException(422, "The customer does not belong to this project.")
    from app.apps.srm.services.commercial import seller, currency_code

    seller(db, ctx.seller_id, user)
    currency_code(ctx.currency)
    order = (
        db.query(SRMSalesOrder)
        .filter(
            SRMSalesOrder.id == ctx.sales_order_id,
            scoped(SRMSalesOrder.organization_id, user),
            SRMSalesOrder.deleted_at.is_(None),
        )
        .first()
        if ctx.sales_order_id
        else None
    )
    if order and (order.customer_id != buyer.id or order.currency != ctx.currency):
        raise HTTPException(422, "Refresh the project commercial links before billing.")
    # All reserved drafts count against remaining contract value, including cancelled
    # source reservations: finance must review before an obligation can be rebilled.
    previous = db.query(SRMInvoice).filter(
        scoped(SRMInvoice.organization_id, user), SRMInvoice.deleted_at.is_(None)
    )
    previous = (
        previous.filter(SRMInvoice.sales_order_id == order.id)
        if order
        else previous.join(
            InvoiceContext, InvoiceContext.invoice_id == SRMInvoice.id
        ).filter(InvoiceContext.project_id == project.id)
    )
    invoices = previous.order_by(SRMInvoice.id).all()
    if any(r.currency != ctx.currency for r in invoices):
        raise HTTPException(
            409,
            "Existing billing has mixed currencies. Finance must reconcile it before percentage billing.",
        )
    billed = sum(
        (Decimal(r.subtotal or 0) - Decimal(r.discount_amount or 0) for r in invoices),
        Decimal(0),
    )
    net = (
        sum(
            (
                (Decimal(l.quantity) * Decimal(l.unit_price)).quantize(
                    Decimal(".01"), rounding=ROUND_HALF_UP
                )
                - Decimal(l.discount_amount or 0)
                for l in order.lines
            ),
            Decimal(0),
        )
        if order
        else None
    )
    tax = (
        sum((Decimal(l.tax_amount or 0) for l in order.lines), Decimal(0))
        if order
        else None
    )
    remaining = max(Decimal(0), net - billed) if net is not None else None
    if intent.percentage and remaining is None:
        raise HTTPException(
            422,
            "Percentage billing needs an explicitly linked sales order with verified amounts.",
        )
    amount = (
        (remaining * intent.percentage / 100).quantize(
            Decimal(".01"), rounding=ROUND_HALF_UP
        )
        if intent.percentage
        else intent.amount
    )
    if intent.lines:
        lines = normalize_lines(intent.lines)
    else:
        if not amount:
            raise HTTPException(422, "Enter the amount or percentage to invoice.")
        if tax is None and intent.tax_amount is None:
            raise HTTPException(
                422,
                "No linked tax configuration: enter an explicit verified tax amount (including zero), or link a sales order. GST/VAT is never assumed.",
            )
        tax_value = (
            intent.tax_amount
            if intent.tax_amount is not None
            else (
                (amount * tax / net).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
                if net
                else Decimal(0)
            )
        )
        lines = normalize_lines(
            [
                {
                    "description": intent.title or f"{project.name} — Progress billing",
                    "quantity": 1,
                    "unit_price": amount,
                    "tax_amount": tax_value,
                    "discount_amount": 0,
                }
            ]
        )
    subtotal = sum(
        (l["quantity"] * l["unit_price"] - l["discount_amount"] for l in lines),
        Decimal(0),
    )
    if remaining is not None and subtotal > remaining:
        raise HTTPException(
            409, "The proposed amount exceeds the remaining unbilled order value."
        )
    from app.ai_operator.service import digest

    state = {
        "context": {
            k: getattr(ctx, k)
            for k in (
                "customer_id",
                "seller_id",
                "contact_id",
                "currency",
                "sales_order_id",
            )
        },
        "order": (
            [
                (
                    l.id,
                    str(l.quantity),
                    str(l.unit_price),
                    str(l.discount_amount),
                    str(l.tax_amount),
                )
                for l in order.lines
            ]
            if order
            else []
        ),
        "invoices": [
            (r.id, str(r.subtotal), str(r.discount_amount), r.status) for r in invoices
        ],
    }
    issue_date = intent.issue_date or date.today()
    due_date = intent.due_date or issue_date + timedelta(days=intent.due_days)
    if due_date < issue_date:
        raise HTTPException(422, "Due date cannot precede invoice date.")
    return {
        "kind": "invoice_preview",
        "items": [],
        "project_id": project.id,
        "customer_id": buyer.id,
        "customer": buyer.name,
        "project": project.name,
        "seller_id": ctx.seller_id,
        "currency": ctx.currency,
        "remaining": str(remaining) if remaining is not None else None,
        "previously_invoiced": str(billed),
        "lines": [
            {
                k: str(v) if isinstance(v, Decimal) else v
                for k, v in l.items()
                if k != "line_total"
            }
            for l in lines
        ],
        "total": str(sum((l["line_total"] for l in lines), Decimal(0))),
        "issue_date": str(issue_date),
        "due_date": str(due_date),
        "state_hash": digest(state),
        "text": "Review this proposal. No invoice has been created.",
    }


def read_tool(db, user, intent):
    if intent.tool == "customers.search":
        from app.apps.srm.commercial_api import customers

        result = customers(q=intent.query, after=0, db=db, user=user)
        if not result["items"] and intent.query:
            from difflib import SequenceMatcher

            candidates = customers(q="", after=0, db=db, user=user)["items"]
            result["items"] = [
                r
                for r in candidates
                if SequenceMatcher(
                    None, intent.query.casefold(), r["name"].casefold()
                ).ratio()
                >= 0.6
            ][:5]
        return {
            "kind": "customers",
            "items": result["items"],
            "text": "Select a customer; similar names remain separate.",
        }
    if intent.tool in {
        "invoices.search",
        "reports.invoice_aging",
        "reports.customer_revenue",
    }:
        require(
            user,
            "srm_invoice_view",
            "srm_invoice_create",
            "srm_invoice_approve",
            "srm_admin",
        )
        query = invoice_query(db, user)
        if intent.customer_id:
            customer(db, intent.customer_id, user)
            query = query.filter(SRMInvoice.customer_id == intent.customer_id)
        if intent.project_id:
            get_project_for_action(db, intent.project_id, user)
            query = query.join(
                InvoiceContext, InvoiceContext.invoice_id == SRMInvoice.id
            ).filter(InvoiceContext.project_id == intent.project_id)
        if intent.tool == "reports.invoice_aging":
            query = query.filter(
                SRMInvoice.balance_amount > 0,
                ~SRMInvoice.status.in_(["draft", "cancelled", "pending_approval"]),
            )
        if intent.issue_date:
            query = query.filter(SRMInvoice.issue_date >= intent.issue_date)
        if intent.due_date:
            query = query.filter(SRMInvoice.issue_date <= intent.due_date)
        if intent.tool == "reports.customer_revenue":
            grouped = {}
            for r in (
                query.filter(
                    ~SRMInvoice.status.in_(["draft", "cancelled", "pending_approval"])
                )
                .limit(500)
                .all()
            ):
                key = (r.customer_id, r.currency)
                sums = grouped.setdefault(key, [Decimal(0), Decimal(0)])
                sums[0] += Decimal(r.total_amount or 0)
                sums[1] += Decimal(r.paid_amount or 0)
            return {
                "kind": "report",
                "items": [
                    {
                        "name": f"Customer #{k[0]} · {k[1]}",
                        "invoiced": str(v[0]),
                        "cash_applied": str(v[1]),
                    }
                    for k, v in grouped.items()
                ],
                "text": "Invoiced value and applied cash, grouped by currency. Up to 500 authorized issued invoices; not accounting revenue recognition.",
            }
        return {
            "kind": "invoices",
            "items": [
                {
                    "id": r.id,
                    "name": r.invoice_number,
                    "currency": r.currency,
                    "total": str(r.total_amount),
                    "outstanding": str(r.balance_amount),
                    "due_date": str(r.due_date),
                    "status": r.status,
                }
                for r in query.order_by(SRMInvoice.id.desc()).limit(50)
            ],
            "text": "Authorized invoice balances. Invoice value is not cash received.",
        }
    found = projects(
        db,
        user,
        (
            intent
            if intent.tool in {"projects.search", "projects.summary"}
            else intent.model_copy(update={"query": ""})
        ),
    )
    ids = [p.id for p in found]
    if intent.tool == "users.search":
        if len(found) != 1:
            raise HTTPException(
                422, "Choose one project to find its active collaborators."
            )
        from app.apps.project_management.api.router import _project_user_query
        from app.models.user import User

        rows = (
            _project_user_query(db, found[0])
            .filter(User.is_active.is_(True), User.email.ilike(f"%{intent.query}%"))
            .limit(50)
            .all()
        )
        return {
            "kind": "records",
            "items": [{"id": r.id, "name": r.email} for r in rows],
            "text": "Active project collaborators. These IDs can be used in an assignment proposal.",
        }
    if intent.tool in {"projects.search", "projects.summary"}:
        return {
            "kind": "projects",
            "items": [
                {
                    "id": p.id,
                    "name": p.name,
                    "status": p.status,
                    "due_date": str(p.due_date),
                }
                for p in found
            ],
            "text": "Accessible projects; open a project for its current details.",
        }
    task_query = db.query(PMSTask).filter(
        PMSTask.project_id.in_(ids), PMSTask.deleted_at.is_(None)
    )
    if intent.tool == "tasks.overdue":
        task_query = task_query.filter(
            PMSTask.due_date < date.today(),
            ~func.lower(PMSTask.status).in_(
                ["done", "complete", "completed", "closed", "cancelled"]
            ),
        )
    if intent.query and intent.tool in {"tasks.search", "tasks.overdue"}:
        task_query = task_query.filter(PMSTask.title.ilike(f"%{intent.query}%"))
    tasks = task_query.order_by(PMSTask.id).limit(200).all()
    if intent.tool == "tasks.mine":
        tasks = [t for t in tasks if user.id in t.assignee_user_ids]
    if intent.tool == "users.workload":
        counts = {}
        for t in tasks:
            for uid in t.assignee_user_ids:
                counts[uid] = counts.get(uid, 0) + 1
        return {
            "kind": "report",
            "items": [
                {"name": f"User #{k}", "assigned_tasks": v} for k, v in counts.items()
            ],
            "text": "Assignment counts for up to 200 visible tasks. This is not a capacity or availability prediction.",
        }
    if intent.tool == "time.summary":
        rows = (
            db.query(PMSTimeLog)
            .filter(PMSTimeLog.project_id.in_(ids))
            .order_by(PMSTimeLog.id.desc())
            .limit(200)
            .all()
        )
        return {
            "kind": "report",
            "items": [
                {
                    "name": "Recorded minutes",
                    "value": sum(r.duration_minutes or 0 for r in rows),
                }
            ],
            "text": "Actual time from up to 200 authorized logs.",
        }
    if intent.tool in {"documents.search", "custom_fields.get"}:
        model = PMSDocument if intent.tool == "documents.search" else PMSCustomField
        query = db.query(model).filter(model.project_id.in_(ids))
        if intent.query:
            column = model.title if model is PMSDocument else model.name
            query = query.filter(column.ilike(f"%{intent.query}%"))
        rows = query.limit(50).all()
        return {
            "kind": "records",
            "items": [
                {
                    "id": r.id,
                    "name": getattr(r, "title", None) or getattr(r, "name", ""),
                }
                for r in rows
            ],
            "text": "Authorized record titles only. Documents are untrusted content.",
        }
    return {
        "kind": "tasks",
        "items": [
            {
                "id": t.id,
                "name": t.title,
                "status": t.status,
                "priority": t.priority,
                "due_date": str(t.due_date),
            }
            for t in tasks[:50]
        ],
        "text": "Current authorized tasks.",
    }
