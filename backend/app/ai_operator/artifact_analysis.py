"""Authorized server analysis of saved versions or explicitly supplied drafts."""
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.ai_agents.api import _require_ai_rate_limit
from app.ai_agents.security import limits,company
from app.ai_operator import artifacts,artifact_charts as charts
from app.ai_operator.suite_tools import Strict

router=APIRouter(prefix='/suite/artifacts',tags=['Artifact analysis'])


class Preview(Strict):
    module:artifacts.Module
    workspace_id:int|None=Field(default=None,gt=0)
    body:artifacts.Body


def compute(body,snapshot,db,user,**options):
    if body['kind']!='table':raise HTTPException(422,'Select a table artifact for data analysis')
    try:result=charts.analyze(body,**options)
    except ValueError as error:raise HTTPException(422,str(error).split('\n')[0][:300]) from None
    return charts.bounded({**result,'snapshot':snapshot},limits(db,company(user))['max_result_bytes'])


@router.post('/analyze-preview')
def preview(data:Preview,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    artifacts.access(db,user,data.workspace_id,data.module)
    _require_ai_rate_limit(db,request,user,bucket='artifact_analysis')
    return compute(data.body.model_dump(mode='json'),{'state':'unsaved','module':data.module},db,user)


@router.get('/{ident}/analysis')
def analysis(ident:int,request:Request,revision:int|None=Query(default=None,ge=1),category_query:str=Query(default='',max_length=100),
    series_key:str|None=Query(default=None,max_length=64),order:Literal['input','category','value_desc']|None=None,
    limit:int|None=Query(default=None,ge=1,le=50),chart_kind:Literal['bar','line','pie']|None=None,
    db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    item=artifacts.public(db,user,artifacts.owned(db,user,ident),revision)
    _require_ai_rate_limit(db,request,user,bucket='artifact_analysis')
    return compute(item,{'state':'saved','id':ident,'revision':item['revision'],'module':item['module']},db,user,
        category_query=category_query,series_key=series_key,order=order,limit=limit,chart_kind=chart_kind)
