"""Core and complete-request provenance in private runs and sanitized audit rows."""
import json
from app.ai_operator.prompt_registry import render


def record(db,user,log,manifest,request_attempted):
    from app.ai_agents.services.audit import AiAuditService
    trace={**manifest,'api_log_id':log.id,'provider':log.provider,'model':log.model,
           'status':log.status,'request_attempted':request_attempted}
    AiAuditService(db).log(user=user,agent_id=None,module=log.module,action='llm.prompt.version',
        input_json={'suite_run_id':log.suite_run_id,'run_id':log.run_id,'policy':json.dumps(trace,sort_keys=True)},
        output_json={'status':log.status},status=log.status,
        related_entity_type='operator_api_log',related_entity_id=str(log.id))
    if log.suite_run_id:
        from app.ai_operator.suite_models import SuiteRun
        run=db.get(SuiteRun,log.suite_run_id)
        if run and run.user_id==user.id and run.scope_key==log.scope_key:
            previous=(run.result or {}).get('prompt_versions') or []
            run.result={**(run.result or {}),'prompt_versions':[*previous,trace][-12:]}
    return trace


def lookup(db,logs):
    """Batch lookup only for already-authorized API log IDs and their exact actors."""
    from app.ai_agents.models import AiAuditLog
    by_id={str(log.id):log for log in logs}
    if not by_id:return {}
    rows=db.query(AiAuditLog).filter(AiAuditLog.action=='llm.prompt.version',
        AiAuditLog.related_entity_type=='operator_api_log',AiAuditLog.related_entity_id.in_(by_id)).order_by(AiAuditLog.id.desc()).limit(len(by_id)*2).all()
    result={}
    for row in rows:
        log=by_id.get(row.related_entity_id)
        if log is None or row.user_id!=log.user_id:continue
        try:trace=json.loads((row.input_json or {}).get('policy',''))
        except (ValueError,TypeError):continue
        if not isinstance(trace,dict) or trace.get('format')!='core-prompt-v1':continue
        if trace.get('api_log_id')!=log.id or trace.get('provider')!=log.provider or trace.get('model')!=log.model:continue
        result.setdefault(log.id,trace)
    return result


def current_suite(task):
    from app.ai_operator.suite import Summary,Plan
    summary=task['output_schema']=='summary'
    return render('suite_summary' if summary else 'suite_plan',(Summary if summary else Plan).model_json_schema())[1]


def compatible(run,log,expected):
    if expected is None:return True
    return any(item.get('api_log_id')==log.id and item.get('provider')==log.provider and item.get('model')==log.model
        and item.get('status')=='success' and all(item.get(key)==value for key,value in expected.items())
        for item in (run.result or {}).get('prompt_versions',[]) if isinstance(item,dict))
