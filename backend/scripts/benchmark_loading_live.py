"""Read-only local HTTP timings; never saves credentials or response records."""
import json
import sys
from time import perf_counter
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from datetime import timedelta
from app.db.init_db import DEMO_USERS
from app.core.security import create_access_token

root='http://127.0.0.1:1534/api/v1'
admin=next(row for row in DEMO_USERS if row['email']=='admin@aihrms.com')
request=Request(root+'/auth/login',data=json.dumps({'email':admin['email'],'password':admin['password']}).encode(),headers={'Content-Type':'application/json'})
with urlopen(request,timeout=90) as response: token=json.load(response)['access_token']
viewer=create_access_token(35,expires_delta=timedelta(minutes=10))
paths=[('admin','/access/me'),('admin','/branches/context'),('admin','/crm/contacts?per_page=10'),
       ('admin','/srm/business/customers?per_page=25'),('admin','/record-360/company/290?source=srm'),
       ('viewer','/record-360/work/queue/items?view=all&source_filter=pms_task&cursor_mode=true&per_page=5')]
results=[]
for actor,path in paths:
    times=[]
    for iteration in range(2):
        started=perf_counter()
        request=Request(root+path,headers={'Authorization':'Bearer '+(token if actor=='admin' else viewer),'X-Suite-Organization':'1','X-Suite-Branch':'6'})
        try:
            with urlopen(request,timeout=90) as response:
                response.read();status=response.status
        except HTTPError as error:
            status=error.code;error.read()
        times.append({'ms':round((perf_counter()-started)*1000),'status':status})
    results.append({'actor':actor,'path':path,'samples':times})
    print(results[-1],flush=True)
output=Path('../docs/qa/record-360/live/loading-'+(sys.argv[1] if len(sys.argv)>1 else 'after')+'.json')
output.write_text(json.dumps(results,indent=2))
