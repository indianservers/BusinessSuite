from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.apps.analytics.models import (
    AnalyticsAnomalyRule,
    AnalyticsDashboard,
    AnalyticsDashboardWidget,
    AnalyticsExport,
    AnalyticsExportAuditLog,
    AnalyticsReport,
    AnalyticsReportRun,
    AnalyticsScheduledReport,
)
from app.apps.analytics.schemas import DashboardPayload, ExportPayload, ReportPayload, ReportRunPayload, SchedulePayload, WidgetPayload
from app.apps.analytics.services.engine import default_fields, ensure_source_allowed, run_report, write_export
from app.apps.communication.models import CommunicationCampaign
from app.apps.crm.models import CRMDeal, CRMLead
from app.apps.srm.models import SRMInvoice, SRMProfitabilitySnapshot, SRMReceipt
from app.core.deps import RequirePermission, get_db
from app.models.user import User


router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _serialize(item) -> dict[str, Any] | None:
    if item is None:
        return None
    data: dict[str, Any] = {}
    for column in item.__table__.columns:
        value = getattr(item, column.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.name] = value
    return data


def _list(items: list[Any]) -> dict[str, Any]:
    return {"items": [_serialize(item) for item in items], "total": len(items)}


def _permissions(user: User) -> set[str]:
    if user.is_superuser:
        return {"*"}
    return {p.name for p in (user.role.permissions if user.role else [])}


def _financial_allowed(user: User) -> bool:
    perms = _permissions(user)
    return "*" in perms or bool(perms & {"analytics_financial_view", "analytics_profitability_view", "analytics_admin", "srm_profitability_view", "srm_admin"})


def _audit(db: Session, user: User, action: str, export_id: int | None = None, report_id: int | None = None, metadata: dict[str, Any] | None = None) -> None:
    db.add(AnalyticsExportAuditLog(export_id=export_id, report_id=report_id, actor_user_id=user.id, action=action, metadata_json=metadata))


def _require_report(db: Session, report_id: int, user: User) -> AnalyticsReport:
    report = db.query(AnalyticsReport).filter(AnalyticsReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Analytics report not found")
    ensure_source_allowed(report.module_name, _financial_allowed(user))
    return report


@router.get("/module-info")
def module_info(current_user: User = Depends(RequirePermission("analytics_view", "analytics_manage"))):
    return {"module": "analytics", "title": "Analytics and Export Engine"}


@router.get("/reports")
def list_reports(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_view", "analytics_manage", "analytics_report_builder"))):
    return _list(db.query(AnalyticsReport).order_by(AnalyticsReport.created_at.desc()).all())


@router.post("/reports", status_code=201)
def create_report(data: ReportPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_report_builder", "analytics_manage"))):
    ensure_source_allowed(data.module_name, _financial_allowed(current_user))
    fields = data.fields_json or default_fields(data.module_name)
    item = AnalyticsReport(**data.model_dump(exclude={"fields_json"}), fields_json=fields, owner_id=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/reports/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_view", "analytics_manage", "analytics_report_builder"))):
    return _serialize(_require_report(db, report_id, current_user))


@router.put("/reports/{report_id}")
def update_report(report_id: int, data: ReportPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_report_builder", "analytics_manage"))):
    report = _require_report(db, report_id, current_user)
    ensure_source_allowed(data.module_name, _financial_allowed(current_user))
    for key, value in data.model_dump().items():
        setattr(report, key, value)
    db.commit()
    return _serialize(report)


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_manage", "analytics_admin"))):
    report = _require_report(db, report_id, current_user)
    db.delete(report)
    db.commit()
    return None


@router.post("/reports/{report_id}/run")
def run_saved_report(report_id: int, data: ReportRunPayload | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_view", "analytics_report_builder", "analytics_manage"))):
    report = _require_report(db, report_id, current_user)
    payload = run_report(db, report, _financial_allowed(current_user), data.page if data else 1, data.page_size if data else 50, data.filters_json if data else None)
    run = AnalyticsReportRun(report_id=report.id, status="completed", row_count=payload["total"], run_by=current_user.id, parameters_json=(data.model_dump() if data else {}), result_preview_json={"items": payload["items"][:10]})
    db.add(run)
    db.commit()
    payload["run_id"] = run.id
    return payload


@router.post("/reports/{report_id}/export", status_code=201)
def export_report(report_id: int, data: ExportPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_export"))):
    report = _require_report(db, report_id, current_user)
    export = AnalyticsExport(report_id=report.id, requested_by=current_user.id, export_type=data.export_type, status="running")
    db.add(export)
    db.flush()
    try:
        payload = run_report(db, report, _financial_allowed(current_user), 1, data.page_size, None)
        file_path, row_count = write_export(report, payload, data.export_type, export.id)
        export.status = "completed"
        export.file_path_or_reference = file_path
        export.row_count = row_count
        export.completed_at = datetime.now(timezone.utc)
        _audit(db, current_user, "export_completed", export.id, report.id, {"export_type": data.export_type, "row_count": row_count})
    except Exception as exc:
        export.status = "failed"
        export.error_message = str(exc)
        _audit(db, current_user, "export_failed", export.id, report.id, {"error": str(exc)})
    db.commit()
    return _serialize(export)


@router.get("/exports/{export_id}")
def get_export(export_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_export", "analytics_view"))):
    item = db.query(AnalyticsExport).filter(AnalyticsExport.id == export_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Export not found")
    return _serialize(item)


@router.get("/exports/{export_id}/download")
def download_export(export_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_export"))):
    item = db.query(AnalyticsExport).filter(AnalyticsExport.id == export_id).first()
    if not item or item.status != "completed" or not item.file_path_or_reference:
        raise HTTPException(status_code=404, detail="Completed export file not found")
    if not os.path.exists(item.file_path_or_reference):
        raise HTTPException(status_code=404, detail="Export file is missing from storage")
    _audit(db, current_user, "export_downloaded", item.id, item.report_id, {"export_type": item.export_type})
    db.commit()
    media = {"csv": "text/csv", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "pdf": "application/pdf"}[item.export_type]
    return FileResponse(item.file_path_or_reference, media_type=media, filename=os.path.basename(item.file_path_or_reference))


@router.get("/dashboards")
def list_dashboards(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_view", "analytics_manage"))):
    return _list(db.query(AnalyticsDashboard).order_by(AnalyticsDashboard.created_at.desc()).all())


@router.post("/dashboards", status_code=201)
def create_dashboard(data: DashboardPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_manage"))):
    item = AnalyticsDashboard(**data.model_dump(), owner_id=current_user.id)
    db.add(item)
    db.commit()
    return _serialize(item)


@router.get("/dashboards/{dashboard_id}")
def get_dashboard(dashboard_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_view", "analytics_manage"))):
    item = db.query(AnalyticsDashboard).filter(AnalyticsDashboard.id == dashboard_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    data = _serialize(item) or {}
    data["widgets"] = [_serialize(widget) for widget in db.query(AnalyticsDashboardWidget).filter(AnalyticsDashboardWidget.dashboard_id == item.id).all()]
    return data


@router.put("/dashboards/{dashboard_id}")
def update_dashboard(dashboard_id: int, data: DashboardPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_manage"))):
    item = db.query(AnalyticsDashboard).filter(AnalyticsDashboard.id == dashboard_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return _serialize(item)


@router.delete("/dashboards/{dashboard_id}", status_code=204)
def delete_dashboard(dashboard_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_manage"))):
    item = db.query(AnalyticsDashboard).filter(AnalyticsDashboard.id == dashboard_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    db.delete(item)
    db.commit()
    return None


@router.post("/dashboards/{dashboard_id}/widgets", status_code=201)
def add_widget(dashboard_id: int, data: WidgetPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_manage"))):
    if not db.query(AnalyticsDashboard).filter(AnalyticsDashboard.id == dashboard_id).first():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    item = AnalyticsDashboardWidget(dashboard_id=dashboard_id, **data.model_dump())
    db.add(item)
    db.commit()
    return _serialize(item)


@router.put("/widgets/{widget_id}")
def update_widget(widget_id: int, data: WidgetPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_manage"))):
    item = db.query(AnalyticsDashboardWidget).filter(AnalyticsDashboardWidget.id == widget_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Widget not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return _serialize(item)


@router.get("/schedules")
def list_schedules(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_schedule", "analytics_manage"))):
    return _list(db.query(AnalyticsScheduledReport).order_by(AnalyticsScheduledReport.created_at.desc()).all())


@router.post("/schedules", status_code=201)
def create_schedule(data: SchedulePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_schedule"))):
    _require_report(db, data.report_id, current_user)
    item = AnalyticsScheduledReport(**data.model_dump(exclude={"active"}), active=1 if data.active else 0, created_by=current_user.id)
    db.add(item)
    db.commit()
    return _serialize(item)


@router.post("/schedules/{schedule_id}/run-now")
def run_schedule_now(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_schedule"))):
    schedule = db.query(AnalyticsScheduledReport).filter(AnalyticsScheduledReport.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    report = _require_report(db, schedule.report_id, current_user)
    payload = run_report(db, report, _financial_allowed(current_user), 1, 50, None)
    run = AnalyticsReportRun(report_id=report.id, status="completed", row_count=payload["total"], run_by=current_user.id, parameters_json={"schedule_id": schedule.id}, result_preview_json={"items": payload["items"][:10]})
    db.add(run)
    db.commit()
    return _serialize(run)


@router.get("/funnel")
def funnel(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_view"))):
    return {"items": [{"stage": "Leads", "count": db.query(CRMLead).count()}, {"stage": "Deals", "count": db.query(CRMDeal).count()}, {"stage": "Invoices", "count": db.query(SRMInvoice).count()}], "total": 3}


@router.get("/forecast")
def forecast(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_view"))):
    pipeline = float(db.query(func.coalesce(func.sum(CRMDeal.amount), 0)).scalar() or 0)
    invoiced = float(db.query(func.coalesce(func.sum(SRMInvoice.total_amount), 0)).scalar() or 0)
    collected = float(db.query(func.coalesce(func.sum(SRMReceipt.amount), 0)).scalar() or 0)
    return {"pipeline": pipeline, "forecast_invoice": invoiced, "forecast_collection": collected, "variance_to_invoice": pipeline - invoiced}


@router.get("/profitability")
def profitability(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_profitability_view", "analytics_admin"))):
    items = db.query(SRMProfitabilitySnapshot).order_by(SRMProfitabilitySnapshot.snapshot_at.desc()).limit(50).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@router.get("/collections")
def collections(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_financial_view", "analytics_admin"))):
    invoices = db.query(SRMInvoice).limit(100).all()
    rows = [{"invoice_id": item.id, "invoice_number": item.invoice_number, "status": item.status, "outstanding": float((item.total_amount or 0) - (item.paid_amount or 0))} for item in invoices]
    return {"items": rows, "total": len(rows)}


@router.get("/campaigns")
def campaigns(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_view"))):
    items = db.query(CommunicationCampaign).order_by(CommunicationCampaign.created_at.desc()).limit(100).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@router.get("/anomalies")
def anomalies(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_view"))):
    rules = db.query(AnalyticsAnomalyRule).filter(AnalyticsAnomalyRule.active == 1).all()
    return {"items": [_serialize(item) for item in rules], "total": len(rules), "status": "placeholder_ready", "message": "Anomaly rules are configured for future detection jobs."}


@router.get("/export-audit")
def export_audit(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("analytics_admin", "analytics_export"))):
    return _list(db.query(AnalyticsExportAuditLog).order_by(AnalyticsExportAuditLog.created_at.desc()).limit(250).all())

