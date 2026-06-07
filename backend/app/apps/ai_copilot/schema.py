from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.apps.ai_copilot.models import (
    AIAgentAction,
    AIActionLog,
    AIProviderSetting,
    AIPromptRun,
    AIPromptTemplate,
    AIRecommendation,
    AIRecordSummary,
    AIScore,
    AIUserFeedback,
)


AI_COPILOT_TABLE_MODELS = [
    AIProviderSetting,
    AIPromptTemplate,
    AIPromptRun,
    AIRecordSummary,
    AIScore,
    AIRecommendation,
    AIAgentAction,
    AIActionLog,
    AIUserFeedback,
]


def ensure_ai_copilot_schema(db: Session) -> None:
    inspector = inspect(db.bind)
    existing_tables = set(inspector.get_table_names())
    missing = [model.__table__ for model in AI_COPILOT_TABLE_MODELS if model.__tablename__ not in existing_tables]
    if missing:
        AIProviderSetting.metadata.create_all(bind=db.bind, tables=missing)

