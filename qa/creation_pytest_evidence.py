"""Record successful real creation responses without payloads or credentials."""
import functools,json,os
from pathlib import Path
from urllib.parse import urlsplit
from starlette.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
_current='';_original=TestClient.request
_targets={r['endpoint'].rstrip('/') for r in json.loads((ROOT/'.local/creation-live/static-create-endpoints.json').read_text(encoding='utf8'))}
@functools.wraps(_original)
def tracked(self,method,url,*args,**kwargs):
 response=_original(self,method,url,*args,**kwargs)
 endpoint=urlsplit(str(url)).path.removeprefix('/api/v1').rstrip('/')
 if method.upper()=='POST' and endpoint in _targets and 200<=response.status_code<300:
  try:data=response.json()
  except ValueError:data={}
  ident=data.get('id',data.get('userId',data.get('user_id'))) if isinstance(data,dict) else None
  row={'test':_current,'endpoint':endpoint,'status':response.status_code,'id':ident,'kind':'real-api-create'}
  with (ROOT/'.local/creation-live/backend-save-evidence.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row)+'\n')
 return response

def pytest_configure(config):TestClient.request=tracked

def pytest_runtest_setup(item):
 global _current
 _current=item.nodeid

def pytest_unconfigure(config):TestClient.request=_original
