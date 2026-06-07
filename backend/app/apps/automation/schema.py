from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.apps.automation.models import (
    AutomationAction,
    AutomationApprovalRequest,
    AutomationApprovalRule,
    AutomationApprovalStep,
    AutomationAssignmentRule,
    AutomationBlueprint,
    AutomationBlueprintStage,
    AutomationBlueprintTransition,
    AutomationCadence,
    AutomationCadenceStep,
    AutomationCondition,
    AutomationExecutionLog,
    AutomationScheduledJob,
    AutomationTrigger,
    AutomationWebhookEndpoint,
    AutomationWorkflow,
)


AUTOMATION_TABLE_MODELS = [
    AutomationWorkflow,
    AutomationTrigger,
    AutomationCondition,
    AutomationAction,
    AutomationExecutionLog,
    AutomationBlueprint,
    AutomationBlueprintStage,
    AutomationBlueprintTransition,
    AutomationApprovalRule,
    AutomationApprovalStep,
    AutomationApprovalRequest,
    AutomationAssignmentRule,
    AutomationCadence,
    AutomationCadenceStep,
    AutomationWebhookEndpoint,
    AutomationScheduledJob,
]


def ensure_automation_schema(db: Session) -> None:
    inspector = inspect(db.bind)
    existing_tables = set(inspector.get_table_names())
    missing = [model.__table__ for model in AUTOMATION_TABLE_MODELS if model.__tablename__ not in existing_tables]
    if missing:
        AutomationWorkflow.metadata.create_all(bind=db.bind, tables=missing)

