from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.deps import RequirePermission, get_db
from app.models.platform import (
    CustomFieldDefinition,
    CustomFieldValue,
    CustomFormDefinition,
    CustomFormField,
    CustomFormSubmission,
)
from app.models.user import User
from app.core.reorder import OrderInput, apply_order


from app.schemas.platform import (
    CustomFieldDefinitionCreate,
    CustomFieldDefinitionSchema,
    CustomFieldValueSchema,
    CustomFieldValueUpsert,
    CustomFormDefinitionCreate,
    CustomFormDefinitionSchema,
    CustomFormSubmissionCreate,
    CustomFormSubmissionReview,
    CustomFormSubmissionSchema,
)

router = APIRouter(prefix="/custom-fields", tags=["Custom Fields"])


@router.post("/definitions/reorder")
def reorder_definitions(data: OrderInput, module: str = Query(..., max_length=80), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("settings_manage"))):
    rows = db.query(CustomFieldDefinition).filter_by(module=module, is_active=True).order_by(CustomFieldDefinition.display_order, CustomFieldDefinition.label, CustomFieldDefinition.id).with_for_update().all()
    apply_order(rows, data, "display_order")
    db.commit()
    return {"ids": data.ids}


@router.post("/definitions", response_model=CustomFieldDefinitionSchema, status_code=201)
def create_custom_field_definition(
    data: CustomFieldDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    exists = db.query(CustomFieldDefinition).filter(
        CustomFieldDefinition.module == data.module,
        CustomFieldDefinition.field_key == data.field_key,
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Custom field key already exists for this module")
    item = CustomFieldDefinition(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/definitions", response_model=List[CustomFieldDefinitionSchema])
def list_custom_field_definitions(
    module: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    query = db.query(CustomFieldDefinition).filter(CustomFieldDefinition.is_active == True)
    if module:
        query = query.filter(CustomFieldDefinition.module == module)
    return query.order_by(CustomFieldDefinition.module, CustomFieldDefinition.display_order, CustomFieldDefinition.label).all()


@router.put("/values", response_model=CustomFieldValueSchema)
def upsert_custom_field_value(
    data: CustomFieldValueUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    definition = db.query(CustomFieldDefinition).filter(CustomFieldDefinition.id == data.definition_id, CustomFieldDefinition.is_active == True).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Custom field definition not found")
    if definition.is_required and not (data.value_text or data.value_json):
        raise HTTPException(status_code=400, detail="Value is required for this custom field")
    item = db.query(CustomFieldValue).filter(
        CustomFieldValue.definition_id == data.definition_id,
        CustomFieldValue.entity_type == data.entity_type,
        CustomFieldValue.entity_id == data.entity_id,
    ).first()
    if not item:
        item = CustomFieldValue(
            definition_id=data.definition_id,
            entity_type=data.entity_type,
            entity_id=data.entity_id,
        )
        db.add(item)
    item.value_text = data.value_text
    item.value_json = data.value_json
    item.updated_by = current_user.id
    db.commit()
    db.refresh(item)
    return item


@router.get("/values", response_model=List[CustomFieldValueSchema])
def list_custom_field_values(
    entity_type: str = Query(...),
    entity_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    return db.query(CustomFieldValue).filter(
        CustomFieldValue.entity_type == entity_type,
        CustomFieldValue.entity_id == entity_id,
    ).order_by(CustomFieldValue.id).all()


def _hydrate_form(form: CustomFormDefinition, db: Session) -> CustomFormDefinition:
    form.fields = db.query(CustomFormField).filter(CustomFormField.form_id == form.id).order_by(
        CustomFormField.display_order, CustomFormField.id
    ).all()
    return form


@router.post("/forms", response_model=CustomFormDefinitionSchema, status_code=201)
def create_custom_form(
    data: CustomFormDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    exists = db.query(CustomFormDefinition).filter(CustomFormDefinition.code == data.code).first()
    if exists:
        raise HTTPException(status_code=400, detail="Custom form code already exists")
    form = CustomFormDefinition(**data.model_dump(exclude={"fields"}), created_by=current_user.id)
    db.add(form)
    db.flush()
    for field in data.fields:
        definition = db.query(CustomFieldDefinition).filter(
            CustomFieldDefinition.id == field.field_definition_id,
            CustomFieldDefinition.is_active == True,
        ).first()
        if not definition:
            raise HTTPException(status_code=404, detail=f"Custom field definition {field.field_definition_id} not found")
        if definition.module != data.module:
            raise HTTPException(status_code=400, detail="Form fields must belong to the same module as the form")
        db.add(CustomFormField(form_id=form.id, **field.model_dump()))
    db.commit()
    db.refresh(form)
    return _hydrate_form(form, db)


@router.get("/forms", response_model=List[CustomFormDefinitionSchema])
def list_custom_forms(
    module: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    query = db.query(CustomFormDefinition).filter(CustomFormDefinition.is_active == True)
    if module:
        query = query.filter(CustomFormDefinition.module == module)
    if entity_type:
        query = query.filter(CustomFormDefinition.entity_type == entity_type)
    forms = query.order_by(CustomFormDefinition.module, CustomFormDefinition.name).all()
    return [_hydrate_form(form, db) for form in forms]


@router.get("/forms/{form_id}", response_model=CustomFormDefinitionSchema)
def get_custom_form(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    form = db.query(CustomFormDefinition).filter(CustomFormDefinition.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Custom form not found")
    return _hydrate_form(form, db)


@router.post("/forms/{form_id}/submissions", response_model=CustomFormSubmissionSchema, status_code=201)
def submit_custom_form(
    form_id: int,
    data: CustomFormSubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    form = db.query(CustomFormDefinition).filter(CustomFormDefinition.id == form_id, CustomFormDefinition.is_active == True).first()
    if not form:
        raise HTTPException(status_code=404, detail="Custom form not found")
    if data.form_id != form_id:
        raise HTTPException(status_code=400, detail="form_id must match route form_id")
    if data.entity_type != form.entity_type:
        raise HTTPException(status_code=400, detail="Submission entity_type does not match form entity_type")
    if not form.allow_multiple_submissions:
        existing = db.query(CustomFormSubmission).filter(
            CustomFormSubmission.form_id == form_id,
            CustomFormSubmission.entity_type == data.entity_type,
            CustomFormSubmission.entity_id == data.entity_id,
            CustomFormSubmission.status != "Rejected",
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="A non-rejected submission already exists for this entity")

    fields = db.query(CustomFormField, CustomFieldDefinition).join(
        CustomFieldDefinition,
        CustomFormField.field_definition_id == CustomFieldDefinition.id,
    ).filter(CustomFormField.form_id == form_id).all()
    missing = []
    for form_field, definition in fields:
        required = form_field.is_required_override if form_field.is_required_override is not None else definition.is_required
        if required and definition.field_key not in data.values_json:
            missing.append(definition.field_key)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing)}")

    submission = CustomFormSubmission(**data.model_dump(), submitted_by=current_user.id)
    db.add(submission)
    db.flush()
    definitions_by_key = {definition.field_key: definition for _, definition in fields}
    for field_key, value in data.values_json.items():
        definition = definitions_by_key.get(field_key)
        if not definition:
            continue
        existing_value = db.query(CustomFieldValue).filter(
            CustomFieldValue.definition_id == definition.id,
            CustomFieldValue.entity_type == data.entity_type,
            CustomFieldValue.entity_id == data.entity_id,
        ).first()
        if not existing_value:
            existing_value = CustomFieldValue(
                definition_id=definition.id,
                entity_type=data.entity_type,
                entity_id=data.entity_id,
            )
            db.add(existing_value)
        existing_value.value_text = value if isinstance(value, str) else None
        existing_value.value_json = value if not isinstance(value, str) else None
        existing_value.updated_by = current_user.id
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/forms/{form_id}/submissions", response_model=List[CustomFormSubmissionSchema])
def list_custom_form_submissions(
    form_id: int,
    entity_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_view")),
):
    query = db.query(CustomFormSubmission).filter(CustomFormSubmission.form_id == form_id)
    if entity_id:
        query = query.filter(CustomFormSubmission.entity_id == entity_id)
    if status:
        query = query.filter(CustomFormSubmission.status == status)
    return query.order_by(CustomFormSubmission.id.desc()).all()


@router.put("/forms/submissions/{submission_id}/review", response_model=CustomFormSubmissionSchema)
def review_custom_form_submission(
    submission_id: int,
    data: CustomFormSubmissionReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("settings_manage")),
):
    if data.status not in {"Submitted", "Approved", "Rejected"}:
        raise HTTPException(status_code=400, detail="status must be Submitted, Approved, or Rejected")
    submission = db.query(CustomFormSubmission).filter(CustomFormSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Custom form submission not found")
    submission.status = data.status
    submission.review_remarks = data.review_remarks
    submission.reviewed_by = current_user.id
    submission.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(submission)
    return submission
