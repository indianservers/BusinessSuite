"""Private synthetic local import/share smoke; never calls a cloud model."""
import hashlib
import io
import json
import zipfile
import time
from pathlib import Path
from uuid import uuid4
import httpx
from PIL import Image
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.models.user import User
from app.ai_operator.models import OperatorApiLog


def main():
    assert make_url(settings.SQLALCHEMY_DATABASE_URI).host in {'localhost','127.0.0.1','::1'}
    root='/api/v1/ai-operator/suite';chat=artifact=share=run=dashboard=None;runs=[]
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            assert response.is_success,f'{method} {path}: HTTP {response.status_code}'
            return response
        auth=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD}).json()
        client.headers['Authorization']='Bearer '+auth['access_token']
        with SessionLocal() as db:
            actor=db.query(User).filter(User.email.ilike(settings.BOOTSTRAP_ADMIN_EMAIL)).one();actor_id=actor.id
        workspace=call('POST','/api/v1/project-management/workspaces',json={'name':'Synthetic local image share QA '+uuid4().hex[:8]}).json()['id']
        try:
            chat=call('POST',root+'/conversations',json={'workspace_id':workspace,'title':'Synthetic local import and self-share verification'}).json()['id']
            image=io.BytesIO();Image.new('RGBA',(4,3),'blue').save(image,format='PNG');content=image.getvalue()
            upload=call('POST',root+f'/conversations/{chat}/attachments',files={'file':('synthetic-logo.png',content,'image/png')}).json()
            run=call('POST',root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'CRM','workspace_id':workspace,
                'conversation_id':chat,'text':f'Import image file #{upload["id"]} called Synthetic logo'}).json()
            assert run['status']=='awaiting_approval' and run['plan']['steps'][0]['tool']=='crm.import_image'
            runs.append(run['id'])
            call('POST',root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']})
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                run=call('GET',root+f'/runs/{run["id"]}').json()
                if run['status'] not in {'queued','executing'}:break
                time.sleep(1)
            assert run['status']=='succeeded','Local import did not complete'
            artifact=run['receipts'][0]['artifact_id']
            preview=call('POST',root+'/artifact-shares/preview',json={'request_key':str(uuid4()),'source_id':artifact,'source_revision':1,
                'audience':{'kind':'members','member_ids':[actor_id]}}).json();share=preview
            review=preview['pending']['preview_hash'];path=root+f'/artifact-shares/{share["id"]}'
            assert call('GET',path+'/preview-image',params={'preview_hash':review}).content==content
            share=call('POST',path+'/publish',json={'preview_hash':review}).json()
            assert call('GET',path+'/image',params={'revision':share['revision']}).content==content
            assert call('GET',path+'/download',params={'revision':share['revision'],'format':'png'}).content==content
            call('POST',path+'/revoke',json={'revision':share['revision']});share=None
            assert client.get(path+'/image').status_code==404
            assert call('GET',root+f'/artifacts/{artifact}/image').content==content
            run=call('POST',root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'CRM','workspace_id':workspace,
                'conversation_id':chat,'text':f'Create dashboard called Synthetic illustrated report: artifact #{artifact} v1'}).json()
            assert run['status']=='awaiting_approval';runs.append(run['id'])
            call('POST',root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']})
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                run=call('GET',root+f'/runs/{run["id"]}').json()
                if run['status'] not in {'queued','executing'}:break
                time.sleep(1)
            assert run['status']=='succeeded';dashboard=run['receipts'][0]['artifact_id']
            preview=call('POST',root+'/artifact-shares/preview',json={'request_key':str(uuid4()),'source_id':dashboard,'source_revision':1,
                'audience':{'kind':'members','member_ids':[actor_id]}}).json();share=preview
            path=root+f'/artifact-shares/{share["id"]}'
            share=call('POST',path+'/publish',json={'preview_hash':preview['pending']['preview_hash']}).json()
            for export_path in (root+f'/artifacts/{dashboard}/download',path+'/download'):
                for fmt in ('pdf','docx','xlsx'):
                    value=call('GET',export_path,params={'revision':1,'format':fmt}).content
                    if fmt=='pdf':
                        from pypdf import PdfReader
                        images=[image.image for page in PdfReader(io.BytesIO(value)).pages for image in page.images]
                        assert len(images)==1 and images[0].size==(4,3)
                    else:
                        with zipfile.ZipFile(io.BytesIO(value)) as archive:
                            assert any(archive.read(name)==content for name in archive.namelist() if '/media/' in name)
            call('POST',path+'/revoke',json={'revision':share['revision']});share=None
            assert client.get(path+'/download',params={'format':'pdf','revision':1}).status_code==404
            with SessionLocal() as db:
                assert db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(runs)).count()==0
            result={'status':'succeeded','workspace_id':workspace,'suite_run_ids':runs,'artifact_id':artifact,'dashboard_id':dashboard,
                'sha256':hashlib.sha256(content).hexdigest(),'reviewed_self_share':True,'revocation_verified':True,
                'private_and_shared_image_exports':['pdf','docx','xlsx'],'external_model_calls':0,'business_messages_sent':0}
            (Path(__file__).resolve().parents[2]/'.local/local-image-sharing-live-result.json').write_text(json.dumps(result,indent=2))
            print(json.dumps(result))
        finally:
            if share:call('POST',root+f'/artifact-shares/{share["id"]}/revoke',json={'revision':share['revision']})
            if not run or run['status'] not in {'queued','executing'}:
                if dashboard:call('DELETE',root+f'/artifacts/{dashboard}')
                if artifact:call('DELETE',root+f'/artifacts/{artifact}')
                if chat:call('DELETE',root+f'/conversations/{chat}')


if __name__=='__main__':main()
