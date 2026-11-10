"""Owner feedback is evidence for review, never permission or a training label."""
from typing import Literal
from datetime import datetime,timezone
from fastapi import HTTPException
from pydantic import Field
from app.ai_operator.suite_tools import Strict

class Feedback(Strict):
    request_key:str=Field(min_length=8,max_length=100)
    revision:int=Field(default=0,ge=0)
    rating:Literal['helpful','needs_correction']
    correction:str=Field(default='',max_length=2000)

def save(db,user,run,data):
    from app.ai_operator.service import digest
    from app.ai_operator.query_memory import sanitize
    from app.ai_operator.query_models import NlpQuery
    from app.ai_agents.services.audit import AiAuditService
    old=(run.result or {}).get('feedback') or {}
    fingerprint=digest(data.model_dump(mode='json'))
    if old.get('request_key')==data.request_key:
        if old.get('request_hash')!=fingerprint:raise HTTPException(409,'Feedback request key already used')
        return old
    if old.get('revision',0)!=data.revision:raise HTTPException(409,'Feedback changed; reload the latest reply')
    query=db.query(NlpQuery).filter_by(suite_run_id=run.id,user_id=user.id).first()
    value={'rating':data.rating,'correction':sanitize(data.correction) if data.correction else '',
        'revision':data.revision+1,'needs_review':True,'training_approved':False,
        'query_id':query.id if query and query.review_status!='deleted' else None,
        'request_key':data.request_key,'request_hash':fingerprint,'created_at':datetime.now(timezone.utc).isoformat()}
    run.result={**(run.result or {}),'feedback':value}
    AiAuditService(db).log(user=user,agent_id=None,module='CROSS',action='suite.feedback',
        input_json={'suite_run_id':run.id,'rating':data.rating},output_json={'revision':value['revision'],'training_approved':False},status='success')
    db.commit()
    return value
