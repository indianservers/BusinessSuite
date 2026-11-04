"""Profile one read-only request against the local configured database."""
import cProfile
import pstats
from pathlib import Path
from app.main import app
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.core.deps import get_current_user
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request
from app.shared.record_360 import queue
from sqlalchemy import event

path='/api/v1/record-360/work/queue/items'
def read():
    with SessionLocal() as db:
        request=Request({'type':'http','method':'GET','path':path,'query_string':b'','headers':[(b'x-suite-organization',b'1'),(b'x-suite-branch',b'6')],'state':{},'client':('127.0.0.1',1234),'server':('127.0.0.1',1534),'scheme':'http','app':app})
        actor=get_current_user(request,HTTPAuthorizationCredentials(scheme='Bearer',credentials=create_access_token(35)),db)
        try:
            user=next(actor)
            def options(execution):
                if execution.is_relationship_load:
                    values=getattr(execution.statement,'_with_options',())
                    print('loader options',len(values),'unique',len({id(value) for value in values}),flush=True)
            event.listen(db,'do_orm_execute',options)
            result=queue(1,5,'all','','pms_task',None,None,db,user,cursor_mode=True)
            print('items',len(result['items']))
        finally:actor.close()
profiler=cProfile.Profile()
try:profiler.runcall(read)
finally:
    with Path('../docs/qa/record-360/live/queue-profile.txt').open('w') as stream:
        pstats.Stats(profiler,stream=stream).strip_dirs().sort_stats('cumulative').print_stats(65)
