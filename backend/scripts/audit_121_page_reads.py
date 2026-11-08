"""Replay each page's observed domain reads under anonymous and read-only sessions."""
import os,json,urllib.request,urllib.error,concurrent.futures
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/os.environ.get('AUDIT_OUTPUT','outputs/crud-permissions-121');BASE=os.environ.get('AUDIT_BASE_URL','http://127.0.0.1:1592')
def request(path,token=None,body=None):
 headers={'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 q=urllib.request.Request(BASE+path,headers=headers,data=json.dumps(body).encode() if body else None)
 try:
  with urllib.request.urlopen(q,timeout=40) as r:return r.status,json.loads(r.read())
 except urllib.error.HTTPError as e:return e.code,{}
 except Exception as e:return 0,{'error':str(e)}
_,auth=request('/api/v1/auth/login',body={'email':'reader@crudqa.example.com','password':'CrudQA@12345'})
token=auth['access_token']
rows=json.load(open(OUT/'browser-merged.json'));paths=sorted({r['path'] for row in rows for r in row['reads'] if r['path'].startswith('/api/v1/')})
def probe(path):
 anonymous,_=request(path);reader,_=request(path,token)
 return path,{'anonymous':anonymous,'reader':reader,'anonymous_denied':anonymous in [401,403],'server_error':anonymous==0 or reader==0 or anonymous>=500 or reader>=500}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=dict(pool.map(probe,paths))
json.dump({'endpoints':results,'pages':{r['route']:{p['path']:results[p['path']] for p in r['reads'] if p['path'] in results} for r in rows}},open(OUT/'page-permissions.json','w'),indent=2)
print(json.dumps({'endpoints':len(results),'anonymous_denied':sum(r['anonymous_denied'] for r in results.values()),'review':{p:r for p,r in results.items() if not r['anonymous_denied'] or r['server_error']}},indent=2))
