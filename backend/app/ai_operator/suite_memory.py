"""Private module/workspace memory using existing security-bound assistant storage."""
from typing import Literal
from datetime import datetime, timezone
import re
from fastapi import HTTPException
from pydantic import Field, field_validator
from app.ai_operator.suite_tools import Strict
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_agents.security import company, verify

Module = Literal['HRMS','CRM','SRM','FAM','PMS']


class MemoryText(Strict):
    text: str = Field(min_length=1,max_length=2000)
    category: Literal['preference','decision','terminology','constraint'] = 'preference'
    expires_at: datetime | None = None

    @field_validator('text')
    @classmethod
    def safe_text(cls,value):
        value=value.strip()
        if re.search(r'\b(?:AIza[A-Za-z0-9_-]{20,}|AQ\.[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,})\b',value):raise ValueError('Keep credentials in the server connection vault')
        if not value or re.search(r'(?i)(?:api[ _-]?key|password|secret|access[ _-]?token)(?:\s*[:=]|\s+is\b)|-----BEGIN .*PRIVATE KEY|\bBearer\s+\S+|\b(?:salary|bank account|aadhaar|social security)\b[^\n]{0,25}\d{3,}',value):
            raise ValueError('Store preferences and decisions, not credentials or sensitive personal records')
        return value

    @field_validator('expires_at')
    @classmethod
    def valid_expiry(cls,value):
        if value and (value.utcoffset() is None or value<=datetime.now(timezone.utc)):
            raise ValueError('Expiry must be a future time with timezone')
        return value


class MemoryInput(MemoryText):
    module: Module
    workspace_id: int | None = Field(default=None,gt=0)


def public(row):
    r=row.references
    return {'id':row.id,'module':r['module'],'text':r['text'],'category':r['category'],'workspace_id':row.workspace_id,
            'revision':r.get('revision',1),'expires_at':r.get('expires_at')}


def active(data):
    expiry=data.get('expires_at')
    if not expiry:return True
    try:
        parsed=datetime.fromisoformat(expiry)
        return parsed.utcoffset() is not None and parsed>datetime.now(timezone.utc)
    except (ValueError,TypeError):return False


def rows(db,user,scope,module,workspace_id):
    query=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),
        workspace_id=workspace_id,deleted_at=None).order_by(AssistantConversation.id.desc())
    result=[]
    for row in query.filter(AssistantConversation.references['suite_memory'].as_boolean()==True,
                            AssistantConversation.references['module'].as_string()==module,
                            AssistantConversation.references['scope_key'].as_string()==scope).limit(100):
        try:verify(db,user,row.security_context,history=True)
        except HTTPException:continue
        if active(row.references):result.append(row)
    return result


def create(db,user,scope,data):
    if len(rows(db,user,scope,data.module,data.workspace_id))>=50:
        raise HTTPException(422,'Forget an old memory before adding more; limit 50 per module/workspace')
    row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=data.workspace_id,
        title=f'{data.module} agent memory',references={'suite_memory':True,'scope_key':scope,
        'module':data.module,'text':data.text,'category':data.category,'revision':1,
        'expires_at':data.expires_at.isoformat() if getattr(data,'expires_at',None) else None})
    db.add(row)
    db.flush()
    return row
