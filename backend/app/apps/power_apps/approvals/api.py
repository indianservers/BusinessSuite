"""Standalone approvals API. Every object is company, environment and participant scoped."""

import hashlib, json, uuid
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.apps.power_apps.approvals import service as s
from app.apps.power_apps.approvals.models import (
    ApprovalPolicy,
    RequestState,
    Assignment,
    Delegation,
    Attachment,
)
from app.apps.power_apps.approvals.contracts import (
    PolicyWrite,
    Submit,
    Decision,
    Revision,
    Comment,
    DelegationWrite,
    Reassign,
)
from app.apps.power_apps.approvals.templates import TEMPLATES
from app.apps.power_apps.models import PowerResource, PowerVersion, PowerActivity
from app.apps.power_apps.service import (
    organization,
    record_change,
    serialize as raw_serialize,
    validate_environment,
)
from app.models.approval_os import ApprovalRequest, ApprovalComment, ApprovalHistory
from app.apps.power_apps.runtime import now, scope_values, finish
from app.apps.power_apps.approvals.calendar import utc

router = APIRouter(
    prefix="/power-apps/approvals",
    tags=["Power Apps Approvals"],
    dependencies=[Depends(RequirePermission("power_apps_view"))],
)
view = RequirePermission("power_apps_view")


def serialize(row):
    return {
        key: (utc(value) if isinstance(value, datetime) else value)
        for key, value in raw_serialize(row).items()
    }


def policy_detail(db, row):
    resource = db.get(PowerResource, row.resource_id)
    return {
        **serialize(row),
        "name": resource.name,
        "version": resource.version,
        "definition": resource.definition,
        "published_definition": (
            db.get(PowerVersion, row.published_version_id).snapshot["definition"]
            if row.published_version_id
            else None
        ),
    }


@router.get("/templates")
def templates(user=Depends(view)):
    return {"items": TEMPLATES}


@router.get("/policies")
def policies(
    environment: str = "development", db: Session = Depends(get_db), user=Depends(view)
):
    return {
        "items": [
            policy_detail(db, p)
            for p in s.scoped(db, ApprovalPolicy, user, environment)
            .order_by(ApprovalPolicy.id.desc())
            .limit(100)
        ]
    }


@router.post("/policies", status_code=201)
def create_policy(
    data: PolicyWrite,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_approval_manage")),
):
    validate_environment(db, user, environment)
    with s.domain(db):
        resource = PowerResource(
            organization_id=organization(user),
            environment=environment,
            owner_user_id=user.id,
            application_id="approvals",
            name=data.name,
            definition=data.definition.model_dump(mode="json"),
        )
        db.add(resource)
        db.flush()
        record_change(db, user, resource, "approval_policy_created")
        row = ApprovalPolicy(**scope_values(resource), resource_id=resource.id)
        db.add(row)
        db.commit()
        return policy_detail(db, row)


@router.put("/policies/{id}")
def update_policy(
    id: int,
    data: PolicyWrite,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_approval_manage")),
):
    with s.domain(db):
        row = (
            s.scoped(db, ApprovalPolicy, user, environment)
            .filter_by(id=id, owner_user_id=user.id)
            .with_for_update()
            .first()
        )
        if not row:
            raise HTTPException(404, "Workflow not found")
        resource = (
            db.query(PowerResource)
            .filter_by(id=row.resource_id)
            .with_for_update()
            .one()
        )
        if data.expected_version != resource.version:
            raise HTTPException(409, "Draft changed; reload before saving")
        resource.name = data.name
        resource.definition = data.definition.model_dump(mode="json")
        resource.version += 1
        record_change(db, user, resource, "approval_policy_updated")
        db.commit()
        return policy_detail(db, row)


@router.post("/policies/{id}/activate")
def activate(
    id: int,
    expected_version: int = Query(ge=1),
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_approval_manage")),
):
    with s.domain(db):
        row = s.publish_policy(db, user, environment, id, expected_version)
        db.commit()
        return policy_detail(db, row)


@router.post("/policies/{id}/disable")
def disable(
    id: int,
    expected_version: int = Query(ge=1),
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_approval_manage")),
):
    with s.domain(db):
        row = s.publish_policy(db, user, environment, id, expected_version, False)
        db.commit()
        return policy_detail(db, row)


@router.post("/requests", status_code=201)
def submit(
    data: Submit,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_approval_submit")),
):
    with s.domain(db):
        root, state = s.submit(db, user, environment, data)
        db.commit()
        return detail(root.id, environment, db, user)


def query(db, user, environment, scope="all", search="", status=None):
    ids = s.visible_ids(db, user, environment)
    rows = db.query(ApprovalRequest).filter(
        ApprovalRequest.source_module == "power_apps",
        ApprovalRequest.organization_id == organization(user),
        ApprovalRequest.id.in_(ids),
    )
    if scope == "submitted":
        rows = rows.filter(ApprovalRequest.requester_user_id == user.id)
    if scope in {"assigned", "delegated", "team"}:
        tasks = s.scoped(db, Assignment, user, environment).filter(
            Assignment.status == "pending"
        )
        if scope == "delegated":
            tasks = tasks.filter(
                Assignment.user_id == user.id, Assignment.original_user_id != user.id
            )
        elif scope == "assigned":
            tasks = tasks.filter(Assignment.user_id == user.id)
        elif not s.administrator(user):
            tasks = tasks.filter(
                or_(
                    Assignment.user_id == user.id,
                    Assignment.original_user_id == user.id,
                )
            )
        rows = rows.filter(
            ApprovalRequest.id.in_(tasks.with_entities(Assignment.request_id)),
            ApprovalRequest.status == "Pending",
        )
    if scope == "overdue":
        rows = rows.filter(
            ApprovalRequest.status.in_(
                ["Pending", "Resolution Required", "Changes Requested"]
            ),
            ApprovalRequest.sla_due_at < now(),
        )
    if status:
        rows = rows.filter(ApprovalRequest.status == status)
    if search:
        rows = rows.filter(
            ApprovalRequest.title.ilike(
                "%" + search.replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"
            )
        )
    return rows


@router.get("/requests")
def requests(
    environment: str = "development",
    scope: str = Query(
        "all", pattern="^(all|assigned|delegated|submitted|overdue|team)$"
    ),
    search: str = Query("", max_length=180),
    status: str | None = None,
    priority: str | None = Query(None, pattern="^(Low|Normal|High|Urgent)$"),
    sort: str = Query("created", pattern="^(created|due|priority)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(40, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(view),
):
    from sqlalchemy import case
    from app.common.models import CommonPerson

    rows = query(db, user, environment, scope, search, status)
    if priority:
        rows = rows.filter(ApprovalRequest.priority == priority)
    total = rows.count()
    order = (
        ApprovalRequest.sla_due_at.asc().nulls_last()
        if sort == "due"
        else (
            case(
                (ApprovalRequest.priority == "Urgent", 0),
                (ApprovalRequest.priority == "High", 1),
                (ApprovalRequest.priority == "Normal", 2),
                else_=3,
            )
            if sort == "priority"
            else ApprovalRequest.created_at.desc()
        )
    )
    page = (
        rows.order_by(
            order, ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    requesters = {
        person.user_id: person.display_name
        for person in db.query(CommonPerson)
        .filter(
            CommonPerson.organization_id == organization(user),
            CommonPerson.user_id.in_([row.requester_user_id for row in page]),
        )
        .all()
    }
    type_names = dict(
        db.query(RequestState.id, PowerVersion.snapshot["name"].as_string())
        .join(PowerVersion, PowerVersion.id == RequestState.version_id)
        .filter(
            RequestState.id.in_([row.id for row in page]),
            RequestState.organization_id == organization(user),
            RequestState.environment == environment,
        )
        .all()
    )
    assignments = (
        db.query(Assignment)
        .filter(
            Assignment.request_id.in_([row.id for row in page]),
            Assignment.status == "pending",
            Assignment.organization_id == organization(user),
            Assignment.environment == environment,
        )
        .order_by(Assignment.id)
        .all()
    )
    return {
        "total": total,
        "items": [
            {
                **serialize(row),
                "environment": environment,
                "requester_name": requesters.get(row.requester_user_id)
                or f"User #{row.requester_user_id}",
                "request_type": type_names.get(row.id),
                "current_stage": next(
                    (a.stage_name for a in assignments if a.request_id == row.id), None
                ),
                "assigned_user_ids": [
                    a.user_id for a in assignments if a.request_id == row.id
                ],
            }
            for row in page
        ],
    }


@router.get("/requests/{id}")
def detail(
    id: int,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(view),
):
    root, state = s.visible(db, user, environment, id, True)
    assignments = (
        db.query(Assignment).filter_by(request_id=id).order_by(Assignment.id).all()
    )
    from app.access.catalog import permission_names

    can_decide = (
        "power_apps_approval_decide" in permission_names(user) or user.is_superuser
    )
    grants = getattr(user, "_suite_grants", None)
    can_decide = can_decide and (
        grants is None or "approve" in grants.get("power_apps", {}).get("actions", [])
    )
    return {
        **serialize(root),
        "state": serialize(state),
        "assignments": [
            {
                **serialize(a),
                "can_decide": can_decide
                and a.user_id == user.id
                and a.status == "pending"
                and root.status == "Pending"
                and root.requester_user_id != user.id,
            }
            for a in assignments
        ],
        "comments": [
            serialize(c)
            for c in db.query(ApprovalComment)
            .filter_by(request_id=id)
            .order_by(ApprovalComment.id)
            .limit(500)
        ],
        "history": [
            serialize(h)
            for h in db.query(ApprovalHistory)
            .filter_by(request_id=id)
            .order_by(ApprovalHistory.id)
            .limit(2000)
        ],
        "attachments": [
            {k: v for k, v in serialize(a).items() if k != "storage_path"}
            for a in db.query(Attachment).filter_by(request_id=id)
        ],
        "evidence_valid": s.verify_history(db, state),
        "can_cancel": root.requester_user_id == user.id or s.administrator(user),
        "can_upload": root.requester_user_id == user.id
        and root.status in {"Pending", "Resolution Required", "Changes Requested"}
        and (
            root.status == "Changes Requested"
            or not any(a.decided_at for a in assignments)
        ),
        "can_reassign": s.administrator(user),
        "can_resubmit": root.requester_user_id == user.id
        and root.status == "Changes Requested",
    }


@router.post("/requests/{id}/decisions")
def decide(
    id: int,
    data: Decision,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_approval_decide")),
):
    with s.domain(db):
        s.decide(db, user, environment, id, data)
        db.commit()
        return detail(id, environment, db, user)


@router.post("/requests/{id}/comments", status_code=201)
def comment(
    id: int,
    data: Comment,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(view),
):
    with s.domain(db):
        root, state = s.visible(db, user, environment, id, True)
        s.ensure_integrity(db, state)
        db.add(
            ApprovalComment(
                request_id=id,
                author_user_id=user.id,
                comment=data.text,
                is_internal=False,
            )
        )
        s.evidence(db, root, state, user.id, "comment", data.text)
        db.commit()
        return detail(id, environment, db, user)


@router.post("/requests/{id}/cancel")
def cancel(
    id: int,
    data: Revision,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(view),
):
    with s.domain(db):
        root, state = s.visible(db, user, environment, id, True)
        s.ensure_integrity(db, state)
        if root.requester_user_id != user.id and not s.administrator(user):
            raise HTTPException(
                403, "Only the requester or approval administrator may cancel"
            )
        if state.revision != data.expected_revision or root.status in s.TERMINAL:
            raise HTTPException(409, "Request changed or already closed")
        root.status = "Cancelled"
        state.revision += 1
        s.evidence(db, root, state, user.id, "cancelled", data.reason)
        finish(db, db.get(s.Run, state.run_id), "cancelled")
        for a in db.query(Assignment).filter_by(request_id=id, status="pending"):
            a.status = "closed"
        s.notify(db, state, [root.requester_user_id], "cancelled", root.title)
        db.commit()
        return detail(id, environment, db, user)


@router.post("/requests/{id}/resubmit")
def resubmit(
    id: int,
    data: Revision,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_approval_submit")),
):
    with s.domain(db):
        root, state = s.visible(db, user, environment, id, True)
        s.ensure_integrity(db, state)
        if root.requester_user_id != user.id:
            raise HTTPException(403, "Only the requester may resubmit")
        if (
            root.status != "Changes Requested"
            or state.revision != data.expected_revision
        ):
            raise HTTPException(409, "Request is not awaiting this revision")
        s.restart_revision(db, root, state, data.fields, user.id, data.reason)
        db.commit()
        return detail(id, environment, db, user)


@router.post("/requests/{id}/reassign")
def reassign(
    id: int,
    data: Reassign,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_approval_manage")),
):
    with s.domain(db):
        root, state = s.visible(db, user, environment, id, True)
        s.ensure_integrity(db, state)
        if (
            root.status not in {"Pending", "Resolution Required"}
            or state.revision != data.expected_revision
            or not state.active_step_id
        ):
            raise HTTPException(409, "Request changed or has no active stage")
        s.ApproverResolver(db, organization(user)).eligible(data.user_id)
        if root.requester_user_id == data.user_id:
            raise HTTPException(403, "Requester cannot fill an approval seat")
        if (
            db.query(Assignment)
            .filter_by(
                request_id=id,
                step_id=state.active_step_id,
                cycle=state.cycle,
                user_id=data.user_id,
            )
            .first()
        ):
            raise HTTPException(409, "User already occupies a seat")
        assignment = (
            db.query(Assignment)
            .filter_by(
                id=data.assignment_id,
                request_id=id,
                step_id=state.active_step_id,
                cycle=state.cycle,
                status="pending",
            )
            .first()
            if data.assignment_id
            else None
        )
        if data.assignment_id and not assignment:
            raise HTTPException(409, "Assignment is no longer pending")
        if assignment:
            assignment.user_id = data.user_id
            assignment.delegation_id = None
        else:
            stage = s.stage_for(db, state)
            cardinality = set(
                uid
                for selector in stage.selectors
                if selector.kind
                in {"user", "group", "organization_owner", "record_user"}
                for uid in selector.ids
            )
            if stage.mode != "any" and (
                len(stage.selectors) != 1
                or stage.selectors[0].kind in {"role", "group"}
                and len(cardinality) != 1
                or len(cardinality) > 1
            ):
                raise HTTPException(
                    409,
                    "Restore the configured group and retry resolution; an unresolved voting group cannot be reduced to fewer seats",
                )
            if (
                stage.mode != "any"
                and db.query(Assignment)
                .filter_by(
                    request_id=id, step_id=state.active_step_id, cycle=state.cycle
                )
                .count()
            ):
                raise HTTPException(
                    409, "Cannot change the published voting group size"
                )
            from app.models.user import User

            assignment = Assignment(
                **scope_values(state),
                request_id=id,
                step_id=state.active_step_id,
                cycle=state.cycle,
                stage_name=stage.name,
                user_id=data.user_id,
                original_user_id=data.user_id,
                role_id=db.get(User, data.user_id).role_id,
                due_at=now() + timedelta(seconds=stage.sla_seconds),
                assigned_at=now(),
            )
            db.add(assignment)
        root.status = "Pending"
        state.revision += 1
        s.evidence(
            db,
            root,
            state,
            user.id,
            "reassigned",
            data.reason,
            {"user_id": data.user_id, "assignment_id": data.assignment_id},
        )
        s.notify(db, state, [data.user_id], "assigned", root.title)
        db.commit()
        return detail(id, environment, db, user)


@router.get("/delegations")
def delegations(
    environment: str = "development", db: Session = Depends(get_db), user=Depends(view)
):
    return {
        "items": [
            serialize(d)
            for d in s.scoped(db, Delegation, user, environment)
            .filter(
                or_(
                    Delegation.owner_user_id == user.id,
                    Delegation.alternate_user_id == user.id,
                )
            )
            .order_by(Delegation.id.desc())
            .limit(100)
        ]
    }


@router.post("/delegations", status_code=201)
def delegate(
    data: DelegationWrite,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_approval_delegate")),
):
    with s.domain(db):
        validate_environment(db, user, environment)
        s.ApproverResolver(db, organization(user)).eligible(user.id)
        s.ApproverResolver(db, organization(user)).eligible(data.alternate_user_id)
        from app.models.user import User

        db.query(User).filter(User.id.in_([user.id, data.alternate_user_id])).order_by(
            User.id
        ).with_for_update().all()
        if (
            data.policy_id
            and not s.scoped(db, ApprovalPolicy, user, environment)
            .filter_by(id=data.policy_id)
            .first()
        ):
            raise HTTPException(404, "Delegation policy not found in this environment")
        if data.alternate_user_id == user.id or utc(data.ends_at) <= now():
            raise HTTPException(
                422, "Choose an independent alternate and future delegation period"
            )
        if (
            s.scoped(db, Delegation, user, environment)
            .filter(
                Delegation.enabled.is_(True),
                or_(
                    Delegation.owner_user_id == data.alternate_user_id,
                    Delegation.alternate_user_id == user.id,
                ),
                Delegation.ends_at > now(),
            )
            .first()
        ):
            raise HTTPException(409, "Delegation chains are prohibited")
        if (
            s.scoped(db, Delegation, user, environment)
            .filter(
                Delegation.owner_user_id == user.id,
                Delegation.enabled.is_(True),
                Delegation.starts_at < data.ends_at,
                Delegation.ends_at > data.starts_at,
            )
            .first()
        ):
            raise HTTPException(409, "An overlapping delegation exists")
        row = Delegation(
            organization_id=organization(user),
            environment=environment,
            owner_user_id=user.id,
            **data.model_dump(),
        )
        db.add(row)
        db.flush()
        db.add(
            PowerActivity(
                organization_id=organization(user),
                environment=environment,
                owner_user_id=user.id,
                actor_user_id=user.id,
                action="approval_delegation_created",
                resource_name=f"Delegation #{row.id}: {data.reason}"[:180],
            )
        )
        from app.models.notification import Notification

        db.add(
            Notification(
                company_id=organization(user),
                user_id=data.alternate_user_id,
                title="Approval delegation received",
                message=f"User #{user.id} delegated eligible approval authority for the recorded date range.",
                module="power_apps",
                event_type="power_approval.delegation_received",
                related_entity_type="power_approval_delegation",
                related_entity_id=row.id,
                action_url=f"/power-apps/approvals/delegations?environment={environment}",
                channels=["in_app"],
            )
        )
        db.commit()
        return serialize(row)


@router.delete("/delegations/{id}")
def revoke_delegation(
    id: int,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_approval_delegate")),
):
    with s.domain(db):
        row = (
            s.scoped(db, Delegation, user, environment)
            .filter_by(id=id, owner_user_id=user.id)
            .with_for_update()
            .first()
        )
        if not row:
            raise HTTPException(404, "Delegation not found")
        row.enabled = False
        db.commit()
        return {"revoked": True}


@router.post("/requests/{id}/attachments", status_code=201)
async def upload(
    id: int,
    file: UploadFile = File(...),
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(view),
):
    with s.domain(db):
        root, state = s.visible(db, user, environment, id, True)
        s.ensure_integrity(db, state)
        if root.requester_user_id != user.id or root.status not in {
            "Pending",
            "Resolution Required",
            "Changes Requested",
        }:
            raise HTTPException(
                403, "Only the requester can add documents to an open request"
            )
        if db.query(Attachment).filter_by(request_id=id).count() >= 10:
            raise HTTPException(
                422, "At most ten document versions are supported per request"
            )
        if (
            root.status != "Changes Requested"
            and db.query(Assignment)
            .filter(Assignment.request_id == id, Assignment.decided_at.is_not(None))
            .first()
        ):
            raise HTTPException(
                409, "Request changes before adding documents after voting has begun"
            )
        state.revision += 1
        data = await file.read(2097153)
        if len(data) > 2097152 or not data:
            raise HTTPException(413, "Choose a nonempty file of at most 2 MB")
        ext = Path(file.filename or "").suffix.lower()
        types = {
            ".pdf": ("application/pdf", b"%PDF-"),
            ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
            ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
            ".txt": ("text/plain", None),
        }
        if ext not in types or (types[ext][1] and not data.startswith(types[ext][1])):
            raise HTTPException(422, "Use a valid PDF, PNG, JPG or UTF-8 text document")
        if ext == ".txt":
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(422, "Text documents must use UTF-8") from None
        from app.core.config import settings
        from app.core.storage import persist_file

        path = (
            Path(settings.UPLOAD_DIR).resolve()
            / "power-approvals"
            / str(organization(user))
            / environment
            / (hashlib.sha256(data).hexdigest() + ".blob")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest()
            != hashlib.sha256(data).hexdigest()
        ):
            temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".part")
            try:
                temporary.write_bytes(data)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        persist_file(str(path))
        row = Attachment(
            **scope_values(state),
            request_id=id,
            request_revision=state.revision,
            name=Path(file.filename or "document").name[:180],
            storage_path=str(path),
            sha256=hashlib.sha256(data).hexdigest(),
            mime_type=types[ext][0],
            size=len(data),
            created_at=now(),
        )
        db.add(row)
        db.flush()
        if (
            root.status == "Resolution Required"
            and db.query(Assignment).filter_by(request_id=id, status="pending").count()
        ):
            root.status = "Pending"
        s.evidence(
            db,
            root,
            state,
            user.id,
            "attachment_added",
            details={
                "attachment_id": row.id,
                "sha256": row.sha256,
                "request_revision": state.revision,
            },
        )
        db.commit()
        return {"id": row.id, "name": row.name, "sha256": row.sha256}


@router.get("/requests/{id}/attachments/{attachment_id}")
def download(
    id: int,
    attachment_id: int,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(view),
):
    root, state = s.visible(db, user, environment, id)
    row = (
        db.query(Attachment)
        .filter_by(
            id=attachment_id,
            request_id=id,
            organization_id=organization(user),
            environment=environment,
        )
        .first()
    )
    if not row:
        raise HTTPException(404, "Document not found")
    if not s.verify_history(db, state):
        raise HTTPException(
            409, "Approval evidence does not match its recorded document versions"
        )
    from app.core.storage import materialize_file
    from fastapi.responses import FileResponse

    materialize_file(row.storage_path)
    path = Path(row.storage_path)
    if (
        not path.is_file()
        or hashlib.sha256(path.read_bytes()).hexdigest() != row.sha256
    ):
        raise HTTPException(409, "Document content does not match its recorded version")
    return FileResponse(
        path,
        filename=row.name,
        media_type=row.mime_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/analytics")
def analytics(
    environment: str = "development",
    start: datetime | None = None,
    end: datetime | None = None,
    policy_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(view),
):
    from sqlalchemy import case

    rows = query(db, user, environment, status=status)
    if start:
        rows = rows.filter(ApprovalRequest.created_at >= utc(start))
    if end:
        rows = rows.filter(ApprovalRequest.created_at < utc(end))
    if policy_id:
        rows = rows.filter(ApprovalRequest.entity_id == policy_id)
    counts = dict(
        rows.with_entities(ApprovalRequest.status, func.count())
        .group_by(ApprovalRequest.status)
        .all()
    )
    total = sum(counts.values())
    ids = rows.with_entities(ApprovalRequest.id)

    def seconds(begin, finish):
        return (
            func.extract("epoch", finish - begin)
            if db.bind.dialect.name == "postgresql"
            else (func.julianday(finish) - func.julianday(begin)) * 86400
        )

    closed = rows.filter(
        ApprovalRequest.status.in_(["Approved", "Rejected"]),
        ApprovalRequest.decided_at.is_not(None),
    )
    completed = closed.count()
    average = closed.with_entities(
        func.avg(seconds(ApprovalRequest.created_at, ApprovalRequest.decided_at))
    ).scalar()
    tasks = s.scoped(db, Assignment, user, environment).filter(
        Assignment.request_id.in_(ids)
    )
    pending = tasks.filter(Assignment.status == "pending")
    workload = (
        pending.with_entities(Assignment.user_id, func.count())
        .group_by(Assignment.user_id)
        .order_by(func.count().desc())
        .limit(100)
        .all()
    )
    timings = (
        tasks.filter(Assignment.decided_at.is_not(None))
        .with_entities(
            Assignment.stage_name,
            func.avg(seconds(Assignment.assigned_at, Assignment.decided_at)),
            func.count(),
        )
        .group_by(Assignment.stage_name)
        .limit(100)
        .all()
    )
    voted = tasks.filter(Assignment.decided_at.is_not(None))
    voted_count = voted.count()
    compliant = voted.filter(Assignment.decided_at <= Assignment.due_at).count()
    bottlenecks = (
        pending.with_entities(
            Assignment.stage_name,
            func.count(),
            func.sum(case((Assignment.due_at < now(), 1), else_=0)),
        )
        .group_by(Assignment.stage_name)
        .order_by(func.count().desc())
        .limit(20)
        .all()
    )
    department_dimension = RequestState.fields["department"].as_string()
    departments = (
        s.scoped(db, RequestState, user, environment)
        .filter(RequestState.id.in_(ids))
        .with_entities(department_dimension, func.count())
        .group_by(department_dimension)
        .limit(100)
        .all()
    )
    trend = (
        rows.with_entities(func.date(ApprovalRequest.created_at), func.count())
        .group_by(func.date(ApprovalRequest.created_at))
        .order_by(func.date(ApprovalRequest.created_at).desc())
        .limit(90)
        .all()
    )
    return {
        "counts": {
            "awaiting_me": query(db, user, environment, "assigned")
            .filter(ApprovalRequest.id.in_(ids))
            .count(),
            "submitted_by_me": rows.filter(
                ApprovalRequest.requester_user_id == user.id
            ).count(),
            "pending": sum(
                counts.get(key, 0)
                for key in ["Pending", "Changes Requested", "Resolution Required"]
            ),
            "overdue": rows.filter(
                ApprovalRequest.status.in_(
                    ["Pending", "Resolution Required", "Changes Requested"]
                ),
                ApprovalRequest.sla_due_at < now(),
            ).count(),
            "approved": counts.get("Approved", 0),
            "rejected": counts.get("Rejected", 0),
            "escalated": rows.filter(ApprovalRequest.escalated_at.is_not(None)).count(),
            "average_seconds": float(average) if average is not None else None,
        },
        "by_status": counts,
        "total": total,
        "rejection_rate": counts.get("Rejected", 0) / completed if completed else None,
        "workload": [{"user_id": u, "pending": n} for u, n in workload],
        "stage_times": [
            {"stage": stage, "average_seconds": float(seconds), "decisions": n}
            for stage, seconds, n in timings
        ],
        "bottlenecks": [
            {"stage": stage, "pending": n, "overdue": late}
            for stage, n, late in bottlenecks
        ],
        "by_department": [
            {"department": department or "Unspecified", "count": n}
            for department, n in departments
        ],
        "volume_trend": [{"date": str(day), "count": n} for day, n in reversed(trend)],
        "sla_compliance": compliant / voted_count if voted_count else None,
        "recent": [
            serialize(h)
            for h in db.query(ApprovalHistory)
            .filter(ApprovalHistory.request_id.in_(ids))
            .order_by(ApprovalHistory.id.desc())
            .limit(20)
        ],
    }


@router.get("/people")
def people(
    environment: str = "development", db: Session = Depends(get_db), user=Depends(view)
):
    validate_environment(db, user, environment)
    from app.models.user import User
    from app.core.tenant_boundary import company_ids

    items = []
    for candidate in (
        db.query(User).filter_by(is_active=True).order_by(User.id).limit(200)
    ):
        if organization(user) not in company_ids(db, candidate):
            continue
        try:
            s.ApproverResolver(db, organization(user)).eligible(candidate.id)
        except HTTPException:
            continue
        items.append({"id": candidate.id, "label": candidate.email})
    return {"items": items}


@router.get("/capabilities")
def capabilities(user=Depends(view)):
    from app.access.catalog import permission_names
    from app.apps.power_apps.registry import PERMISSIONS

    names = set(PERMISSIONS) if user.is_superuser else permission_names(user)
    return {
        "permissions": sorted(names.intersection(PERMISSIONS)),
        "execution_engine": "phase3",
        "decision_evidence": "HMAC chained audit, not a qualified digital signature",
        "bulk_decisions": False,
        "file_limit_bytes": 2097152,
        "business_calendar": "versioned IANA timezone, weekdays, working hours and explicit holidays; elapsed UTC by default",
    }


@router.post("/requests/{id}/resolve")
def resolve_request(
    id: int,
    data: Revision,
    environment: str = "development",
    db: Session = Depends(get_db),
    user=Depends(RequirePermission("power_apps_approval_manage")),
):
    with s.domain(db):
        root, state = s.visible(db, user, environment, id, True)
        s.ensure_integrity(db, state)
        if (
            root.status != "Resolution Required"
            or state.revision != data.expected_revision
            or not state.active_step_id
        ):
            raise HTTPException(
                409, "This request is not awaiting administrative resolution"
            )
        root.status = "Pending"
        s.evidence(db, root, state, user.id, "resolution_retried", data.reason)
        step = db.get(s.Step, state.active_step_id)
        stage = s.stage_for(db, state)
        s.open_stage(
            db,
            db.get(s.Run, state.run_id),
            step,
            {"stage": stage.model_dump(mode="json")},
        )
        db.commit()
        return detail(id, environment, db, user)
