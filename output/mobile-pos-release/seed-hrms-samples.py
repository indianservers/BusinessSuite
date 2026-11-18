from pathlib import Path
import argparse, json
from copy import deepcopy
import app.db.base
from app.db.session import SessionLocal
from app.models.user import User
from app.models.company import Company
from app.shared.employee_category_taxonomy import options, save, TaxonomyInput
from app.apps.srm.services.commercial import tenant, require
from fastapi import HTTPException

BASE=Path('/srv/business-suite/shared/sample-hrms-categories-20261118')
SAMPLES=[('technical','DEMO Technical Services',['Computer Repair','Network Support','Device Setup']),('consulting','DEMO Consulting',['Business Consultation','Tax Consultation','IT Advisory']),('maintenance','DEMO Maintenance',['Routine Inspection','Equipment Servicing','Safety Checks'])]

def actor_for(db):
 actor=db.query(User).filter(User.email=='saisatish@indianservers.com',User.is_active.is_(True)).one()
 if tenant(actor)!=1:raise RuntimeError('The authorized actor is not in the intended Indian Servers company')
 require(actor,'employee_update')
 return actor

def clean(node,children=False):
 result={key:node[key] for key in ('id','name','active')}
 if children:result['children']=[clean(child) for child in node.get('children',[])]
 return result

parser=argparse.ArgumentParser();parser.add_argument('--inspect',action='store_true');args=parser.parse_args()
BASE.mkdir(parents=True,exist_ok=True)
with SessionLocal() as db:
 actor=actor_for(db);before=options(db,actor);company=db.get(Company,1)
 if args.inspect:
  print(json.dumps({'company':company.name,'version':before['version'],'can_manage':before['can_manage'],'managed_categories':len([x for x in before['categories'] if not x.get('legacy')]),'existing_category_names':[x['name'] for x in before['categories']]},ensure_ascii=False));raise SystemExit(0)
 (BASE/'before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2))
 for attempt in range(3):
  actor=actor_for(db);state=options(db,actor);rows=[clean(x,True) for x in state['categories'] if not x.get('legacy')]
  ids={n['id'] for row in rows for n in [row,*row['children']]};added_categories=added_children=0
  for key,name,children in SAMPLES:
   row=next((r for r in rows if r['name'].casefold()==name.casefold()),None)
   if row is None:
    ident='sample-hrms-'+key+'-20261118'
    if ident in ids:raise RuntimeError('Sample id collision; no existing category will be overwritten')
    row={'id':ident,'name':name,'active':True,'children':[]};rows.append(row);ids.add(ident);added_categories+=1
   for i,child_name in enumerate(children,1):
    if any(c['name'].casefold()==child_name.casefold() for c in row['children']):continue
    ident='sample-hrms-'+key+'-'+str(i)+'-20261118'
    if ident in ids:raise RuntimeError('Sample child id collision; no existing subcategory will be overwritten')
    row['children'].append({'id':ident,'name':child_name,'active':True});ids.add(ident);added_children+=1
  try:
   result=save(db,actor,TaxonomyInput(version=state['version'],categories=rows)) if added_categories or added_children else state
   break
  except HTTPException as error:
   db.rollback()
   if error.status_code!=409 or attempt==2:raise
with SessionLocal() as db:
 actor=actor_for(db);result=options(db,actor)
 for _,name,children in SAMPLES:
  row=next(x for x in result['categories'] if x['name']==name)
  assert set(children)<={x['name'] for x in row['children']}
 assert set(before['items'])<=set(result['items'])
 (BASE/'after.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 summary={'company':'Indian Servers','added_categories':added_categories,'added_subcategories':added_children,'sample_categories':3,'sample_subcategories':9,'version':result['version'],'samples':{name:children for _,name,children in SAMPLES},'existing_names_preserved':True,'employee_assignments_changed':False}
 (BASE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 print(json.dumps(summary,ensure_ascii=False))
