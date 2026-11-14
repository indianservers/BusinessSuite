"""Private typed views reuse pipeline preferences, native permissions and revisions."""
import re
from pydantic import BaseModel,ConfigDict,Field,field_validator
from fastapi import APIRouter,Depends,HTTPException,Query,Header,Response
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.shared import pipeline_workspace as pipeline


class NamedView(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=60)

    @field_validator('name')
    @classmethod
    def name_valid(cls,value):
        value=value.strip()
        if not value or re.search(r'[\x00-\x1f\ud800-\udfff]',value):raise ValueError('Choose a plain view name')
        return value


class PrivateViews:
    def __init__(self,module,scope,filters):
        self.module,self.scope,self.filters=module,scope,filters

    def access(self,db,user):pipeline.access(db,user,self.module,self.scope)


    def personal(self,db,user,lock=False):
        from app.shared.models import ServicePolicy
        org=pipeline.tenant(user)
        query=db.query(ServicePolicy).filter_by(scope_key=pipeline.policy_key(self.module,self.scope,org,user.id),organization_id=org,kind='pipeline_ui')
        if lock:
            db.query(User.id).filter_by(id=user.id).with_for_update().one()
            query=query.with_for_update().populate_existing()
        return query.first()


    def public(self,value):
        if value.get('shared') is not False or not re.fullmatch(r'[a-f0-9]{32}',str(value.get('id',''))):raise ValueError('Invalid private view')
        filters=self.filters.model_validate(value['preferences']['module_filters'])
        return {'id':value['id'],'name':value['name'],'filters':filters.model_dump()}


    def listing(self,db,user):
        self.access(db,user);row=self.personal(db,user);items=[];invalid=0
        for value in (row.values_json or {}).get('views',[]) if row else []:
            try:items.append(self.public(value))
            except (ValueError,KeyError,TypeError):invalid+=1
        return {'items':items,'revision':row.version if row else 0,'limit':30,'unsupported_views':invalid}


    def create_record(self,db,user,data,*,commit=True,expected_revision=None):
        self.access(db,user)
        if expected_revision is not None:
            current=self.personal(db,user,True)
            if (current.version if current else 0)!=expected_revision:raise HTTPException(409,'View collection changed before creation')
        value=pipeline.ViewInput(name=data.name,shared=False,preferences=pipeline.Preferences(module_filters=data.filters.model_dump()))
        result=pipeline.create_view_record(self.module,self.scope,value,db,user,commit=commit)
        return self.public(result)



    def edit_record(self,db,user,ident,data,*,commit=True):
        self.access(db,user);row=self.personal(db,user,True)
        if not row:raise HTTPException(404,'Private view not found')
        if row.version!=data.revision:raise HTTPException(409,'Views changed; reload before saving')
        values=list(row.values_json.get('views',[]));current=next((value for value in values if value.get('id')==ident),None)
        if not current:raise HTTPException(404,'Private view not found')
        if any(value['id']!=ident and value['name'].casefold()==data.name.casefold() for value in values):raise HTTPException(409,'A view with that name already exists')
        replacement={**current,'name':data.name,'shared':False,'preferences':pipeline.Preferences(module_filters=data.filters.model_dump()).model_dump()}
        pipeline.write_policy(db,self.module,self.scope,user,{'views':[replacement if value['id']==ident else value for value in values]},commit=commit)
        return self.listing(db,user)

    def remove_record(self,db,user,ident,revision,*,commit=True):
        self.access(db,user);row=self.personal(db,user,True)
        if not row:raise HTTPException(404,'Private view not found')
        if row.version!=revision:raise HTTPException(409,'Views changed; reload before removing')
        values=list(row.values_json.get('views',[]))
        if not any(value.get('id')==ident for value in values):raise HTTPException(404,'Private view not found')
        pipeline.write_policy(db,self.module,self.scope,user,{'views':[value for value in values if value.get('id')!=ident]},commit=commit)
        return self.listing(db,user)


def view_router(store,prefix,Create,Edit,Import=None):
    def expected_scope(user=Depends(get_current_user),expected_user:int|None=Header(default=None,alias='X-Task-View-User'),
                       expected_company:int|None=Header(default=None,alias='X-Task-View-Company')):
        # Preconditions do not grant identity or access.
        if expected_user is not None and expected_user!=user.id or expected_company is not None and expected_company!=pipeline.tenant(user):
            raise HTTPException(409,'View account or company changed; reload before continuing')
    router=APIRouter(prefix=prefix,tags=['Private saved views'],dependencies=[Depends(expected_scope)])

    @router.get('')
    def views(response:Response,db=Depends(get_db),user=Depends(get_current_user)):
        response.headers['Cache-Control']='private, no-store'
        return store.listing(db,user)

    @router.post('',status_code=201)
    def create(data:Create,db=Depends(get_db),user=Depends(get_current_user)):
        store.create_record(db,user,data);return store.listing(db,user)

    @router.put('/{ident}')
    def edit(ident:str,data:Edit,db=Depends(get_db),user=Depends(get_current_user)):
        return store.edit_record(db,user,ident,data)

    @router.delete('/{ident}')
    def remove(ident:str,revision:int=Query(ge=1),db=Depends(get_db),user=Depends(get_current_user)):
        return store.remove_record(db,user,ident,revision)

    if Import is not None:
        @router.post('/import-browser')
        def import_browser(data:Import,db=Depends(get_db),user=Depends(get_current_user)):
            store.access(db,user);store.personal(db,user,True);imported=retained=0
            try:
                for item in data.views:
                    existing=next((value for value in store.listing(db,user)['items'] if value['name'].casefold()==item.name.casefold()),None)
                    if existing:
                        if existing['filters']!=item.filters.model_dump():raise HTTPException(409,'A browser view conflicts with a server view; rename it before importing')
                        retained+=1;continue
                    store.create_record(db,user,item,commit=False);imported+=1
                db.commit()
            except Exception:
                db.rollback();raise
            return {**store.listing(db,user),'imported':imported,'retained':retained}
    return router
