"""Shared identities, invoice policy, document and delivery orchestration."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, DecimalException
from io import BytesIO
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.apps.crm.models import CRMCompany, CRMContact, CRMTeam
from app.apps.project_management.models import PMSProject
from app.apps.srm.models import SRMInvoice, SRMInvoiceHistory
from app.apps.srm.commercial_models import InvoiceContext, InvoiceDelivery, SellerGrant
from app.models.company import Company
from app.models.user import User


def tenant(user):
    explicit = getattr(user, "organization_id", None)
    if explicit is None:
        explicit = getattr(user, "company_id", None)
    if explicit is not None:
        return int(explicit)
    person = getattr(user, "person", None)
    if person and person.organization_id:
        return int(person.organization_id)
    employee = getattr(user, "employee", None)
    branch = getattr(employee, "branch", None) if employee else None
    return int(branch.company_id if branch else 1)


def scoped(column, user):
    # NULL is the pre-tenant legacy partition, assigned solely to legacy tenant 1.
    return func.coalesce(column, 1) == tenant(user)


def require(user, *permissions):
    names = {p.name for p in (user.role.permissions if user.role else [])}
    if not user.is_superuser and not names.intersection(permissions):
        raise HTTPException(403, "Required permissions: " + ", ".join(permissions))


def record(db, model, ident, user):
    query = db.query(model).filter(
        model.id == ident, scoped(model.organization_id, user)
    )
    if hasattr(model, "deleted_at"):
        query = query.filter(model.deleted_at.is_(None))
    value = query.first()
    if not value:
        raise HTTPException(404, "Linked record not found in your organization")
    return value


def customer(db, ident, user):
    value = record(db, CRMCompany, ident, user)
    # Reuse CRM's record visibility for CRM-only users; financial staff use the
    # SRM customer directory scope, never a project role as a financial grant.
    names = {p.name for p in (user.role.permissions if user.role else [])}
    if not user.is_superuser and not names.intersection(
        {
            "srm_admin",
            "srm_invoice_create",
            "srm_invoice_view",
            "srm_invoice_approve",
            "srm_view",
            "pms_manage_projects",
            "pms_admin",
        }
    ):
        from app.apps.crm.api.router import _assert_record_visible, _get_resource

        _assert_record_visible(
            db, _get_resource("companies"), ident, tenant(user), user
        )
    return value


def seller(db, ident, user):
    value = (
        db.query(Company)
        .filter(Company.id == ident, Company.is_active.is_(True))
        .first()
    )
    grant = (
        db.query(SellerGrant)
        .filter_by(organization_id=tenant(user), seller_id=ident, active=True)
        .first()
    )
    if not value or (ident != tenant(user) and not grant):
        raise HTTPException(
            403, "Seller legal entity is not authorized for this organization"
        )
    return value


def lock_tenant(db, user):
    """Serialize source reservation and invoice numbering in the existing transaction."""
    if db.bind.dialect.name == "postgresql":
        db.execute(
            __import__("sqlalchemy").text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": 720000000 + tenant(user)},
        )
    else:
        # SQLite acquires the writer lock before reading numbering/source state.
        db.execute(
            update(User).where(User.id == user.id).values(is_active=User.is_active)
        )


def next_invoice_number(db, prefix):
    """One authoritative INV series, unique even for a seller shared by grants.

    Existing issued numbers remain untouched. The initial counter scans legacy
    numbers in bounded batches; subsequent assignments update one locked row.
    """
    from sqlalchemy import text
    from app.apps.srm.commercial_models import CommercialNumberSequence

    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(719999999)"))
    else:
        db.execute(
            update(CommercialNumberSequence).values(
                last_number=CommercialNumberSequence.last_number
            )
        )
    series = "srm_invoice:" + prefix
    counter = (
        db.query(CommercialNumberSequence)
        .filter_by(series=series)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not counter:
        last = 0
        for (value,) in db.query(SRMInvoice.invoice_number).yield_per(500):
            suffix = (
                value[len(prefix) + 1 :]
                if value and value.startswith(prefix + "-")
                else ""
            )
            if suffix.isdigit():
                last = max(last, int(suffix))
        counter = CommercialNumberSequence(series=series, last_number=last)
        db.add(counter)
    counter.last_number += 1
    db.flush()
    return f"{prefix}-{counter.last_number:06d}"


def money(value):
    try:
        amount = Decimal(str(value or 0))
    except (DecimalException, ValueError, TypeError):
        raise HTTPException(422, "Invalid monetary value")
    if not amount.is_finite() or amount < 0 or amount > Decimal("99999999999"):
        raise HTTPException(
            422,
            "Money and quantities must be finite, nonnegative and within supported limits",
        )
    return amount


def normalize_lines(lines):
    if not 1 <= len(lines) <= 200:
        raise HTTPException(422, "Use between 1 and 200 invoice lines")
    result = []
    for item in lines:
        line = dict(item)
        qty, price, tax = (
            money(line.get("quantity", 1)),
            money(line.get("unit_price")),
            money(line.get("tax_amount")),
        )
        qty = qty.quantize(Decimal(".0000000001"), rounding=ROUND_HALF_UP)
        price = price.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        tax = tax.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        discount = money(line.get("discount_amount")).quantize(
            Decimal(".01"), rounding=ROUND_HALF_UP
        )
        if (
            not isinstance(line.get("description"), str)
            or len(line["description"]) > 2000
            or discount > qty * price
        ):
            raise HTTPException(
                422,
                "Use a valid description and a discount no greater than the line subtotal",
            )
        if not qty or not str(line.get("description", "")).strip():
            raise HTTPException(422, "A description and positive quantity are required")
        base = (qty * price).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        money(base + tax - discount)
        line.update(
            quantity=qty,
            unit_price=price,
            discount_amount=discount,
            tax_amount=tax.quantize(Decimal(".01")),
            line_total=(base - discount + tax).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP
            ),
        )
        result.append(line)
    return result


def currency_code(code):
    if code not in {
        "INR",
        "USD",
        "AED",
        "EUR",
        "GBP",
        "SAR",
        "CAD",
        "AUD",
        "SGD",
        "JPY",
        "CHF",
        "CNY",
        "NZD",
        "ZAR",
        "QAR",
        "BHD",
        "OMR",
        "KWD",
    }:
        raise HTTPException(
            422, "Unsupported currency; configure a supported commercial currency"
        )
    # The maintained SRM schema uses 2 decimal monetary fields. Do not silently
    # misrepresent a currency requiring three decimals.
    if code in {"BHD", "OMR", "KWD"}:
        raise HTTPException(
            422, "Three-decimal currencies are not supported by the existing ledger"
        )
    return code


def invoice_query(db, user):
    from app.apps.srm.access import can_view_all_srm
    from app.apps.srm.models import SRMSalesOrder, SRMEngagement
    from app.apps.project_management.access import accessible_project_query

    query = db.query(SRMInvoice).filter(
        SRMInvoice.deleted_at.is_(None), scoped(SRMInvoice.organization_id, user)
    )
    allowed_sellers = [tenant(user)] + [
        r.seller_id
        for r in db.query(SellerGrant).filter_by(
            organization_id=tenant(user), active=True
        )
    ]
    inaccessible = db.query(InvoiceContext.invoice_id).filter(
        ~InvoiceContext.seller_id.in_(allowed_sellers)
    )
    query = query.filter(~SRMInvoice.id.in_(inaccessible))
    permissions = {p.name for p in (user.role.permissions if user.role else [])}
    if user.is_superuser or can_view_all_srm(user) or permissions.intersection({"fam_admin", "fam_srm_posting_manage", "fam_srm_integration_view", "fam_accounting_status_view", "srm_collection_view", "srm_collection_create"}):
        return query
    orders = db.query(SRMSalesOrder.id).filter(
        scoped(SRMSalesOrder.organization_id, user),
        SRMSalesOrder.assigned_user_id == user.id,
    )
    engagements = db.query(SRMEngagement.id).filter(
        scoped(SRMEngagement.organization_id, user),
        (SRMEngagement.assigned_user_id == user.id)
        | (SRMEngagement.project_manager_user_id == user.id),
    )
    projects = accessible_project_query(db, user).with_entities(PMSProject.id)
    linked = db.query(InvoiceContext.invoice_id).filter(
        InvoiceContext.project_id.in_(projects)
    )
    owned_customers = db.query(CRMCompany.id).filter(
        scoped(CRMCompany.organization_id, user), CRMCompany.owner_user_id == user.id
    )
    return query.filter(
        (SRMInvoice.created_by == user.id)
        | SRMInvoice.sales_order_id.in_(orders)
        | SRMInvoice.engagement_id.in_(engagements)
        | SRMInvoice.id.in_(linked)
        | SRMInvoice.customer_id.in_(owned_customers)
    )


def invoice_for(db, ident, user, lock=False):
    query = invoice_query(db, user).filter(SRMInvoice.id == ident)
    if lock:
        lock_tenant(db, user)
        query = query.with_for_update().populate_existing()
    invoice = query.first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return invoice


def context(db, invoice, user):
    value = db.get(InvoiceContext, invoice.id)
    if not value:
        value = InvoiceContext(
            invoice_id=invoice.id,
            seller_id=tenant(user),
            request_id=str(uuid4()),
            origin="srm",
        )
        db.add(value)
    return value


def issue_snapshot(db, invoice, user):
    ctx = context(db, invoice, user)
    if ctx.issued_at:
        return ctx
    if not invoice.customer_id:
        raise HTTPException(422, "Link a shared customer before issuing the invoice")
    buyer = customer(db, invoice.customer_id, user)
    entity = seller(db, ctx.seller_id, user)
    ctx.customer_snapshot = {
        key: getattr(buyer, key)
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
    ctx.seller_snapshot = {
        key: getattr(entity, key)
        for key in ("id", "name", "legal_name", "address", "gstin", "email", "phone")
    }
    contact = record(db, CRMContact, ctx.contact_id, user) if ctx.contact_id else None
    if contact and contact.company_id != buyer.id:
        raise HTTPException(422, "Billing contact must belong to the linked customer")
    ctx.contact_snapshot = (
        {"id": contact.id, "name": contact.full_name, "email": contact.email}
        if contact
        else {}
    )
    ctx.issued_at = datetime.now(timezone.utc)
    return ctx


def invoice_document(db, invoice):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase.pdfmetrics import stringWidth

    ctx = db.get(InvoiceContext, invoice.id)
    buyer = (ctx.customer_snapshot or {}) if ctx else {}
    entity = (ctx.seller_snapshot or {}) if ctx else {}
    if invoice.status in {"draft", "pending_approval"} and not invoice.approved_at:
        current_buyer = db.get(CRMCompany, invoice.customer_id) if invoice.customer_id else None
        current_seller = db.get(Company, ctx.seller_id if ctx else (invoice.organization_id or 1))
        buyer = {key: getattr(current_buyer, key) for key in ("name", "address")} if current_buyer else {}
        entity = {key: getattr(current_seller, key) for key in ("name", "legal_name", "address", "gstin")} if current_seller else {}
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    y = 795

    def row(text):
        nonlocal y
        # Wrap by rendered width; never truncate a financial line description.
        pending = str(text).replace("\n", " ")
        while pending:
            cut = 1
            while cut < len(pending) and stringWidth(pending[:cut + 1], "Helvetica", 11) <= 510:
                cut += 1
            if cut < len(pending) and " " in pending[:cut]:
                cut = pending.rfind(" ", 0, cut) or cut
            if y < 65:
                pdf.showPage()
                pdf.setFont("Helvetica", 11)
                y = 795
            pdf.drawString(42, y, pending[:cut])
            y -= 20
            pending = pending[cut:].lstrip()

    pdf.setTitle(str(invoice.invoice_number))
    pdf.setFont("Helvetica", 11)
    row(
        f"Invoice {invoice.invoice_number}"
        + (" — DRAFT" if not ctx or not ctx.issued_at else "")
    )
    row(
        entity.get("legal_name") or entity.get("name") or "Seller details pending issue"
    )
    row(entity.get("address") or "")
    if entity.get("gstin"):
        row(f"Seller GSTIN: {entity['gstin']}")
    row(f"Customer: {buyer.get('name', invoice.customer_id or 'Not linked')}")
    row(buyer.get("address") or "")
    row(f"Date: {invoice.issue_date}    Due: {invoice.due_date}")
    for line in invoice.lines:
        row(
            f"{line.description} | {format(line.quantity.normalize(), 'f')} x {line.unit_price} | discount {line.discount_amount} | tax {line.tax_amount} | {line.line_total}"
        )
    row(f"Total {invoice.currency} {invoice.total_amount}")
    row(f"Paid {invoice.paid_amount}    Outstanding {invoice.balance_amount}")
    pdf.save()
    return output.getvalue()


def delivery_payload(db, delivery):
    return {
        "id": delivery.id,
        "request_id": delivery.request_id,
        "status": delivery.status,
        "error": delivery.error,
        "message_id": delivery.message_id,
        "created_at": delivery.created_at,
    }


def send(db, invoice, user, request_id, recipient=None):
    import smtplib
    from app.apps.communication.models import CommunicationEmailMessage
    from app.apps.communication.services.delivery import deliver_email, validate_email
    from app.apps.srm.api.router import _audit

    ctx = db.get(InvoiceContext, invoice.id)
    if (
        not ctx
        or not ctx.issued_at
        or invoice.status in {"draft", "pending_approval", "cancelled"}
    ):
        raise HTTPException(409, "Finance must issue the invoice before sending")
    previous = (
        db.query(InvoiceDelivery)
        .filter_by(invoice_id=invoice.id, request_id=request_id)
        .first()
    )
    if previous and previous.status not in {"failed", "blocked"}:
        return delivery_payload(db, previous)
    recipient = (
        recipient
        or (ctx.contact_snapshot or {}).get("email")
        or (ctx.customer_snapshot or {}).get("email")
    )
    if not recipient:
        raise HTTPException(422, "Select a billing recipient")
    validate_email(recipient)
    allowed = {
        (ctx.contact_snapshot or {}).get("email"),
        (ctx.customer_snapshot or {}).get("email"),
    }
    if recipient not in allowed:
        raise HTTPException(
            422, "Recipient must match the issued billing contact or customer"
        )
    job = previous or InvoiceDelivery(
        invoice_id=invoice.id, request_id=request_id, actor_id=user.id
    )
    if previous:
        # Failed/blocked jobs are safe to retry; an indeterminate SMTP result is not.
        message = db.get(CommunicationEmailMessage, job.message_id)
    else:
        message = CommunicationEmailMessage(
            related_record_type="srm_invoice",
            related_record_id=invoice.id,
            to_email=recipient,
            subject=f"Invoice {invoice.invoice_number}",
            body=f"Please find invoice {invoice.invoice_number} attached. Total: {invoice.currency} {invoice.total_amount}.",
            sent_by=user.id,
            status="queued",
        )
        db.add(message)
        db.flush()
        job.message_id = message.id
        db.add(job)
    job.status = "sending"
    db.commit()  # Durable attempt before external delivery. Unknown outcomes never auto-resend.
    try:
        deliver_email(
            db,
            message,
            user,
            attachments=[
                (
                    f"{invoice.invoice_number}.pdf",
                    invoice_document(db, invoice),
                    "application/pdf",
                )
            ],
        )
        job.status = message.status
        job.error = message.error_message
    except HTTPException as error:
        job.status, message.status = "blocked", "blocked"
        job.error = str(error.detail)[:300]
        message.error_message = job.error
    except (
        smtplib.SMTPAuthenticationError,
        smtplib.SMTPRecipientsRefused,
        smtplib.SMTPSenderRefused,
        smtplib.SMTPDataError,
    ):
        job.status, message.status = "failed", "failed"
        job.error = "SMTP rejected authentication, recipient or document. Review provider configuration and retry."
        message.error_message = job.error
    except Exception:
        job.status = "unknown"
        job.error = "Delivery outcome is uncertain. Check the provider before attempting another send."
    if job.status == "sent":
        invoice.sent_at = datetime.now(timezone.utc)
        if invoice.status == "approved":
            invoice.status = "sent"  # Legacy status compatibility; DTO has independent status fields.
        db.add(
            SRMInvoiceHistory(
                invoice_id=invoice.id,
                to_status=invoice.status,
                actor_user_id=user.id,
                notes=f"Delivery accepted; correlation {request_id}",
            )
        )
    _audit(
        db,
        user,
        "invoice",
        invoice.id,
        "delivery_" + job.status,
        after={"correlation_id": request_id, "delivery_id": job.id},
    )
    db.commit()
    return delivery_payload(db, job)
