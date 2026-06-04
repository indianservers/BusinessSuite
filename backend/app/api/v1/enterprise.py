from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.deps import RequirePermission, get_db
from app.core.hr_audit import (
    anonymize_employee,
    has_active_legal_hold,
    privacy_export_package,
    statutory_retention_blockers,
)
from app.models.employee import Employee
from app.models.platform import (
    DomainPackRegistry,
    ManufacturingContractLaborBatch,
    ManufacturingMedicalFitnessRecord,
    ManufacturingPPEIssuance,
    ManufacturingSafetyIncident,
    ConsentRecord, DataPrivacyRequest, DataRetentionPolicy, IntegrationCredential,
    IntegrationEvent, LegalHold, MetricDefinition, WebhookSubscription,
)
from app.models.user import User
from app.schemas.platform import (
    ConsentRecordCreate, ConsentRecordSchema, DataPrivacyRequestCreate,
    DataPrivacyRequestReview, DataPrivacyRequestSchema, DataRetentionPolicyCreate,
    DomainPackEnable, DomainPackRegistrySchema,
    DataRetentionPolicySchema, IntegrationCredentialCreate, IntegrationCredentialSchema,
    IntegrationEventCreate, IntegrationEventSchema, LegalHoldCreate, LegalHoldSchema,
    ManufacturingContractLaborBatchCreate, ManufacturingContractLaborBatchSchema,
    ManufacturingMedicalFitnessRecordCreate, ManufacturingMedicalFitnessRecordSchema,
    ManufacturingPPEIssuanceCreate, ManufacturingPPEIssuanceSchema,
    ManufacturingSafetyIncidentCreate, ManufacturingSafetyIncidentSchema,
    MetricDefinitionCreate, MetricDefinitionSchema, WebhookSubscriptionCreate,
    WebhookSubscriptionSchema,
)

router = APIRouter(prefix="/enterprise", tags=["Enterprise Platform"])


DOMAIN_PACK_CATALOG = {
    "manufacturing": {
        "pack_name": "Manufacturing",
        "modules": ["safety_incidents", "ppe_issuances", "medical_fitness", "contract_labor"],
        "description": "Factory workforce compliance foundation for safety, PPE, fitness, and contract labor.",
    }
}


def _ensure_pack_enabled(db: Session, pack_key: str, company_id: int | None = None) -> DomainPackRegistry:
    item = db.query(DomainPackRegistry).filter(
        DomainPackRegistry.pack_key == pack_key,
        DomainPackRegistry.company_id == company_id,
        DomainPackRegistry.status == "Enabled",
    ).first()
    if not item:
        raise HTTPException(status_code=400, detail=f"{pack_key} domain pack is not enabled")
    return item


@router.post("/integration-credentials", response_model=IntegrationCredentialSchema, status_code=201)
def create_integration_credential(data: IntegrationCredentialCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_manage"))):
    item = IntegrationCredential(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/integration-credentials", response_model=List[IntegrationCredentialSchema])
def list_integration_credentials(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_view"))):
    return db.query(IntegrationCredential).order_by(IntegrationCredential.id.desc()).all()


@router.post("/webhooks", response_model=WebhookSubscriptionSchema, status_code=201)
def create_webhook_subscription(data: WebhookSubscriptionCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_manage"))):
    item = WebhookSubscription(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/webhooks", response_model=List[WebhookSubscriptionSchema])
def list_webhook_subscriptions(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_view"))):
    return db.query(WebhookSubscription).order_by(WebhookSubscription.id.desc()).all()


@router.post("/integration-events", response_model=IntegrationEventSchema, status_code=201)
def queue_integration_event(data: IntegrationEventCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_manage"))):
    item = IntegrationEvent(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/integration-events", response_model=List[IntegrationEventSchema])
def list_integration_events(
    status: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    query = db.query(IntegrationEvent)
    if event_type:
        query = query.filter(IntegrationEvent.event_type == event_type)
    if status:
        query = query.filter(IntegrationEvent.status == status)
    return query.order_by(IntegrationEvent.id.desc()).limit(300).all()


@router.post("/consents", response_model=ConsentRecordSchema, status_code=201)
def create_consent(data: ConsentRecordCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_manage"))):
    item = ConsentRecord(**data.model_dump(), captured_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/consents/{consent_id}/revoke", response_model=ConsentRecordSchema)
def revoke_consent(consent_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_manage"))):
    item = db.query(ConsentRecord).filter(ConsentRecord.id == consent_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Consent not found")
    item.status = "Revoked"
    item.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.get("/consents", response_model=List[ConsentRecordSchema])
def list_consents(employee_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_view"))):
    query = db.query(ConsentRecord)
    if employee_id:
        query = query.filter(ConsentRecord.employee_id == employee_id)
    return query.order_by(ConsentRecord.id.desc()).limit(300).all()


@router.post("/privacy-requests", response_model=DataPrivacyRequestSchema, status_code=201)
def create_privacy_request(data: DataPrivacyRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_manage"))):
    item = DataPrivacyRequest(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/privacy-requests/{request_id}", response_model=DataPrivacyRequestSchema)
def review_privacy_request(request_id: int, data: DataPrivacyRequestReview, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_manage"))):
    item = db.query(DataPrivacyRequest).filter(DataPrivacyRequest.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Privacy request not found")
    item.status = data.status
    item.resolution_notes = data.resolution_notes
    if data.status in {"Closed", "Rejected", "Completed"}:
        item.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.post("/privacy-requests/{request_id}/process")
def process_privacy_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    item = db.query(DataPrivacyRequest).filter(DataPrivacyRequest.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Privacy request not found")
    if not item.employee_id:
        raise HTTPException(status_code=400, detail="Privacy request requires employee_id")
    employee = db.query(Employee).filter(Employee.id == item.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    request_type = item.request_type.lower()
    result: dict = {"request_id": item.id, "employee_id": employee.id, "request_type": item.request_type}
    if request_type in {"export", "access", "data_export"}:
        result["package"] = privacy_export_package(db, employee)
        item.status = "Completed"
    elif request_type in {"delete", "anonymize", "erasure"}:
        blockers = []
        if has_active_legal_hold(db, employee.id):
            blockers.append("active_legal_hold")
        blockers.extend(statutory_retention_blockers(db, employee))
        if blockers:
            result["blocked"] = True
            result["blockers"] = blockers
            item.status = "Blocked"
            item.resolution_notes = "Deletion blocked by legal hold or statutory retention."
        else:
            result.update(anonymize_employee(db, employee, current_user.id, reason=f"Privacy request #{item.id}"))
            item.status = "Completed"
            item.resolution_notes = "Eligible employee fields anonymized."
    else:
        raise HTTPException(status_code=400, detail="Unsupported privacy request type")

    item.processing_result_json = result
    item.processed_at = datetime.now(timezone.utc)
    if item.status in {"Completed", "Blocked"}:
        item.closed_at = datetime.now(timezone.utc) if item.status == "Completed" else None
    db.commit()
    db.refresh(item)
    return item


@router.get("/privacy-requests/{request_id}/export")
def get_privacy_export(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    item = db.query(DataPrivacyRequest).filter(DataPrivacyRequest.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Privacy request not found")
    if not item.employee_id:
        raise HTTPException(status_code=400, detail="Privacy request requires employee_id")
    employee = db.query(Employee).filter(Employee.id == item.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return privacy_export_package(db, employee)


@router.get("/privacy-requests", response_model=List[DataPrivacyRequestSchema])
def list_privacy_requests(status: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_view"))):
    query = db.query(DataPrivacyRequest)
    if status:
        query = query.filter(DataPrivacyRequest.status == status)
    return query.order_by(DataPrivacyRequest.id.desc()).limit(300).all()


@router.post("/retention-policies", response_model=DataRetentionPolicySchema, status_code=201)
def create_retention_policy(data: DataRetentionPolicyCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_manage"))):
    item = DataRetentionPolicy(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/retention-policies", response_model=List[DataRetentionPolicySchema])
def list_retention_policies(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_view"))):
    return db.query(DataRetentionPolicy).order_by(DataRetentionPolicy.module, DataRetentionPolicy.record_type).all()


@router.post("/retention-policies/run")
def run_retention_policies(
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    now = datetime.now(timezone.utc)
    summary = {"dry_run": dry_run, "evaluated": 0, "eligible": 0, "blocked": 0, "processed": 0, "records": []}
    policies = db.query(DataRetentionPolicy).filter(DataRetentionPolicy.is_active.is_(True)).all()
    for policy in policies:
        if policy.module not in {"employee", "hrms"} or policy.record_type not in {"employee", "employee_profile"}:
            continue
        cutoff = now - timedelta(days=policy.retention_days)
        employees = db.query(Employee).filter(Employee.created_at <= cutoff).limit(500).all()
        for employee in employees:
            summary["evaluated"] += 1
            blockers = []
            if has_active_legal_hold(db, employee.id):
                blockers.append("active_legal_hold")
            if blockers:
                summary["blocked"] += 1
                summary["records"].append({"employee_id": employee.id, "eligible": False, "blockers": blockers})
                continue
            summary["eligible"] += 1
            record = {"employee_id": employee.id, "eligible": True, "action": policy.action}
            if not dry_run and policy.action.lower() in {"anonymize", "delete"}:
                record.update(anonymize_employee(db, employee, current_user.id, reason=f"Retention policy #{policy.id}"))
                summary["processed"] += 1
            summary["records"].append(record)
        policy.last_run_at = now
        policy.last_run_summary_json = summary
    db.commit()
    return summary


@router.post("/legal-holds", response_model=LegalHoldSchema, status_code=201)
def create_legal_hold(data: LegalHoldCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_manage"))):
    item = LegalHold(**data.model_dump(), placed_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/legal-holds/{hold_id}/release", response_model=LegalHoldSchema)
def release_legal_hold(hold_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_manage"))):
    item = db.query(LegalHold).filter(LegalHold.id == hold_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Legal hold not found")
    item.status = "Released"
    item.released_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.get("/legal-holds", response_model=List[LegalHoldSchema])
def list_legal_holds(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_view"))):
    return db.query(LegalHold).order_by(LegalHold.id.desc()).all()


@router.post("/metrics", response_model=MetricDefinitionSchema, status_code=201)
def create_metric_definition(data: MetricDefinitionCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("reports_manage"))):
    item = MetricDefinition(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/metrics", response_model=List[MetricDefinitionSchema])
def list_metric_definitions(module: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("reports_view"))):
    query = db.query(MetricDefinition).filter(MetricDefinition.is_active == True)
    if module:
        query = query.filter(MetricDefinition.module == module)
    return query.order_by(MetricDefinition.module, MetricDefinition.name).all()


@router.get("/domain-packs/catalog")
def domain_pack_catalog(current_user: User = Depends(RequirePermission("settings_view"))):
    return DOMAIN_PACK_CATALOG


@router.post("/domain-packs/enable", response_model=DomainPackRegistrySchema, status_code=201)
def enable_domain_pack(
    data: DomainPackEnable,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    if data.pack_key not in DOMAIN_PACK_CATALOG:
        raise HTTPException(status_code=400, detail="Unsupported domain pack")
    existing = db.query(DomainPackRegistry).filter(
        DomainPackRegistry.company_id == data.company_id,
        DomainPackRegistry.pack_key == data.pack_key,
    ).first()
    if existing:
        existing.status = "Enabled"
        existing.config_json = data.config_json or existing.config_json
        existing.disabled_at = None
        existing.enabled_by = current_user.id
        db.commit()
        db.refresh(existing)
        return existing
    catalog = DOMAIN_PACK_CATALOG[data.pack_key]
    item = DomainPackRegistry(
        company_id=data.company_id,
        pack_key=data.pack_key,
        pack_name=data.pack_name or catalog["pack_name"],
        config_json=data.config_json or {},
        enabled_by=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/domain-packs", response_model=List[DomainPackRegistrySchema])
def list_domain_packs(
    company_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    query = db.query(DomainPackRegistry)
    if company_id:
        query = query.filter(DomainPackRegistry.company_id == company_id)
    return query.order_by(DomainPackRegistry.pack_key).all()


@router.put("/domain-packs/{pack_id}/disable", response_model=DomainPackRegistrySchema)
def disable_domain_pack(
    pack_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    item = db.query(DomainPackRegistry).filter(DomainPackRegistry.id == pack_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Domain pack not found")
    item.status = "Disabled"
    item.disabled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.post("/domain-packs/manufacturing/safety-incidents", response_model=ManufacturingSafetyIncidentSchema, status_code=201)
def create_manufacturing_safety_incident(
    data: ManufacturingSafetyIncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    _ensure_pack_enabled(db, "manufacturing", data.company_id)
    item = ManufacturingSafetyIncident(**data.model_dump(), reported_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/domain-packs/manufacturing/safety-incidents", response_model=List[ManufacturingSafetyIncidentSchema])
def list_manufacturing_safety_incidents(
    company_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    _ensure_pack_enabled(db, "manufacturing", company_id)
    query = db.query(ManufacturingSafetyIncident)
    if company_id:
        query = query.filter(ManufacturingSafetyIncident.company_id == company_id)
    if status:
        query = query.filter(ManufacturingSafetyIncident.status == status)
    return query.order_by(ManufacturingSafetyIncident.incident_date.desc(), ManufacturingSafetyIncident.id.desc()).limit(300).all()


@router.post("/domain-packs/manufacturing/ppe-issuances", response_model=ManufacturingPPEIssuanceSchema, status_code=201)
def create_manufacturing_ppe_issuance(
    data: ManufacturingPPEIssuanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    _ensure_pack_enabled(db, "manufacturing", data.company_id)
    item = ManufacturingPPEIssuance(**data.model_dump(), issued_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/domain-packs/manufacturing/ppe-issuances", response_model=List[ManufacturingPPEIssuanceSchema])
def list_manufacturing_ppe_issuances(
    company_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    _ensure_pack_enabled(db, "manufacturing", company_id)
    query = db.query(ManufacturingPPEIssuance)
    if company_id:
        query = query.filter(ManufacturingPPEIssuance.company_id == company_id)
    if employee_id:
        query = query.filter(ManufacturingPPEIssuance.employee_id == employee_id)
    return query.order_by(ManufacturingPPEIssuance.issued_on.desc(), ManufacturingPPEIssuance.id.desc()).limit(300).all()


@router.post("/domain-packs/manufacturing/medical-fitness", response_model=ManufacturingMedicalFitnessRecordSchema, status_code=201)
def create_manufacturing_medical_fitness(
    data: ManufacturingMedicalFitnessRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    _ensure_pack_enabled(db, "manufacturing", data.company_id)
    item = ManufacturingMedicalFitnessRecord(**data.model_dump(), recorded_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/domain-packs/manufacturing/medical-fitness", response_model=List[ManufacturingMedicalFitnessRecordSchema])
def list_manufacturing_medical_fitness(
    company_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    _ensure_pack_enabled(db, "manufacturing", company_id)
    query = db.query(ManufacturingMedicalFitnessRecord)
    if company_id:
        query = query.filter(ManufacturingMedicalFitnessRecord.company_id == company_id)
    if employee_id:
        query = query.filter(ManufacturingMedicalFitnessRecord.employee_id == employee_id)
    return query.order_by(ManufacturingMedicalFitnessRecord.exam_date.desc(), ManufacturingMedicalFitnessRecord.id.desc()).limit(300).all()


@router.post("/domain-packs/manufacturing/contract-labor-batches", response_model=ManufacturingContractLaborBatchSchema, status_code=201)
def create_manufacturing_contract_labor_batch(
    data: ManufacturingContractLaborBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    _ensure_pack_enabled(db, "manufacturing", data.company_id)
    item = ManufacturingContractLaborBatch(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/domain-packs/manufacturing/contract-labor-batches", response_model=List[ManufacturingContractLaborBatchSchema])
def list_manufacturing_contract_labor_batches(
    company_id: Optional[int] = Query(None),
    compliance_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    _ensure_pack_enabled(db, "manufacturing", company_id)
    query = db.query(ManufacturingContractLaborBatch)
    if company_id:
        query = query.filter(ManufacturingContractLaborBatch.company_id == company_id)
    if compliance_status:
        query = query.filter(ManufacturingContractLaborBatch.compliance_status == compliance_status)
    return query.order_by(ManufacturingContractLaborBatch.start_date.desc(), ManufacturingContractLaborBatch.id.desc()).limit(300).all()
