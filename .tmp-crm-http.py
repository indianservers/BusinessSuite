import json,requests
from pathlib import Path
a=json.loads(Path('backend/.tmp-crm-local-auth.json').read_text())
h={'Authorization':'Bearer '+a['token']}
for base in ['http://127.0.0.1:1534','http://127.0.0.1:5173']:
 try:
  r=requests.get(base+'/api/v1/crm/lead-management/meeting-metrics',headers=h,timeout=20)
  print(base,r.status_code,r.text[:800])
 except Exception as e: print(type(e).__name__)
