"""Live private retrieval only. Synthetic uploads are deleted in finally."""
import json
import httpx
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite';chat=None;files=[]
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        login=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert login.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+login.json()['access_token']
        status=client.get(root+'/workspace/search-status');assert status.is_success and status.json()['embedding']['available']
        try:
            r=client.post(root+'/conversations',json={'title':'Synthetic local retrieval smoke'})
            assert r.is_success;chat=r.json()['id']
            for name,text in [('leave.txt','Annual leave requests require approval from the reporting manager before absence.'),('expenses.txt','Staff can claim reimbursement for approved business travel with receipts.'),('stock.txt','Warehouse inventory below the reorder threshold requires a purchase request.')]:
                r=client.post(root+f'/conversations/{chat}/attachments',files={'file':(name,text.encode(),'text/plain')})
                assert r.is_success;files.append(r.json()['id'])
            response=client.post(root+'/workspace/search',json={'conversation_id':chat,'query':'Who authorizes a vacation?','mode':'hybrid'})
            assert response.is_success,f'Retrieval HTTP {response.status_code}'
            data=response.json();assert data['semantic_used'] and data['items'][0]['label']=='leave.txt'
            assert data['items'][0]['file_id']==files[0] and data['items'][0]['href']==f'#bot-attachment-{files[0]}'
            checked=[]
            for tools in (['crm.tasks','crm.leads','crm.deals'],['pms.projects'],['hrms.directory','hrms.policies'],['srm.invoices','srm.inventory'],['fam.cost_centers','fam.vouchers']):
                r=client.post(root+'/workspace/search',json={'conversation_id':chat,'query':'Synthetic nonexistent delivery 143','mode':'lexical','include_uploads':False,'tools':tools})
                assert r.is_success,f'Native search HTTP {r.status_code}: {tools}'
                assert {p['tool'] for p in r.json()['records']}==set(tools)
                checked.extend(tools)
            print(json.dumps({'local_semantic_used':True,'hybrid_correct_source':True,'native_sources_checked':len(checked),'synthetic_files':len(files),'business_writes':0,'external_model_calls':0}),flush=True)
        finally:
            for ident in files:assert client.delete(root+f'/conversations/{chat}/attachments/{ident}').is_success
            if chat:assert client.delete(root+f'/conversations/{chat}').is_success


if __name__=='__main__':main()
