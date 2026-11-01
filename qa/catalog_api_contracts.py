"""Inventory API contracts without invoking handlers or touching business records."""
from pathlib import Path
import json,os,sys
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT/'backend');sys.path.insert(0,str(ROOT/'backend'))
from app.main import app
schema=app.openapi()
rows=[]
for path,operations in schema['paths'].items():
 for method,operation in operations.items():
  if method not in {'get','post','put','patch','delete','head','options'}:continue
  rows.append({'method':method.upper(),'path':path,'operation_id':operation.get('operationId'),'tags':operation.get('tags',[]),'required_parameters':[{'name':p['name'],'in':p['in']} for p in operation.get('parameters',[]) if p.get('required')],'request_body_required':operation.get('requestBody',{}).get('required',False),'status':'not_exercised_by_inventory'})
out=ROOT/'.local/full-interaction-audit';out.mkdir(parents=True,exist_ok=True)
(out/'api-contracts.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps({'operations':len(rows),'methods':dict(Counter(r['method'] for r in rows))}))
