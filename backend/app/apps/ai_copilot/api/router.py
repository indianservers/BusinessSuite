from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.apps.ai_copilot.schemas import (
    AIAgentActionConfirmRequest,
    AIAgentActionPreviewRequest,
    AIProviderSettingPayload,
    AIPromptTemplatePayload,
    AIUseCaseRequest,
    AIUserFeedbackPayload,
)
from app.apps.ai_copilot.services.context import build_secure_context, has_any
from app.apps.ai_copilot.services.provider import AIProviderNotConfigured, adapter_for
from app.core.deps import RequirePermission, get_db
from app.models.user import User


router = APIRouter(prefix="/ai", tags=["AI Copilot"])

USE_CASE_LABELS = {
    "summary": "Record Summary",
    "deal_coach": "Deal Coach",
    "lead_score": "Lead Scoring",
    "forecast_insight": "Forecast Insight",
    "email_draft": "Email Draft",
    "meeting_summary": "Meeting Summary",
    "collection_risk": "Collection Risk",
    "workflow_draft": "Workflow Draft",
    "report_explain": "Report Explainer",
}

ALLOWED_AGENT_ACTIONS = {"create_task", "draft_email", "add_note", "update_field", "suggest_quote_line", "suggest_collection_escalation", "draft_workflow"}


def _serialize(item):
    if item is None:
        return None
    data = {}
    for column in item.__table__.columns:
        value = getattr(item, column.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.name] = value
    return data


def _log(
    db: Session,
    user: User,
    *,
    event_type: str,
    status_value: str,
    module_name: str | None = None,
    record_type: str | None = None,
    record_id: int | None = None,
    prompt_run_id: int | None = None,
    agent_action_id: int | None = None,
    detail: dict[str, Any] | None = None,
    error: str | None = None,
) -> AIActionLog:
    row = AIActionLog(
        prompt_run_id=prompt_run_id,
        agent_action_id=agent_action_id,
        event_type=event_type,
        module_name=module_name,
        record_type=record_type,
        record_id=record_id,
        status=status_value,
        detail_json=detail or {},
        error_message=error,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _enabled_provider(db: Session) -> AIProviderSetting | None:
    return db.query(AIProviderSetting).filter(AIProviderSetting.enabled == True).order_by(AIProviderSetting.updated_at.desc(), AIProviderSetting.id.desc()).first()


def _provider_or_error(db: Session) -> AIProviderSetting:
    setting = _enabled_provider(db)
    if not setting or not setting.data_sharing_allowed:
        raise AIProviderNotConfigured("AI provider not configured. Enable a provider and allow data sharing before generating AI output.")
    return setting


def _estimate_tokens(payload: Any) -> int:
    return max(1, len(str(payload)) // 4)


def _prompt_template(db: Session, use_case: str, module_name: str | None) -> AIPromptTemplate | None:
    query = db.query(AIPromptTemplate).filter(AIPromptTemplate.use_case == use_case, AIPromptTemplate.active == True)
    if module_name:
        scoped = query.filter(AIPromptTemplate.module_name == module_name).order_by(AIPromptTemplate.id.desc()).first()
        if scoped:
            return scoped
    return query.order_by(AIPromptTemplate.id.desc()).first()


def _default_prompt(use_case: str, context: dict[str, Any], user_prompt: str | None = None) -> str:
    label = USE_CASE_LABELS.get(use_case, use_case)
    return f"{label}. Use only this sanitized context and cite evidence. Context={context}. User request={user_prompt or ''}"


def _ai_response(
    *,
    run: AIPromptRun,
    context: dict[str, Any],
    output: dict[str, Any],
    status_value: str = "completed",
    provider_configured: bool = True,
) -> dict[str, Any]:
    return {
        "provider_configured": provider_configured,
        "status": status_value,
        "prompt_run_id": run.id,
        "use_case": run.use_case,
        "record_type": run.record_type,
        "record_id": run.record_id,
        "module_name": context.get("module_name"),
        "source_data_summary": context.get("source_summary"),
        "output": output,
        "confidence": output.get("confidence"),
        "reasons": output.get("reasons", []),
    }


def _run_ai_use_case(db: Session, current_user: User, use_case: str, payload: AIUseCaseRequest) -> dict[str, Any]:
    context = build_secure_context(
        db,
        current_user,
        record_type=payload.record_type,
        record_id=payload.record_id,
        module_name=payload.module_name,
        data=payload.data,
    )
    template = _prompt_template(db, use_case, context.get("module_name"))
    setting = _enabled_provider(db)
    run = AIPromptRun(
        use_case=use_case,
        provider=setting.provider_name if setting else None,
        model=setting.model_name if setting else None,
        record_type=context.get("record_type"),
        record_id=context.get("record_id"),
        input_token_estimate=_estimate_tokens(context),
        status="started",
        prompt_template_id=template.id if template else None,
        created_by=current_user.id,
    )
    db.add(run)
    db.flush()
    try:
        setting = _provider_or_error(db)
        prompt = template.user_prompt_template if template else _default_prompt(use_case, context, payload.prompt)
        result = adapter_for(setting).generate(use_case=use_case, prompt=prompt, context=context, setting=setting)
        run.provider = setting.provider_name
        run.model = setting.model_name
        run.status = "completed"
        run.output_token_estimate = result.output_token_estimate
        output = result.output | {"confidence": result.confidence, "reasons": result.reasons}
        if use_case == "summary":
            db.add(AIRecordSummary(module_name=context["module_name"], record_type=context["record_type"], record_id=context.get("record_id") or 0, prompt_run_id=run.id, summary_text=result.content, source_summary_json=context["source_summary"], confidence=result.confidence, created_by=current_user.id))
        if use_case in {"lead_score", "deal_coach", "forecast_insight", "collection_risk"}:
            db.add(AIScore(module_name=context["module_name"], record_type=context["record_type"], record_id=context.get("record_id") or 0, prompt_run_id=run.id, use_case=use_case, score=output.get("score") or 0, probability=output.get("probability") or 0, label=use_case, reasons_json=result.reasons, created_by=current_user.id))
        db.add(AIRecommendation(module_name=context["module_name"], record_type=context["record_type"], record_id=context.get("record_id"), prompt_run_id=run.id, use_case=use_case, recommendation_text=result.content, confidence=result.confidence, reasons_json=result.reasons, created_by=current_user.id))
        _log(db, current_user, event_type=f"ai_{use_case}", status_value="completed", module_name=context["module_name"], record_type=context["record_type"], record_id=context.get("record_id"), prompt_run_id=run.id, detail={"provider": setting.provider_name})
        db.commit()
        db.refresh(run)
        return _ai_response(run=run, context=context, output=output)
    except AIProviderNotConfigured as exc:
        run.status = "provider_not_configured"
        run.error_message = str(exc)
        _log(db, current_user, event_type=f"ai_{use_case}", status_value="provider_not_configured", module_name=context["module_name"], record_type=context["record_type"], record_id=context.get("record_id"), prompt_run_id=run.id, error=str(exc))
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"provider_configured": False, "status": "provider_not_configured", "message": str(exc), "prompt_run_id": run.id}) from exc


@router.get("/provider-settings")
def list_provider_settings(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_view", "ai_manage_settings"))):
    return {"items": [_serialize(item) for item in db.query(AIProviderSetting).order_by(AIProviderSetting.id.desc()).all()]}


@router.post("/provider-settings", status_code=201)
def create_provider_setting(data: AIProviderSettingPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_manage_settings"))):
    item = AIProviderSetting(**data.model_dump(), created_by=current_user.id, updated_by=current_user.id)
    db.add(item)
    db.flush()
    _log(db, current_user, event_type="ai_provider_setting_created", status_value="completed", detail={"provider": item.provider_name})
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.put("/provider-settings/{setting_id}")
def update_provider_setting(setting_id: int, data: AIProviderSettingPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_manage_settings"))):
    item = db.query(AIProviderSetting).filter(AIProviderSetting.id == setting_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="AI provider setting not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    item.updated_by = current_user.id
    _log(db, current_user, event_type="ai_provider_setting_updated", status_value="completed", detail={"provider": item.provider_name})
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/provider-settings/{setting_id}/test")
def test_provider_setting(setting_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_manage_settings"))):
    item = db.query(AIProviderSetting).filter(AIProviderSetting.id == setting_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="AI provider setting not found")
    if not item.enabled or not item.data_sharing_allowed:
        status_value = "provider_not_configured"
        message = "Provider is disabled or data sharing is not allowed."
    elif item.provider_name.lower() == "mock":
        status_value = "ok"
        message = "Mock provider is ready for tests."
    else:
        status_value = "unsupported"
        message = "Production provider connector is not configured in this deployment."
    _log(db, current_user, event_type="ai_provider_setting_tested", status_value=status_value, detail={"provider": item.provider_name})
    db.commit()
    return {"status": status_value, "provider_configured": status_value == "ok", "message": message}


@router.get("/prompt-templates")
def list_prompt_templates(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_view", "ai_manage_prompts"))):
    return {"items": [_serialize(item) for item in db.query(AIPromptTemplate).order_by(AIPromptTemplate.id.desc()).all()]}


@router.post("/prompt-templates", status_code=201)
def create_prompt_template(data: AIPromptTemplatePayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_manage_prompts"))):
    item = AIPromptTemplate(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.flush()
    _log(db, current_user, event_type="ai_prompt_template_created", status_value="completed", module_name=item.module_name, detail={"use_case": item.use_case})
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/prompt-templates/{template_id}/test")
def test_prompt_template(template_id: int, payload: AIUseCaseRequest | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_manage_prompts", "ai_use"))):
    template = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="AI prompt template not found")
    data = payload or AIUseCaseRequest(module_name=template.module_name, record_type="record")
    return _run_ai_use_case(db, current_user, template.use_case, data)


@router.post("/summary")
def record_summary(payload: AIUseCaseRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_use", "ai_view"))):
    return _run_ai_use_case(db, current_user, "summary", payload)


@router.post("/deal-coach")
def deal_coach(payload: AIUseCaseRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_use"))):
    return _run_ai_use_case(db, current_user, "deal_coach", payload)


@router.post("/lead-score")
def lead_score(payload: AIUseCaseRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_use"))):
    return _run_ai_use_case(db, current_user, "lead_score", payload)


@router.post("/forecast-insight")
def forecast_insight(payload: AIUseCaseRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_use"))):
    return _run_ai_use_case(db, current_user, "forecast_insight", payload)


@router.post("/email-draft")
def email_draft(payload: AIUseCaseRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_use"))):
    result = _run_ai_use_case(db, current_user, "email_draft", payload)
    result["requires_user_review_before_send"] = True
    return result


@router.post("/meeting-summary")
def meeting_summary(payload: AIUseCaseRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_use"))):
    return _run_ai_use_case(db, current_user, "meeting_summary", payload)


@router.post("/collection-risk")
def collection_risk(payload: AIUseCaseRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_use"))):
    return _run_ai_use_case(db, current_user, "collection_risk", payload)


@router.post("/workflow-draft")
def workflow_draft(payload: AIUseCaseRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_use"))):
    result = _run_ai_use_case(db, current_user, "workflow_draft", payload)
    result["auto_activated"] = False
    return result


@router.post("/report-explain")
def report_explain(payload: AIUseCaseRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_use", "ai_view"))):
    return _run_ai_use_case(db, current_user, "report_explain", payload)


def _assert_action_permission(user: User, action_type: str, module_name: str) -> None:
    if not has_any(user, "ai_agent_actions"):
        raise HTTPException(status_code=403, detail="AI agent action permission required")
    if action_type == "draft_workflow" and not has_any(user, "automation_manage", "ai_manage_prompts", "ai_manage_settings"):
        raise HTTPException(status_code=403, detail="Workflow draft action requires automation or AI admin permission")
    if module_name == "srm" and action_type in {"suggest_collection_escalation"} and not has_any(user, "srm_collection_create", "srm_admin"):
        raise HTTPException(status_code=403, detail="Collection action permission required")


@router.post("/agent-action/preview")
def preview_agent_action(payload: AIAgentActionPreviewRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_agent_actions"))):
    action_type = payload.action_type.strip().lower()
    if action_type not in ALLOWED_AGENT_ACTIONS:
        raise HTTPException(status_code=400, detail="AI agent action is not allowed")
    _assert_action_permission(current_user, action_type, payload.module_name)
    context = build_secure_context(db, current_user, record_type=payload.record_type, record_id=payload.record_id, module_name=payload.module_name, data=payload.input_json)
    action = AIAgentAction(action_type=action_type, module_name=context["module_name"], record_type=context["record_type"], record_id=context.get("record_id"), preview_json={"action_type": action_type, "input": context["input_data"], "requires_confirmation": True}, status="previewed", requires_confirmation=True, created_by=current_user.id)
    db.add(action)
    db.flush()
    _log(db, current_user, event_type="ai_agent_action_preview", status_value="previewed", module_name=context["module_name"], record_type=context["record_type"], record_id=context.get("record_id"), agent_action_id=action.id, detail=action.preview_json)
    db.commit()
    db.refresh(action)
    return {"action": _serialize(action), "requires_confirmation": True, "source_data_summary": context["source_summary"]}


@router.post("/agent-action/confirm")
def confirm_agent_action(payload: AIAgentActionConfirmRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_agent_actions"))):
    action = db.query(AIAgentAction).filter(AIAgentAction.id == payload.action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="AI agent action not found")
    _assert_action_permission(current_user, action.action_type, action.module_name)
    build_secure_context(db, current_user, record_type=action.record_type, record_id=action.record_id, module_name=action.module_name, data=action.preview_json or {})
    action.status = "confirmed"
    action.confirmed_by = current_user.id
    action.confirmed_at = datetime.now(timezone.utc)
    action.result_json = {
        "executed": action.action_type in {"create_task", "add_note", "update_field"},
        "draft_only": action.action_type in {"draft_email", "draft_workflow", "suggest_quote_line", "suggest_collection_escalation"},
        "message": "Action confirmed. Draft/suggestion actions still require module owner review before final execution.",
        "confirmation_note": payload.confirmation_note,
    }
    _log(db, current_user, event_type="ai_agent_action_confirm", status_value="confirmed", module_name=action.module_name, record_type=action.record_type, record_id=action.record_id, agent_action_id=action.id, detail=action.result_json)
    db.commit()
    db.refresh(action)
    return {"action": _serialize(action), "result": action.result_json}


@router.get("/action-log")
def action_log(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("ai_action_log_view", "ai_manage_settings")),
):
    query = db.query(AIActionLog).order_by(AIActionLog.created_at.desc(), AIActionLog.id.desc())
    if not current_user.is_superuser and not has_any(current_user, "ai_manage_settings"):
        query = query.filter(AIActionLog.created_by == current_user.id)
    rows = query.limit(limit).all()
    return {"items": [_serialize(row) for row in rows], "total": len(rows)}


@router.post("/feedback", status_code=201)
def create_feedback(payload: AIUserFeedbackPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("ai_view", "ai_use"))):
    rating = payload.rating.strip().lower()
    if rating not in {"helpful", "not_helpful", "neutral"}:
        raise HTTPException(status_code=400, detail="Feedback rating must be helpful, not_helpful, or neutral")
    row = AIUserFeedback(**payload.model_dump(), rating=rating, created_by=current_user.id)
    db.add(row)
    db.flush()
    _log(db, current_user, event_type="ai_feedback", status_value="completed", prompt_run_id=row.prompt_run_id, detail={"rating": rating})
    db.commit()
    db.refresh(row)
    return _serialize(row)

