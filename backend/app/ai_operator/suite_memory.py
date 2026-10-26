"""Private module/workspace memory using existing security-bound assistant storage."""
from typing import Literal
from fastapi import HTTPException
from pydantic import Field
from app.ai_operator.suite_tools import Strict
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_agents.security import company, verify

Module = Literal['HRMS','CRM','SRM','FAM']


class MemoryText(Strict):
    text: str = Field(min_length=1,max_length=2000)
    category: Literal['preference','decision','terminology','constraint'] = 'preference'


class MemoryInput(MemoryText):
    module: Module
    workspace_id: int | None = Field(default=None,gt=0)


def public(row):
    r=row.references
    return {'id':row.id,'module':r['module'],'text':r['text'],'category':r['category'],'workspace_id':row.workspace_id}


def rows(db,user,scope,module,workspace_id):
    query=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),
        workspace_id=workspace_id,deleted_at=None).order_by(AssistantConversation.id.desc())
    result=[]
    for row in query.filter(AssistantConversation.references['suite_memory'].as_boolean()==True,
                            AssistantConversation.references['module'].as_string()==module,
                            AssistantConversation.references['scope_key'].as_string()==scope).limit(100):
        try:verify(db,user,row.security_context,history=True)
        except HTTPException:continue
        result.append(row)
    return result


def create(db,user,scope,data):
    if len(rows(db,user,scope,data.module,data.workspace_id))>=50:
        raise HTTPException(422,'Forget an old memory before adding more; limit 50 per module/workspace')
    row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=data.workspace_id,
        title=f'{data.module} agent memory',references={'suite_memory':True,'scope_key':scope,
        'module':data.module,'text':data.text,'category':data.category})
    db.add(row)
    db.flush()
    return row
