from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.apps.analytics.models import (
    AnalyticsAnomalyRule,
    AnalyticsDashboard,
    AnalyticsDashboardWidget,
    AnalyticsExport,
    AnalyticsExportAuditLog,
    AnalyticsReport,
    AnalyticsReportField,
    AnalyticsReportFilter,
    AnalyticsReportJoin,
    AnalyticsReportRun,
    AnalyticsReportSort,
    AnalyticsScheduledReport,
)


ANALYTICS_TABLE_MODELS = [
    AnalyticsReport,
    AnalyticsReportField,
    AnalyticsReportFilter,
    AnalyticsReportSort,
    AnalyticsReportJoin,
    AnalyticsDashboard,
    AnalyticsDashboardWidget,
    AnalyticsScheduledReport,
    AnalyticsReportRun,
    AnalyticsExport,
    AnalyticsExportAuditLog,
    AnalyticsAnomalyRule,
]


def ensure_analytics_schema(db: Session) -> None:
    inspector = inspect(db.bind)
    existing_tables = set(inspector.get_table_names())
    missing = [model.__table__ for model in ANALYTICS_TABLE_MODELS if model.__tablename__ not in existing_tables]
    if missing:
        AnalyticsReport.metadata.create_all(bind=db.bind, tables=missing)

