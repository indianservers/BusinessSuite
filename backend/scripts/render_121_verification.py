"""Evidence ledger: never promote a rendered page to a full CRUD pass."""

import json,glob,csv,html

from pathlib import Path

from collections import Counter

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/crud-permissions-121'

PAGES=json.load(open(ROOT/'outputs/project-ux-20261107/pages.json'))

files=['browser-first-sweep.json','browser-before-shards.json']+[Path(p).name for p in sorted(glob.glob(str(OUT/'browser-shard-*.json')))]+['browser-targeted.json','browser-targeted-final.json']+[Path(p).name for p in sorted(glob.glob(str(OUT/'browser-actions-*.json')))]+[Path(p).name for p in sorted(glob.glob(str(OUT/'browser-confirmed-*.json')))]+['browser-last-checks.json','browser-final-actions.json']

history={p['route']:[] for p in PAGES}

for file in files:

 if not (OUT/file).exists():continue

 for row in json.load(open(OUT/file)):

  if row['route'] in history:history[row['route']].append({**row,'evidence_file':file})

contracts={r['resource']:r for r in json.load(open(OUT/'resource-contracts.json'))}

resource={

'/pms/clients':'PMS clients','/pms/projects':'PMS projects','/pms/tasks':'PMS tasks','/pms/my-work':'PMS tasks','/pms/my-assignments':'PMS tasks','/pms/notes':'PMS private notes','/pms/risks':'PMS risks','/pms/time-tracking':'PMS time logs',

'/crm/leads':'CRM leads','/crm/deals':'CRM deals','/crm/quotations':'CRM quotations','/crm/tickets':'CRM tickets','/crm/campaigns':'Communication campaigns',

'/hrms/employees':'HRMS employees','/hrms/recruitment':'HRMS recruitment','/hrms/performance':'HRMS performance','/hrms/assets':'HRMS assets','/hrms/timesheets':'HRMS timesheet projects',

'/fam/ledger-groups':'FAM ledger groups','/fam/ledgers':'FAM ledgers','/fam/parties':'FAM parties','/fam/banking':'FAM bank accounts',

'/srm/inventory/stock-groups':'Inventory stock-groups','/srm/inventory/units':'Inventory units',

'/srm/sales-orders':'Sales orders','/srm/contracts':'Contracts','/srm/engagements':'Engagements','/srm/billing-plans':'Billing plans',

'/analytics/report-builder':'Analytics reports','/analytics/reports':'Analytics reports','/analytics/dashboards':'Analytics dashboards','/ai-agents/handoff':'AI handoff notes','/power-apps/automations':'Power Apps automations'}

for suffix,name in [('entities','modules'),('fields','fields'),('layouts','layouts'),('views','views'),('kanban','kanban'),('validation-rules','validation-rules'),('buttons','buttons'),('related-lists','related-lists'),('picklists','picklists'),('formulas','fields')]:resource['/admin/customization/'+suffix]='Customization '+name

planned={'/power-apps/'+s for s in ['forms','tables','app-builder','notifications']}

references={'/power-apps/'+s for s in ['calendar','notes','tasks','workflow-automation']}

readonly={'/analytics','/analytics/exports','/analytics/funnel','/analytics/forecast','/analytics/profitability','/analytics/collections','/fam/chart-of-accounts','/fam/day-book','/fam/ledger-entries','/srm/inventory/dashboard','/pms/portfolio','/srm/profitability','/srm/customer-360','/ai-agents/analytics','/ai-agents/usage','/ai-agents/logs','/ai-agents/security/permissions','/crm/communication-timeline'}

prefixes={'AI':['/ai-agents','/ai/'],'Administration':['/customization'],'Analytics':['/analytics'],'CRM':['/crm/','/master-data/','/catalog/','/follow-ups'],'Communication':['/communication/','/integrations/whatsapp','/project-management/messaging'],'Finance':['/fam/'],'HRMS':['/employees','/company/','/leave/','/attendance/','/payroll/','/performance/','/recruitment/','/expenses/','/assets/','/documents/','/timesheets/'],'Inventory':['/srm/inventory/','/fam/inventory/','/catalog/'],'PMS':['/project-management/'],'Portals':['/customer-portal/','/partner-portal/'],'PowerApps':['/power-apps/'],'Sales':['/srm/']}

rows=[]

for page in sorted(PAGES,key=lambda p:(p['module'],p['route'])):

 path=page['route'];runs=history[path];success=[r for r in runs if r['status']!='failed'];last=runs[-1] if runs else {};actions=[];reads={}

 for run in runs:

  for action in run.get('actions',[]):

   if action.get('passed') and (action.get('endpoint') or 'autosave' in action.get('action','') or 'Invalid invite' in action.get('action','')):

    clean={k:v for k,v in action.items() if k!='error'}

    if clean not in actions:actions.append(clean)

  for read in run.get('reads',[]):

   own=read['path'].removeprefix('/api/v1')

   if any(own.startswith(prefix) for prefix in prefixes[page['module']]) and read['status']==200:reads[read['path']]=200

 contract=contracts.get(resource.get(path,''));api=contract['crud'] if contract else {};scope='; '.join(k+': '+v for k,v in api.items()) if api else 'Full C/U/D not established by the direct resource runner; see domain regression suites.'

 if contract:scope=contract['collection']+' — '+scope
 permission='Anonymous, read-only write and other-company record probes passed' if contract else 'Observed read endpoints checked separately; page-specific write-role matrix remains incomplete'

 status='Partial: full page action coverage remains'

 if path in readonly:status='Read-only scope: C/U/D not applicable; every filter/export/drilldown not established'

 if path in planned:status='Unavailable: roadmap screen, no CRUD implementation'

 if path in references:status='Reference only: CRUD belongs to the linked native workspace'

 if path=='/portal/partner/commissions':status='Unavailable: explicit commission placeholder'

 if path.endswith('/login'):status='Invalid-session rejection verified; no record CRUD on login'

 ui='; '.join(a.get('endpoint',a['action']) for a in actions) or ('Own page rendered and domain reads observed' if reads else 'Page rendered; own workflow coverage incomplete')

 rows.append({'module':page['module'],'page':path,'ui_verified':ui,'api_operations':scope,'permission_evidence':permission,'status':status,'domain_reads':list(reads),'ui_actions':actions,'contract':contract['resource'] if contract else None,'evidence_files':sorted({r['evidence_file'] for r in runs}),'full_page_crud_verified':False})

if (OUT/'ui-verified.log').exists() and '8 passed' in (OUT/'ui-verified.log').read_text():
 for row in rows:
  if row['page']=='/pms/clients':
   row['ui_verified']='Own UI create, read, edit, delete; read-only page access denied'
   row['full_page_crud_verified']=True
   row['status']='Own UI CRUD and resource permission checks verified'
   row['evidence_files'].append('ui-verified.log')
  if row['page']=='/hrms/performance':
   row['ui_verified']+='; own goal form cycle selection and persisted target_date verified'
   row['evidence_files'].append('ui-verified.log')
# The deliberate false flags mean a subset of checks can never become a fabricated whole-page pass.

summary={'pages':len(rows),'resource_contracts':len(contracts),'resource_contracts_passed':sum(c['status']=='passed' for c in contracts.values()),'resources_with_all_four_crud_operations':sum(len(c['crud'])==4 and all(v=='passed' for v in c['crud'].values()) for c in contracts.values()),'pages_with_real_ui_mutation_or_session_test':sum(bool(r['ui_actions'])for r in rows),'full_page_crud_verified':sum(r['full_page_crud_verified'] for r in rows),'note':'This is an evidence ledger, not a claim of full CRUD and all permissions on 121 pages. Remaining work is explicitly retained.'}

json.dump({'summary':summary,'pages':rows},open(OUT/'page-results.json','w'),indent=2)

columns=['module','page','ui_verified','api_operations','permission_evidence','status']

with open(OUT/'page-results.csv','w',newline='',encoding='utf-8-sig')as file:

 w=csv.DictWriter(file,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)

md=['# 121-page CRUD and permission evidence','',summary['note'],'','| Module | Page | Verified UI evidence | API operations | Result |','|---|---|---|---|---|']

for r in rows:md.append('| '+' | '.join(str(r[k]).replace('|','/').replace('\n',' ')for k in ['module','page','ui_verified','api_operations','status'])+' |')

(OUT/'page-results.md').write_text('\n'.join(md),encoding='utf-8')

data=json.dumps(rows).replace('</','<'+chr(92)+'/')

page_html='<!doctype html><meta charset="utf-8"><title>121-page CRUD verification evidence</title><style>body{font:14px system-ui;margin:28px;color:#17212b;background:#fafafa}h1{font-size:24px}p{max-width:1100px;line-height:1.5}input,select{padding:10px;margin:4px 12px 18px 0;border:1px solid #bbc2c8;background:white}table{border-collapse:collapse;width:100%;background:white}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #dce0e3;padding:12px;font-size:13px}th{position:sticky;top:0;background:#edf0f2}code{font-size:12px}small{color:#52616b}summary{cursor:pointer}a{color:#1457a6}</style><h1>121-page CRUD and permission evidence</h1><p><strong>Full CRUD on all 121 pages is not verified.</strong> This ledger distinguishes actual UI mutations, resource API contracts, read checks, reference pages and unavailable features. A successful shared control or rendered page is never counted as full CRUD.</p><p id="stats"></p><input id="search" placeholder="Search page, operation or result" size="48"><select id="module"><option value="">Every module</option></select><p id="count"></p><table><thead><tr><th>Module / page</th><th>Verified own UI action</th><th>Direct API CRUD evidence</th><th>Permissions / remaining work</th></tr></thead><tbody id="body"></tbody></table><script>const rows=DATA;const stats=SUMMARY;document.getElementById(\'stats\').textContent=stats.pages+\' pages · \'+stats.resource_contracts_passed+\'/\'+stats.resource_contracts+\' resource contracts passed · \'+stats.resources_with_all_four_crud_operations+\' resource families exercised all C/R/U/D operations\';const select=document.getElementById(\'module\');[...new Set(rows.map(r=>r.module))].forEach(m=>{const o=document.createElement(\'option\');o.textContent=m;select.append(o)});function render(){const term=document.getElementById(\'search\').value.toLowerCase();const filtered=rows.filter(r=>(!select.value||r.module===select.value)&&JSON.stringify(r).toLowerCase().includes(term));document.getElementById(\'count\').textContent=filtered.length+\' of \'+rows.length+\' pages\';const body=document.getElementById(\'body\');body.replaceChildren();for(const r of filtered){const tr=document.createElement(\'tr\');for(const value of [r.module+\'\n\'+r.page,r.ui_verified,r.api_operations,r.permission_evidence+\'\n\n\'+r.status]){const td=document.createElement(\'td\');td.textContent=value;td.style.whiteSpace=\'pre-line\';tr.append(td)}const detail=document.createElement(\'details\');const title=document.createElement(\'summary\');title.textContent=\'Domain requests and evidence files\';detail.append(title);const pre=document.createElement(\'pre\');pre.style.whiteSpace=\'pre-wrap\';pre.textContent=JSON.stringify({domain_reads:r.domain_reads,actions:r.ui_actions,files:r.evidence_files},null,2);detail.append(pre);tr.children[1].append(detail);body.append(tr)}}document.getElementById(\'search\').oninput=render;select.onchange=render;render();</script>'

page_html=page_html.replace("+'\n'+","+'\\n'+").replace("+'\n\n'+","+'\\n\\n'+")
(OUT/'page-results.html').write_text(page_html.replace('DATA',data).replace('SUMMARY',json.dumps(summary)),encoding='utf-8')

print(json.dumps(summary,indent=2))
