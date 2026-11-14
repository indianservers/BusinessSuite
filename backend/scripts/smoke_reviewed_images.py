"""Opt-in live image generation/edit test; private synthetic workspace only."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4
import httpx
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.models.user import User
from app.ai_operator.models import OperatorProvider,OperatorApiLog
from app.ai_operator.provider_scope import resolve_provider


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--allow-gemini-image-calls',action='store_true')
    parser.add_argument('--image-model',choices=['gemini-3.1-flash-image','gemini-3.1-flash-lite-image','gemini-3-pro-image'],default='gemini-3.1-flash-image');args=parser.parse_args()
    if not args.allow_gemini_image_calls:raise SystemExit('Explicit live image inference flag required')
    assert make_url(settings.SQLALCHEMY_DATABASE_URI).host in {'localhost','127.0.0.1','::1'}
    root='/api/v1/ai-operator/suite';workspace=chat=artifact=current=None;runs=[];stage='login'
    directory=Path(__file__).resolve().parents[2]/'.local'
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=90) as client:
        response=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert response.is_success,'Local login failed';client.headers['Authorization']='Bearer '+response.json()['access_token']
        try:
            stage='workspace'
            response=client.post('/api/v1/project-management/workspaces',json={'name':'Synthetic reviewed image QA '+uuid4().hex[:8]})
            assert response.status_code==201;workspace=response.json()['id']
            with SessionLocal() as db:
                actor=db.query(User).filter(User.email.ilike(settings.BOOTSTRAP_ADMIN_EMAIL)).one();source=resolve_provider(db,actor,'gemini')
                assert source and source.enabled and source.data_sharing_allowed
                from app.apps.project_management.workspaces import workspace_member
                _,member=workspace_member(db,workspace,actor,True);assert member.role=='Owner'
                override=OperatorProvider(scope_key=f'workspace:{workspace}',provider='gemini',model=source.model,encrypted_key=source.encrypted_key,
                    enabled=True,data_sharing_allowed=True,max_tokens=source.max_tokens,updated_by=actor.id,
                    media_settings={'image_enabled':True,'image_model':args.image_model})
                db.add(override)
                from app.ai_agents.services.audit import AiAuditService
                AiAuditService(db).log(user=actor,agent_id=None,module='PMS',action='operator.provider.updated',
                    input_json={'scope':override.scope_key},output_json={'policy':'synthetic-image-only'},status='success');db.commit()
            response=client.post(root+'/conversations',json={'title':'Synthetic image generation and edit verification','workspace_id':workspace})
            assert response.status_code==201;chat=response.json()['id']
            outputs=[]
            for index,text in enumerate(['Create image called Synthetic shape: A single plain blue circle centered on a white background, flat illustration, no text or labels. Aspect ratio 1:1.',
                    'Make the circle red while preserving its position, size and white background. No text.'],1):
                stage='create preview' if index==1 else 'edit preview'
                response=client.post(root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'CRM',
                    'workspace_id':workspace,'conversation_id':chat,'text':text})
                assert response.is_success,'Image planning failed';current=response.json();runs.append(current['id'])
                assert current['status']=='awaiting_approval' and not current['receipts']
                stage='reviewed image execution'
                response=client.post(root+f'/runs/{current["id"]}/approve',json={'plan_hash':current['plan_hash']});assert response.is_success
                deadline=time.monotonic()+100
                while time.monotonic()<deadline:
                    response=client.get(root+f'/runs/{current["id"]}');assert response.is_success;current=response.json()
                    if current['status'] not in {'queued','executing'}:break
                    time.sleep(1)
                assert current['status']=='succeeded','Image execution ended '+current['status']
                receipt=current['receipts'][0]
                if artifact is None:artifact=receipt['artifact_id']
                assert receipt['artifact_id']==artifact and receipt['artifact_revision']==index
                response=client.get(root+f'/artifacts/{artifact}/image',params={'revision':index});assert response.is_success
                from app.ai_operator.gemini_media import image_bytes
                _,width,height=image_bytes(response.content,'image/png')
                path=directory/f'reviewed-live-image-v{index}.png';path.write_bytes(response.content)
                outputs.append({'revision':index,'width':width,'height':height,'sha256':hashlib.sha256(response.content).hexdigest(),'path':str(path)})
            assert outputs[0]['sha256']!=outputs[1]['sha256'],'Image edit produced identical bytes'
            with SessionLocal() as db:
                logs=db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(runs),OperatorApiLog.purpose=='media_image').all()
                assert len(logs)==2 and all(l.status=='success' and l.estimated_cost is None for l in logs)
                usage=[{'model':l.model,'input_tokens':l.input_tokens,'output_tokens':l.output_tokens} for l in logs]
            evidence={'status':'succeeded','workspace_id':workspace,'runs':runs,'artifact_id':artifact,'versions':outputs,'usage':usage,
                'reviewed_provider_calls':2,'company_settings_changed':False,'business_messages_sent':0}
            (directory/'reviewed-image-live-result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
            print(json.dumps(evidence),flush=True)
        except Exception as error:
            print(json.dumps({'stage':stage,'error_type':type(error).__name__,'workspace_id':workspace,'runs':runs}),flush=True);raise
        finally:
            if workspace:
                with SessionLocal() as db:
                    override=db.query(OperatorProvider).filter_by(scope_key=f'workspace:{workspace}',provider='gemini').first()
                    if override:override.enabled=False;override.data_sharing_allowed=False;override.media_settings={};db.commit()
            terminal=not current or current['status'] not in {'queued','executing'}
            if terminal:
                if artifact:assert client.delete(root+f'/artifacts/{artifact}').is_success
                if chat:assert client.delete(root+f'/conversations/{chat}').is_success


if __name__=='__main__':main()
