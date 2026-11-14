"""Opt-in live Gemini test on synthetic audio and a private QA workspace.

Never changes company provider configuration or sends business messages. The
workspace retains execution/usage audit evidence; its media override is disabled
afterward. Keys remain in server memory/storage and are never printed.
"""
import argparse
import json
from pathlib import Path
import time
from uuid import uuid4
import httpx
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.db.base import Base  # Register all relationships before ORM resolution.
from app.db.session import SessionLocal
from app.models.user import User
from app.ai_operator.models import OperatorProvider,OperatorApiLog
from app.ai_operator.provider_scope import resolve_provider


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--synthetic-wav',type=Path,required=True)
    parser.add_argument('--allow-gemini-transcription',action='store_true');args=parser.parse_args()
    if not args.allow_gemini_transcription:raise SystemExit('Explicit live inference flag required')
    assert make_url(settings.SQLALCHEMY_DATABASE_URI).host in {'localhost','127.0.0.1','::1'}
    from app.ai_operator.gemini_media import wav_duration
    audio=args.synthetic_wav.read_bytes();assert 0<wav_duration(audio)<=15,'Use a short synthetic speech fixture'
    root='/api/v1/ai-operator/suite';workspace=chat=artifact=attachment=run_id=None;stage='login'
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=90) as client:
        response=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert response.is_success,'Local login failed'
        client.headers['Authorization']='Bearer '+response.json()['access_token']
        try:
            stage='workspace'
            response=client.post('/api/v1/project-management/workspaces',json={'name':'Synthetic reviewed media QA '+uuid4().hex[:8]})
            assert response.status_code==201,'QA workspace creation failed'
            workspace=response.json()['id']
            stage='private capability'
            with SessionLocal() as db:
                actor=db.query(User).filter(User.email.ilike(settings.BOOTSTRAP_ADMIN_EMAIL)).one()
                source=resolve_provider(db,actor,'gemini')
                assert source and source.enabled and source.data_sharing_allowed,'No authorized Gemini configuration'
                from app.apps.project_management.workspaces import workspace_member
                _,member=workspace_member(db,workspace,actor,True);assert member.role=='Owner'
                override=OperatorProvider(scope_key=f'workspace:{workspace}',provider='gemini',model=source.model,
                    encrypted_key=source.encrypted_key,enabled=True,data_sharing_allowed=True,max_tokens=source.max_tokens,
                    updated_by=actor.id,media_settings={'transcription_enabled':True})
                db.add(override)
                from app.ai_agents.services.audit import AiAuditService
                AiAuditService(db).log(user=actor,agent_id=None,module='PMS',action='operator.provider.updated',
                    input_json={'scope':override.scope_key},output_json={'policy':'synthetic-media-only'},status='success')
                db.commit()
            stage='upload'
            response=client.post(root+'/conversations',json={'title':'Synthetic reviewed transcription verification','workspace_id':workspace})
            assert response.status_code==201,'Private conversation failed';chat=response.json()['id']
            response=client.post(root+f'/conversations/{chat}/attachments',files={'file':('synthetic-speech.wav',audio,'audio/wav')})
            assert response.status_code==201,'Synthetic audio upload failed';attachment=response.json()['id']
            stage='preview'
            response=client.post(root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'CRM',
                'workspace_id':workspace,'conversation_id':chat,'text':f'Transcribe audio file #{attachment}'})
            assert response.is_success,'Transcription planning failed';run=response.json();run_id=run['id']
            assert run['status']=='awaiting_approval' and not run['receipts'],'No exact media review'
            stage='reviewed execution'
            response=client.post(root+f'/runs/{run_id}/approve',json={'plan_hash':run['plan_hash']})
            assert response.is_success,'Media approval failed'
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                response=client.get(root+f'/runs/{run_id}');assert response.is_success,'Media run unavailable'
                run=response.json()
                if run['status'] not in {'queued','executing'}:break
                time.sleep(1)
            assert run['status']=='succeeded','Media execution ended '+run['status']
            artifact=run['receipts'][0]['artifact_id'];stage='artifact verification'
            response=client.get(root+f'/artifacts/{artifact}');assert response.is_success
            item=response.json();text=item['content']
            assert 'delivery' in text.casefold() and 'monday' in text.casefold(),'Synthetic speech was not recognized'
            assert item['provenance']['media']['source_sha256']
            with SessionLocal() as db:
                logs=db.query(OperatorApiLog).filter_by(suite_run_id=run_id,purpose='media_transcription').all()
                assert len(logs)==1 and logs[0].status=='success' and logs[0].estimated_cost is None
                usage={'model':logs[0].model,'input_tokens':logs[0].input_tokens,'output_tokens':logs[0].output_tokens}
            print(json.dumps({'workspace_id':workspace,'run_id':run_id,'artifact_id':artifact,'status':'succeeded',
                'transcript':text,'usage':usage,'external_model_calls':1,'business_messages_sent':0,'company_settings_changed':False}),flush=True)
        except Exception as error:
            print(json.dumps({'stage':stage,'error_type':type(error).__name__,'workspace_id':workspace,'run_id':run_id}),flush=True)
            raise
        finally:
            if workspace:
                with SessionLocal() as db:
                    override=db.query(OperatorProvider).filter_by(scope_key=f'workspace:{workspace}',provider='gemini').first()
                    if override:override.enabled=False;override.data_sharing_allowed=False;override.media_settings={};db.commit()
            # A still-running model operation must retain its source for diagnosis.
            if run_id:
                current=client.get(root+f'/runs/{run_id}')
                terminal=current.is_success and current.json()['status'] in {'succeeded','failed','cancelled','needs_reconciliation','paused'}
            else:terminal=True
            if terminal:
                if artifact:assert client.delete(root+f'/artifacts/{artifact}').is_success
                if attachment:assert client.delete(root+f'/conversations/{chat}/attachments/{attachment}').is_success
                if chat:assert client.delete(root+f'/conversations/{chat}').is_success


if __name__=='__main__':main()
