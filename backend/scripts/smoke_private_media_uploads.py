"""Live private upload/settings smoke; no inference, grants or business writes."""
import hashlib
import io
import json
import wave
from uuid import uuid4
import httpx
from PIL import Image
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite';chat=None;files=[]
    picture=io.BytesIO();Image.new('RGB',(4,3),'blue').save(picture,format='PNG')
    sound=io.BytesIO()
    with wave.open(sound,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000);audio.writeframes(b'\x00\x00'*8000)
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        response=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert response.is_success,'Local login failed'
        client.headers['Authorization']='Bearer '+response.json()['access_token']
        response=client.get(root+'/providers');assert response.is_success,'Provider metadata unavailable'
        provider=response.json()['items'];assert provider,'No configured provider'
        assert all('media' in row and 'encrypted_key' not in row for row in provider)
        try:
            response=client.post(root+'/conversations',json={'title':'Synthetic private media verification'})
            assert response.status_code==201,'Conversation creation failed'
            chat=response.json()['id']
            for name,content,kind in [('synthetic.png',picture.getvalue(),'image'),('synthetic.wav',sound.getvalue(),'audio')]:
                response=client.post(root+f'/conversations/{chat}/attachments',files={'file':(name,content)})
                assert response.status_code==201,'Media upload failed'
                item=response.json();files.append(item['id']);assert item['media']['kind']==kind
                assert 'content_b64' not in item
                response=client.get(root+f'/conversations/{chat}/attachments/{item["id"]}/download')
                assert response.is_success and hashlib.sha256(response.content).digest()==hashlib.sha256(content).digest()
                assert response.headers['cache-control']=='private, no-store'
                response=client.post(root+'/commands',json={'conversation_id':chat,'provider':'local','module':'CRM',
                    'request_key':str(uuid4()),'text':'Summarize this upload','attachment_ids':[item['id']]})
                assert response.status_code==422,'Raw media must not masquerade as extracted text'
            response=client.get(root+f'/conversations/{chat}');assert response.is_success
            assert {v['id'] for v in response.json()['attachments']}==set(files)
        finally:
            if chat:
                for ident in files:
                    response=client.delete(root+f'/conversations/{chat}/attachments/{ident}');assert response.is_success,'Private media cleanup failed'
                response=client.delete(root+f'/conversations/{chat}');assert response.is_success,'Conversation cleanup failed'
        print(json.dumps({'provider_media_metadata':True,'image_and_pcm_wav_upload':True,'private_restore_and_download':True,
            'raw_media_context_blocked':True,'private_sources_deleted':True,'conversation_archived':True,
            'provider_settings_changed':False,'external_model_calls':0,'business_approvals':0}))


if __name__=='__main__':main()
