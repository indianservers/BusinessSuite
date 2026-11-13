"""Suite conversations reuse private assistant storage; action runs remain authoritative.

No client transcript is trusted as context. Every historical run is reauthorized.
"""
from fastapi import HTTPException
from datetime import datetime, timezone
from pydantic import Field
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_operator.suite_models import SuiteRun
from app.ai_operator.suite_tools import Strict
from app.ai_agents.security import company, verify


class ConversationInput(Strict):
    title: str = Field(default='New conversation', min_length=1, max_length=160)
    workspace_id: int | None = Field(default=None, gt=0)


def owned(db,user,ident):
    from app.ai_operator.suite import authorize
    row=db.query(AssistantConversation).execution_options(ai_owner_control=True).filter_by(id=ident,user_id=user.id,
        organization_id=company(user),deleted_at=None).first()
    if not row or not (row.references or {}).get('suite_conversation'):
        raise HTTPException(404,'Conversation not found')
    verify(db,user,row.security_context,history=True,control=True)
    if authorize(db,user,row.workspace_id,control=True)!=(row.references or {}).get('scope_key'):
        raise HTTPException(403,'Conversation scope changed')
    return row


def public(row):
    return {'id':row.id,'title':row.title,'workspace_id':row.workspace_id,'created_at':row.created_at}


def runs(db,user,row,limit=100):
    from app.ai_operator.suite import owned as owned_run
    values=db.query(SuiteRun).filter_by(user_id=user.id,scope_key=row.references['scope_key'],workspace_id=row.workspace_id).filter(
        SuiteRun.result['request']['conversation_id'].as_integer()==row.id).order_by(SuiteRun.id.desc()).limit(limit).all()
    # Fail closed rather than using hidden records as conversational memory.
    return list(reversed([owned_run(db,user,r.id,control=True) for r in values]))


def listing(db,user,workspace_id):
    from app.ai_operator.suite import authorize
    scope=authorize(db,user,workspace_id,control=True)
    values=db.query(AssistantConversation).execution_options(ai_owner_control=True).filter_by(user_id=user.id,organization_id=company(user),
        workspace_id=workspace_id,deleted_at=None).filter(
        AssistantConversation.references['suite_conversation'].as_boolean()==True,
        AssistantConversation.references['scope_key'].as_string()==scope).order_by(AssistantConversation.references['suite_last_active'].as_string().desc().nullslast(),AssistantConversation.id.desc()).limit(100)
    result=[]
    for row in values:
        try:verify(db,user,row.security_context,history=True,control=True)
        except HTTPException:continue
        result.append(public(row))
    return result


def create(db,user,data,commit=True):
    from app.ai_operator.suite import authorize
    scope=authorize(db,user,data.workspace_id)
    row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=data.workspace_id,
        title=data.title,references={'suite_conversation':True,'scope_key':scope,'suite_last_active':datetime.now(timezone.utc).isoformat()})
    db.add(row)
    if commit:db.commit();db.refresh(row)
    else:db.flush()
    return public(row)


def continue_completed(intent,parent,text):
    """Resolve singular task references only from successful, exact receipts.

    Never reuse a create intent (which would duplicate a completed operation),
    never infer IDs from prose, and leave ambiguous collections to clarification.
    """
    import re
    from app.ai_operator.local_nlp import Interpretation
    if parent.status!='succeeded':return intent
    if intent.intent not in {'tasks.priority','tasks.status','tasks.schedule','reminders.create'}:return intent
    if not re.search(r'\b(it|this task|that task|the task)\b',text,re.I) or intent.slots.get('record_id'):return intent
    receipts=[r for r in parent.receipts or [] if r.get('status')=='succeeded' and r.get('tool') in {'crm.create_task','crm.update_task','pms.create_task'} and type(r.get('record_id')) is int]
    ids={r['record_id'] for r in receipts}
    if len(ids)!=1:
        return Interpretation(intent.module,intent.intent,intent.confidence,intent.slots,'Which task ID do you mean? I cannot identify one completed task unambiguously.',intent.neural)
    slots={**intent.slots,'record_id':next(iter(ids))}
    if intent.intent=='reminders.create':slots['entity']='task'
    return Interpretation(intent.module,intent.intent,intent.confidence,slots,None,intent.neural)


def resolve_task_reference(text,history,module):
    """Rewrite a narrow singular reference for the existing local parser only."""
    import re
    if module not in {'CRM','PMS'} or not re.search(r'\b(?:it|this task|that task|the task)\b',text,re.I):return text
    if not re.search(r'\b(?:mark|set|change|update|schedule|remind|make|complete|finish)\b',text,re.I):return text
    if re.search(r'\b(?:task|record)\s*#?\s*\d+',text,re.I):return text
    for run in reversed(history):
        if (run.result or {}).get('request',{}).get('module')!=module or run.status!='succeeded':continue
        ids=set()
        for receipt in run.receipts or []:
            if receipt.get('status')!='succeeded':continue
            if receipt.get('tool') in {'crm.create_task','crm.update_task','pms.create_task'} and type(receipt.get('record_id')) is int:ids.add(receipt['record_id'])
            if receipt.get('tool')=='pms.task_plan':
                for nested in receipt.get('task_receipts') or []:
                    if type(nested.get('task_id')) is int:ids.add(nested['task_id'])
        if len(ids)==1:return re.sub(r'\b(?:this task|that task|the task|it)\b',f'task #{next(iter(ids))}',text,count=1,flags=re.I)
        # Do not reach behind a more recent ambiguous task batch.
        if ids:return text
    return text


def receipt_summary(history):
    completed=[r for r in history if r.receipts]
    if not completed:return 'No completed action receipts are recorded in this conversation.'
    parts=[]
    for run in completed[-8:]:
        for receipt in run.receipts:
            parts.append(f"{receipt.get('tool','Action')}: {receipt.get('status','recorded')}"+(f" (record #{receipt['record_id']})" if receipt.get('record_id') else ''))
    body='; '.join(parts)
    if len(body)>1700:body=body[:1700]+'… (additional outcomes remain in saved run receipts)'
    return 'Recorded action outcomes in this conversation: '+body+'. These are execution receipts, not a fresh check of current record state.'
