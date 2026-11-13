"""Opt-in routing from owner-reviewed outcomes, never provider marketing scores."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException


def measurements(db, user, workspace_id, project_id, task=None):
    from app.ai_operator.suite import authorize, now
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_operator.models import OperatorApiLog
    from app.ai_operator.workbench_models import AssistantSignal
    from app.ai_agents.security import verify
    from app.ai_operator.routing_tasks import profile,final_provider,reviewed_output
    from app.ai_operator.prompt_provenance import current_suite,compatible
    expected_prompt=current_suite(task) if task is not None else None
    scope = authorize(db, user, workspace_id)
    runs = db.query(SuiteRun).filter_by(user_id=user.id, scope_key=scope).order_by(SuiteRun.id.desc()).limit(200).all()
    visible = {}
    for run in runs:
        if (run.result or {}).get('request', {}).get('project_id') != project_id: continue
        if task is not None and profile((run.result or {}).get('request',{}),run.command)!=task:continue
        try:
            verify(db, user, run.security_context, history=True)
            visible[run.id] = run
        except HTTPException: pass
    logs = db.query(OperatorApiLog).filter(OperatorApiLog.user_id == user.id, OperatorApiLog.suite_run_id.in_(visible),
        OperatorApiLog.created_at >= now()-timedelta(days=30)).order_by(OperatorApiLog.id.desc()).limit(500).all()
    reviews = db.query(AssistantSignal).filter_by(user_id=user.id, project_id=project_id, kind='suite_quality_v1').order_by(AssistantSignal.id.desc()).limit(200).all()
    rated = {r.details['suite_run_id']: r.details for r in reviews if r.details.get('suite_run_id') in visible}
    groups = defaultdict(list)
    for log in logs: groups[(log.provider, log.model)].append(log)
    result = []
    for (provider, model), group in groups.items():
        unique = {log.suite_run_id for log in group if log.status == 'success' and log.suite_run_id in rated
                  and final_provider(visible[log.suite_run_id])==(provider,model)
                  and compatible(visible[log.suite_run_id],log,expected_prompt)
                  and reviewed_output(visible[log.suite_run_id],task)}
        passed = sum(bool(rated[ident].get('supported') and rated[ident].get('correct')) for ident in unique)
        priced = [r for r in group if r.estimated_cost is not None]
        result.append({'provider': provider, 'model': model, 'calls': len(group), 'success_rate': sum(r.status == 'success' for r in group)/len(group),
            'reviews': len(unique), 'review_pass_rate': passed/len(unique) if unique else None,
            'mean_cost': str(sum((r.estimated_cost for r in priced), Decimal(0))/len(priced)) if priced and len(priced) == len(group) else None,
            'mean_duration_ms': sum(r.duration_ms for r in group)/len(group), 'basis': 'Owner ratings of the final provider output, technical success and configured pricing; bounded 30-day sample',
            **({'task_profile':task} if task is not None else {})})
        if expected_prompt:result[-1]['core_prompt']=expected_prompt
    return result


def select(db, user, workspace_id, project_id, task=None):
    from app.ai_operator.provider_scope import resolve_provider
    from app.ai_operator.providers import circuit_open
    from app.ai_operator.service import scope_key
    if not project_id: raise HTTPException(422, 'Measured routing requires a selected project and reviewed outcomes')
    choices = []
    for row in measurements(db,user,workspace_id,project_id,task):
        if row['reviews'] < 3 or row['review_pass_rate'] < .8 or row['success_rate'] < .8: continue
        config = resolve_provider(db,user,row['provider'],workspace_id)
        if not config or config.model != row['model'] or not config.enabled or not config.data_sharing_allowed: continue
        if circuit_open(db,user,config,scope_key(db,user,workspace_id)): continue
        choices.append((row,config))
    if not choices:
        raise HTTPException(409, 'No eligible measured model: require 3 reviewed successful outcomes'+(' matching this task profile and current core instructions' if task is not None else '')+', 80% quality and availability, and a currently enabled scoped provider. Choose a provider explicitly to collect evidence.')
    choices.sort(key=lambda pair: (-pair[0]['review_pass_rate'], Decimal(pair[0]['mean_cost']) if pair[0]['mean_cost'] is not None else Decimal('Infinity'), pair[0]['mean_duration_ms'], pair[0]['provider']))
    row, config = choices[0]
    return config, {'version':1, 'selected_provider':config.provider, 'selected_model':config.model, 'measurement':row,
                    **({'task_profile':task,'matching_policy':'task-shape-v1: same modules, operation, complexity, features and output schema; heuristic request shape, not independent capability certification'} if task is not None else {}),
                    'policy':'Owner-rated quality, then fully priced mean cost, then latency. Unknown cost sorts last. No implicit provider fallback; an explicit request fallback is recorded separately.'}
