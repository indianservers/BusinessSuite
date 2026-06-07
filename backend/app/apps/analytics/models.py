from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base_class import Base


class AnalyticsReport(Base):
    __tablename__ = "analytics_reports"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    description = Column(Text)
    module_name = Column(String(100), nullable=False, index=True)
    report_type = Column(String(40), default="table", nullable=False, index=True)
    data_source_json = Column(JSON)
    fields_json = Column(JSON)
    filters_json = Column(JSON)
    grouping_json = Column(JSON)
    sorting_json = Column(JSON)
    visibility = Column(String(40), default="private", index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AnalyticsReportField(Base):
    __tablename__ = "analytics_report_fields"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("analytics_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(120), nullable=False)
    label = Column(String(160))
    order_index = Column(Integer, default=0)


class AnalyticsReportFilter(Base):
    __tablename__ = "analytics_report_filters"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("analytics_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(120), nullable=False)
    operator = Column(String(40), default="equals")
    value_json = Column(JSON)


class AnalyticsReportSort(Base):
    __tablename__ = "analytics_report_sorts"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("analytics_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(120), nullable=False)
    direction = Column(String(10), default="asc")


class AnalyticsReportJoin(Base):
    __tablename__ = "analytics_report_joins"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("analytics_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    source_module = Column(String(100), nullable=False)
    target_module = Column(String(100), nullable=False)
    join_config_json = Column(JSON)


class AnalyticsDashboard(Base):
    __tablename__ = "analytics_dashboards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    description = Column(Text)
    visibility = Column(String(40), default="private", index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    filters_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AnalyticsDashboardWidget(Base):
    __tablename__ = "analytics_dashboard_widgets"

    id = Column(Integer, primary_key=True, index=True)
    dashboard_id = Column(Integer, ForeignKey("analytics_dashboards.id", ondelete="CASCADE"), nullable=False, index=True)
    widget_type = Column(String(40), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    config_json = Column(JSON)
    position_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AnalyticsScheduledReport(Base):
    __tablename__ = "analytics_scheduled_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("analytics_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(180), nullable=False, index=True)
    frequency = Column(String(40), default="weekly", index=True)
    recipients_json = Column(JSON)
    active = Column(Integer, default=1, index=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AnalyticsReportRun(Base):
    __tablename__ = "analytics_report_runs"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("analytics_reports.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(40), default="completed", index=True)
    row_count = Column(Integer, default=0)
    run_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    parameters_json = Column(JSON)
    result_preview_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AnalyticsExport(Base):
    __tablename__ = "analytics_exports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("analytics_reports.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    export_type = Column(String(20), nullable=False, index=True)
    status = Column(String(40), default="queued", index=True)
    file_path_or_reference = Column(Text)
    row_count = Column(Integer, default=0)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True, index=True)


class AnalyticsExportAuditLog(Base):
    __tablename__ = "analytics_export_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    export_id = Column(Integer, ForeignKey("analytics_exports.id", ondelete="SET NULL"), nullable=True, index=True)
    report_id = Column(Integer, ForeignKey("analytics_reports.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AnalyticsAnomalyRule(Base):
    __tablename__ = "analytics_anomaly_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    module_name = Column(String(100), nullable=False, index=True)
    rule_json = Column(JSON)
    active = Column(Integer, default=1, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

