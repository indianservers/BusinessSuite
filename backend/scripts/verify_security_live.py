"""Bounded live checks. This script refuses any target except the isolated QA server."""
import json
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import httpx
import jwt
from datetime import date
from websockets.sync.client import connect

TARGET='http://127.0.0.1:1549'
results=[]


def check(name,response,expected):
    statuses=expected if isinstance(expected,tuple) else (expected,)
    results.append({'case':name,'status':response.status_code,'expected':list(statuses),'passed':response.status_code in statuses})


with httpx.Client(base_url=TARGET,timeout=15,follow_redirects=False) as client:
    check('Anonymous employee directory',client.get('/api/v1/employees/'),403)
    for folder in ('employee_docs','certificates','_private'):
        check('Anonymous restricted file: '+folder,client.get('/uploads/'+folder+'/synthetic-canary.txt'),404)
    check('Forged download capability',client.get('/api/v1/files/blob',params={'token':'synthetic-invalid'}),403)
    check('Scheduler without secret',client.get('/api/v1/internal/cron'),401)
    check('Intern cannot use HRMS login',client.post('/api/v1/auth/login',json={'email':'intern@example.com','password':'InternHub@123','module':'hrms'}),403)
    login=client.post('/api/v1/auth/login',json={'email':'intern@example.com','password':'InternHub@123','module':'interns_hub'})
    check('Approved intern login',login,200)
    token=login.json()
    headers={'Authorization':'Bearer '+token['access_token']}
    check('Intern own profile',client.get('/api/v1/interns-hub/me',headers=headers),200)
    check('Intern own assignments',client.get('/api/v1/interns-hub/tasks',headers=headers),200)
    check('Intern token blocked at HRMS',client.get('/api/v1/employees/',headers=headers),403)
    check('Intern cannot review applications',client.get('/api/v1/interns-hub/admin/applications',headers=headers),403)
    check('Intern cannot administer batches',client.get('/api/v1/interns-hub/management/batches',headers=headers),403)
    websocket_status=None
    try:
        with connect(TARGET.replace('http://','ws://')+'/api/v1/project-management/realtime?token='+token['access_token'],open_timeout=5):
            websocket_status=101
    except Exception as error:
        websocket_status=getattr(getattr(error,'response',None),'status_code',None) or getattr(error,'code',None)
    results.append({'case':'Intern portal token rejected at PMS WebSocket','status':websocket_status,'expected':[403,1008],'passed':websocket_status in (403,1008)})
    access_log=Path(__file__).resolve().parents[2]/'docs/qa/shared-batch-workflow/security-qa-server.log'
    results.append({'case':'WebSocket access token omitted from server logs','passed':token['access_token'] not in access_log.read_text(encoding='utf-8',errors='replace')})
    check('Client score tampering rejected',client.post('/api/v1/interns-hub/tasks/1/submissions',headers=headers,json={'score':100,'status':'Approved'}),422)
    check('Logout',client.post('/api/v1/interns-hub/logout',headers=headers),200)
    check('Access replay after logout',client.get('/api/v1/interns-hub/me',headers=headers),401)
    check('Refresh replay after logout',client.post('/api/v1/auth/refresh',json={'refresh_token':token['refresh_token']}),401)
    admin=client.post('/api/v1/auth/login',json={'email':'admin@example.com','password':'AdminHub@123','module':'hrms'})
    check('Legitimate administrator login',admin,200)
    headers={'Authorization':'Bearer '+admin.json()['access_token']}
    check('Administrator directory',client.get('/api/v1/employees/',headers=headers),200)
    check('Employee account requires explicit password',client.post('/api/v1/employees/',headers=headers,json={'first_name':'Synthetic','last_name':'No Default','date_of_joining':str(date.today()),'create_user_account':True,'user_email':'qa-no-default@example.com'}),422)
    directory=client.get('/api/v1/employees/',headers=headers).json()['items']
    employee_id=next(item['id'] for item in directory if item['employee_id']=='QA-INT-001')
    uploaded=client.post(f'/api/v1/employees/{employee_id}/documents',headers=headers,data={'document_type':'Synthetic QA'},files={'file':('synthetic-security.pdf',b'%PDF-1.4 SYNTHETIC QA ONLY','application/pdf')})
    check('Authorized private upload',uploaded,201)
    link=uploaded.json()['file_url']
    assert urlsplit(link).netloc==urlsplit(TARGET).netloc
    capability=parse_qs(urlsplit(link).query)['token'][0]
    download=client.get(link)
    check('Authorized private capability download',download,200)
    results.append({'case':'Private download attachment and cache headers','passed':download.headers.get('content-disposition','').startswith('attachment') and download.headers.get('cache-control')=='private, no-store' and download.content.startswith(b'%PDF-')})
    path=jwt.decode(capability,options={'verify_signature':False})['path']
    check('Anonymous direct path of uploaded file',client.get('/uploads/'+path),404)
    server_log=Path(__file__).resolve().parents[2]/'docs/qa/shared-batch-workflow/security-qa-server.log'
    results.append({'case':'Private capability omitted from server access logs','passed':capability not in server_log.read_text(encoding='utf-8',errors='replace')})
    check('Storage path re-signing rejected',client.post('/api/v1/documents/certificates/exports',headers=headers,params={'output_file_url':'/uploads/employee_docs/synthetic-canary.txt'}),422)
    invalid=client.post('/api/v1/interns-hub/application-uploads',data={'category':'Identity'},files={'file':('synthetic.pdf',b'not a PDF','application/pdf')})
    check('Invalid document signature',invalid,422)
    response=client.get('/api/v1/auth/me',headers=headers)
    results.append({'case':'Sensitive API security headers','passed':response.headers.get('cache-control')=='private, no-store' and response.headers.get('x-content-type-options')=='nosniff'})
output=Path(__file__).resolve().parents[2]/'docs/qa/shared-batch-workflow/security-live-http.json'
output.write_text(json.dumps({'target':TARGET,'data':'Synthetic QA fixtures only','cases':results},indent=2),encoding='utf-8')
print(json.dumps({'passed':sum(item['passed'] for item in results),'total':len(results),'failed':[item['case'] for item in results if not item['passed']]}))
raise SystemExit(0 if all(item['passed'] for item in results) else 1)
