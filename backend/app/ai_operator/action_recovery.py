"""Conversational recovery from private confirmed receipts, through normal review."""
import re
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from sqlalchemy import or_
from app.ai_operator.service import digest

FORMAT='suite-recovery-v1'
PATTERN=r'\s*(?:(?:please|(?:can|could|would)\s+you(?:\s+please)?)\s+)?(?:undo|revert|roll\s+back)(?:\s+(?:(?:the|my)\s+)?(?:last\s+(?:change|action|update|edit)|that\s+(?:change|action|update)|it|run\s*#?\s*(?P<id>[1-9]\d*)))?\s*[.!?]*\s*'


def intent(text):
    found=re.fullmatch(PATTERN,text,re.I)
    if found and found['id'] and (len(found['id'])>10 or int(found['id'])>2147483647):
        return None  # Suite execution IDs use the native PostgreSQL integer contract.
    return {'source_run_id':int(found['id']) if found['id'] else None} if found else None


def task_digest(record):
    from app.apps.crm.models import CRMTask
    # GET adds timeline/related panels whereas PATCH returns the native task.
    # Compare the complete task columns, not these different presentation envelopes.
    return digest({column.key:record.get(column.key) for column in CRMTask.__table__.columns})


def before_snapshot(step, record):
    if step.tool!='crm.update_task' or type(step.record_id) is not int:
        return None
    return {'tool':step.tool,'record_id':step.record_id,
            'before':{key:record[key] for key in step.payload if key in record}}


def record_completion(run,index,tool,response):
    proof=(run.snapshots or {}).get('recovery_before',{}).get(str(index))
    if tool!='crm.update_task' or not proof or response.get('id')!=proof['record_id']:
        return
    entries=(run.result or {}).get('recovery_evidence',{})
    run.result={**(run.result or {}),'recovery_evidence':{**entries,str(index):{
        **proof,'after_sha256':task_digest(response)}}}


def preview_available(db,user,source):
    from app.ai_operator.suite import owned
    from app.ai_agents.models import AiActionApproval
    ident=(source.result or {}).get('recovery_preview_id')
    if not ident:return
    old=owned(db,user,ident)
    approval=db.get(AiActionApproval,old.approval_id) if old.approval_id else None
    abandoned=old.status in {'failed','cancelled','superseded'} and not old.receipts and (not approval or approval.status in {'pending','cancelled'})
    if not abandoned:
        raise HTTPException(409,'This source already has a recovery preview. Open its existing conversation run to review, resume or inspect its receipts.')


def validate_source(db,user,run):
    packet=(run.result or {}).get('recovery') or {}
    if packet.get('format')!=FORMAT:return
    from app.ai_operator.suite import owned,Plan
    from app.ai_operator.saved_agents import enforce
    source=owned(db,user,packet['source_run_id'])
    if source.id>=run.id or source.status!='succeeded' or source.plan_hash!=packet['source_plan_hash'] or digest(source.plan)!=source.plan_hash:
        raise HTTPException(409,'Recovery source execution changed')
    if source.workspace_id!=run.workspace_id or source.scope_key!=run.scope_key or (source.result or {}).get('request',{}).get('conversation_id')!=(run.result or {}).get('request',{}).get('conversation_id'):
        raise HTTPException(409,'Recovery must retain its original private conversation and scope')
    if (source.result or {}).get('recovery_preview_id')!=run.id:
        raise HTTPException(409,'Recovery preview was replaced')
    enforce(db,user,source,Plan.model_validate(source.plan).steps)


def reserve(db,user,run,packet):
    from app.ai_operator.suite import owned
    source=owned(db,user,packet['source_run_id'],True)
    preview_available(db,user,source)
    source.result={**source.result,'recovery_preview_id':run.id}
    run.result={**run.result,'recovery':packet}


def check_target(run,index,record):
    if run is None:return
    packet=(run.result or {}).get('recovery') or {}
    target=next((r for r in packet.get('targets',[]) if r['inverse_step']==index),None)
    if target and target.get('after_sha256') and task_digest(record)!=target['after_sha256']:
        raise HTTPException(409,'Record changed after the source execution; prepare a new explicit action from current data')


async def prepare(db,user,data,parent,history,request,call):
    selected=intent(data.text)
    if parent and (parent.result or {}).get('recovery') and parent.status in {'needs_clarification','awaiting_approval'}:
        if re.fullmatch(r'\s*(?:please\s+)?(?:cancel|cancel\s+(?:(?:the|this)\s+)?(?:recovery|undo|draft)|never\s+mind|nevermind)[.!? ]*',data.text,re.I):
            from app.ai_operator.suite import Plan
            await call(request.app,request.headers.get('authorization',''),'POST',f'/ai-operator/suite/runs/{parent.id}/cancel')
            db.refresh(parent)
            return Plan(summary='Recovery draft cancelled. No recovery action executed.',steps=[]),None
        raise HTTPException(409,'Review or cancel the exact recovery draft before starting another request. Its recorded restoration values cannot be revised.')
    if selected is None:
        if re.match(r'\s*(?:(?:please|(?:can|could|would)\s+you(?:\s+please)?)\s+)?(?:undo|revert|roll\s+back)\b',data.text,re.I):
            from app.ai_operator.suite import Plan
            return Plan(summary='Request recovery separately, for example “undo the last change” or “undo run #123”. Review any additional update after recovery. No reversal was prepared.',steps=[]),None
        return None,None
    from app.ai_operator.suite import owned,Plan,Step
    from app.ai_operator.saved_agents import enforce
    if data.local_plan:raise HTTPException(422,'Conversational undo uses server execution evidence; omit a manual plan')
    if not data.conversation_id:raise HTTPException(422,'Open the original persistent conversation before requesting recovery')
    if parent and parent.status in {'needs_clarification','awaiting_approval'}:
        raise HTTPException(409,'Review or cancel the pending draft before requesting recovery')
    from app.ai_operator.suite_models import SuiteRun
    if selected['source_run_id']:
        source=owned(db,user,selected['source_run_id'])
        if (source.result or {}).get('request',{}).get('conversation_id')!=data.conversation_id:
            raise HTTPException(404,'Execution is not available in this conversation')
    else:
        source=db.query(SuiteRun).filter_by(user_id=user.id,workspace_id=data.workspace_id).filter(
            SuiteRun.result['request']['conversation_id'].as_integer()==data.conversation_id,
            or_(SuiteRun.receipts[0]['step'].as_integer().is_not(None),
                SuiteRun.status.in_(['queued','executing','waiting_pms','cancelling','paused','needs_reconciliation']))).order_by(SuiteRun.id.desc()).first()
    if not source:
        return Plan(summary='No confirmed action is available to recover in this conversation.',steps=[]),None
    source=owned(db,user,source.id)
    if source.status!='succeeded':
        return Plan(summary='This action is incomplete or needs reconciliation. Review its execution receipts before recovery.',steps=[]),None
    if source.workspace_id!=data.workspace_id or (source.result or {}).get('request',{}).get('agent_id')!=data.agent_id:
        raise HTTPException(409,'Continue in the original workspace and agent selection before recovering this action')
    if not source.plan_hash or digest(source.plan)!=source.plan_hash:
        raise HTTPException(409,'Recovery source plan changed')
    await run_in_threadpool(enforce,db,user,source,Plan.model_validate(source.plan).steps)
    preview_available(db,user,source)
    receipts={r['step']:r for r in source.receipts if r.get('status')=='succeeded'}
    inverses=[];targets=[];unsupported=[];seen=set()
    for position,step in reversed(list(enumerate(source.plan['steps'],1))):
        receipt=receipts.get(position,{})
        tool=step['tool']
        if receipt.get('tool')!=tool:
            unsupported.append('An action has no exact successful receipt');continue
        if tool=='crm.update_task':
            proof=(source.result or {}).get('recovery_evidence',{}).get(str(position))
            fields=step['payload'];ident=step.get('record_id')
            if not proof or proof.get('tool')!=tool or proof.get('record_id')!=ident or receipt.get('record_id')!=ident or set(proof['before'])!=set(fields) or ident in seen:
                unsupported.append('CRM task update lacks complete restorable before-values');continue
            seen.add(ident)
            current=await call(request.app,request.headers.get('authorization',''),'GET',f'/crm/tasks/{ident}')
            if task_digest(current)!=proof['after_sha256']:raise HTTPException(409,'Record changed after execution; review current values before recovery')
            inverses.append(Step(tool=tool,record_id=ident,payload=proof['before']))
            targets.append({'inverse_step':len(inverses),'source_step':position,'after_sha256':proof['after_sha256'],
                'tool':tool,'record_id':ident,'changes':[{'field':key,'current':current.get(key),'restore':value}
                    for key,value in proof['before'].items()]})
        elif tool=='pms.task_plan':
            child=(source.snapshots or {}).get('pms_children',{}).get(str(position))
            if not child or child.get('kind')!='task' or receipt.get('pms_run_id')!=child['id']:
                unsupported.append('PMS task action lacks its confirmed native execution');continue
            inverses.append(Step(tool='pms.undo',record_id=child['project_id'],payload={'run_id':child['id']}))
        else:unsupported.append(f'{tool} requires native manual recovery')
    if unsupported or not inverses:
        return Plan(summary=('No automatic reversal was prepared. '+'; '.join(dict.fromkeys(unsupported)))[:1900],steps=[]),None
    data.module=(source.result or {}).get('request',{}).get('module')
    data.project_id=(source.result or {}).get('request',{}).get('project_id')
    data.task_ids=[];data.context=[];data.provider='local'
    return Plan(summary=f'Restore supported changes from completed run #{source.id}.',steps=inverses),{
        'format':FORMAT,'source_run_id':source.id,'source_plan_hash':source.plan_hash,'targets':targets}
