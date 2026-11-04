"""Run the real frontend against the real isolated API, with provider transport faked.

Opt in: WHATSAPP_HUB_BROWSER=1 pytest tests/test_whatsapp_hub_browser_e2e.py -q
Requires the local Vite server (WHATSAPP_QA_ORIGIN, default port 5191).
"""
import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import pytest
from tests.test_communication_engagement import customer_thread
from tests.test_pms_workspaces import middleware_database
from test_identity_utils import own_workflow_records
from app.services import whatsapp_workspace as wa,whatsapp_media
from app.shared.whatsapp_models import WhatsAppConnection,WhatsAppMessage,WhatsAppContact
from app.apps.crm.models import CRMCompany,CRMPipeline,CRMPipelineStage,CRMDeal,CRMQuotation,CRMNote
from app.apps.project_management.models import PMSProject,PMSTask
from app.apps.srm.models import SRMInvoice

pytestmark=pytest.mark.skipif(os.environ.get('WHATSAPP_HUB_BROWSER')!='1',reason='Opt-in browser integration test')

def test_real_chat_workflows(client,db,customer_thread,middleware_database,monkeypatch):
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    company=CRMCompany(organization_id=1,branch_id=branch.id,name='Sandbox account')
    pipeline=CRMPipeline(organization_id=1,name='Sandbox sales')
    project=PMSProject(organization_id=1,project_key='HUBQA',name='Sandbox delivery')
    db.add_all([company,pipeline,project]);own_workflow_records(db,company,pipeline,project)
    stage=CRMPipelineStage(organization_id=1,pipeline_id=pipeline.id,name='New',stage_type='open')
    db.add(stage);own_workflow_records(db,stage)
    record.company_id=company.id;contact.consent='opted_in'
    messages[0].provider_message_id='wamid.sandbox.original'
    connection=db.query(WhatsAppConnection).filter_by(organization_id=1).one()
    connection.token_ciphertext=wa.protect('sandbox-token-only')
    db.commit()
    from app.core.config import settings
    monkeypatch.setattr(settings,'CRM_WHATSAPP_APP_SECRET','sandbox-webhook-secret')
    monkeypatch.setattr(settings,'CRM_WHATSAPP_VERIFY_TOKEN','sandbox-verify-token')
    recipient.phone='+'+contact.recipient;recipient.preferences={'whatsapp.marketing':True};db.commit()
    campaign=client.post('/api/v1/communication/customers/automations',headers=headers,json={'name':'Sandbox campaign','trigger':'campaign','purpose':'marketing','channel':'whatsapp','subject':'Sandbox update','body':'Hello {{name}}','status':'active','whatsapp_template':{'name':'sandbox_update','language':{'code':'en'},'components':[{'type':'body','parameters':[{'type':'text','text':'{{name}}'}]}]}})
    assert campaign.status_code==201,campaign.text
    calls=[]
    template={'id':'100','name':'sandbox_update','language':'en','status':'APPROVED','category':'UTILITY','components':[{'type':'BODY','text':'Hello {{1}}, your update is ready.'}]}
    def graph(self,method,path,**kwargs):
        if method=='GET' and path.endswith('/message_templates'):return {'data':[template]}
        if method=='POST' and path.endswith('/messages'):
            calls.append(kwargs['payload']);return {'messages':[{'id':'wamid.sandbox.'+str(len(calls))}]}
        raise AssertionError('Unexpected provider operation: '+method+' '+path)
    monkeypatch.setattr(wa.WhatsAppGraph,'request',graph)
    monkeypatch.setattr(whatsapp_media,'upload',lambda connection,token,content,mime,name:{'id':'9988','kind':'document','mimeType':mime,'filename':name,'size':len(content)})
    monkeypatch.setattr('app.core.email.send_email',lambda *a,**k:pytest.fail('Email delivery is forbidden'))
    # Every request uses actual authentication, branch/tenant checks, domain services,
    # SQL persistence and validation. Only the outside provider is simulated.
    lock=threading.Lock();mutations=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def handle_api(self):
            body=self.rfile.read(int(self.headers.get('Content-Length','0')))
            request_headers={**headers}
            if self.headers.get('Content-Type'):request_headers['Content-Type']=self.headers['Content-Type']
            if self.headers.get('X-Hub-Signature-256'):request_headers['X-Hub-Signature-256']=self.headers['X-Hub-Signature-256']
            with lock:
                response=client.request(self.command,self.path,headers=request_headers,content=body)
                if self.command!='GET':mutations.append((self.command,self.path,response.status_code))
            self.send_response(response.status_code)
            for key in ('content-type','content-disposition','cache-control'):
                if key in response.headers:self.send_header(key,response.headers[key])
            self.send_header('Content-Length',str(len(response.content)));self.end_headers();self.wfile.write(response.content)
        do_GET=do_POST=do_PUT=do_PATCH=do_DELETE=handle_api
    class Bridge(ThreadingHTTPServer):
        request_queue_size=128
        def handle_error(self,request,client_address):
            import sys
            if isinstance(sys.exception(),(ConnectionResetError,ConnectionAbortedError,BrokenPipeError)):return
            super().handle_error(request,client_address)
    server=Bridge(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    env={**os.environ,'WHATSAPP_QA_BRIDGE':f'http://127.0.0.1:{server.server_port}','WHATSAPP_QA_FIXTURE':json.dumps({'campaignId':campaign.json()['id'],'recipientId':recipient.id,'contactId':contact.id,'personId':record.id,'pipelineId':pipeline.id,'stageId':stage.id,'userId':actor.id,'branchId':branch.id,'token':headers['Authorization'].split(' ',1)[1]})}
    root=Path(__file__).resolve().parents[2]
    try:
        result=subprocess.run(['node',str(root/'qa/whatsapp_hub_api_browser.cjs')],cwd=root,env=env,text=True,capture_output=True,timeout=240,encoding='utf-8')
        assert result.returncode==0,result.stdout+'\n'+result.stderr+'\nAPI mutations: '+str(mutations)
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    assert len(calls)==3 # Quoted text, document and approved template; no Meta traffic.
    assert calls[0]['context']=={'message_id':'wamid.sandbox.original'}
    assert calls[1]['type']=='document'
    assert calls[2]['template']['components'][0]['parameters'][0]['text']=='Synthetic Customer'
    from app.apps.communication.customer_models import CustomerDelivery
    delivery=db.query(CustomerDelivery).filter_by(automation_id=campaign.json()['id']).one()
    assert delivery.status=='cancelled' and delivery.whatsapp_message_id is None
    assert db.query(WhatsAppMessage).filter_by(provider_message_id='wamid.sandbox.1').one().status=='read'
    assert db.query(CRMNote).filter_by(contact_id=record.id,body='Sandbox internal note').count()==1
    assert db.query(CRMDeal).filter_by(contact_id=record.id).count()==1
    assert db.query(CRMQuotation).filter_by(contact_id=record.id).count()==1
    assert db.query(SRMInvoice).count()==1
    assert db.query(PMSTask).count()==1
    unknown=db.query(WhatsAppContact).filter_by(recipient='919876543299').one()
    assert unknown.entity_type=='contact' and unknown.entity_id!=record.id
    assert db.query(WhatsAppMessage).filter_by(provider_message_id='wamid.sandbox.inbound-new').count()==1
    print(result.stdout.encode('ascii','backslashreplace').decode('ascii'))
