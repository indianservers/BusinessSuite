"""Workflow endpoints extending the existing asset API, not another register."""
from datetime import date
from decimal import Decimal
from uuid import uuid4
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_
from app.core.deps import get_db, RequirePermission
from app.apps.srm.services.commercial import tenant
from app.core.masking import user_has_permission
from app.models.asset import Asset, AssetAssignment
from app.models.approval_os import ApprovalRequest
from app.models.audit import AuditLog
from app.models.employee import Employee
from app.models.exit import ExitRecord, ExitChecklistItem
from app.models.user import User
from app.shared.models import ServicePolicy, ServiceDocument
from app.schemas.asset import (AssetHandover, AssetReturn, AssetInspection, AssetRecovery, AssetDecision,
    AssetSettlement, AssetExtension, AssetTransfer, AssetException, AssetPolicy)
from app.services import asset_lifecycle as lifecycle
from app.services.metrics.queries import business_day, registered_users

router = APIRouter()
viewer = RequirePermission("asset_view")
manager = RequirePermission("asset_manage")


def save(db):
    from sqlalchemy.exc import IntegrityError
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "The asset or transaction changed concurrently; reload and retry")


def approval_output(db, user, request):
    from app.api.v1.approval_os import _can_decide_request
    return {"id": request.id, "status": request.status, "type": request.approval_type,
        "reason": request.decision_reason, "assigned_to_user_id": request.assigned_to_user_id,
        "can_decide": _can_decide_request(request, user) and (user.is_superuser or request.requester_user_id != user.id and user_has_permission(user, "asset_manage"))}


@router.get("/policy")
def get_policy(db=Depends(get_db), user=Depends(viewer)):
    return {"values": lifecycle.policy(db, user), "can_configure": user_has_permission(user, "company_manage") or user.is_superuser}


@router.post("/policy")
def set_policy(data: AssetPolicy, db=Depends(get_db), user=Depends(RequirePermission("company_manage"))):
    for identity in set(filter(None, [data.inspection_approver_id, data.recovery_approver_id, data.exception_approver_id, *data.manager_user_ids])):
        recipient = lifecycle.validate_recipient(db, user, identity)
        if not (recipient.is_superuser or user_has_permission(recipient, "asset_manage")):
            raise HTTPException(422, "Asset approvers must have asset management permission")
    from app.shared.settings import effective
    if "whatsapp" in data.channels:
        from app.services import whatsapp_workspace as wa
        if not wa.admin(user) or not wa.connection_for(db, tenant(user)) or not data.whatsapp_template:
            raise HTTPException(422, "WhatsApp requires an authorized sender, connected account and approved template")
    if (set(data.channels) - {"whatsapp"}) - set(effective(db, tenant(user), "hrms")["values"]["notification_channels"]):
        raise HTTPException(422, "A selected channel is disabled by the company notification policy")
    row = lifecycle.policy_row(db, user, lock=True)
    if not row:
        row = ServicePolicy(scope_key=f"asset-lifecycle:{tenant(user)}", organization_id=tenant(user), module_key="hrms", kind="asset_lifecycle", updated_by=user.id)
        db.add(row)
    row.values_json = data.model_dump(mode="json")
    row.version = (row.version or 0) + 1
    row.updated_by = user.id
    db.add(AuditLog(organization_id=tenant(user), user_id=user.id, method="POST", module="hrms", action="asset_policy_updated", entity_type="asset_policy", description="Asset approval and reminder policy updated", new_values=json.dumps(row.values_json)))
    save(db)
    return row.values_json


@router.get("/approvers")
def approvers(search: str = "", db=Depends(get_db), user=Depends(manager)):
    query = registered_users(db, user).filter(User.is_active.is_(True))
    if search:
        query = query.filter(User.email.icontains(search, autoescape=True))
    return [{"id": r.id, "name": r.email} for r in query.order_by(User.id).limit(100) if r.is_superuser or user_has_permission(r, "asset_manage")]


@router.post("/assignments/batch", status_code=201)
def batch_assign(data: AssetHandover, db=Depends(get_db), user=Depends(manager)):
    rows = lifecycle.issue_batch(db, user, data)
    save(db)
    return {"handover_group": data.request_key, "assignment_ids": [r.id for r in rows]}


@router.post("/assignments/{assignment_id}/receive")
def receive(assignment_id: int, data: AssetReturn, db=Depends(get_db), user=Depends(manager)):
    row, item = lifecycle.assignment(db, user, assignment_id, lock=True)
    lifecycle.receive_return(db, user, row, item, data)
    save(db)
    return {"id": row.id, "inspection_status": row.inspection_status, "asset_status": item.status}


@router.post("/assignments/{assignment_id}/inspection")
def inspect_return(assignment_id: int, data: AssetInspection, db=Depends(get_db), user=Depends(manager)):
    row, item = lifecycle.assignment(db, user, assignment_id, lock=True)
    request = lifecycle.submit_inspection(db, user, row, item, data)
    save(db)
    return approval_output(db, user, request)


@router.post("/assignments/{assignment_id}/recovery")
def propose_recovery(assignment_id: int, data: AssetRecovery, db=Depends(get_db), user=Depends(manager)):
    row, item = lifecycle.assignment(db, user, assignment_id, lock=True)
    settings = lifecycle.policy(db, user)
    if row.is_active:
        raise HTTPException(409, "Record the return or loss before proposing recovery")
    if not settings["recovery_enabled"]:
        raise HTTPException(409, "Recovery proposals are disabled; configure company policy first")
    cap = Decimal(str(settings["recovery_limit"]))
    if cap > 0 and data.amount > cap:
        raise HTTPException(422, "Proposal exceeds the configured recovery limit")
    if row.recovery_status not in {"None", "Rejected"}:
        raise HTTPException(409, "This custody record already has an unresolved or settled recovery")
    request = lifecycle.new_approval(db, user, row, "recovery", data.model_dump(mode="json"))
    row.recovery_amount, row.recovery_status, row.recovery_approval_id = data.amount, "Pending", request.id
    row.return_details = {**(row.return_details or {}), "recovery_proposal": data.model_dump(mode="json")}
    lifecycle.audit(db, user, item, "recovery_proposed", row=row, after=data.model_dump(mode="json"))
    save(db)
    return approval_output(db, user, request)


@router.post("/assignments/{assignment_id}/settle-recovery")
def settle_recovery(assignment_id: int, data: AssetSettlement, db=Depends(get_db), user=Depends(manager)):
    row, item = lifecycle.assignment(db, user, assignment_id, lock=True)
    settings = lifecycle.policy(db, user)
    if not user.is_superuser and user.id != settings.get("recovery_approver_id"):
        raise HTTPException(403, "The configured Finance recovery approver must record settlement")
    if row.recovery_status != "Approved":
        raise HTTPException(409, "Only an approved recovery can be settled")
    row.recovery_status = "Settled"
    row.return_details = {**(row.return_details or {}), "settlement": {"reference": data.reference, "recorded_by": user.id, "recorded_at": lifecycle.now().isoformat()}}
    lifecycle.audit(db, user, item, "recovery_settled", row=row, after={"reference": data.reference})
    save(db)
    return {"recovery_status": row.recovery_status, "payroll_deduction_created": False}


@router.post("/assignments/{assignment_id}/exception")
def request_exception(assignment_id: int, data: AssetException, db=Depends(get_db), user=Depends(manager)):
    row, item = lifecycle.assignment(db, user, assignment_id, lock=True)
    if row.is_active or not (row.condition_at_return in {"Lost", "Poor", "Damaged"} or (row.return_details or {}).get("missing_accessories")):
        raise HTTPException(409, "An exception requires a recorded loss, damage or missing items; returns and inspection approval remain required")
    if (row.return_details or {}).get("exception_status") in {"Pending", "Approved"}:
        raise HTTPException(409, "An exception has already been submitted")
    request = lifecycle.new_approval(db, user, row, "exception", data.model_dump(mode="json"))
    row.return_details = {**(row.return_details or {}), "exception_approval_id": request.id, "exception_status": "Pending", "exception_reason": data.reason, "exception_policy": data.policy_reference}
    lifecycle.audit(db, user, item, "exception_requested", row=row, after=data.model_dump(mode="json"))
    save(db)
    return approval_output(db, user, request)


@router.post("/approvals/{approval_id}/decision")
def decide(approval_id: int, data: AssetDecision, db=Depends(get_db), user=Depends(manager)):
    request = db.query(ApprovalRequest).filter_by(id=approval_id, organization_id=tenant(user)).first()
    if not request or not (request.context_json or {}).get("asset_lifecycle"):
        raise HTTPException(404, "Asset approval not found")
    from app.api.v1.approval_os import _decide
    from app.schemas.approval_os import ApprovalDecision
    result = _decide(approval_id, data.decision, ApprovalDecision(reason=data.reason), db, user)
    return approval_output(db, user, result)


@router.post("/assignments/{assignment_id}/extend")
def extend(assignment_id: int, data: AssetExtension, db=Depends(get_db), user=Depends(manager)):
    row, item = lifecycle.assignment(db, user, assignment_id, lock=True)
    if not row.is_active:
        raise HTTPException(409, "Returned custody cannot be extended")
    if data.expected_return_date < business_day(db, user) or data.expected_return_date < row.assigned_date or row.expected_return_date and data.expected_return_date <= row.expected_return_date:
        raise HTTPException(422, "Choose a future return date later than the current due date")
    previous = row.expected_return_date
    row.expected_return_date = data.expected_return_date
    lifecycle.audit(db, user, item, "custody_extended", row=row, before={"expected_return_date": previous}, after=data.model_dump(mode="json"))
    save(db)
    return {"expected_return_date": row.expected_return_date}


@router.post("/assignments/{assignment_id}/transfer", status_code=201)
def transfer(assignment_id: int, data: AssetTransfer, db=Depends(get_db), user=Depends(manager)):
    lifecycle.person(db, user, data.employee_id, lock=True)
    row, item = lifecycle.assignment(db, user, assignment_id, lock=True)
    if not row.is_active or data.employee_id == row.employee_id:
        raise HTTPException(409, "Select another employee for an active custody transfer")
    if data.assigned_date < row.assigned_date:
        raise HTTPException(422, "Transfer cannot precede the original handover")
    # Supported same-transaction transfer: old custody ends, new custody starts.
    row.is_active = False
    row.returned_date = data.assigned_date
    row.returned_by = user.id
    row.condition_at_return = data.condition
    row.return_details = {"transfer": True, "reason": data.reason, "transferred_to": data.employee_id, "recorded_by": user.id}
    item.status = "Available"
    db.flush()
    batch = AssetHandover(employee_id=data.employee_id, asset_ids=[item.id], assigned_date=data.assigned_date,
        expected_return_date=data.expected_return_date, condition_at_assignment=data.condition, accessories=row.accessories or [], remarks=data.reason, request_key=str(uuid4()))
    result = lifecycle.issue_batch(db, user, batch)
    lifecycle.audit(db, user, item, "reassignment", row=row, after={"new_assignment_id": result[0].id, "employee_id": data.employee_id, "reason": data.reason})
    save(db)
    return {"assignment_id": result[0].id}


@router.post("/assignments/{assignment_id}/request-return")
def request_return(assignment_id: int, db=Depends(get_db), user=Depends(manager)):
    row, item = lifecycle.assignment(db, user, assignment_id, lock=True)
    if not row.is_active:
        raise HTTPException(409, "Asset has already been returned")
    row.return_details = {**(row.return_details or {}), "return_requested_on": business_day(db, user).isoformat()}
    lifecycle.audit(db, user, item, "return_requested", row=row)
    from app.services.asset_reminders import notify_once
    if row.employee.user_id:
        notify_once(db, user, row.employee.user_id, item, "return_requested", str(row.id), f"Return requested: {item.asset_tag}")
    save(db)
    return {"requested": True}


@router.post("/exit-clearance/{exit_id}/complete-assets")
def complete_assets(exit_id: int, db=Depends(get_db), user=Depends(manager)):
    from app.services.employee_exit import scoped_exit
    record = scoped_exit(db, user, exit_id)
    result = lifecycle.clear_exit_assets(db, user, record)
    save(db)
    return result


@router.post("/reminders/run")
def run_reminders(db=Depends(get_db), user=Depends(manager)):
    from app.services.asset_reminders import enqueue_asset_reminders
    result = enqueue_asset_reminders(db, user)
    save(db)
    return {"queued": result}


@router.get("/insights")
def insights(db=Depends(get_db), user=Depends(viewer)):
    today = business_day(db, user)
    from datetime import timedelta
    rows = lifecycle.assets(db, user)
    active = db.query(AssetAssignment).join(Asset).filter(Asset.organization_id == tenant(user), AssetAssignment.is_active.is_(True))
    returned = db.query(AssetAssignment).join(Asset).filter(Asset.organization_id == tenant(user), AssetAssignment.is_active.is_(False), AssetAssignment.returned_date.is_not(None))
    return {"due_soon": active.filter(AssetAssignment.expected_return_date >= today, AssetAssignment.expected_return_date <= today + timedelta(days=30)).count(),
        "overdue": active.filter(AssetAssignment.expected_return_date < today).count(),
        "pending_acknowledgments": active.filter(AssetAssignment.acknowledgement_signed.is_(False)).count(),
        "damaged_in_custody": active.filter(Asset.condition.in_(["Poor", "Damaged"])).count(),
        "pending_inspections": returned.filter(AssetAssignment.inspection_status.in_(["Pending", "Awaiting Approval", "Rejected"])).count(),
        "outstanding_recoveries": str(returned.filter(AssetAssignment.recovery_status.in_(["Pending", "Approved"])).with_entities(func.coalesce(func.sum(AssetAssignment.recovery_amount), 0)).scalar()),
        "warranty_expiring": [{"id": r.id, "name": r.name, "asset_tag": r.asset_tag, "date": r.warranty_expiry} for r in rows.filter(Asset.warranty_expiry >= today, Asset.warranty_expiry <= today + timedelta(days=30)).limit(10)],
        "high_value": [{"id": r.id, "name": r.name, "asset_tag": r.asset_tag, "value": str(r.purchase_cost)} for r in rows.filter(Asset.purchase_cost.is_not(None)).order_by(Asset.purchase_cost.desc()).limit(5)],
        "without_custodian": rows.filter(Asset.status == "Assigned", ~Asset.assignments.any(AssetAssignment.is_active.is_(True))).count(),
        "repair_backlog": rows.filter(Asset.status == "Under Repair").count(),
        "replacement_due": [{"id": r.id, "name": r.name, "asset_tag": r.asset_tag} for r in rows.filter(Asset.details["replacement_due"].as_string() != "", Asset.details["replacement_due"].as_string() <= today.isoformat()).limit(10)]}


@router.get("/assignments/{assignment_id}/receipt")
def receipt(assignment_id: int, db=Depends(get_db), user=Depends(viewer)):
    row, item = lifecycle.assignment(db, user, assignment_id)
    from app.services.asset_documents import handover_pdf
    return Response(handover_pdf(db, user, row), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="handover-{row.id}.pdf"', "Cache-Control": "private, no-store"})


@router.get("/exit-clearance/{exit_id}/certificate")
def clearance_certificate(exit_id: int, db=Depends(get_db), user=Depends(viewer)):
    from app.services.employee_exit import scoped_exit
    record = scoped_exit(db, user, exit_id)
    issues = lifecycle.blockers_for_employee(db, user, record.employee_id)
    if issues:
        raise HTTPException(409, "Asset clearance certificate requires all asset issues to be resolved")
    tasks = db.query(ExitChecklistItem).filter_by(exit_record_id=record.id).all()
    if not any("asset" in t.task_name.lower() for t in tasks) or any("asset" in t.task_name.lower() and not t.is_completed for t in tasks):
        raise HTTPException(409, "Sign off the asset clearance checklist first")
    from app.services.asset_documents import clearance_pdf
    return Response(clearance_pdf(db, user, record), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="asset-clearance-{record.id}.pdf"', "Cache-Control": "private, no-store"})


@router.get("/employees/{employee_id}/profile")
def employee_profile(employee_id: int, db=Depends(get_db), user=Depends(viewer)):
    employee = lifecycle.person(db, user, employee_id)
    rows = db.query(AssetAssignment).join(Asset).filter(Asset.organization_id == tenant(user), AssetAssignment.employee_id == employee.id).order_by(AssetAssignment.assigned_date.desc()).all()
    return {"id": employee.id, "name": f"{employee.first_name} {employee.last_name}", "employee_code": employee.employee_id,
        "department": employee.department.name if employee.department else "Unassigned", "designation": employee.designation.name if employee.designation else "",
        "photo": employee.profile_photo_url, "status": employee.status,
        "assignments": [{"id": r.id, "asset_id": r.asset_id, "asset_name": r.asset.name, "asset_tag": r.asset.asset_tag, "employee_id": employee.id,
            "employee_name": f"{employee.first_name} {employee.last_name}", "assigned_date": r.assigned_date, "expected_return_date": r.expected_return_date,
            "returned_date": r.returned_date, "acknowledged": r.acknowledgement_signed, "condition_at_assignment": r.condition_at_assignment,
            "condition_at_return": r.condition_at_return, "accessories": r.accessories, "inspection_status": r.inspection_status,
            "recovery_status": r.recovery_status, "return_details": r.return_details} for r in rows]}


@router.get("/export")
def export_register(register: str = Query("inventory", pattern="^(inventory|custody|history)$"),
                    format: str = Query("csv", pattern="^(csv|xlsx)$"), search: str = "", status: str = "",
                    from_date: str = "", to_date: str = "", department: str = "",
                    category_id: int | None = None, db=Depends(get_db), user=Depends(viewer)):
    from io import BytesIO, StringIO
    import csv
    if register == "inventory":
        query = lifecycle.assets(db, user)
        if search: query = query.filter(or_(Asset.name.icontains(search, autoescape=True), Asset.asset_tag.icontains(search, autoescape=True), Asset.serial_number.icontains(search, autoescape=True)))
        if category_id: query = query.filter(Asset.category_id == category_id)
        if status and status not in {"Returned", "Lost / Damaged", "Retired / Disposed"}: query = query.filter(Asset.status == status)
        elif status == "Returned": query = query.filter(Asset.assignments.any(AssetAssignment.returned_date.is_not(None)))
        elif status == "Lost / Damaged": query = query.filter(Asset.status.in_(["Lost", "Damaged"]))
        elif status == "Retired / Disposed": query = query.filter(Asset.status.in_(["Retired", "Disposed"]))
        headings = ["Asset tag", "Asset name", "Category", "Brand", "Model", "Serial / registration", "Location", "Condition", "Status", "Purchase date", "Purchase cost", "Warranty expiry"]
        def values():
            for a in query.order_by(Asset.id).yield_per(500):
                yield [a.asset_tag,a.name,a.category.name if a.category else "",a.brand,a.model,a.serial_number,a.location,a.condition,a.status,a.purchase_date,a.purchase_cost,a.warranty_expiry]
    else:
        query = db.query(AssetAssignment).join(Asset).join(Employee).filter(Asset.organization_id == tenant(user), AssetAssignment.is_active.is_(register == "custody"))
        if search: query = query.filter(or_(Asset.name.icontains(search, autoescape=True), Asset.asset_tag.icontains(search, autoescape=True), (Employee.first_name+" "+Employee.last_name).icontains(search, autoescape=True)))
        if department:
            from app.models.company import Department
            query=query.filter(Employee.department.has(Department.name == department))
        if status == "Acknowledged":query=query.filter(AssetAssignment.acknowledgement_signed.is_(True))
        elif status == "Acknowledgment pending":query=query.filter(AssetAssignment.acknowledgement_signed.is_(False))
        elif status == "Overdue":query=query.filter(AssetAssignment.expected_return_date < business_day(db,user))
        elif status == "Outstanding Recovery":query=query.filter(AssetAssignment.recovery_status.in_(["Pending","Approved"]))
        elif status in {"Pending","Awaiting Approval","Approved","Rejected"}:query=query.filter(AssetAssignment.inspection_status == status)
        field=AssetAssignment.assigned_date if register == "custody" else AssetAssignment.returned_date
        for value,lower in [(from_date,True),(to_date,False)]:
            if value:
                try:parsed=date.fromisoformat(value)
                except ValueError:raise HTTPException(422,"Choose a valid export date range")
                query=query.filter(field >= parsed if lower else field <= parsed)
        headings = ["Reference", "Asset", "Asset tag", "Employee", "Employee code", "Assigned date", "Expected return", "Returned date", "Handover condition", "Return condition", "Acknowledged", "Inspection", "Recovery amount", "Recovery status", "Missing accessories", "Damage remarks"]
        def values():
            for a in query.order_by(AssetAssignment.id).yield_per(500):
                yield [a.id,a.asset.name,a.asset.asset_tag,f"{a.employee.first_name} {a.employee.last_name}",a.employee.employee_id,a.assigned_date,a.expected_return_date,a.returned_date,a.condition_at_assignment,a.condition_at_return,a.acknowledgement_signed,a.inspection_status,a.recovery_amount,a.recovery_status,", ".join((a.return_details or {}).get("missing_accessories",[])),(a.return_details or {}).get("damage_description","")]
    def safe(value):
        if value is None:return ""
        return "'"+value if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@")) else value
    if format == "xlsx":
        from openpyxl import Workbook
        book=Workbook(write_only=True);sheet=book.create_sheet("Company assets");sheet.append(headings)
        for row in values():sheet.append([safe(v) for v in row])
        output=BytesIO();book.save(output);content=output.getvalue();mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        output=StringIO();writer=csv.writer(output);writer.writerow(headings)
        for row in values():writer.writerow([safe(v) for v in row])
        content=("\ufeff"+output.getvalue()).encode("utf-8");mime="text/csv; charset=utf-8"
    return Response(content, media_type=mime, headers={"Content-Disposition":f'attachment; filename="assets-{register}.{format}"',"Cache-Control":"private, no-store"})


@router.get("/{asset_id}")
def asset_360(asset_id: int, db=Depends(get_db), user=Depends(viewer)):
    item = lifecycle.asset(db, user, asset_id)
    from app.schemas.asset import AssetSchema
    rows = db.query(AssetAssignment).filter_by(asset_id=item.id).order_by(AssetAssignment.id.desc()).all()
    documents = db.query(ServiceDocument).filter_by(organization_id=tenant(user), module_key="hrms", entity_type="asset", entity_id=item.id).order_by(ServiceDocument.id.desc()).all()
    approval_ids = {identity for row in rows for identity in [row.inspection_approval_id, row.recovery_approval_id, (row.return_details or {}).get("exception_approval_id")] if identity}
    approvals = db.query(ApprovalRequest).filter(ApprovalRequest.organization_id == tenant(user), ApprovalRequest.id.in_(approval_ids)).all() if approval_ids else []
    timeline = db.query(AuditLog).filter_by(organization_id=tenant(user), entity_type="asset", entity_id=item.id).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(100).all()
    return {**AssetSchema.model_validate(item).model_dump(mode="json"), "assignments": [{"id": r.id, "employee_id": r.employee_id,
        "employee_name": f"{r.employee.first_name} {r.employee.last_name}", "is_active": r.is_active,
        "assigned_date": r.assigned_date, "expected_return_date": r.expected_return_date, "condition_at_assignment": r.condition_at_assignment,
        "returned_date": r.returned_date, "condition_at_return": r.condition_at_return,
        "accessories": r.accessories, "acknowledged": r.acknowledgement_signed, "acknowledged_at": r.acknowledged_at,
        "return_details": r.return_details, "inspection_status": r.inspection_status, "inspection_approval_id": r.inspection_approval_id,
        "recovery_status": r.recovery_status, "recovery_amount": str(r.recovery_amount), "recovery_approval_id": r.recovery_approval_id} for r in rows],
        "documents": [{"id": d.id, "name": d.name, "version": d.version, "mime_type": d.mime_type} for d in documents],
        "approvals": [approval_output(db, user, a) for a in approvals],
        "timeline": [{"id": t.id, "action": t.action, "at": t.created_at, "actor_id": t.user_id, "changes": json.loads(t.new_values) if t.new_values else None} for t in timeline]}
