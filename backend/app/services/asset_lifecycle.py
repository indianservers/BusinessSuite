"""Asset transitions over existing custody, approvals, documents and notifications.

All mutations are transactional. Physical return, inspection, recovery and exit
approval are separate states; none of them silently authorizes payroll deductions.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import json

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from app.apps.srm.services.commercial import tenant
from app.core.masking import user_has_permission
from app.models.asset import Asset, AssetAssignment
from app.models.audit import AuditLog
from app.models.approval_os import ApprovalRequest, ApprovalHistory
from app.models.employee import Employee
from app.models.exit import ExitRecord, ExitChecklistItem
from app.models.user import User
from app.shared.models import ServicePolicy, ServiceDocument, ServiceEvent
from app.schemas.asset import AssetPolicy
from app.services.metrics.queries import employee_records, registered_users, business_day

CONDITIONS = {"New", "Good", "Fair", "Poor", "Damaged", "Lost"}
STATUSES = {"Available", "Assigned", "Pending Inspection", "Under Repair", "Lost", "Damaged", "Retired", "Disposed"}


def now():
    return datetime.now(timezone.utc)


def assets(db, user):
    return db.query(Asset).filter(Asset.organization_id == tenant(user))


def asset(db, user, ident, lock=False):
    query = assets(db, user).filter(Asset.id == ident)
    if lock:
        query = query.populate_existing().with_for_update()
    row = query.first()
    if not row:
        raise HTTPException(404, "Asset not found in your permitted scope")
    return row


def person(db, user, ident, lock=False):
    query = employee_records(db, user).filter(Employee.id == ident)
    row = (query.populate_existing().with_for_update() if lock else query).first()
    if not row:
        raise HTTPException(404, "Employee not found in your permitted scope")
    return row


def assignment(db, user, ident, lock=False):
    row = db.query(AssetAssignment).join(Asset).filter(AssetAssignment.id == ident, Asset.organization_id == tenant(user)).first()
    if not row:
        raise HTTPException(404, "Custody record not found")
    item = asset(db, user, row.asset_id, lock=lock)
    if lock:
        db.refresh(row)
    return row, item


def audit(db, user, item, action, *, row=None, before=None, after=None):
    db.add(AuditLog(organization_id=tenant(user), user_id=user.id, method="POST", module="hrms",
        entity_type="asset", entity_id=item.id, action=action[:50],
        old_values=json.dumps(before, default=str) if before else None,
        new_values=json.dumps({"assignment_id": row.id if row else None, "employee_id": row.employee_id if row else None, **(after or {})}, default=str),
        description=f"Asset {item.asset_tag}: {action}"))


def policy_row(db, user, lock=False):
    query = db.query(ServicePolicy).filter_by(scope_key=f"asset-lifecycle:{tenant(user)}", organization_id=tenant(user))
    return (query.with_for_update() if lock else query).first()


def policy(db, user):
    row = policy_row(db, user)
    return AssetPolicy.model_validate(row.values_json if row else {}).model_dump(mode="json")


def validate_recipient(db, user, ident):
    row = registered_users(db, user, organization_id=tenant(user)).filter(User.id == ident, User.is_active.is_(True)).first()
    if not row:
        raise HTTPException(422, "Approver or recipient must be an active company user")
    return row


def validate_documents(db, user, item, ids):
    if not ids:
        return
    found = db.query(ServiceDocument).filter(ServiceDocument.id.in_(ids), ServiceDocument.organization_id == tenant(user),
        ServiceDocument.module_key == "hrms", ServiceDocument.entity_type == "asset", ServiceDocument.entity_id == item.id).all()
    if len({r.id for r in found}) != len(set(ids)):
        raise HTTPException(422, "Evidence must be an authorized document attached to this asset")


def validate_asset_values(db, user, values, current=None):
    from app.models.asset import AssetCategory
    for key, maximum in (("name", 200), ("asset_tag", 50), ("serial_number", 100)):
        if key in values and values[key] is not None:
            value = str(values[key]).strip()
            if not value and key != "serial_number":
                raise HTTPException(422, f"{key.replace('_', ' ')} is required")
            if len(value) > maximum:
                raise HTTPException(422, f"{key} exceeds {maximum} characters")
            values[key] = value or None
    for key in ("name", "condition", "status", "details"):
        if key in values and values[key] is None:
            raise HTTPException(422, f"{key} cannot be empty")
    for key in ("asset_tag", "serial_number"):
        value = values.get(key)
        if value:
            # Keep the established global unique keys; report no other tenant's data.
            from sqlalchemy import select, func
            table = Asset.__table__
            query = select(table.c.id).where(func.lower(table.c[key]) == value.casefold())
            if current:
                query = query.where(table.c.id != current.id)
            if db.connection().execute(query).first():
                raise HTTPException(409, "An asset tag or serial / registration number is already in use")
    if values.get("category_id") and not db.query(AssetCategory.id).filter_by(id=values["category_id"]).first():
        raise HTTPException(422, "Choose an existing asset category")
    if values.get("status") and values["status"] not in STATUSES:
        raise HTTPException(422, "Choose a valid lifecycle status")
    if values.get("condition") and values["condition"] not in CONDITIONS:
        raise HTTPException(422, "Choose a valid physical condition")
    details = values.get("details")
    if details is not None:
        if len(json.dumps(details, default=str)) > 24000:
            raise HTTPException(422, "Additional details exceed the supported size")
        for key in ("insurance_expiry", "maintenance_due", "replacement_due", "roadworthiness_expiry"):
            if details.get(key):
                from datetime import date
                try:
                    date.fromisoformat(str(details[key]))
                except ValueError:
                    raise HTTPException(422, f"{key.replace('_', ' ')} must be a date")


def new_approval(db, user, row, kind, context):
    settings = policy(db, user)
    key = {"inspection": "inspection_approver_id", "recovery": "recovery_approver_id", "exception": "exception_approver_id"}[kind]
    approver = settings.get(key)
    if approver:
        validate_recipient(db, user, approver)
    request = ApprovalRequest(organization_id=tenant(user), source_module="hrms", approval_type=f"asset_{kind}",
        entity_type="asset_assignment", entity_id=row.id, title=f"Asset {kind}: {row.asset.asset_tag}",
        requester_user_id=user.id, assigned_to_user_id=approver, assigned_role=None if approver else "super_admin",
        status="Pending", context_json={"asset_lifecycle": kind, "asset_id": row.asset_id, **context})
    db.add(request)
    db.flush()
    db.add(ApprovalHistory(request_id=request.id, event_type="submitted", actor_user_id=user.id, after_status="Pending", details_json=context))
    return request


def issue_batch(db, user, data):
    employee = person(db, user, data.employee_id, lock=True)
    if employee.status != "Active":
        raise HTTPException(409, "Only active employees can receive assets")
    if data.assigned_date > business_day(db, user):
        raise HTTPException(422, "Assignment date cannot be in the future")
    if data.condition_at_assignment not in {"New", "Good", "Fair"}:
        raise HTTPException(422, "Assets must be fit for handover")
    latest_exit = db.query(ExitRecord).filter(ExitRecord.employee_id == employee.id, ExitRecord.status != "Cancelled").order_by(ExitRecord.id.desc()).first()
    if latest_exit and latest_exit.status == "Completed":
        raise HTTPException(409, "Assets cannot be assigned after completed offboarding")
    existing = db.query(AssetAssignment).join(Asset).filter(Asset.organization_id == tenant(user), AssetAssignment.handover_group == data.request_key).all()
    if existing:
        if {r.asset_id for r in existing} != set(data.asset_ids) or any(r.employee_id != employee.id or r.assigned_date != data.assigned_date or r.expected_return_date != data.expected_return_date or r.condition_at_assignment != data.condition_at_assignment or (r.accessories or []) != data.accessories or (r.remarks or "") != data.remarks or (r.return_details or {}).get("handover_photo_document_ids",[]) != data.handover_document_ids.get(r.asset_id,[]) for r in existing):
            raise HTTPException(409, "This handover request key was already used for different details")
        return existing
    # One tenant-scoped request key reserves the complete handover, even when
    # concurrent retries select disjoint asset sets.
    event = ServiceEvent(organization_id=tenant(user), module_key="hrms", event_type="asset.handover",
        entity_type="asset", entity_id=data.asset_ids[0], actor_id=user.id,
        request_key="asset-handover:"+data.request_key, payload_json={"asset_ids": data.asset_ids, "employee_id": data.employee_id}, status="completed")
    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
    except IntegrityError:
        raise HTTPException(409, "This handover request is already reserved; reload its recorded result")
    # Lock in a fixed order to avoid deadlocks in overlapping multi-asset batches.
    locked = [asset(db, user, ident, lock=True) for ident in sorted(data.asset_ids)]
    for item in locked:
        validate_documents(db,user,item,data.handover_document_ids.get(item.id,[]))
        if item.status != "Available" or item.condition in {"Poor", "Damaged", "Lost"} or db.query(AssetAssignment.id).filter_by(asset_id=item.id, is_active=True).first():
            raise HTTPException(409, f"Asset {item.asset_tag} is not available for handover")
    result = []
    for item in locked:
        item.status = "Assigned"
        row = AssetAssignment(asset_id=item.id, employee_id=employee.id, assigned_date=data.assigned_date,
            expected_return_date=data.expected_return_date, condition_at_assignment=data.condition_at_assignment,
            accessories=data.accessories, remarks=data.remarks, handover_group=data.request_key, assigned_by=user.id,
            return_details={"handover_photo_document_ids":data.handover_document_ids.get(item.id,[])})
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Another handover acquired this asset; reload availability")
        audit(db, user, item, "assignment", row=row, after=data.model_dump(mode="json"))
        result.append(row)
    return result


def receive_return(db, user, row, item, data):
    if not row.is_active:
        raise HTTPException(409, "This custody record has already been returned")
    if data.return_date < row.assigned_date or data.return_date > business_day(db, user):
        raise HTTPException(422, "Return date must be between assignment and today")
    if data.condition == "Lost" and not data.damage_description.strip():
        raise HTTPException(422, "Describe the loss and circumstances")
    validate_documents(db, user, item, data.photo_document_ids)
    recorded_accessories = set(row.accessories or [])
    returned = set(data.accessories_returned)
    missing = set(data.missing_accessories)
    if returned & missing:
        raise HTTPException(422, "An accessory cannot be both returned and missing")
    missing |= recorded_accessories - returned
    row.returned_date = data.return_date
    row.returned_by = user.id
    row.condition_at_return = data.condition
    handover_photos=(row.return_details or {}).get("handover_photo_document_ids",[])
    row.return_details = {**(row.return_details or {}), **data.model_dump(mode="json"), "missing_accessories": sorted(missing), "received_by": user.id, "received_at": now().isoformat(),
        "at_handover": {"condition": row.condition_at_assignment, "accessories": row.accessories or [], "remarks": row.remarks, "photo_document_ids":handover_photos}}
    row.is_active = False
    row.inspection_status = "Pending"
    item.status = "Pending Inspection"
    item.condition = data.condition if data.condition in CONDITIONS else "Fair"
    audit(db, user, item, "return_recorded", row=row, after=row.return_details)


def submit_inspection(db, user, row, item, data):
    if row.is_active or row.inspection_status not in {"Pending", "Rejected"}:
        raise HTTPException(409, "Only a returned asset awaiting inspection can be inspected")
    validate_documents(db, user, item, data.photo_document_ids)
    details = row.return_details or {}
    if data.disposition == "Available":
        if data.condition in {"Poor", "Damaged", "Lost"}:
            raise HTTPException(422, "An unfit asset cannot be released as available")
        if details.get("missing_accessories") and not data.missing_resolved:
            raise HTTPException(422, "Resolve missing accessories before releasing this asset")
        if row.condition_at_return == "Lost":
            raise HTTPException(422, "A lost asset requires recovery or an approved exception")
    request = new_approval(db, user, row, "inspection", data.model_dump(mode="json"))
    row.inspection_status = "Awaiting Approval"
    row.inspection_approval_id = request.id
    row.return_details = {**details, "inspection": {**data.model_dump(mode="json"), "inspected_by": user.id, "inspected_at": now().isoformat()}}
    audit(db, user, item, "inspection_submitted", row=row, after={"approval_id": request.id, **data.model_dump(mode="json")})
    return request


def apply_approval(db, user, request, decision, reason):
    """Called by Approval OS and the asset workspace in the same transaction."""
    kind = (request.context_json or {}).get("asset_lifecycle")
    if kind not in {"inspection", "recovery", "exception"}:
        raise HTTPException(422, "Unsupported asset approval")
    if request.organization_id != tenant(user):
        raise HTTPException(404, "Approval not found")
    if not user.is_superuser and (not user_has_permission(user, "asset_manage") or request.requester_user_id == user.id):
        raise HTTPException(403, "An independent authorized approver is required")
    row, item = assignment(db, user, request.entity_id, lock=True)
    approved = decision == "approve"
    if kind == "inspection":
        if row.inspection_approval_id != request.id or row.inspection_status != "Awaiting Approval":
            raise HTTPException(409, "Inspection approval is stale")
        row.inspection_status = "Approved" if approved else "Rejected"
        if approved:
            item.status = request.context_json["disposition"]
            item.condition = request.context_json["condition"]
    elif kind == "recovery":
        if row.recovery_approval_id != request.id or row.recovery_status != "Pending":
            raise HTTPException(409, "Recovery approval is stale")
        row.recovery_status = "Approved" if approved else "Rejected"
    else:
        details = row.return_details or {}
        if details.get("exception_approval_id") != request.id:
            raise HTTPException(409, "Exception approval is stale")
        row.return_details = {**details, "exception_status": "Approved" if approved else "Rejected", "exception_decision_reason": reason}
    audit(db, user, item, f"{kind}_{'approved' if approved else 'rejected'}", row=row, after={"approval_id": request.id, "reason": reason})


def blockers_for_employee(db, user, employee_id):
    rows = db.query(AssetAssignment).join(Asset).filter(Asset.organization_id == tenant(user), AssetAssignment.employee_id == employee_id).all()
    issues = []
    rules = policy(db, user)
    for row in rows:
        if row.is_active:
            issues.append({"assignment_id": row.id, "asset_tag": row.asset.asset_tag, "kind": "Awaiting Return"})
        elif row.inspection_status in {"Pending", "Awaiting Approval", "Rejected"}:
            issues.append({"assignment_id": row.id, "asset_tag": row.asset.asset_tag, "kind": "Under Inspection"})
        if row.recovery_status in {"Pending", "Approved"}:
            issues.append({"assignment_id": row.id, "asset_tag": row.asset.asset_tag, "kind": "Outstanding Recovery"})
        if row.condition_at_return == "Lost" and (row.return_details or {}).get("exception_status") != "Approved":
            issues.append({"assignment_id": row.id, "asset_tag": row.asset.asset_tag, "kind": "Loss Exception Required"})
        details = row.return_details or {}
        if details.get("exception_status") != "Approved":
            if rules["block_missing_clearance"] and details.get("missing_accessories") and not (details.get("inspection") or {}).get("missing_resolved"):
                issues.append({"assignment_id": row.id, "asset_tag": row.asset.asset_tag, "kind": "Missing Accessories"})
            if rules["block_damaged_clearance"] and row.condition_at_return in {"Poor", "Damaged"} and row.recovery_status not in {"Settled", "Rejected"}:
                issues.append({"assignment_id": row.id, "asset_tag": row.asset.asset_tag, "kind": "Damage Resolution Required"})
    return issues


def clear_exit_assets(db, user, record):
    if record.status in {"Cancelled", "Completed"}:
        raise HTTPException(409, "This exit case is closed")
    person(db, user, record.employee_id)
    if blockers_for_employee(db, user, record.employee_id):
        raise HTTPException(409, "Resolve asset returns, inspection approvals, recoveries and loss exceptions first")
    tasks = db.query(ExitChecklistItem).filter_by(exit_record_id=record.id).all()
    if not any("asset" in task.task_name.lower() for task in tasks):
        task = ExitChecklistItem(exit_record_id=record.id, task_name="Return company assets and confirm condition", assigned_to_role="IT")
        db.add(task)
        tasks.append(task)
    for task in tasks:
        if "asset" in task.task_name.lower():
            if task.assigned_to_user and task.assigned_to_user != user.id and not user.is_superuser:
                raise HTTPException(403, "The configured asset clearance assignee must sign off this task")
            # Assets may sign off their own task only. Every other department remains independent.
            task.is_completed = True
            task.completed_at = now()
            task.remarks = f"Asset reconciliation verified by user {user.id} at {now().isoformat()}"
    db.add(AuditLog(organization_id=tenant(user), user_id=user.id, method="POST", module="hrms", entity_type="exit_record", entity_id=record.id,
        action="asset_clearance", description="Asset checks completed; company-wide exit approval unchanged"))
    return {"asset_cleared": True, "exit_status": record.status, "company_exit_completed": False}


def approval_scope(model, user, company, grants):
    """HRMS may see only its own asset approvals, without an Approvals app grant."""
    if getattr(user, '_suite_current_module', None) != 'hrms' or not user_has_permission(user, 'asset_manage'):
        return None
    from sqlalchemy import and_, select
    from app.models.approval_os import ApprovalComment
    if model not in {ApprovalRequest, ApprovalHistory, ApprovalComment}:
        return None
    request = ApprovalRequest.__table__
    role = user.role.name if user.role else ''
    visible = select(request.c.id).where(request.c.organization_id == company, request.c.source_module == 'hrms',
        request.c.entity_type == 'asset_assignment', request.c.approval_type.in_(['asset_inspection','asset_recovery','asset_exception']),
        or_(request.c.requester_user_id == user.id, request.c.assigned_to_user_id == user.id,
            request.c.delegated_to_user_id == user.id, request.c.assigned_role == role, request.c.delegated_role == role))
    return model.id.in_(visible) if model is ApprovalRequest else model.request_id.in_(visible)


def approval_domain_write(db, item, user, company):
    """Permit exact native asset operations, never generic approval writes."""
    if getattr(user, '_suite_current_module', None) != 'hrms' or not user_has_permission(user, 'asset_manage'):
        return False
    if not isinstance(item, (ApprovalRequest, ApprovalHistory)):
        return False
    request = item if isinstance(item, ApprovalRequest) else db.query(ApprovalRequest).filter_by(id=item.request_id).first()
    if not request or request.organization_id != company or request.source_module != 'hrms' or request.entity_type != 'asset_assignment' or (request.context_json or {}).get('asset_lifecycle') not in {'inspection','recovery','exception'}:
        return False
    # Parent assignment access is still enforced by HRMS scope and branch ownership.
    visible = db.query(AssetAssignment.id).join(Asset).filter(AssetAssignment.id == request.entity_id, Asset.organization_id == company).first()
    return visible is not None
