"""Opt-in real-browser journey against the full ASGI app and isolated databases.

Start the candidate frontend preview, then set RUN_SIGNUP_BROWSER=1 to run.
The localhost bridge serializes the fixture session and never sends external mail.
"""
import os,json,threading,subprocess,secrets
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
import pytest
from tests.test_public_signup import platform_store,platform_headers,submit,PASSWORD
from app.platform_owner.models import PlatformSignupRequest,PlatformRecord
from app.models.email_outbox import EmailOutbox
from app.core.config import settings
from app.platform_owner.signup_journey import deliver

@pytest.mark.skipif(os.environ.get('RUN_SIGNUP_BROWSER')!='1',reason='Requires candidate frontend preview and Playwright')
def test_signup_approval_browser_journey(client,db,platform_store,monkeypatch):
 origin=os.environ.get('SIGNUP_FRONTEND_ORIGIN','http://127.0.0.1:5198')
 monkeypatch.setattr(settings,'FRONTEND_PUBLIC_URL',origin)
 lock=threading.RLock();key=secrets.token_hex(24)
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def dispatch(self):
   with lock:
    try:
     if self.path.startswith('/__qa/'):
      if self.headers.get('X-QA-Key')!=key:self.send_error(403);return
      query=parse_qs(urlparse(self.path).query);email=query.get('email',[''])[0]
      if self.path.startswith('/__qa/dispatch'):
       deliver(platform_store,db)
       value=[{'subject':m.subject,'body':m.body,'status':m.status} for m in db.query(EmailOutbox).filter_by(recipient=email)]
      elif self.path.startswith('/__qa/application'):
       row=platform_store.query(PlatformSignupRequest).filter_by(email=email).one()
       value={'id':row.id,'status':row.status,'version':row.version,'user_id':row.user_id}
      elif self.path.startswith('/__qa/concurrent-edit'):
       row=platform_store.query(PlatformSignupRequest).filter_by(email=email).one();row.version+=1;row.notes='A second reviewer updated this application';platform_store.commit();value={'updated':True}
      else:self.send_error(404);return
      body=json.dumps(value).encode();status=200;headers={'content-type':'application/json'}
     else:
      body=self.rfile.read(int(self.headers.get('content-length','0')))
      r=client.request(self.command,self.path,content=body or None,headers={k:v for k,v in self.headers.items() if k.lower() not in {'host','connection','content-length','accept-encoding'}})
      status=r.status_code;body=r.content;headers={'content-type':r.headers.get('content-type','application/json')}
     self.send_response(status)
     for k,v in headers.items():self.send_header(k,v)
     self.send_header('content-length',str(len(body)));self.end_headers();self.wfile.write(body)
    except (ConnectionAbortedError,ConnectionResetError,BrokenPipeError):
     pass
    except Exception as exc:
     self.send_response(500);self.end_headers();self.wfile.write(str(exc).encode())
  do_GET=dispatch;do_POST=dispatch;do_PUT=dispatch;do_PATCH=dispatch;do_DELETE=dispatch;do_OPTIONS=dispatch
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  env={**os.environ,'SIGNUP_FRONTEND_ORIGIN':origin,'SIGNUP_QA_API':f'http://127.0.0.1:{server.server_port}','SIGNUP_QA_KEY':key,'SIGNUP_QA_PASSWORD':PASSWORD}
  result=subprocess.run(['node','qa/signup_approval_30.cjs'],cwd=Path(__file__).resolve().parents[2],env=env,capture_output=True,text=True,timeout=240)
  assert result.returncode==0,result.stdout+'\n'+result.stderr
  print(result.stdout)
 finally:server.shutdown();server.server_close();thread.join(timeout=5)
