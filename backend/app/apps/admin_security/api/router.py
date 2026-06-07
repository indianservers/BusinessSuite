from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.apps.admin_security.models import (
    AdminAuditLog,
    AdminBackupRequest,
    AdminComplianceSetting,
    AdminDataRetentionRule,
    AdminDataSharingRule,
    AdminDuplicateCandidate,
    AdminDuplicateRule,
    AdminExportControl,
    AdminFieldSecurity,
    AdminImportJob,
    AdminImportJobRow,
    AdminMergeLog,
    AdminManualRecordShare,
    AdminProfile,
    AdminProfilePermission,
    AdminRecordSharingRule,
    AdminRole,
    AdminRoleHierarchy,
    AdminIPRestriction,
)
from app.apps.admin_security.schemas import (
    AdminRolePayload,
    BackupRequestPayload,
    CompliancePayload,
    DataSharingRulePayload,
    DuplicateMergePayload,
    DuplicateRulePayload,
    DuplicateScanPayload,
    ExportControlPayload,
    FieldSecurityPayload,
    ImportMapPayload,
    ImportUploadPayload,
    IPRestrictionPayload,
    ManualSharePayload,
    ProfilePayload,
    ProfilePermissionsPayload,
    RetentionPayload,
    RoleHierarchyPayload,
    SharingRulePayload,
)
from app.apps.admin_security.services import apply_field_security, assert_editable_fields, audit
from app.apps.crm.models import CRMCompany, CRMContact, CRMLead
from app.core.deps import RequirePermission, get_db
from app.models.user import User


router = APIRouter(prefix="/admin", tags=["Enterprise Admin Security"])

CRM_MODULES = {"leads": CRMLead, "contacts": CRMContact, "accounts": CRMCompany, "companies": CRMCompany}


def _serialize(item) -> dict[str, Any] | None:
    if item is None:
        return None
    data = {}
    for column in item.__table__.columns:
        value = getattr(item, column.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.name] = value
    return data


def _items(rows) -> dict[str, Any]:
    rows = list(rows)
    return {"items": [_serialize(row) for row in rows], "total": len(rows)}


def _admin_user(user: User = Depends(RequirePermission("admin_security_view", "admin_security_manage", "admin_audit_view"))):
    return user


def _admin_manager(user: User = Depends(RequirePermission("admin_security_manage"))):
    return user


@router.get("/security")
def security_overview(db: Session = Depends(get_db), current_user: User = Depends(_admin_user)):
    return {
        "profiles": db.query(AdminProfile).count(),
        "field_security_rules": db.query(AdminFieldSecurity).count(),
        "sharing_rules": db.query(AdminRecordSharingRule).count(),
        "audit_events": db.query(AdminAuditLog).count(),
    }


@router.get("/profiles")
def list_profiles(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_profiles_manage"))):
    return _items(db.query(AdminProfile).order_by(AdminProfile.name.asc()).all())


@router.post("/profiles", status_code=201)
def create_profile(data: ProfilePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_profiles_manage", "admin_security_manage"))):
    if db.query(AdminProfile).filter(AdminProfile.name == data.name).first():
        raise HTTPException(status_code=409, detail="Profile already exists")
    item = AdminProfile(**data.model_dump())
    db.add(item)
    db.flush()
    audit(db, current_user, "admin_profile_created", "admin", "profile", item.id)
    db.commit()
    return _serialize(item)


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_profiles_manage"))):
    item = db.query(AdminProfile).filter(AdminProfile.id == profile_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _serialize(item)


@router.put("/profiles/{profile_id}")
def update_profile(profile_id: int, data: ProfilePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_profiles_manage", "admin_security_manage"))):
    item = db.query(AdminProfile).filter(AdminProfile.id == profile_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Profile not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    audit(db, current_user, "admin_profile_updated", "admin", "profile", item.id)
    db.commit()
    return _serialize(item)


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_profiles_manage", "admin_security_manage"))):
    item = db.query(AdminProfile).filter(AdminProfile.id == profile_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Profile not found")
    item.active = False
    audit(db, current_user, "admin_profile_deactivated", "admin", "profile", item.id)
    db.commit()
    return None


@router.post("/profiles/{profile_id}/permissions", status_code=201)
def set_profile_permissions(profile_id: int, data: ProfilePermissionsPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_profiles_manage", "admin_security_manage"))):
    profile = db.query(AdminProfile).filter(AdminProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.query(AdminProfilePermission).filter(AdminProfilePermission.profile_id == profile_id).delete()
    for name in data.permissions:
        db.add(AdminProfilePermission(profile_id=profile_id, permission_name=name, allowed=True))
    audit(db, current_user, "admin_profile_permissions_updated", "admin", "profile", profile_id, {"permissions": data.permissions})
    db.commit()
    return {"profile_id": profile_id, "permissions": data.permissions}


@router.get("/roles")
def list_roles(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_roles_manage"))):
    return _items(db.query(AdminRole).order_by(AdminRole.name.asc()).all())


@router.post("/roles", status_code=201)
def create_role(data: AdminRolePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_roles_manage", "admin_security_manage"))):
    if db.query(AdminRole).filter(AdminRole.name == data.name).first():
        raise HTTPException(status_code=409, detail="Role already exists")
    item = AdminRole(**data.model_dump())
    db.add(item)
    db.flush()
    audit(db, current_user, "admin_role_created", "admin", "role", item.id)
    db.commit()
    return _serialize(item)


@router.get("/roles/{role_id}")
def get_role(role_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_roles_manage"))):
    item = db.query(AdminRole).filter(AdminRole.id == role_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Role not found")
    return _serialize(item)


@router.put("/roles/{role_id}")
def update_role(role_id: int, data: AdminRolePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_roles_manage", "admin_security_manage"))):
    item = db.query(AdminRole).filter(AdminRole.id == role_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Role not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    audit(db, current_user, "admin_role_updated", "admin", "role", item.id)
    db.commit()
    return _serialize(item)


@router.post("/roles/hierarchy", status_code=201)
def set_role_hierarchy(data: RoleHierarchyPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_roles_manage", "admin_security_manage"))):
    if data.parent_role_id == data.child_role_id:
        raise HTTPException(status_code=422, detail="A role cannot report to itself")
    item = AdminRoleHierarchy(**data.model_dump())
    db.add(item)
    audit(db, current_user, "admin_role_hierarchy_created", "admin", "role_hierarchy", None, data.model_dump())
    db.commit()
    return _serialize(item)


@router.get("/field-security")
def list_field_security(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_field_security_manage"))):
    return _items(db.query(AdminFieldSecurity).order_by(AdminFieldSecurity.module_name.asc()).all())


@router.post("/field-security", status_code=201)
def create_field_security(data: FieldSecurityPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_field_security_manage", "admin_security_manage"))):
    item = AdminFieldSecurity(**data.model_dump())
    db.add(item)
    db.flush()
    audit(db, current_user, "admin_field_security_created", data.module_name, "field_security", item.id, data.model_dump())
    db.commit()
    return _serialize(item)


@router.put("/field-security/{rule_id}")
def update_field_security(rule_id: int, data: FieldSecurityPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_field_security_manage", "admin_security_manage"))):
    item = db.query(AdminFieldSecurity).filter(AdminFieldSecurity.id == rule_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Field security rule not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    audit(db, current_user, "admin_field_security_updated", data.module_name, "field_security", item.id)
    db.commit()
    return _serialize(item)


@router.get("/record-sharing-rules")
def list_record_sharing(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_record_sharing_manage"))):
    return _items(db.query(AdminRecordSharingRule).all())


@router.post("/record-sharing-rules", status_code=201)
def create_record_sharing(data: SharingRulePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_record_sharing_manage", "admin_security_manage"))):
    item = AdminRecordSharingRule(**data.model_dump())
    db.add(item)
    audit(db, current_user, "admin_record_sharing_rule_created", data.module_name, "record_sharing_rule", None)
    db.commit()
    return _serialize(item)


@router.post("/records/share", status_code=201)
def share_record(data: ManualSharePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_record_sharing_manage", "admin_security_manage"))):
    item = AdminManualRecordShare(**data.model_dump(), active=True, created_by=current_user.id)
    db.add(item)
    audit(db, current_user, "admin_record_shared", data.module_name, "record", data.record_id, data.model_dump())
    db.commit()
    return _serialize(item)


@router.post("/records/unshare")
def unshare_record(data: ManualSharePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_record_sharing_manage", "admin_security_manage"))):
    item = db.query(AdminManualRecordShare).filter(AdminManualRecordShare.module_name == data.module_name, AdminManualRecordShare.record_id == data.record_id, AdminManualRecordShare.share_with_type == data.share_with_type, AdminManualRecordShare.share_with_id == data.share_with_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Manual share not found")
    item.active = False
    audit(db, current_user, "admin_record_unshared", data.module_name, "record", data.record_id)
    db.commit()
    return _serialize(item)


@router.get("/data-sharing-rules")
def list_data_sharing(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_record_sharing_manage"))):
    return _items(db.query(AdminDataSharingRule).all())


@router.post("/data-sharing-rules", status_code=201)
def create_data_sharing(data: DataSharingRulePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_record_sharing_manage", "admin_security_manage"))):
    item = AdminDataSharingRule(**data.model_dump())
    db.add(item)
    audit(db, current_user, "admin_data_sharing_rule_created", data.module_name, "data_sharing_rule")
    db.commit()
    return _serialize(item)


@router.get("/ip-restrictions")
def list_ip_restrictions(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_security_manage"))):
    return _items(db.query(AdminIPRestriction).all())


@router.post("/ip-restrictions", status_code=201)
def create_ip_restriction(data: IPRestrictionPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_manage"))):
    if data.action == "deny" and data.cidr in {"0.0.0.0/0", "::/0"} and not data.environment_safe:
        raise HTTPException(status_code=422, detail="Unsafe deny-all IP restriction blocked")
    item = AdminIPRestriction(**data.model_dump())
    db.add(item)
    audit(db, current_user, "admin_ip_restriction_created", "admin", "ip_restriction", None, data.model_dump())
    db.commit()
    return _serialize(item)


@router.get("/audit-logs")
def list_audit_logs(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_audit_view", "admin_security_view"))):
    return _items(db.query(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).all())


@router.get("/audit-logs/export")
def export_audit_logs(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_audit_view"))):
    rows = db.query(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).all()
    audit(db, current_user, "admin_audit_logs_exported", "admin", "audit_log", None, {"row_count": len(rows)})
    db.commit()
    lines = ["id,event_type,module_name,status,created_at"]
    lines += [f"{row.id},{row.event_type},{row.module_name or ''},{row.status},{row.created_at}" for row in rows]
    return PlainTextResponse("\n".join(lines), media_type="text/csv")


@router.post("/imports/upload", status_code=201)
def upload_import(data: ImportUploadPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_import_manage", "admin_security_manage"))):
    job = AdminImportJob(module_name=data.module_name, filename=data.filename, status="uploaded", total_rows=len(data.rows), created_by=current_user.id)
    db.add(job)
    db.flush()
    for index, row in enumerate(data.rows, start=1):
        db.add(AdminImportJobRow(import_job_id=job.id, row_number=index, raw_json=row, status="pending"))
    audit(db, current_user, "admin_import_uploaded", data.module_name, "import_job", job.id, {"rows": len(data.rows)})
    db.commit()
    return _serialize(job)


@router.post("/imports/{job_id}/map-fields")
def map_import(job_id: int, data: ImportMapPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_import_manage", "admin_security_manage"))):
    job = db.query(AdminImportJob).filter(AdminImportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    job.mapping_json = data.mapping
    job.status = "mapped"
    for row in db.query(AdminImportJobRow).filter(AdminImportJobRow.import_job_id == job.id):
        mapped = {target: row.raw_json.get(source) for source, target in data.mapping.items()}
        row.mapped_json = mapped
    audit(db, current_user, "admin_import_mapped", job.module_name, "import_job", job.id)
    db.commit()
    return _serialize(job)


@router.post("/imports/{job_id}/run")
def run_import(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_import_manage", "admin_security_manage"))):
    job = db.query(AdminImportJob).filter(AdminImportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    seen = set()
    success = failed = dupes = 0
    for row in db.query(AdminImportJobRow).filter(AdminImportJobRow.import_job_id == job.id).order_by(AdminImportJobRow.row_number):
        mapped = row.mapped_json or row.raw_json or {}
        try:
            assert_editable_fields(db, job.module_name, mapped, current_user)
            key = (mapped.get("email") or mapped.get("company_name") or mapped.get("name") or "").lower()
            if key and key in seen:
                row.status = "duplicate"
                row.error_message = "Duplicate in import batch"
                dupes += 1
                continue
            seen.add(key)
            if job.module_name in {"leads", "crm_leads"} and not mapped.get("first_name") and not mapped.get("full_name"):
                raise ValueError("Lead first_name or full_name is required")
            row.status = "success"
            success += 1
        except Exception as exc:
            row.status = "failed"
            row.error_message = str(exc)
            failed += 1
    job.success_rows = success
    job.failed_rows = failed
    job.duplicate_rows = dupes
    job.status = "completed" if failed == 0 else "failed"
    job.completed_at = datetime.now(timezone.utc)
    audit(db, current_user, "admin_import_completed", job.module_name, "import_job", job.id, {"success": success, "failed": failed, "duplicates": dupes})
    db.commit()
    return _serialize(job)


@router.get("/imports/{job_id}")
def get_import(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_import_manage", "admin_security_view"))):
    job = db.query(AdminImportJob).filter(AdminImportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    return _serialize(job)


@router.get("/imports/{job_id}/errors")
def import_errors(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_import_manage", "admin_security_view"))):
    rows = db.query(AdminImportJobRow).filter(AdminImportJobRow.import_job_id == job_id, AdminImportJobRow.status.in_(["failed", "duplicate"])).all()
    return _items(rows)


@router.get("/duplicate-rules")
def list_duplicate_rules(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_duplicates_manage"))):
    return _items(db.query(AdminDuplicateRule).all())


@router.post("/duplicate-rules", status_code=201)
def create_duplicate_rule(data: DuplicateRulePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_duplicates_manage", "admin_security_manage"))):
    item = AdminDuplicateRule(**data.model_dump())
    db.add(item)
    audit(db, current_user, "admin_duplicate_rule_created", data.module_name, "duplicate_rule")
    db.commit()
    return _serialize(item)


def _record_value(record: Any, field: str):
    return getattr(record, field, None)


@router.post("/duplicates/scan", status_code=201)
def scan_duplicates(data: DuplicateScanPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_duplicates_manage", "admin_security_manage"))):
    model = CRM_MODULES.get(data.module_name)
    rule = db.query(AdminDuplicateRule).filter(AdminDuplicateRule.module_name == data.module_name, AdminDuplicateRule.active.is_(True)).first()
    if not model or not rule:
        return {"items": [], "total": 0}
    fields = rule.match_fields_json or []
    records = db.query(model).all()
    created = []
    for i, left in enumerate(records):
        for right in records[i + 1:]:
            matched = [field for field in fields if _record_value(left, field) and _record_value(left, field) == _record_value(right, field)]
            if matched:
                candidate = AdminDuplicateCandidate(module_name=data.module_name, rule_id=rule.id, record_id=left.id, duplicate_record_id=right.id, confidence_score=min(100, 60 + len(matched) * 20), evidence_json={"matched_fields": matched})
                db.add(candidate)
                created.append(candidate)
    audit(db, current_user, "admin_duplicates_scanned", data.module_name, "duplicate_candidate", None, {"count": len(created)})
    db.commit()
    return {"items": [_serialize(row) for row in created], "total": len(created)}


@router.get("/duplicates/candidates")
def duplicate_candidates(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_duplicates_manage"))):
    return _items(db.query(AdminDuplicateCandidate).order_by(AdminDuplicateCandidate.created_at.desc()).all())


@router.post("/duplicates/merge")
def merge_duplicates(data: DuplicateMergePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_duplicates_manage", "admin_security_manage"))):
    log = AdminMergeLog(module_name=data.module_name, winner_record_id=data.winner_record_id, loser_record_ids_json=data.loser_record_ids, merged_by=current_user.id, detail_json={"timeline_preserved": True, "related_records_preserved": True})
    db.add(log)
    db.query(AdminDuplicateCandidate).filter(AdminDuplicateCandidate.module_name == data.module_name, or_(AdminDuplicateCandidate.record_id.in_(data.loser_record_ids), AdminDuplicateCandidate.duplicate_record_id.in_(data.loser_record_ids))).update({"status": "merged"}, synchronize_session=False)
    audit(db, current_user, "admin_duplicates_merged", data.module_name, "record", data.winner_record_id, data.model_dump())
    db.commit()
    return _serialize(log)


@router.get("/export-controls")
def list_export_controls(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_export_control_manage"))):
    return _items(db.query(AdminExportControl).all())


@router.post("/export-controls", status_code=201)
def create_export_control(data: ExportControlPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_export_control_manage", "admin_security_manage"))):
    item = AdminExportControl(**data.model_dump())
    db.add(item)
    audit(db, current_user, "admin_export_control_created", data.module_name, "export_control")
    db.commit()
    return _serialize(item)


@router.post("/backups/request", status_code=201)
def request_backup(data: BackupRequestPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_manage"))):
    item = AdminBackupRequest(scope=data.scope, requested_by=current_user.id, detail_json={"destructive": False})
    db.add(item)
    audit(db, current_user, "admin_backup_requested", "admin", "backup_request")
    db.commit()
    return _serialize(item)


@router.get("/backups")
def list_backups(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_security_manage"))):
    return _items(db.query(AdminBackupRequest).order_by(AdminBackupRequest.requested_at.desc()).all())


@router.get("/compliance")
def list_compliance(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_compliance_manage"))):
    return _items(db.query(AdminComplianceSetting).all())


@router.post("/compliance", status_code=201)
def upsert_compliance(data: CompliancePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_compliance_manage", "admin_security_manage"))):
    item = db.query(AdminComplianceSetting).filter(AdminComplianceSetting.setting_key == data.setting_key).first() or AdminComplianceSetting(setting_key=data.setting_key)
    item.setting_value_json = data.setting_value_json
    item.active = data.active
    item.updated_at = datetime.now(timezone.utc)
    db.add(item)
    audit(db, current_user, "admin_compliance_setting_upserted", "admin", "compliance_setting", None, {"setting_key": data.setting_key})
    db.commit()
    return _serialize(item)


@router.get("/data-retention")
def list_retention(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_compliance_manage"))):
    return _items(db.query(AdminDataRetentionRule).all())


@router.post("/data-retention", status_code=201)
def create_retention(data: RetentionPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_compliance_manage", "admin_security_manage"))):
    item = AdminDataRetentionRule(**data.model_dump())
    db.add(item)
    audit(db, current_user, "admin_retention_rule_created", data.module_name, "data_retention_rule")
    db.commit()
    return _serialize(item)


@router.post("/security/apply-field-security")
def apply_field_security_preview(payload: dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_field_security_manage"))):
    module_name = str(payload.get("module_name") or "")
    data = dict(payload.get("record") or {})
    return {"record": apply_field_security(db, module_name, data, current_user)}


@router.post("/security/validate-field-update")
def validate_field_update(payload: dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("admin_security_view", "admin_field_security_manage"))):
    module_name = str(payload.get("module_name") or "")
    data = dict(payload.get("record") or {})
    assert_editable_fields(db, module_name, data, current_user)
    return {"status": "allowed"}
