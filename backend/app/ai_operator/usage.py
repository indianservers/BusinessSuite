"""Scoped provider telemetry shared by legacy PMS and central AI administration."""
from datetime import datetime,timedelta,timezone
from sqlalchemy import func
from app.ai_operator.models import OperatorApiLog,OperatorEvent,OperatorRun


def report(db,user,scope,days,*,legacy=True):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    base = db.query(OperatorApiLog).filter(OperatorApiLog.scope_key == scope, OperatorApiLog.created_at >= start)
    groups = db.query(OperatorApiLog.provider, OperatorApiLog.model, OperatorApiLog.status,
        func.count(OperatorApiLog.id).label("requests"), func.sum(OperatorApiLog.input_tokens).label("input_tokens"),
        func.sum(OperatorApiLog.output_tokens).label("output_tokens"), func.sum(OperatorApiLog.estimated_cost).label("estimated_cost"),
        func.count(OperatorApiLog.estimated_cost).label("priced_requests"), func.avg(OperatorApiLog.duration_ms).label("average_latency_ms")
        ).filter(OperatorApiLog.scope_key == scope, OperatorApiLog.created_at >= start).group_by(OperatorApiLog.provider, OperatorApiLog.model, OperatorApiLog.status).all()
    fields = ("id", "user_id", "run_id", "suite_run_id", "module", "provider", "model", "purpose", "status", "error_code", "http_status",
              "provider_request_id", "input_tokens", "output_tokens", "estimated_cost", "duration_ms", "created_at")
    if legacy:
        local_plans = db.query(func.count(OperatorEvent.id)).join(OperatorRun, OperatorRun.id == OperatorEvent.run_id).filter(
            OperatorRun.scope_key == scope, OperatorEvent.event_type == "plan.local", OperatorEvent.created_at >= start).scalar()
    else:
        from app.ai_operator.suite_models import SuiteRun
        local_plans = db.query(func.count(SuiteRun.id)).filter(SuiteRun.scope_key==scope,SuiteRun.created_at>=start,
            SuiteRun.result['intelligence']['engine'].as_string()=='server',
            SuiteRun.plan['summary'].as_string().is_not(None)).scalar()
    rows=base.order_by(OperatorApiLog.id.desc()).limit(200).all()
    from app.ai_operator.prompt_provenance import lookup
    prompts=lookup(db,rows)
    return {"days": days, "local_plans": local_plans, **({"server_plans":local_plans} if not legacy else {}), "groups": [dict(g._mapping) for g in groups],
        "logs": [{**{f: getattr(r, f) for f in fields},'core_prompt':prompts.get(r.id)} for r in rows],
        "cost_note": "USD estimates use administrator-supplied rates per million tokens. Null means unknown; not a provider invoice. Group sums cover priced requests only; compare priced_requests with requests for completeness. Logs exclude prompt content, responses and credentials."}
