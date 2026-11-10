"""Inspect the non-sensitive corpus used to fit the offline local intent model."""
from typing import Literal
from fastapi import APIRouter, Depends,Query
from sqlalchemy.orm import Session
from app.core.deps import get_current_user,get_db
from app.models.user import User
from app.ai_operator.local_corpus import VERSION,FAMILIES,examples

router=APIRouter(prefix='/suite',tags=['Local NLP model'])


@router.get('/local-model')
def model(module: Literal['CRM','PMS','Sales','HRMS'] | None=None,workspace_id:int|None=Query(None,gt=0),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    from app.ai_operator.local_tensorflow import status,runtime_scope
    authorize(db,user,workspace_id)
    runtime=status(runtime_scope(db,user,workspace_id))
    rows=examples()
    trained=runtime.get('training_commands') or {}
    if all(trained.get(key,0)>=1000 for key in ('CRM','PMS','HRMS')):
        from app.ai_operator.expanded_corpus import examples as expanded
        per_intent=60 if all(trained.get(key,0)>=1200 for key in ('CRM','PMS','HRMS')) else 50
        rows=expanded(per_intent)+[row for row in rows if row['module']=='Sales']
    return {'version':VERSION,'type':runtime['description'],'runtime':runtime,'cloud_required':False,
            'training_data':'Authored synthetic command examples only; no customer records or automatic learning from chats',
            'modules':{key:{'commands':sum(row['module']==key for row in rows),'intent_families':len(intents)} for key,intents in FAMILIES.items()},
            'examples':[r for r in rows if r['module']==module] if module else [],
            'limits':'Examples cover reads, reviewable task drafts and clarifications/handoffs. They are not 120 distinct capabilities per module. Unknown or ambiguous phrases abstain; every source/action still requires native permissions.'}
