"""Synthetic local writing previews only; never insert, save or send a draft."""
import argparse
import json
import httpx
from app.core.config import settings


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--gemini',action='store_true');args=parser.parse_args()
    source='Please review reference R-742 on Friday.'
    with httpx.Client(base_url='http://127.0.0.1:1534/api/v1',timeout=70) as client:
        response=client.post('/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert response.is_success,'Local application login failed'
        client.headers['Authorization']='Bearer '+response.json()['access_token']
        def generate(action,provider):
            response=client.post('/ai-operator/writing/draft',json={'module':'CRM','action':action,'text':source,'language':'Hindi','provider':provider})
            assert response.is_success,f'Writing preview HTTP {response.status_code}'
            return response.json()
        local=generate('improve','local')
        assert local['cloud_calls']==0 and 'R-742' in local['text']
        report={'local_server_preview':True,'business_actions_submitted':0,'drafts_saved':0,'external_model_requests':0}
        if args.gemini:
            response=client.get('/ai-operator/suite/providers');assert response.is_success,'Provider catalog unavailable'
            available=next((p for p in response.json()['items'] if p['provider']=='gemini'),None)
            assert available and available['enabled'] and available['data_sharing_allowed'],'Gemini is unavailable in this scope'
            improved=generate('improve','gemini');translated=generate('translate','gemini')
            assert improved['method']==translated['method']=='server-language-model'
            assert 'R-742' in improved['text'] and 'R-742' in translated['text'],'A source reference was changed'
            assert any('\u0900'<=letter<='\u097f' for letter in translated['text']),'No Hindi translation returned'
            report.update(gemini_server_rewrite=True,gemini_server_translation=True,source_reference_preserved=True,external_model_requests=2,engine=improved['engine'])
        print(json.dumps(report),flush=True)


if __name__=='__main__':main()
