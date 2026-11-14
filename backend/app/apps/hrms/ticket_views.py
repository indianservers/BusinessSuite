"""Private HRMS helpdesk views; never a grant to underlying tickets."""
from typing import Literal
from pydantic import Field,StrictBool
from app.ai_operator.suite_tools import Strict
from app.shared.private_views import NamedView,PrivateViews,view_router


class Filters(Strict):
    status:Literal['','Open','In Progress','Pending','Resolved','Closed']='Open'
    priority:Literal['','Low','Medium','High','Critical']=''
    assigned_to_me:StrictBool=False
    my_tickets:StrictBool=False


class Create(NamedView):
    filters:Filters=Field(default_factory=Filters)


class Edit(Create):
    revision:int=Field(ge=1)


store=PrivateViews('hrms','helpdesk_tickets',Filters)
access,personal,public,listing,create_record=store.access,store.personal,store.public,store.listing,store.create_record
router=view_router(store,'/ticket-views',Create,Edit)
