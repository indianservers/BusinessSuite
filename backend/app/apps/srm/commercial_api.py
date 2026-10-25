"""Module entry points for the same commercial records and services."""
from app.access.catalog import permission_objects

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.company import Company
from app.apps.crm.models import CRMCompany, CRMContact, CRMTeam, CRMOwner
from app.apps.project_management.models import PMSProject, PMSClient, PMSTimeLog
from app.apps.project_management.access import (
    get_project_for_action,
    accessible_project_query,
)
from app.apps.srm.models import SRMInvoice, SRMInvoiceLine, SRMEngagement, SRMSalesOrder
from app.apps.srm.commercial_models import (
    CustomerLink,
    ProjectCommercial,
    InvoiceContext,
    InvoiceDelivery,
    SellerGrant,
    TimeBillingAllocation,
)
from app.apps.srm.services.commercial import (
    tenant,
    scoped,
    require,
    record,
    customer,
    seller,
    lock_tenant,
    money,
    invoice_for,
    invoice_query,
)

router = APIRouter()
DIRECTORY = (
    "crm_view",
    "crm_manage",
    "crm_admin",
    "srm_view",
    "srm_manage",
    "srm_admin",
    "srm_invoice_create",
    "srm_invoice_view",
    "srm_invoice_approve",
    "pms_manage_projects",
    "pms_admin",
)
FINANCE = ("srm_invoice_view", "srm_invoice_create", "srm_invoice_approve", "srm_admin")


def output(value):
    return {c.name: getattr(value, c.name) for c in value.__table__.columns}


def customer_profile(value):
    return {
        key: getattr(value, key)
        for key in (
            "id",
            "name",
            "address",
            "city",
            "state",
            "country",
            "email",
            "phone",
        )
    }


def allocation_profile(db, value):
    from app.apps.srm.commercial_models import ReceiptContext
    ctx = db.get(ReceiptContext, value.receipt_id)
    return output(value) | {"reversed_at": ctx.reversed_at if ctx else None, "can_reverse": bool(ctx and ctx.invoice_id == value.invoice_id and not ctx.reversed_at)}


@router.get("/business/customers")
def customers(
    q: str = Query("", max_length=100),
    after: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require(user, *DIRECTORY)
    query = db.query(CRMCompany).filter(
        scoped(CRMCompany.organization_id, user),
        CRMCompany.deleted_at.is_(None),
        CRMCompany.id > after,
    )
    # Respect existing CRM record visibility for CRM-only callers.
    names = {p.name for p in (permission_objects(user))}
    if not user.is_superuser and not names.intersection(set(DIRECTORY[3:])):
        from app.apps.crm.api.router import _apply_record_visibility, _get_resource

        query = _apply_record_visibility(query, _get_resource("companies"), user, db)
    if q:
        query = query.filter(
            CRMCompany.name.ilike(
                "%" + q.replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"
            )
        )
    rows = query.order_by(CRMCompany.id).limit(51).all()
    return {
        "items": [
            {"id": r.id, "name": r.name, "email": r.email, "address": r.address}
            for r in rows[:50]
        ],
        "next": rows[49].id if len(rows) > 50 else None,
    }


@router.get("/business/customers/{customer_id}")
def customer_detail(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require(user, *DIRECTORY)
    return customer_profile(customer(db, customer_id, user))


@router.get("/business/customers/{customer_id}/contacts")
def contacts(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require(user, *DIRECTORY)
    customer(db, customer_id, user)
    return [
        {
            key: getattr(r, key)
            for key in ("id", "company_id", "full_name", "email", "phone", "job_title")
        }
        for r in db.query(CRMContact)
        .filter(
            CRMContact.company_id == customer_id,
            scoped(CRMContact.organization_id, user),
            CRMContact.deleted_at.is_(None),
        )
        .limit(200)
    ]


@router.get("/business/teams")
def teams(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require(user, *DIRECTORY)
    rows = (
        db.query(CRMTeam)
        .filter(scoped(CRMTeam.organization_id, user), CRMTeam.deleted_at.is_(None))
        .order_by(CRMTeam.name)
        .limit(200)
        .all()
    )
    members = (
        db.query(CRMOwner)
        .join(User, User.id == CRMOwner.user_id)
        .filter(
            scoped(CRMOwner.organization_id, user),
            CRMOwner.team_id.in_([r.id for r in rows]),
            CRMOwner.deleted_at.is_(None),
            User.is_active.is_(True),
        )
        .all()
    )
    return [
        output(r)
        | {
            "members": [
                {
                    "user_id": m.user_id,
                    "name": m.full_name,
                    "active": m.status == "Active" and r.status == "Active",
                }
                for m in members
                if m.team_id == r.id
            ]
        }
        for r in rows
    ]


@router.get("/business/sellers")
def sellers(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require(user, *DIRECTORY)
    ids = [
        r.seller_id
        for r in db.query(SellerGrant).filter_by(
            organization_id=tenant(user), active=True
        )
    ] + [tenant(user)]
    return [
        {"id": r.id, "name": r.legal_name or r.name, "currency": r.default_currency}
        for r in db.query(Company).filter(
            Company.id.in_(ids), Company.is_active.is_(True)
        )
    ]


class LinkInput(BaseModel):
    customer_id: int
    contact_id: int | None = None
    seller_id: int
    team_id: int | None = None
    currency: str = Field("INR", pattern="^[A-Z]{3}$")
    opportunity_id: int | None = None
    sales_order_id: int | None = None
    engagement_id: int | None = None


def project(db, ident, user, action="browse"):
    value = get_project_for_action(db, ident, user, action)
    if not (
        value.organization_id == tenant(user)
        or (value.organization_id is None and tenant(user) == 1)
    ):
        raise HTTPException(404, "Project not found in your organization")
    return value


@router.put("/projects/{project_id}/commercial")
def link_project(
    project_id: int,
    data: LinkInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return link_project_service(project_id,data,db,user)


def link_project_service(project_id,data,db,user,*,commit=True):
    from app.apps.srm.api.router import _audit

    project(db, project_id, user, "edit_project")
    require(user, "pms_manage_projects", "pms_admin", "srm_manage", "srm_admin")
    from app.apps.srm.services.commercial import currency_code

    currency_code(data.currency)
    customer(db, data.customer_id, user)
    seller(db, data.seller_id, user)
    if (
        data.contact_id
        and record(db, CRMContact, data.contact_id, user).company_id != data.customer_id
    ):
        raise HTTPException(422, "Contact must belong to the customer")
    if data.team_id:
        team = record(db, CRMTeam, data.team_id, user)
        if team.status != "Active":
            raise HTTPException(422, "Choose an active shared team")
    from app.apps.srm.access import get_sales_order_for_user, get_engagement_for_user
    from app.apps.crm.models import CRMDeal

    if data.sales_order_id:
        order = get_sales_order_for_user(db, data.sales_order_id, user)
        if order.customer_id != data.customer_id:
            raise HTTPException(422, "Sales order belongs to a different customer")
    if data.engagement_id:
        engagement = get_engagement_for_user(db, data.engagement_id, user)
        if engagement.customer_id != data.customer_id:
            raise HTTPException(422, "Engagement belongs to a different customer")
    if data.opportunity_id:
        from app.apps.crm.api.router import _assert_record_visible, _get_resource

        opportunity = record(db, CRMDeal, data.opportunity_id, user)
        _assert_record_visible(
            db, _get_resource("deals"), opportunity.id, tenant(user), user
        )
        if opportunity.company_id != data.customer_id:
            raise HTTPException(422, "Opportunity belongs to a different customer")
    value = db.get(ProjectCommercial, project_id) or ProjectCommercial(
        project_id=project_id
    )
    for key, field in data.model_dump().items():
        if (
            key in {"opportunity_id", "sales_order_id", "engagement_id"}
            and key not in data.model_fields_set
        ):
            continue
        setattr(value, key, field)
    value.updated_by = user.id
    db.add(value)
    _audit(
        db, user, "project", project_id, "commercial_linked", after=data.model_dump()
    )
    db.commit() if commit else db.flush()
    return output(value)


@router.get("/projects/{project_id}/billing")
def billing(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.apps.srm.api.router import _invoice_payload

    project(db, project_id, user)
    require(user, *FINANCE)
    ctx = db.get(ProjectCommercial, project_id)
    engagement_ids = db.query(SRMEngagement.id).filter(
        SRMEngagement.pms_project_id == project_id,
        scoped(SRMEngagement.organization_id, user),
    )
    direct_ids = db.query(InvoiceContext.invoice_id).filter(
        InvoiceContext.project_id == project_id
    )
    related_orders = db.query(SRMEngagement.sales_order_id).filter(
        SRMEngagement.id.in_(engagement_ids)
    )
    related = (
        SRMInvoice.id.in_(direct_ids)
        | SRMInvoice.engagement_id.in_(engagement_ids)
        | SRMInvoice.sales_order_id.in_(related_orders)
    )
    if ctx and ctx.sales_order_id:
        related = related | (SRMInvoice.sales_order_id == ctx.sales_order_id)
    rows = (
        invoice_query(db, user)
        .filter(related)
        .order_by(SRMInvoice.id.desc())
        .limit(200)
        .all()
    )
    names = {p.name for p in (permission_objects(user))}
    return {
        "commercial": output(ctx) if ctx else None,
        "customer": (
            customer_profile(customer(db, ctx.customer_id, user)) if ctx else None
        ),
        "invoices": [_invoice_payload(r, db) for r in rows],
        "can_create": user.is_superuser
        or bool(names.intersection({"srm_invoice_create", "srm_admin"})),
        "can_issue": user.is_superuser
        or bool(names.intersection({"srm_invoice_approve", "srm_admin"})),
        "can_send": user.is_superuser
        or bool(names.intersection({"srm_invoice_create", "srm_admin"})),
        "engagements": [
            output(r)
            for r in db.query(SRMEngagement).filter(
                SRMEngagement.id.in_(engagement_ids)
            )
        ],
    }


@router.get("/business/related-projects")
def related_projects(
    sales_order_id: int | None = None,
    engagement_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.apps.srm.access import get_sales_order_for_user, get_engagement_for_user

    require(user, "srm_view", "srm_manage", "srm_admin")
    query = (
        accessible_project_query(db, user)
        .join(ProjectCommercial, ProjectCommercial.project_id == PMSProject.id)
        .filter(scoped(PMSProject.organization_id, user))
    )
    if sales_order_id:
        get_sales_order_for_user(db, sales_order_id, user)
        query = query.filter(ProjectCommercial.sales_order_id == sales_order_id)
    elif engagement_id:
        get_engagement_for_user(db, engagement_id, user)
        query = query.filter(ProjectCommercial.engagement_id == engagement_id)
    else:
        raise HTTPException(422, "Select an order or engagement")
    return [{"id": p.id, "name": p.name} for p in query.limit(200)]


class TeamAssignmentInput(BaseModel):
    team_id: int


@router.get("/business/sales-orders/{order_id}/team")
def order_team(
    order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    from app.apps.srm.access import get_sales_order_for_user
    from app.apps.srm.commercial_models import SalesTeamAssignment

    require(user, "srm_view", "srm_manage", "srm_admin")
    get_sales_order_for_user(db, order_id, user)
    assignment = db.get(SalesTeamAssignment, order_id)
    return output(assignment) if assignment else None


@router.put("/business/sales-orders/{order_id}/team")
def assign_team(
    order_id: int,
    data: TeamAssignmentInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.apps.srm.access import get_sales_order_for_user
    from app.apps.srm.commercial_models import SalesTeamAssignment
    from app.apps.srm.api.router import _audit

    require(user, "srm_manage", "srm_admin")
    get_sales_order_for_user(db, order_id, user)
    team = record(db, CRMTeam, data.team_id, user)
    if team.status != "Active":
        raise HTTPException(422, "Team is inactive; choose an active team")
    assignment = db.get(SalesTeamAssignment, order_id) or SalesTeamAssignment(
        sales_order_id=order_id
    )
    old = assignment.team_id
    assignment.team_id, assignment.assigned_by = team.id, user.id
    db.add(assignment)
    _audit(
        db,
        user,
        "sales_order",
        order_id,
        "team_reassigned",
        before={"team_id": old},
        after={"team_id": team.id},
    )
    db.commit()
    return output(assignment)


class DraftInput(BaseModel):
    request_id: UUID
    lines: list[dict] = Field(default_factory=list, max_length=200)
    time_log_ids: list[int] = Field(default_factory=list, max_length=200)
    time_minutes: dict[int, int] = Field(default_factory=dict)
    hourly_rate: Decimal = Decimal("0")
    milestone_ids: list[int] = Field(default_factory=list, max_length=100)


@router.post("/projects/{project_id}/invoices", status_code=201)
def draft(
    project_id: int,
    data: DraftInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return draft_project_invoice_service(project_id,data,db,user)


def draft_project_invoice_service(project_id,data,db,user,*,commit=True):
    from app.apps.srm.api.router import _create_invoice_from_lines, _invoice_payload

    require(user, "srm_invoice_create", "srm_admin")
    project(db, project_id, user)
    lock_tenant(db, user)
    previous = (
        db.query(InvoiceContext)
        .filter_by(project_id=project_id, request_id=str(data.request_id))
        .first()
    )
    if previous:
        return _invoice_payload(invoice_for(db, previous.invoice_id, user), db)
    ctx = db.get(ProjectCommercial, project_id)
    if not ctx:
        raise HTTPException(
            422, "Link a shared customer and seller in project billing first"
        )
    customer(db, ctx.customer_id, user)
    seller(db, ctx.seller_id, user)
    lines = []
    for line in data.lines:
        if set(line) - {
            "description",
            "quantity",
            "unit_price",
            "tax_amount",
            "discount_amount",
        }:
            raise HTTPException(
                422,
                "Manual lines support description, quantity, unit price and tax amount",
            )
        lines.append(line | {"source_type": "manual", "source_id": None})
    logs = (
        db.query(PMSTimeLog)
        .filter(
            PMSTimeLog.id.in_(set(data.time_log_ids)),
            PMSTimeLog.project_id == project_id,
            PMSTimeLog.is_billable.is_(True),
            PMSTimeLog.approval_status.in_(["Approved", "approved"]),
        )
        .with_for_update()
        .all()
        if data.time_log_ids
        else []
    )
    if len(logs) != len(set(data.time_log_ids)):
        raise HTTPException(
            422, "Time logs must be approved, billable and belong to this project"
        )
    reservations = []
    for log in logs:
        if log.duration_minutes <= 0 or money(data.hourly_rate) <= 0:
            raise HTTPException(422, "Billable hours and hourly rate must be positive")
        legacy = (
            db.query(SRMInvoiceLine)
            .filter_by(source_type="pms_time_log", source_id=log.id)
            .first()
        )
        reserved = (
            db.query(func.coalesce(func.sum(TimeBillingAllocation.minutes), 0))
            .filter_by(time_log_id=log.id)
            .scalar()
        )
        minutes = data.time_minutes.get(log.id, log.duration_minutes - reserved)
        if legacy or minutes <= 0 or minutes > log.duration_minutes - reserved:
            raise HTTPException(
                409, "Selected time exceeds the remaining billable balance"
            )
        reservations.append((log.id, minutes))
        lines.append(
            {
                "description": log.description or f"Time log {log.id}",
                "source_type": "project_time",
                "source_id": None,
                "quantity": Decimal(minutes) / 60,
                "unit_price": data.hourly_rate,
            }
        )
    from app.apps.srm.commercial_models import MilestoneBillingSource
    from app.apps.project_management.models import PMSMilestone
    from app.apps.srm.models import SRMBillingMilestone, SRMBillingPlan

    milestone_sources = []
    for ident in set(data.milestone_ids):
        mapping = db.get(MilestoneBillingSource, ident)
        milestone = (
            db.query(PMSMilestone).filter_by(id=ident, project_id=project_id).first()
        )
        source = (
            db.get(SRMBillingMilestone, mapping.billing_milestone_id)
            if mapping
            else None
        )
        plan = db.get(SRMBillingPlan, source.billing_plan_id) if source else None
        if (
            not source
            or not milestone
            or not plan
            or not (
                milestone.client_approved_at
                or str(milestone.client_approval_status).lower()
                in {"approved", "accepted", "client approved"}
            )
        ):
            raise HTTPException(
                422, "Select mapped, client-approved project milestones"
            )
        from app.apps.srm.access import get_engagement_for_user

        engagement = get_engagement_for_user(db, plan.engagement_id, user)
        if (
            engagement.pms_project_id != project_id
            and ctx.engagement_id != engagement.id
        ):
            raise HTTPException(422, "Milestone source belongs to another project")
        if source.invoice_draft_id or source.status not in {
            "approved",
            "ready",
            "completed",
        }:
            raise HTTPException(
                409, "Commercial milestone is not available for billing"
            )
        if plan.currency != ctx.currency:
            raise HTTPException(
                422, "Milestone currency must match the project billing currency"
            )
        milestone_sources.append(source)
        from app.apps.srm.api.router import billing_milestone_line
        lines.append(billing_milestone_line(db, source))
    linked_order = (
        record(db, SRMSalesOrder, ctx.sales_order_id, user)
        if ctx.sales_order_id
        else None
    )
    linked_engagement = (
        record(db, SRMEngagement, ctx.engagement_id, user)
        if ctx.engagement_id
        else None
    )
    if (linked_order and linked_order.customer_id != ctx.customer_id) or (
        linked_engagement and linked_engagement.customer_id != ctx.customer_id
    ):
        raise HTTPException(
            422,
            "Refresh the project's commercial links after the source customer changed",
        )
    invoice = _create_invoice_from_lines(
        db,
        user,
        "pms_project",
        None,
        linked_engagement,
        linked_order,
        lines,
        ctx.currency,
    )
    invoice.customer_id = ctx.customer_id
    for log_id, minutes in reservations:
        db.add(
            TimeBillingAllocation(
                time_log_id=log_id, invoice_id=invoice.id, minutes=minutes
            )
        )
    for source in milestone_sources:
        source.invoice_draft_id, source.status = invoice.invoice_draft_id, "invoiced"
    db.add(
        InvoiceContext(
            invoice_id=invoice.id,
            project_id=project_id,
            seller_id=ctx.seller_id,
            contact_id=ctx.contact_id,
            request_id=str(data.request_id),
            origin="pms",
        )
    )
    from app.apps.srm.api.router import _audit

    _audit(
        db,
        user,
        "invoice",
        invoice.id,
        "project_invoice_created",
        after={"project_id": project_id, "correlation_id": str(data.request_id)},
    )
    db.commit() if commit else db.flush()
    return _invoice_payload(invoice, db)


@router.get("/business/customers/{customer_id}/history")
def history(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.apps.srm.api.router import _invoice_payload

    require(user, *FINANCE)
    buyer = customer(db, customer_id, user)
    rows = (
        invoice_query(db, user)
        .filter(SRMInvoice.customer_id == buyer.id)
        .order_by(SRMInvoice.id.desc())
        .limit(200)
        .all()
    )
    projects = (
        accessible_project_query(db, user)
        .join(ProjectCommercial, ProjectCommercial.project_id == PMSProject.id)
        .filter(
            ProjectCommercial.customer_id == buyer.id,
            scoped(PMSProject.organization_id, user),
        )
        .all()
    )
    return {
        "customer": customer_profile(buyer),
        "invoices": [_invoice_payload(r, db) for r in rows],
        "projects": [{"id": p.id, "name": p.name} for p in projects],
    }


class ClientLinkInput(BaseModel):
    customer_id: int


@router.put("/clients/{client_id}/shared-customer")
def link_client(
    client_id: int,
    data: ClientLinkInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.apps.srm.api.router import _audit

    require(user, "pms_manage_projects", "pms_admin")
    record(db, PMSClient, client_id, user)
    customer(db, data.customer_id, user)
    link = (
        db.query(CustomerLink)
        .filter_by(source_type="pms_client", source_id=client_id)
        .first()
    )
    if link and link.customer_id != data.customer_id:
        raise HTTPException(
            409, "Client already mapped; an administrator must review reassignment"
        )
    if not link:
        db.add(
            CustomerLink(
                organization_id=tenant(user),
                customer_id=data.customer_id,
                source_type="pms_client",
                source_id=client_id,
                actor_id=user.id,
            )
        )
        _audit(
            db,
            user,
            "client",
            client_id,
            "shared_customer_linked",
            after={"customer_id": data.customer_id},
        )
    db.commit()
    return {"client_id": client_id, "customer_id": data.customer_id}


@router.get("/business/invoices/{invoice_id}")
def invoice_detail(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.apps.srm.api.router import _invoice_payload
    from app.apps.srm.models import SRMInvoiceHistory, SRMReceiptAllocation

    require(user, *FINANCE)
    invoice = invoice_for(db, invoice_id, user)
    ctx = db.get(InvoiceContext, invoice_id)
    names = {p.name for p in (permission_objects(user))}
    return _invoice_payload(invoice, db) | {
        "context": output(ctx) if ctx else None,
        "history": [
            output(r)
            for r in db.query(SRMInvoiceHistory)
            .filter_by(invoice_id=invoice_id)
            .order_by(SRMInvoiceHistory.id.desc())
            .limit(100)
        ],
        "deliveries": [
            output(r)
            for r in db.query(InvoiceDelivery)
            .filter_by(invoice_id=invoice_id)
            .order_by(InvoiceDelivery.id.desc())
            .limit(100)
        ],
        "payments": [
            allocation_profile(db, r)
            for r in db.query(SRMReceiptAllocation)
            .filter_by(invoice_id=invoice_id)
            .limit(100)
        ],
        "can_issue": user.is_superuser
        or bool(names.intersection({"srm_invoice_approve", "srm_admin"})),
        "can_record_payment": user.is_superuser or bool(names.intersection({"srm_collection_create", "srm_admin"})),
        "can_edit": user.is_superuser
        or bool(names.intersection({"srm_invoice_create", "srm_admin"})),
    }


class LinePatch(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")


class CancelInvoiceInput(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.post("/business/invoices/{invoice_id}/cancel")
def cancel_invoice(invoice_id: int, data: CancelInvoiceInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.apps.fam.models import FAMSRMMapping
    from app.apps.srm.models import SRMInvoiceHistory
    from app.apps.srm.api.router import _audit, _invoice_payload
    require(user, "srm_invoice_approve", "srm_admin")
    invoice = invoice_for(db, invoice_id, user, lock=True)
    if invoice.status == "cancelled":
        return _invoice_payload(invoice, db)
    if money(invoice.paid_amount) > 0:
        raise HTTPException(409, "Review and reverse applied payments through accounting before cancellation")
    mappings = db.query(FAMSRMMapping).filter_by(company_id=invoice.organization_id or 1, srm_record_type="invoice", srm_record_id=invoice.id).all()
    if any(m.fam_record_type == "voucher" for m in mappings) and not any(m.fam_record_type == "reversal_voucher" for m in mappings):
        raise HTTPException(409, "Reverse the posted FAM voucher through the established accounting workflow first")
    old = invoice.status
    invoice.status, invoice.balance_amount = "cancelled", Decimal("0")
    db.add(SRMInvoiceHistory(invoice_id=invoice.id, from_status=old, to_status="cancelled", actor_user_id=user.id, notes=data.reason))
    _audit(db, user, "invoice", invoice.id, "cancelled", before={"status": old}, after={"reason": data.reason, "source_reservations": "retained_for_finance_review"})
    db.commit()
    return _invoice_payload(invoice, db)


@router.patch("/business/invoices/{invoice_id}/lines/{line_id}")
def edit_line(
    invoice_id: int,
    line_id: int,
    data: LinePatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.apps.srm.services.commercial import normalize_lines
    from app.apps.srm.api.router import _recalculate_invoice, _audit, _invoice_payload

    require(user, "srm_invoice_create", "srm_admin")
    invoice = invoice_for(db, invoice_id, user, lock=True)
    if invoice.status not in {"draft", "pending_approval"}:
        raise HTTPException(409, "Issued invoice lines are immutable")
    line = db.query(SRMInvoiceLine).filter_by(id=line_id, invoice_id=invoice_id).first()
    if not line:
        raise HTTPException(404, "Line not found")
    if line.source_type not in {None, "manual", "external_adjustment"}:
        raise HTTPException(
            409, "Source-based lines must retain their reserved quantity and price"
        )
    before = {key: str(getattr(line, key)) for key in data.model_dump()}
    for key, value in normalize_lines([data.model_dump()])[0].items():
        setattr(line, key, value)
    _recalculate_invoice(db, invoice)
    _audit(
        db,
        user,
        "invoice",
        invoice_id,
        "line_updated",
        before=before,
        after={"line_id": line_id},
    )
    db.commit()
    return _invoice_payload(invoice, db)


@router.put("/business/invoices/{invoice_id}/context")
def update_invoice_context(
    invoice_id: int,
    data: LinkInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.apps.srm.services.commercial import context
    from app.apps.srm.api.router import _audit

    require(user, "srm_invoice_create", "srm_admin")
    invoice = invoice_for(db, invoice_id, user, lock=True)
    if invoice.status not in {"draft", "pending_approval"}:
        raise HTTPException(409, "Issued document identity is immutable")
    from app.apps.srm.services.commercial import currency_code

    currency_code(data.currency)
    customer(db, data.customer_id, user)
    seller(db, data.seller_id, user)
    if (
        data.contact_id
        and record(db, CRMContact, data.contact_id, user).company_id != data.customer_id
    ):
        raise HTTPException(422, "Contact must belong to the customer")
    ctx = context(db, invoice, user)
    ctx.seller_id, ctx.contact_id = data.seller_id, data.contact_id
    if data.currency != invoice.currency:
        raise HTTPException(422, "Currency cannot change after line creation")
    invoice.customer_id = data.customer_id
    _audit(db, user, "invoice", invoice.id, "identity_updated", after=data.model_dump())
    db.commit()
    return output(ctx)


@router.get("/projects/{project_id}/billing/sources")
def sources(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require(user, "srm_invoice_create", "srm_admin")
    project(db, project_id, user)
    billed = db.query(SRMInvoiceLine.source_id).filter(
        SRMInvoiceLine.source_type == "pms_time_log",
        SRMInvoiceLine.source_id.isnot(None),
    )
    already_reserved = (
        db.query(func.coalesce(func.sum(TimeBillingAllocation.minutes), 0))
        .filter(TimeBillingAllocation.time_log_id == PMSTimeLog.id)
        .correlate(PMSTimeLog)
        .scalar_subquery()
    )
    logs = (
        db.query(PMSTimeLog)
        .filter(
            PMSTimeLog.project_id == project_id,
            PMSTimeLog.is_billable.is_(True),
            PMSTimeLog.approval_status.in_(["Approved", "approved"]),
            ~PMSTimeLog.id.in_(billed),
            PMSTimeLog.duration_minutes > already_reserved,
        )
        .order_by(PMSTimeLog.id)
        .limit(200)
        .all()
    )
    reserved = dict(
        db.query(
            TimeBillingAllocation.time_log_id, func.sum(TimeBillingAllocation.minutes)
        )
        .filter(TimeBillingAllocation.time_log_id.in_([r.id for r in logs]))
        .group_by(TimeBillingAllocation.time_log_id)
        .all()
    )
    from app.apps.srm.commercial_models import MilestoneBillingSource
    from app.apps.project_management.models import PMSMilestone
    from app.apps.srm.models import SRMBillingMilestone

    milestones = (
        db.query(PMSMilestone, SRMBillingMilestone)
        .join(
            MilestoneBillingSource,
            MilestoneBillingSource.pms_milestone_id == PMSMilestone.id,
        )
        .join(
            SRMBillingMilestone,
            SRMBillingMilestone.id == MilestoneBillingSource.billing_milestone_id,
        )
        .filter(
            PMSMilestone.project_id == project_id,
            SRMBillingMilestone.invoice_draft_id.is_(None),
            SRMBillingMilestone.status.in_(["approved", "ready", "completed"]),
        )
        .limit(200)
        .all()
    )
    return {
        "time_logs": [
            output(r)
            | {"remaining_minutes": r.duration_minutes - reserved.get(r.id, 0)}
            for r in logs
            if r.duration_minutes > reserved.get(r.id, 0)
        ],
        "milestones": [
            {"id": p.id, "name": p.name, "amount": s.amount}
            for p, s in milestones
            if p.client_approved_at
            or str(p.client_approval_status).lower()
            in {"approved", "accepted", "client approved"}
        ],
        "policy": "Approved time can be partially billed. Drafts reserve sources immediately. Milestones use explicit commercial mappings. Cancellation/credit retains reservations pending finance review; expenses are not supported.",
    }


# Register one-way compatibility projections once at app startup.
from app.apps.srm.services.customer_identity import (
    refresh_legacy_projections,
)  # noqa: E402,F401

from app.apps.srm.payments import router as payments_router
router.include_router(payments_router)
