"""Direct, authenticated page actions sharing the local agent writing skills."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.ai_operator.local_writing import draft
from app.ai_operator.writing_corpus import SKILLS

router = APIRouter(prefix='/writing', tags=['Local AI writing'])


class WritingInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: str = Field(max_length=60)
    module: Literal['CRM', 'PMS', 'HRMS', 'SRM', 'FAM']
    text: str = Field(default='', max_length=16000)
    title: str = Field(default='', max_length=200)
    recipient: str = Field(default='', max_length=120)
    tone: Literal['professional', 'friendly', 'formal'] = 'professional'
    language: str = Field(default='English', min_length=1, max_length=60)
    workspace_id: int | None = Field(default=None, gt=0)


@router.post('/draft')
def generate(data: WritingInput, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_operator.suite import authorize, MODULES
    from app.access.service import check_background_access
    from app.ai_agents.api import _require_ai_rate_limit
    authorize(db, user, data.workspace_id, data.module)
    check_background_access(db, user, MODULES[data.module], 'view')
    _require_ai_rate_limit(db, request, user, bucket='local_writing')
    if data.action not in SKILLS:
        raise HTTPException(422, 'Unknown writing action')
    # Only caller-supplied, already-visible text is processed. This endpoint
    # never fetches arbitrary record IDs or introduces a second save/send path.
    return draft(data.action, data.text, title=data.title, recipient=data.recipient, tone=data.tone, language=data.language)
