"""Private CRM task views on the existing pipeline preference store."""
from pydantic import Field,StrictBool
from typing import Literal
from app.ai_operator.suite_tools import Strict
from app.shared.private_views import NamedView,PrivateViews,view_router

SCOPE='task_list'

class Filters(Strict):
    queue:Literal['all','open','completed','overdue','today','week','unscheduled']='all'
    status:str=Field(default='all',max_length=80)
    priority:str=Field(default='all',max_length=60)
    mine:StrictBool=False
    sort:Literal['due_date:asc','due_date:desc','created_at:desc','title:asc']='due_date:asc'
    search:str=Field(default='',max_length=300)


class Create(NamedView):
    filters:Filters=Field(default_factory=Filters)


class Edit(Create):
    revision:int=Field(ge=1)


class Import(Strict):
    views:list[Create]=Field(min_length=1,max_length=20)


store=PrivateViews('crm',SCOPE,Filters)
access,personal,public,listing,create_record=store.access,store.personal,store.public,store.listing,store.create_record
router=view_router(store,'/task-views',Create,Edit,Import)
