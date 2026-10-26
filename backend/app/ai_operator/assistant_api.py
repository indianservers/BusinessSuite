"""PMS assistant: private conversations, bounded discovery, explicit confirmations."""

import json
import re
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.ai_agents.api import _require_ai_access, _require_ai_rate_limit
from app.ai_agents.services.audit import AiAuditService
from app.ai_operator.service import digest, scope_key, require_enabled
from app.ai_operator.models import OperatorProvider
from app.ai_operator.provider_scope import resolve_provider
from app.ai_operator.assistant_models import AssistantConversation, AssistantMessage
from app.ai_operator.assistant_tools import (
    Intent,
    MUTATIONS,
    registry,
    projects,
    invoice_preview,
    read_tool,
)
from app.apps.srm.services.commercial import tenant, require, lock_tenant, invoice_for
from app.apps.srm.commercial_models import InvoiceContext
from app.apps.project_management.access import (
    get_project_for_action,
    get_task_project_for_action,
)

router = APIRouter(prefix="/assistant", tags=["PMS Assistant"])


class ConversationInput(BaseModel):
    model_config={"extra":"forbid"}
    title: str = Field("New conversation", min_length=1, max_length=160)
    workspace_id: int | None = None


class MessageInput(BaseModel):
    model_config={"extra":"forbid"}
    request_key: UUID
    text: str = Field("", max_length=6000)
    project_id: int | None = None
    customer_id: int | None = None
    intent: Intent | None = None
    provider: str | None = None


class Confirmation(BaseModel):
    model_config={"extra":"forbid"}
    approval_hash: str = Field(min_length=64, max_length=64)


def owned(db, user, ident):
    _require_ai_access(user)
    row = (
        db.query(AssistantConversation)
        .filter_by(
            id=ident, user_id=user.id, organization_id=tenant(user), deleted_at=None
        )
        .first()
    )
    if not row:
        raise HTTPException(404, "Conversation not found")
    if row.workspace_id:
        from app.apps.project_management.workspaces import workspace_member

        workspace_member(db, row.workspace_id, user)
    from app.ai_agents.security import verify
    verify(db,user,row.security_context,history=True)
    return row


def audit(db, user, message, action):
    AiAuditService(db).log(
        user=user,
        agent_id=None,
        module="PMS",
        action=f"assistant.{action}",
        input_json={
            "message_id": message.id,
            "tool": message.tool,
            "organization_id": tenant(user),
        },
        output_json={"status": message.status},
        status="success",
    )


def parse_local(text, project_id=None):
    """An explicit guided fallback, never presented as a language-model response."""
    low = text.lower()
    tool = "projects.summary"
    if "payment" in low and "record" in low:
        tool = "payments.record"
    elif "revenue" in low:
        tool = "reports.customer_revenue"
    elif "invoice" in low:
        tool = (
            "invoices.prepare"
            if any(x in low for x in ("create", "draft", "prepare"))
            else "invoices.search"
        )
    elif "customer" in low or low.startswith("find "):
        tool = "customers.search"
    elif "overdue" in low:
        tool = "tasks.overdue"
    elif "plan my day" in low:
        tool = "tasks.mine"
    elif "assign" in low:
        tool = "tasks.assign"
    elif "task" in low:
        tool = "tasks.create" if "create" in low else "tasks.search"
    elif "create" in low and "project" in low:
        tool = "projects.create"
    elif "time" in low or "timesheet" in low:
        tool = "time.summary"
    elif "document" in low or "file" in low:
        tool = "documents.search"
    elif "workload" in low or "availability" in low:
        tool = "users.workload"
    elif "custom field" in low:
        tool = "custom_fields.get"
    match = re.search(r"(?:₹|rs\.?\s*|inr\s*|amount\s+)([\d,]+(?:\.\d+)?)", low)
    parsed_amount = Decimal(match.group(1).replace(",", "")) if match else None
    if match:
        suffix = low[match.end() :].strip()
        for unit, factor in [
            ("crore", 10000000),
            ("lakh", 100000),
            ("lac", 100000),
            ("million", 1000000),
            ("k", 1000),
        ]:
            if re.match(rf"^{unit}\b", suffix):
                parsed_amount *= factor
                break
    percent = re.search(r"(\d+(?:\.\d+)?)\s*%", low)
    days = re.search(r"due\s+in\s+(\d+)\s+days", low)
    query = re.sub(
        r"^(find|search)( a| the)?( customer)?\s+", "", text, flags=re.I
    ).strip()
    if tool == "invoices.prepare":
        name = re.search(
            r"invoice\s+for\s+(.+?)(?:\s+for\s+|\s+worth\s+|\s+₹|$)", text, re.I
        )
        query = name.group(1).strip().rstrip(".") if name and not project_id else ""
    return Intent(
        tool=tool,
        query=query if tool in {"customers.search", "invoices.prepare"} else "",
        project_id=project_id,
        amount=parsed_amount,
        percentage=percent.group(1) if percent else None,
        due_days=int(days.group(1)) if days else 15,
    )


def prepare(db, user, intent):
    from app.ai_agents.security import authorize_tool
    authorize_tool(db,user,"assistant",intent.tool)
    if intent.tool == "payments.record":
        require(user, "srm_collection_create", "srm_admin")
        if not intent.invoice_id or not intent.amount:
            raise HTTPException(
                422, "Select an invoice ID and the amount actually received."
            )
        invoice = invoice_for(db, intent.invoice_id, user)
        if (
            invoice.status in {"draft", "cancelled", "pending_approval"}
            or intent.amount > invoice.balance_amount
        ):
            raise HTTPException(
                422, "Record cash only within an issued invoice outstanding balance."
            )
        return {
            "kind": "approval",
            "items": [],
            "text": f"Record {invoice.currency} {intent.amount} received against {invoice.invoice_number}. This records a receipt, not a transfer.",
            "state_hash": digest(
                [invoice.id, invoice.status, str(invoice.balance_amount)]
            ),
        }
    if intent.tool == "invoices.prepare":
        if not intent.project_id and not intent.customer_id:
            found = read_tool(
                db, user, Intent(tool="customers.search", query=intent.query)
            )
            return {
                **found,
                "kind": "selection",
                "entity": "customer",
                "next": intent.model_dump(mode="json"),
            }
        preview = invoice_preview(
            db,
            user,
            intent.model_copy(update={"query": ""}) if intent.customer_id else intent,
        )
        if preview["kind"] == "selection":
            preview["next"] = intent.model_dump(mode="json")
        return preview
    if intent.tool in {"invoices.issue", "invoices.send"}:
        require(
            user,
            (
                "srm_invoice_approve"
                if intent.tool == "invoices.issue"
                else "srm_invoice_create"
            ),
            "srm_admin",
        )
        if not intent.invoice_id:
            raise HTTPException(422, "Select an invoice ID first.")
        invoice = invoice_for(db, intent.invoice_id, user)
        return {
            "kind": "approval",
            "items": [],
            "text": f"Confirm {intent.tool} for {invoice.invoice_number}",
            "state_hash": digest(
                [
                    invoice.id,
                    invoice.status,
                    str(invoice.total_amount),
                    str(invoice.sent_at),
                ]
            ),
        }
    if intent.tool in {"tasks.create", "tasks.assign"}:
        if not intent.project_id:
            return {
                "kind": "selection",
                "entity": "project",
                "items": [
                    {"id": p.id, "name": p.name} for p in projects(db, user, intent)
                ],
                "next": intent.model_dump(mode="json"),
                "text": "Choose the task's project.",
            }
        get_project_for_action(db, intent.project_id, user, "manage_tasks")
        if intent.tool == "tasks.assign":
            if not intent.task_id or not intent.assignee_id:
                raise HTTPException(
                    422,
                    "Choose the task ID and collaborator ID in the task planner; assignments are never guessed.",
                )
            task, project = get_task_project_for_action(
                db, intent.task_id, user, "manage_tasks"
            )
            if project.id != intent.project_id:
                raise HTTPException(422, "The task is outside the selected project.")
            from app.apps.project_management.api.router import _project_user_query

            if (
                not _project_user_query(db, project)
                .filter(User.id == intent.assignee_id, User.is_active.is_(True))
                .first()
            ):
                raise HTTPException(422, "Choose an active project collaborator.")
        elif not intent.title:
            raise HTTPException(422, "Enter a task title in the action details.")
        elif intent.assignee_id:
            raise HTTPException(
                422,
                "Create the task first, then prepare an assignment for a verified collaborator.",
            )
        return {
            "kind": "approval",
            "items": [],
            "text": f"Review {intent.tool}",
            "details": intent.model_dump(mode="json"),
        }
    if intent.tool == "projects.create":
        require(user, "pms_manage_projects", "pms_admin")
        if intent.customer_id:
            from app.apps.srm.services.commercial import customer, seller, currency_code

            customer(db, intent.customer_id, user)
            seller(db, intent.seller_id or tenant(user), user)
            currency_code(intent.currency or "INR")
        if (
            intent.start_date
            and intent.due_date
            and intent.due_date < intent.start_date
        ):
            raise HTTPException(422, "Project due date cannot precede start date.")
        if not intent.title:
            raise HTTPException(422, "Enter a project title in the action details.")
        return {
            "kind": "approval",
            "items": [],
            "text": "Review independent project creation",
            "details": intent.model_dump(mode="json"),
        }
    return read_tool(db, user, intent)


def public_message(db, user, row):
    data = {
        "id": row.id,
        "prompt": row.prompt,
        "tool": row.tool,
        "status": row.status,
        "created_at": row.created_at,
    }
    intent = Intent.model_validate(row.arguments)
    try:
        if row.status == "completed":
            result = row.result or {}
            if result.get("invoice_id"):
                require(
                    user,
                    "srm_invoice_view",
                    "srm_invoice_create",
                    "srm_invoice_approve",
                    "srm_invoice_send",
                    "srm_admin",
                )
                invoice = invoice_for(db, result["invoice_id"], user)
                from app.apps.srm.api.router import _invoice_payload

                state = _invoice_payload(invoice, db)
                data["card"] = {
                    "kind": "saved_invoice",
                    "items": [],
                    "id": invoice.id,
                    "number": invoice.invoice_number,
                    "total": str(invoice.total_amount),
                    "currency": invoice.currency,
                    "balance": str(invoice.balance_amount),
                    "document_status": state["document_status"],
                    "delivery_status": state["delivery_status"],
                    "text": f"Saved in Sales invoicing. Document: {state['document_status']}; delivery: {state['delivery_status']}.",
                }
            elif result.get("project_id"):
                get_project_for_action(db, result["project_id"], user)
                data["card"] = {
                    "kind": "saved_project",
                    "items": [],
                    **result,
                    "text": "Saved in PMS.",
                }
        elif row.status not in {"cancelled"}:
            # Read results and financial proposals are reauthorized, never replayed
            # from cached conversation snapshots after access has changed.
            fresh = prepare(db, user, intent)
            data["card"] = row.proposal if row.status == "awaiting_approval" else fresh
            if row.status == "awaiting_approval":
                data.update(approval_hash=row.approval_hash, expires_at=row.expires_at)
    except HTTPException:
        data["card"] = {
            "kind": "notice",
            "items": [],
            "text": "This result is unavailable under your current permissions or data state. Prepare it again.",
        }
    return data


@router.get("/tools")
def tools(user: User = Depends(get_current_user)):
    _require_ai_access(user)
    return {
        "tools": registry(),
        "provider_settings": "/pms/settings/ai/openai",
        "fallback": "guided",
        "unavailable": [
            "expense creation",
            "refunds",
            "bank changes",
            "bulk deletion",
            "automatic tax determination",
        ],
    }


@router.get("/conversations")
def conversations(
    q: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    _require_ai_access(user)
    rows = db.query(AssistantConversation).filter_by(
        user_id=user.id, organization_id=tenant(user), deleted_at=None
    )
    return [
        {"id": r.id, "title": r.title, "created_at": r.created_at}
        for r in rows.filter(AssistantConversation.title.ilike(f"%{q[:100]}%"))
        .order_by(AssistantConversation.id.desc())
        .limit(50)
    ]


@router.post("/conversations", status_code=201)
def create_conversation(
    data: ConversationInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_ai_access(user)
    if data.workspace_id:
        from app.apps.project_management.workspaces import workspace_member

        workspace_member(db, data.workspace_id, user)
    row = AssistantConversation(
        user_id=user.id,
        organization_id=tenant(user),
        workspace_id=data.workspace_id,
        title=data.title,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "title": row.title}


@router.patch("/conversations/{ident}")
def rename(
    ident: int,
    data: ConversationInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = owned(db, user, ident)
    row.title = data.title
    db.commit()
    return {"id": row.id, "title": row.title}


@router.delete("/conversations/{ident}")
def delete(
    ident: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    row = owned(db, user, ident)
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"deleted": True}


@router.get("/conversations/{ident}")
def conversation(
    ident: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    row = owned(db, user, ident)
    return {
        "id": row.id,
        "title": row.title,
        "messages": [
            public_message(db, user, m)
            for m in db.query(AssistantMessage)
            .filter_by(conversation_id=ident)
            .order_by(AssistantMessage.id)
            .limit(100)
        ],
    }


@router.post("/conversations/{ident}/messages")
def message(
    ident: int,
    data: MessageInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = owned(db, user, ident)
    _require_ai_rate_limit(db, request, user, bucket="pms_assistant")
    require_enabled(db, user)
    if data.project_id:
        get_project_for_action(db, data.project_id, user)
    if data.customer_id:
        from app.apps.srm.services.commercial import customer

        customer(db, data.customer_id, user)
    old = (
        db.query(AssistantMessage)
        .filter_by(conversation_id=ident, request_key=str(data.request_key))
        .first()
    )
    if old:
        if old.request_hash != digest(
            data.model_dump(mode="json", exclude={"request_key"})
        ):
            raise HTTPException(
                409, "Request key is already used. Start a new request for edits."
            )
        return public_message(db, user, old)
    from app.ai_agents.services.advanced_security import AiDataRedactionService

    redactor = AiDataRedactionService()
    safe_text = redactor.redact_text(data.text)
    intent = data.intent
    if not intent and data.provider:
        from app.ai_operator.providers import generate_json

        config = resolve_provider(db, user, data.provider, conv.workspace_id)
        if not config or not config.enabled or not config.data_sharing_allowed:
            raise HTTPException(
                409,
                "Provider is not configured. Use guided mode or ask an administrator.",
            )
        db.commit()  # No tenant-wide business lock is held during provider I/O.
        try:
            intent = Intent.model_validate(
                generate_json(
                    db,
                    user,
                    config,
                    prompt=json.dumps(
                        {
                            "request": safe_text,
                            "verified_project_id": data.project_id,
                            "tools": [
                                {
                                    "name": t["name"],
                                    "description": t["description"],
                                    "confirmation_required": t["confirmation_required"],
                                }
                                for t in registry()
                            ],
                        },
                        default=str,
                    ),
                    schema=Intent.model_json_schema(),
                    output_type=Intent,
                    purpose="assistant",
                    usage_scope=scope_key(db, user, conv.workspace_id),
                )
            )
        except HTTPException:
            db.commit()  # Preserve sanitized provider telemetry; no business write has run.
            raise
        if intent.tool == "invoices.prepare":
            # Tax and lines must originate in verified billing data or explicit
            # user-edited details, never a model's guessed jurisdiction/rate.
            intent = intent.model_copy(update={"tax_amount": None, "lines": []})
    intent = intent or parse_local(safe_text, data.project_id)
    references = conv.references or {}
    if re.search(r"\b(its|their|this|second|first|third)\b", data.text, re.I):
        updates = {}
        if not intent.customer_id and references.get("customer_id"):
            updates["customer_id"] = references["customer_id"]
        if not intent.project_id and references.get("project_id"):
            updates["project_id"] = references["project_id"]
        ordinal = next(
            (
                n
                for n, word in enumerate(["first", "second", "third"])
                if re.search(rf"\b{word} project\b", data.text, re.I)
            ),
            None,
        )
        candidates = references.get("project_ids", [])
        if ordinal is not None and len(candidates) > ordinal:
            updates["project_id"] = candidates[ordinal]
        intent = intent.model_copy(update=updates)
    if data.project_id and not intent.project_id:
        intent = intent.model_copy(update={"project_id": data.project_id})
    if data.customer_id and not intent.customer_id:
        intent = intent.model_copy(update={"customer_id": data.customer_id})
    intent = Intent.model_validate(
        redactor.redact_for_ai(user, "PMS", intent.model_dump(mode="json"))
    )
    lock_tenant(db, user)
    db.expire_all()
    conv = owned(db, user, ident)
    previous = (
        db.query(AssistantMessage)
        .filter_by(conversation_id=ident, request_key=str(data.request_key))
        .first()
    )
    if previous:
        if previous.request_hash != digest(
            data.model_dump(mode="json", exclude={"request_key"})
        ):
            raise HTTPException(409, "Request key is already used for another action.")
        return public_message(db, user, previous)
    card = prepare(db, user, intent)
    approval = intent.tool in MUTATIONS and card["kind"] not in {
        "selection",
        "customers",
    }
    row = AssistantMessage(
        conversation_id=ident,
        request_key=str(data.request_key),
        request_hash=digest(data.model_dump(mode="json", exclude={"request_key"})),
        prompt=safe_text,
        tool=intent.tool,
        arguments=intent.model_dump(mode="json"),
        proposal=card if approval else None,
        status="awaiting_approval" if approval else "answered",
    )
    if approval:
        row.approval_hash = digest(
            {"nonce": str(uuid4()), "card": card, "user": user.id}
        )
        row.expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    db.add(row)
    db.flush()
    if conv.title == "New conversation":
        conv.title = (safe_text or intent.tool)[:150]
    conv.references = {
        "project_id": intent.project_id,
        "customer_id": intent.customer_id,
        "project_ids": (
            [item["id"] for item in card.get("items", []) if "id" in item]
            if card.get("kind") == "projects" or card.get("entity") == "project"
            else references.get("project_ids", [])
        ),
    }
    audit(db, user, row, "prepared" if approval else "read")
    from app.ai_agents.services.advanced_security import AiUsageService

    AiUsageService(db).record_event(
        user=user, agent_id=None, module="PMS", event_type="assistant_request"
    )
    db.commit()
    return public_message(db, user, row)


@router.post("/conversations/{ident}/messages/{message_id}/cancel")
def cancel(
    ident: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owned(db, user, ident)
    row = (
        db.query(AssistantMessage)
        .filter_by(id=message_id, conversation_id=ident)
        .first()
    )
    if not row:
        raise HTTPException(404, "Action not found")
    if row.status == "completed":
        raise HTTPException(
            409, "The action already completed; use the normal business reversal flow."
        )
    row.status = "cancelled"
    audit(db, user, row, "cancelled")
    db.commit()
    return {"status": row.status}


@router.post("/conversations/{ident}/messages/{message_id}/confirm")
def confirm(
    ident: int,
    message_id: int,
    data: Confirmation,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owned(db, user, ident)
    require_enabled(db, user)
    _require_ai_rate_limit(db, request, user, bucket="pms_assistant_confirm")
    lock_tenant(db, user)
    row = (
        db.query(AssistantMessage)
        .filter_by(id=message_id, conversation_id=ident)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not row or row.approval_hash != data.approval_hash:
        raise HTTPException(409, "Approval does not match this action.")
    from app.ai_agents.security import verify,operation
    verify(db,user,row.security_context,payload=operation(row),confirmation=True)
    if row.status == "completed":
        return public_message(db, user, row)
    if row.status != "awaiting_approval":
        raise HTTPException(409, "Action is no longer pending.")
    expires = (
        row.expires_at.replace(tzinfo=timezone.utc)
        if row.expires_at.tzinfo is None
        else row.expires_at
    )
    if expires <= datetime.now(timezone.utc):
        raise HTTPException(409, "Proposal expired. Prepare a fresh preview.")
    intent = Intent.model_validate(row.arguments)
    action_key = str(
        uuid5(
            NAMESPACE_URL, f"businesssuite:assistant:{tenant(user)}:{user.id}:{row.id}"
        )
    )
    if intent.tool == "invoices.prepare":
        require(user, "srm_invoice_create", "srm_admin")
        # Recover after a successful business commit whose response was lost.
        previous = (
            db.query(InvoiceContext)
            .filter_by(request_id=action_key, project_id=row.proposal["project_id"])
            .first()
        )
        if previous:
            invoice = invoice_for(db, previous.invoice_id, user)
        else:
            fresh = invoice_preview(
                db,
                user,
                intent.model_copy(
                    update={"project_id": row.proposal["project_id"], "query": ""}
                ),
            )
            if fresh != row.proposal:
                raise HTTPException(
                    409, "Billing data changed. Prepare and review a fresh preview."
                )
            from app.apps.srm.commercial_api import (
                draft_project_invoice_service,
                DraftInput,
            )

            saved = draft_project_invoice_service(
                row.proposal["project_id"],
                DraftInput(request_id=UUID(action_key), lines=row.proposal["lines"]),
                db,
                user,
                commit=False,
            )
            invoice = invoice_for(db, saved["id"], user, lock=True)
        if invoice.status == "draft":
            invoice.issue_date = date_from_iso(row.proposal["issue_date"])
            invoice.due_date = date_from_iso(row.proposal["due_date"])
        row.result = {"invoice_id": invoice.id}
    elif intent.tool in {"invoices.issue", "invoices.send", "payments.record"}:
        recovered = False
        if intent.tool == "payments.record":
            from app.apps.srm.commercial_models import ReceiptContext

            recovered = (
                db.query(ReceiptContext)
                .filter_by(invoice_id=intent.invoice_id, request_id=action_key)
                .first()
                is not None
            )
        if not recovered:
            fresh = prepare(db, user, intent)
            if fresh != row.proposal:
                raise HTTPException(409, "Invoice changed. Review a fresh action.")
        if intent.tool == "payments.record":
            from app.apps.srm.payments import record_payment, PaymentInput

            record_payment(
                intent.invoice_id,
                PaymentInput(request_id=UUID(action_key), amount=intent.amount),
                db,
                user,
            )
        else:
            from app.apps.srm.api.router import approve_invoice, send_invoice

            (approve_invoice if intent.tool == "invoices.issue" else send_invoice)(
                intent.invoice_id, db, user
            )
        row.result = {"invoice_id": intent.invoice_id}
    else:
        fresh = prepare(db, user, intent)
        if fresh != row.proposal:
            raise HTTPException(
                409, "The proposed action context changed. Prepare it again."
            )
        from app.apps.project_management.api.router import (
            create_project_operation as create_project,
            create_task_operation as create_task,
            update_task_operation as update_task,
        )
        from app.apps.project_management.schemas import (
            PMSProjectCreate,
            PMSTaskCreate,
            PMSTaskUpdate,
        )
        from app.apps.project_management.models import PMSProject, PMSTask

        key = f"AI-{row.id}"
        if intent.tool == "projects.create":
            result = (
                db.query(PMSProject)
                .filter_by(
                    project_key=key, organization_id=tenant(user), owner_user_id=user.id
                )
                .first()
            )
            result = result or create_project(
                PMSProjectCreate(
                    name=intent.title,
                    project_key=key,
                    budget_amount=intent.amount,
                    start_date=intent.start_date,
                    due_date=intent.due_date,
                ),
                db,
                user,
                commit=False,
            )
            if intent.customer_id:
                from app.apps.srm.commercial_api import link_project_service, LinkInput

                link_project_service(
                    result.id,
                    LinkInput(
                        customer_id=intent.customer_id,
                        seller_id=intent.seller_id or tenant(user),
                        currency=intent.currency or "INR",
                    ),
                    db,
                    user,
                    commit=False,
                )
            row.result = {"project_id": result.id}
        elif intent.tool == "tasks.create":
            result = (
                db.query(PMSTask)
                .filter_by(project_id=intent.project_id, task_key=key)
                .first()
            )
            result = result or create_task(
                intent.project_id,
                PMSTaskCreate(title=intent.title, task_key=key),
                db,
                user,
                commit=False,
            )
            row.result = {"project_id": intent.project_id, "task_id": result.id}
        elif intent.tool == "tasks.assign":
            update_task(
                intent.task_id,
                PMSTaskUpdate(assignee_user_ids=[intent.assignee_id]),
                db,
                user,
                commit=False,
            )
            row.result = {"project_id": intent.project_id, "task_id": intent.task_id}
        else:
            raise HTTPException(422, "This tool has no approved mutation.")
    row.status = "completed"
    audit(db, user, row, "completed")
    db.commit()
    return public_message(db, user, row)


def date_from_iso(value):
    from datetime import date

    return date.fromisoformat(value)


@router.post("/conversations/{ident}/messages/stream")
def stream_message(
    ident: int,
    data: MessageInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from fastapi.responses import StreamingResponse

    owned(db, user, ident)
    bind, user_id = db.get_bind(), user.id

    def events():
        yield 'event: status\ndata: {"stage":"Validating context and preparing a proposal"}\n\n'
        # FastAPI may close yielded dependencies before iterating a response.
        # Own the streaming session and reload live identity in that session.
        with Session(bind=bind, join_transaction_mode="create_savepoint") as session:
            try:
                actor = session.get(User, user_id)
                if not actor or not actor.is_active:
                    raise HTTPException(403, "Active sign-in required.")
                result = message(ident, data, request, session, actor)
                yield "event: result\ndata: " + json.dumps(result, default=str) + "\n\n"
            except HTTPException as error:
                session.rollback()
                yield "event: failure\ndata: " + json.dumps(
                    {"detail": error.detail, "status": error.status_code}
                ) + "\n\n"
            except Exception:
                session.rollback()
                yield 'event: failure\ndata: {"detail":"Unable to prepare this action. No confirmation was executed. Retry or review conversation history.","status":500}\n\n'

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "private, no-store", "X-Accel-Buffering": "no"},
    )
