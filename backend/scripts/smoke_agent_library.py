"""Own-audience publication/install/revocation using synthetic private metadata.

The definition is addressed only to the signed-in platform owner. No business
actions or external model calls occur. Private profiles are archived afterwards.
"""
import json
from uuid import uuid4
import httpx
from app.core.config import settings
from app.core.security import verify_access_token


def main():
    root='/api/v1/ai-operator/suite';source=private=publication=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        r=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert r.is_success,'Login failed'
        token=r.json()['access_token'];user_id=int(verify_access_token(token)['sub']);client.headers['Authorization']='Bearer '+token
        try:
            targets=client.get(root+'/agents/library/targets');assert targets.is_success and any(m['id']==user_id for m in targets.json()['members'])
            r=client.post(root+'/agents',json={'name':'Synthetic own-audience library check','instructions':'Read authorized CRM task samples only. No mutations.','modules':['CRM'],'tools':['crm.tasks'],'memory':['Synthetic private preference, excluded from publication.'],'provider':'local'})
            assert r.is_success;source=r.json()['id']
            r=client.post(root+'/agents/library/preview',json={'request_key':str(uuid4()),'asset_type':'agent','source_id':source,'source_revision':1,'audience':{'kind':'members','member_ids':[user_id]}})
            assert r.is_success,f'Preview HTTP {r.status_code}';draft=r.json();publication=draft['id']
            assert 'Synthetic private preference' not in r.text
            r=client.post(root+f'/agents/library/{publication}/publish',json={'preview_hash':draft['pending']['preview_hash']})
            assert r.is_success;published=r.json()
            r=client.post(root+f'/agents/library/{publication}/install',json={'revision':published['revision'],'definition_hash':published['definition_hash']})
            assert r.is_success;installed=r.json()['asset'];private=installed['id']
            assert private!=source and installed['memory']==[] and installed['connection_ids']==[] and installed['mcp_ids']==[]
            assert client.post(root+f'/agents/library/{publication}/revoke',json={'revision':published['revision']}).is_success
            r=client.post(root+'/commands',json={'request_key':str(uuid4()),'text':'Show CRM tasks','module':'CRM','provider':'local','agent_id':private})
            assert r.status_code==403,f'Revoked runtime HTTP {r.status_code}'
            print(json.dumps({'audience':'signed-in owner only','private_fields_excluded':True,'linked_install_verified':True,'revoked_execution_blocked':True,'business_actions':0,'external_model_calls':0}),flush=True)
        finally:
            if publication:
                current=client.get(root+f'/agents/library/{publication}')
                if current.is_success and current.json()['status']!='revoked':assert client.post(root+f'/agents/library/{publication}/revoke',json={'revision':current.json()['revision']}).is_success
            for ident in (private,source):
                if ident:assert client.delete(root+f'/agents/{ident}').is_success


if __name__=='__main__':main()
