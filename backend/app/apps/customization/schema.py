from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.apps.customization.models import (
    CustomizationAuditLog,
    CustomizationButton,
    CustomizationField,
    CustomizationFieldOption,
    CustomizationFormulaField,
    CustomizationGlobalPicklist,
    CustomizationGlobalPicklistValue,
    CustomizationKanbanView,
    CustomizationLayout,
    CustomizationLayoutField,
    CustomizationLayoutSection,
    CustomizationModule,
    CustomizationRecord,
    CustomizationRecordValue,
    CustomizationRelatedList,
    CustomizationRollupField,
    CustomizationValidationRule,
    CustomizationView,
)


CUSTOMIZATION_TABLE_MODELS = [
    CustomizationModule,
    CustomizationField,
    CustomizationFieldOption,
    CustomizationLayout,
    CustomizationLayoutSection,
    CustomizationLayoutField,
    CustomizationView,
    CustomizationKanbanView,
    CustomizationValidationRule,
    CustomizationRelatedList,
    CustomizationButton,
    CustomizationGlobalPicklist,
    CustomizationGlobalPicklistValue,
    CustomizationFormulaField,
    CustomizationRollupField,
    CustomizationRecord,
    CustomizationRecordValue,
    CustomizationAuditLog,
]


def ensure_customization_schema(db: Session) -> None:
    inspector = inspect(db.bind)
    existing_tables = set(inspector.get_table_names())
    missing = [model.__table__ for model in CUSTOMIZATION_TABLE_MODELS if model.__tablename__ not in existing_tables]
    if missing:
        CustomizationModule.metadata.create_all(bind=db.bind, tables=missing)

