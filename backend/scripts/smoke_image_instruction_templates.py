"""Live private instruction-template review/clarification; no image inference."""
import io
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx
from PIL import Image
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite';chat=artifact=template=run=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs);assert response.is_success,f'{path}: HTTP {response.status_code}'
            return response.json()
        auth=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        client.headers['Authorization']='Bearer '+auth['access_token']
        workspace=call('POST','/api/v1/project-management/workspaces',json={'name':'Synthetic image instruction QA '+uuid4().hex[:8]})['id']
        try:
            chat=call('POST',root+'/conversations',json={'workspace_id':workspace,'title':'Synthetic image instruction template verification'})['id']
            stream=io.BytesIO();Image.new('RGBA',(4,3),'blue').save(stream,format='PNG')
            uploaded=call('POST',root+f'/conversations/{chat}/attachments',files={'file':('synthetic-blue.png',stream.getvalue(),'image/png')})
            def say(text):
                nonlocal run
                run=call('POST',root+'/commands',json={'request_key':str(uuid4()),'module':'CRM','provider':'local','workspace_id':workspace,'conversation_id':chat,'text':text})
                return run
            run=say(f'Import image file #{uploaded["id"]} called Synthetic source')
            assert run['status']=='awaiting_approval'
            call('POST',root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']})
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                run=call('GET',root+f'/runs/{run["id"]}')
                if run['status'] not in {'queued','executing'}:break
                time.sleep(1)
            assert run['status']=='succeeded';artifact=run['receipts'][0]['artifact_id']
            review=call('POST',root+'/artifact-templates/preview',json={'request_key':str(uuid4()),'name':'Synthetic reusable illustration',
                'source_artifact_id':artifact,'source_revision':1,'body':{'kind':'image_instruction','title':'{{customer}} illustration',
                    'content':'A {{color}} van for {{customer}}. No text.','aspect_ratio':'16:9'}})
            assert review['variables']==['customer','color'] and 'image_b64' not in str(review)
            template=call('POST',root+f'/artifact-templates/reviews/{review["id"]}/confirm',json={'preview_hash':review['preview_hash']})['template']['id']
            assert say(f'Use template #{template}')['status']=='needs_clarification' and 'customer' in run['plan']['question']
            assert say('Synthetic client')['status']=='needs_clarification' and 'color' in run['plan']['question']
            call('POST',root+f'/runs/{run["id"]}/cancel')
            run=call('GET',root+f'/runs/{run["id"]}');assert run['status']=='cancelled' and not run['receipts']
            evidence={'workspace_id':workspace,'template_id':template,'reviewed_save':True,'placeholder_followups':True,
                'generation_approval_submitted':False,'external_model_calls':0,'business_messages_sent':0}
            (Path(__file__).resolve().parents[2]/'.local/image-instruction-templates-live-result.json').write_text(json.dumps(evidence,indent=2))
            print(json.dumps(evidence))
        finally:
            if run and run['status'] in {'needs_clarification','awaiting_approval'}:call('POST',root+f'/runs/{run["id"]}/cancel')
            if not run or run['status'] not in {'queued','executing'}:
                if template:call('DELETE',root+f'/artifact-templates/{template}')
                if artifact:call('DELETE',root+f'/artifacts/{artifact}')
                if chat:call('DELETE',root+f'/conversations/{chat}')


if __name__=='__main__':main()
