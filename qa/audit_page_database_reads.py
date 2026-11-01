"""Bounded page-data GET audit. Never invoke schedulers, sends, workers or mutations.

Credentials/tokens and response records are held only in memory. Reports contain
route templates, status codes and timings; real account data is never persisted.
"""
from pathlib import Path
import concurrent.futures
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date, timedelta
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
ENV=ROOT/'.local/indianservers-setup/production.env'
OUTPUT=ROOT/'.local/page-database-audit'
BASE='https://app.indianservers.com'
DENY=re.compile(r'/(?:internal|auth|oauth|callback|callbacks|cron|webhooks?|public|external|stream|events/stream|realtime|ws|downloads?|export|exports|pdf|render|preview|dispatch|send|sync|execute|process|trigger|reset|activate|verify|unsubscribe|track|pixel|redirect|worker|email-dispatch)(?:/|$)|\.(?:pdf|csv|xlsx|zip)$',re.I)
SIDE_EFFECT_WORDS=re.compile(r'(?:^|[_/\-])(?:mark|consume|acknowledge|approve|reject|run|retry|refresh|generate|issue|convert|test|validate|connect|disconnect|exchange|authorize)(?:$|[_/\-])',re.I)

def run():
 from dotenv import dotenv_values
 env=dotenv_values(ENV)
 for key,value in env.items():
  if value is not None:os.environ[key]=value
 # The saved app-specific configuration supplies the existing deployment signing
 # key. Use the same short-lived operational smoke-check mechanism as provisioning.
 for item in json.loads((ENV.parent/'app-env.json').read_text()):
  if item.get('value') is not None:os.environ[item['key']]=item['value']
 os.environ['ENVIRONMENT']='provisioning';os.environ['SERVERLESS']='false';os.environ['DATABASE_AUTO_MIGRATE']='false'
 os.chdir(ROOT/'backend');sys.path.insert(0,str(ROOT/'backend'))
 from sqlalchemy import create_engine,text
 from sqlalchemy.orm import Session
 from sqlalchemy.engine import make_url
 from sqlalchemy.pool import NullPool
 from app.module_registry import APP_MODULES
 from importlib import import_module
 for m in APP_MODULES.values():
  for name in m.model_modules:import_module(name)
 from app.db.base import Base
 from app.models.user import User
 from app.core.security import create_access_token
 from app.core.config import settings
 u=make_url(settings.SQLALCHEMY_DATABASE_URI)
 assert '.neon.tech' in (u.host or '')
 engine=create_engine(u,poolclass=NullPool,connect_args={'connect_timeout':10},hide_parameters=True)
 with Session(engine) as db:
  db.execute(text('SET TRANSACTION READ ONLY'))
  # Reuse the application's existing active administrator; create no accounts,
  # permissions, sessions, API keys, or durable access.
  actor=db.query(User).filter(User.is_superuser.is_(True),User.is_active.is_(True)).order_by(User.id).first()
  if not actor:raise RuntimeError('No existing active administrator for the smoke audit')
  token=create_access_token(str(actor.id),expires_delta=timedelta(minutes=25))
  db.rollback()
 engine.dispose()
 import httpx
 client=httpx.Client(base_url=BASE,headers={'Authorization':'Bearer '+token},timeout=25,follow_redirects=False)
 auth=client.get('/api/v1/auth/me');auth.raise_for_status()
 response=client.get('/api/v1/openapi.json');response.raise_for_status();schema=response.json()
 resources={};rows=[]
 previous={}
 if (OUTPUT/'results.json').exists():
  previous={r['path']:r for r in json.loads((OUTPUT/'results.json').read_text())}
 for path,operations in schema['paths'].items():
  op=operations.get('get')
  if not op or not path.startswith('/api/v1/'):continue
  row={'path':path,'module':path.split('/')[3],'status':None,'coverage':'pending','ms':None}
  if DENY.search(path) or SIDE_EFFECT_WORDS.search(path) or any(p in path for p in ('{token}','{code}','{secret}','{key}','{filename}','{file_path}','{path}')):
   row['coverage']='excluded_non_page_or_side_effect'
  old=previous.get(path)
  if old and old.get('coverage') not in {'pending','rate_limited','network_error','needs_existing_resource'}:
   row.update(old)
   # Rebuild only collection IDs needed by resource-specific pages. No private
   # response records or resource IDs are retained on disk.
   if old.get('status')==200 and '{' not in path and path.rstrip('/').split('/')[-1] in {'projects','tasks','workspaces','people','employees','companies','users','batches','teams','leads','deals','contacts','sprints','courses','notes','folders','forms','templates','assets','invoices','customers','vendors','departments','branches','products','quotes','quotations','documents'}:
    row['coverage']='pending'
  rows.append((row,op))
 OUTPUT.mkdir(parents=True,exist_ok=True)
 def save():
  (OUTPUT/'results.json').write_text(json.dumps([r for r,_ in rows],indent=2),encoding='utf-8')
 def params_for(op):
  params={}
  for p in op.get('parameters',[]):
   if p['in']!='query':continue
   d=p.get('schema',{});name=p['name']
   if name in {'limit','pageSize','page_size','per_page'}:params[name]=max(5,d.get('minimum',1));continue
   if not p.get('required'):continue
   if 'default' in d:params[name]=d['default']
   elif d.get('enum'):params[name]=d['enum'][0]
   elif name in {'start','start_date','date_from','from_date'}:params[name]=date.today().isoformat()
   elif name in {'end','end_date','date_to','to_date','date'}:params[name]=(date.today()+timedelta(days=7)).isoformat()
   else:return None
  return params
 def check(pair):
  row,op=pair
  if row['coverage']!='pending':return
  path=row['path'];known=True
  for name in re.findall(r'{([^}]+)}',path):
   plural={'person_id':'people','company_id':'companies','employee_id':'employees','task_id':'tasks','project_id':'projects','workspace_id':'workspaces','lead_id':'leads','deal_id':'deals','user_id':'users','batch_id':'batches'}.get(name,name.removesuffix('_id')+'s')
   prefix=path.split('/{'+name+'}')[0].rstrip('/')
   options=resources.get(prefix)
   if options is None:
    module_prefix='/'.join(path.split('/')[:4])
    choices=[v for k,v in resources.items() if k.startswith(module_prefix+'/') and k.rstrip('/').split('/')[-1]==plural]
    options=choices[0] if len(choices)==1 else None
   if not options:known=False;break
   path=path.replace('{'+name+'}',str(options[0]))
  if not known:row['coverage']='needs_existing_resource';return
  params=params_for(op)
  if params is None:row['coverage']='needs_required_filter';return
  time.sleep(1.5)
  started=time.monotonic()
  try:
   r=client.get(path,params=params)
   if r.status_code==429:
    time.sleep(min(45,max(2,int(r.headers.get('Retry-After','15')))))
    r=client.get(path,params=params)
    if r.status_code==429:
     row.update(status=429,coverage='rate_limited');return
   row.update(status=r.status_code,coverage='page_read',ms=round((time.monotonic()-started)*1000))
   if r.status_code==200 and 'application/json' in r.headers.get('content-type','') and len(r.content)<500_000:
    try:
     data=r.json();items=data if isinstance(data,list) else next((data[k] for k in ['items','data','results','employees','projects','workspaces','people','leads','deals'] if isinstance(data,dict) and isinstance(data.get(k),list)),[])
     ids=[i['id'] for i in items if isinstance(i,dict) and isinstance(i.get('id'),(int,str))]
     if ids:resources[row['path'].rstrip('/')]=ids[:3]
    except (ValueError,TypeError):pass
   if r.status_code>=500:print('FAIL',r.status_code,row['path'],flush=True)
  except httpx.HTTPError as e:row.update(coverage='network_error',error=type(e).__name__)
  time.sleep(.25)
 total=0
 for parameterized in [False,True]:
  batch=[pair for pair in rows if pair[0]['coverage']=='pending' and ('{' in pair[0]['path'])==parameterized]
  print('Checking',len(batch),'parameterized' if parameterized else 'list/dashboard','page reads',flush=True)
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   for _ in pool.map(check,batch):
    total+=1
    if total%25==0:
     save();print('Checked',total,'server failures',sum(isinstance(r['status'],int) and r['status']>=500 for r,_ in rows),flush=True)
 save();client.close()
 summary={'target':urlsplit(BASE).hostname,'inventory':len(rows),'coverage':dict(Counter(r['coverage'] for r,_ in rows)),'statuses':dict(Counter(str(r['status']) for r,_ in rows if r['status'] is not None)),'server_failures':[r for r,_ in rows if isinstance(r['status'],int) and r['status']>=500]}
 (OUTPUT/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':run()
