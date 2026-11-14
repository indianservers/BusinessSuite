"""Shared single-attempt media call journal over existing assistant messages."""
import time
from fastapi import HTTPException
from app.ai_operator.assistant_models import AssistantMessage
from app.ai_operator.models import OperatorApiLog
from app.ai_operator.service import digest
from app.ai_agents.security import verify


def output(db,user,run,data,step,config,journal_tool,purpose,manifest,invoke):
    # The caller holds the reviewed SuiteRun lock before this unique lookup.
    key=digest({'media_run':run.id,'step':data.suite_step})
    journal=db.query(AssistantMessage).filter_by(conversation_id=data.conversation_id,request_key=key).first()
    if journal:
        verify(db,user,journal.security_context,history=True)
        if journal.tool!=journal_tool or journal.request_hash!=digest(step.payload):raise HTTPException(409,'Media journal changed')
        if journal.status not in {'completed','output_stored'}:raise HTTPException(409,'MEDIA_OUTCOME_REQUIRES_RECONCILIATION')
        return journal
    journal=AssistantMessage(conversation_id=data.conversation_id,request_key=key,request_hash=digest(step.payload),
        prompt='Reviewed media processing',tool=journal_tool,arguments={'suite_run_id':run.id,'step':data.suite_step,
            'model':config.model,'media_policy_sha256':config.media_policy_sha256,'core_prompt':manifest},status='started',result={})
    log=OperatorApiLog(scope_key=config.scope_key,module=step.tool.split('.')[0].upper(),suite_run_id=run.id,user_id=user.id,
        provider='gemini',model=config.model,purpose=purpose,status='started',duration_ms=0,estimated_cost=None)
    db.add(journal);db.add(log);db.flush();log_id=log.id;db.commit()
    start=time.monotonic()
    try:
        value,usage=invoke()
        journal.result={**value,'usage':usage};journal.status='output_stored'
        log=db.get(OperatorApiLog,log_id);log.status='success';log.duration_ms=round((time.monotonic()-start)*1000)
        log.input_tokens=usage.get('promptTokenCount')
        counts=[usage.get(k) for k in ('candidatesTokenCount','thoughtsTokenCount')]
        log.output_tokens=sum(v for v in counts if type(v) is int) if any(type(v) is int for v in counts) else None
        from app.ai_operator.suite_models import SuiteRun
        current=db.query(SuiteRun).filter_by(id=run.id).with_for_update().populate_existing().one()
        current.result={**(current.result or {}),'media_checkpoint':{'step':data.suite_step,'state':'output_stored'}}
        db.commit()  # Save validated output before artifact writes; never bill twice.
        return journal
    except Exception as exc:
        if not db.is_active:db.rollback()
        journal=db.query(AssistantMessage).filter_by(conversation_id=data.conversation_id,request_key=key).one()
        provider_status=getattr(exc,'provider_status',None)
        rejected=provider_status in {400,401,403,404,413,429}
        error={'provider_http_status':provider_status,'quota_limit':getattr(exc,'quota_limit',None),'retry_after_seconds':getattr(exc,'retry_after',None)}
        journal.status='rejected' if rejected else 'uncertain';journal.result={'provider_error':error} if rejected else {}
        log=db.get(OperatorApiLog,log_id);log.status='failed'
        log.http_status=provider_status
        log.error_code=exc.detail[:60] if isinstance(exc,HTTPException) and isinstance(exc.detail,str) else 'MEDIA_PROVIDER_FAILED'
        log.duration_ms=round((time.monotonic()-start)*1000)
        if rejected:
            from app.ai_operator.suite_models import SuiteRun
            current=db.query(SuiteRun).filter_by(id=run.id).with_for_update().populate_existing().one()
            current.result={**(current.result or {}),'media_error':error}
        db.commit()
        raise HTTPException(409,'MEDIA_PROVIDER_REJECTED' if rejected else 'MEDIA_OUTCOME_REQUIRES_RECONCILIATION') from None
