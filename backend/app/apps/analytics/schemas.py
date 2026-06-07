from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReportPayload(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    module_name: str = "crm_deals"
    report_type: Literal["table", "summary", "matrix", "chart", "funnel"] = "table"
    data_source_json: dict[str, Any] | None = None
    fields_json: list[str] | None = None
    filters_json: dict[str, Any] | None = None
    grouping_json: dict[str, Any] | None = None
    sorting_json: dict[str, Any] | None = None
    visibility: Literal["private", "team", "public", "role_based"] = "private"


class ReportRunPayload(BaseModel):
    page: int = 1
    page_size: int = 50
    filters_json: dict[str, Any] | None = None


class ExportPayload(BaseModel):
    export_type: Literal["csv", "xlsx", "pdf"] = "csv"
    page_size: int = 1000


class DashboardPayload(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    visibility: Literal["private", "team", "public", "role_based"] = "private"
    filters_json: dict[str, Any] | None = None


class WidgetPayload(BaseModel):
    widget_type: Literal["kpi", "chart", "table", "funnel"] = "kpi"
    title: str = Field(min_length=2, max_length=180)
    config_json: dict[str, Any] | None = None
    position_json: dict[str, Any] | None = None


class SchedulePayload(BaseModel):
    report_id: int
    name: str = Field(min_length=2, max_length=180)
    frequency: Literal["daily", "weekly", "monthly"] = "weekly"
    recipients_json: list[str] | None = None
    active: bool = True
    next_run_at: datetime | None = None

