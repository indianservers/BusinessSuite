"""Render page-specific evidence without treating API tests as UI CRUD."""
import json,csv,html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/crud-permissions-121-final'
pages=json.loads((ROOT/'outputs/project-ux-20261107/pages.json').read_text(encoding='utf-8'))
DATA="""
/pms/projects|Create, rename, preview, double-click open, trash|Upgraded
/pms/tasks|Create task in project UI; API CRUD|Existing
/pms/my-work|Inline status persists after refresh|Fixed
/pms/my-assignments|Start, progress, draft, submit for review|Existing
/pms/time-tracking|Create, edit duration, delete|Existing
/pms/risks|Create risk UI; API CRUD|Existing
/pms/files|Upload, folder, move, download, soft-delete|Upgraded
/pms/notes|Create, autosave, trash, restore|Fixed
/pms/clients|Create, edit, delete; conflict handling|Upgraded
/pms/portfolio|Project health reads; native status filter|Read-only
/crm/leads|Create lead UI; API CRUD|Existing
/crm/contacts|Create contact UI; API CRUD|Existing
/crm/companies|Create shared company UI; API CRUD|Existing
/crm/deals|Create, edit, archive deal|Existing
/crm/follow-ups|Schedule follow-up; saved readback|Existing
/crm/pipeline|Reviewed board stage transition; persisted stage|Existing
/crm/tickets|Create ticket UI; API CRUD; reader write gate|Upgraded
/crm/quotations|Create quote UI; API CRUD; delete/recreate regression|Fixed
/crm/campaigns|Create campaign UI; API CRUD; no delivery|Existing
/crm/products-services|Create product UI; API CRUD|Existing
/hrms/employees|Quick-add with branch/department; API CRUD|Fixed
/hrms/attendance|Manual WFH/hours persist; lock/unlock|Fixed
/hrms/leave|Apply leave; reader action blocked|Upgraded
/hrms/payroll|Calculate payroll; persisted guided run; no payout|Existing
/hrms/recruitment|Post job UI; API create/update|Existing
/hrms/performance|Create goal with cycle/due date; reader gate|Fixed
/hrms/assets|Register, assign, acknowledge, return/history|Fixed
/hrms/expenses|Claim, manager/finance approval, reimbursement record|Upgraded
/hrms/documents|Upload, verify, signed file download on 1582|Fixed
/hrms/timesheets|Project, sheet, entry, submit, independent review|Upgraded
/srm/sales-orders|Create order UI; API create/read/update|Existing
/srm/contracts|Create contract UI; API create/read/update|Existing
/srm/engagements|Create engagement UI; API create/read/update|Existing
/srm/billing-plans|Create plan UI; API create/read/update|Existing
/srm/invoice-drafts|Manual invoice composer; draft readback|Existing
/srm/invoices|Create, issue, authenticated PDF|Fixed
/srm/collections|Record synthetic received payment; receipt readback|Existing
/srm/revenue-recognition|Operational revenue-event reads and refresh|Read-only
/srm/profitability|Profitability data and domain refresh|Read-only
/srm/customer-360|Customer profile and shared company reads|Read-only
/fam/chart-of-accounts|Account tree reads and native refresh|Read-only
/fam/ledger-groups|Create, rename, delete group|Upgraded
/fam/ledgers|Create, rename, delete ledger|Upgraded
/fam/opening-balances|Two-sided entries and balanced posting|Upgraded
/fam/vouchers|Register to new draft; save and cancel voucher|Existing
/fam/journal|Create/edit draft, post and reversal|Upgraded
/fam/day-book|Posted transaction reads and native refresh|Read-only
/fam/ledger-entries|Ledger-entry reads and native refresh|Read-only
/fam/parties|Create party with ledger UI; API update/retire|Fixed
/fam/banking|Account/statement links; synthetic bank account registration|Fixed
/srm/inventory/dashboard|Stock metrics and native refresh|Read-only
/srm/inventory/items|Create catalog item UI; API update/retire|Upgraded
/srm/inventory/stock-groups|Create group; persisted collection|Existing
/srm/inventory/units|Create unit; persisted collection|Existing
/srm/inventory/warehouses|Create warehouse using native inventory API|Fixed
/srm/inventory/opening-stock|Post opening quantity; persisted stock|Fixed
/srm/inventory/stock-in|Post inbound movement|Fixed
/srm/inventory/stock-out|Post outbound movement|Fixed
/srm/inventory/stock-transfers|Post warehouse transfer|Fixed
/srm/inventory/stock-adjustments|Post quantity adjustment|Fixed
/ai-agents|Disable/enable agent; restore original state|Upgraded
/ai-agents/config|Change/save scope; restore original state|Upgraded
/ai-agents/approvals|Approve executes native task; reject has no task effect|Existing
/ai-agents/analytics|Scoped agent analytics reads|Read-only
/ai-agents/usage|Add/save limit; deactivate limit|Upgraded
/ai-agents/security|Save controls; restore original values|Upgraded
/ai-agents/security/permissions|Add rule; repeated save retains IDs|Fixed
/ai-agents/feedback|Scoped feedback records and filters available|Read-only
/ai-agents/handoff|Review and resolve native handoff|Upgraded
/ai-agents/logs|Scoped audit logs and domain filter|Read-only
/power-apps/calendar|Open linked native PMS calendar|Reference
/power-apps/notes|Open linked native PMS notes|Reference
/power-apps/tasks|Open linked native PMS tasks|Reference
/power-apps/workflow-automation|Open linked native PMS workflows|Reference
/power-apps/automations|Create, rename, version history, delete draft|Upgraded
/power-apps/approvals|Submit, native worker, different reviewer approves|Existing
/power-apps/forms|Explicit roadmap state; no CRUD endpoint|Planned
/power-apps/tables|Explicit roadmap state; no CRUD endpoint|Planned
/power-apps/app-builder|Explicit roadmap state; no CRUD endpoint|Planned
/power-apps/notifications|Explicit roadmap state; no CRUD endpoint|Planned
/crm/communication-hub|Own inbox/matching/delivery queue links|Existing
/crm/whatsapp|Native status/filters; Meta connection absent|Provider blocked
/crm/whatsapp/inbox|Inbox reads/filter; provider send unavailable|Provider blocked
/crm/whatsapp/sent|Sent-log reads/filter; provider delivery unavailable|Provider blocked
/crm/whatsapp/templates|Template reads; reader submission denied|Provider blocked
/crm/whatsapp/profile|Profile state; no connected Meta profile|Provider blocked
/crm/whatsapp/settings|Settings state; no connected Meta account|Provider blocked
/crm/communication-timeline|Customer communication history reads|Read-only
/crm/messages|Private self-only channel; message create/edit/delete|Existing
/pms/messages|Private self-only channel; message create/edit/delete|Existing
/portal/customer|Valid customer session and home reads|Fixed
/portal/customer/quotes|Own quote acceptance; viewer acceptance denied|Fixed
/portal/customer/invoices|Customer-scoped invoice reads|Existing
/portal/customer/projects|Customer-scoped project reads|Existing
/portal/customer/profile|Customer-scoped profile reads|Read-only
/portal/partner|Valid partner session and home reads|Fixed
/portal/partner/leads|Submit lead; view-only submission denied|Fixed
/portal/partner/commissions|Explicit placeholder; no commission/payout workflow|Planned
/portal/partner/profile|Partner-scoped profile reads|Read-only
/portal/customer/login|Valid login; invalid session rejected|Fixed
/portal/partner/login|Valid login; invalid session rejected|Fixed
/analytics|Scoped analytics summary reads|Read-only
/analytics/report-builder|Create report; API update/delete|Upgraded
/analytics/reports|Create, rename, run, authenticated CSV, delete|Fixed
/analytics/dashboards|Create dashboard/widget, rename, delete|Upgraded
/analytics/scheduled-reports|Own named schedule/frequency/recipient; no email sent|Upgraded
/analytics/exports|Scoped export history reads|Read-only
/analytics/funnel|Funnel analysis reads|Read-only
/analytics/forecast|Forecast analysis reads|Read-only
/analytics/profitability|Profitability analysis reads|Read-only
/analytics/collections|Collections analysis reads|Read-only
/admin/customization/entities|Create, rename, retire module|Upgraded
/admin/customization/fields|Create, edit, hide field; API CRUD|Upgraded
/admin/customization/layouts|Create and rename layout; no native delete|Upgraded
/admin/customization/views|Create, rename, delete saved view|Upgraded
/admin/customization/kanban|Create board definition; no native update/delete|Upgraded
/admin/customization/validation-rules|Create validation rule; no native update/delete|Existing
/admin/customization/buttons|Create custom action; no native update/delete|Existing
/admin/customization/related-lists|Create related-list definition; no native update/delete|Existing
/admin/customization/picklists|Create picklist values; no native update/delete|Upgraded
/admin/customization/formulas|Create, edit, hide formula field|Upgraded
"""
lookup={line.split('|')[0]:line.split('|')[1:] for line in DATA.strip().splitlines()}
lookup.update({'/pms/tasks': ('Create in project; inline title edit and trash', 'Upgraded'), '/pms/risks': ('Create, edit title, delete risk', 'Fixed'), '/crm/leads': ('Create lead; edit and archive with reason', 'Fixed'), '/crm/contacts': ('Create, edit contact, delete selected', 'Fixed'), '/crm/companies': ('Create, edit company, move to trash', 'Upgraded'), '/crm/tickets': ('Create ticket; inline subject edit, delete selected', 'Upgraded'), '/crm/quotations': ('Create quote; inline number edit, delete selected', 'Fixed'), '/crm/campaigns': ('Create, edit, delete unused campaign draft; no delivery', 'Upgraded'), '/crm/products-services': ('Create, edit product, archive', 'Upgraded'), '/hrms/employees': ('Quick-add; edit employee, retire', 'Upgraded'), '/hrms/recruitment': ('Post job, edit title, delete unused job', 'Upgraded'), '/hrms/performance': ('Create goal, edit title, delete unused goal', 'Upgraded'), '/hrms/assets': ('Register/edit/delete unused asset; custody history protected', 'Upgraded'), '/hrms/timesheets': ('Project CRUD; sheet, entry, submit, independent review', 'Upgraded'), '/srm/customer-360': ('Create customer, edit, move to trash', 'Upgraded'), '/fam/parties': ('Create party with ledger, edit, retire', 'Upgraded'), '/fam/banking': ('Create linked bank account, edit, retire', 'Upgraded'), '/srm/inventory/items': ('Create catalog item, edit, archive', 'Upgraded'), '/analytics/report-builder': ('Create, select saved report, edit, delete', 'Upgraded'), '/analytics/scheduled-reports': ('Create schedule, edit, delete; no email sent', 'Upgraded'), '/portal/partner/commissions': ('Create claim, edit, delete; own portal scope; no payout', 'New'), '/srm/sales-orders': ('Create, edit, delete unused draft/planned record', 'Upgraded'), '/srm/contracts': ('Create, edit, delete unused draft/planned record', 'Upgraded'), '/srm/engagements': ('Create, edit, delete unused draft/planned record', 'Upgraded'), '/srm/billing-plans': ('Create, edit, delete unused draft/planned record', 'Upgraded'), '/srm/inventory/stock-groups': ('Create, edit, retire master record', 'Upgraded'), '/srm/inventory/units': ('Create, edit, retire master record', 'Upgraded'), '/srm/inventory/warehouses': ('Create, edit, retire master record', 'Upgraded'), '/power-apps/forms': ('Form CRUD; submission CRUD; preview', 'New'), '/power-apps/tables': ('Table CRUD; row CRUD; preview', 'New'), '/power-apps/app-builder': ('App page CRUD; content and connected-table preview', 'New'), '/power-apps/notifications': ('Internal notice CRUD and acknowledgement', 'New'), '/admin/customization/entities': ('Create, full edit, delete / retire module', 'Upgraded'), '/admin/customization/layouts': ('Create, full edit, delete', 'Upgraded'), '/admin/customization/views': ('Create, full edit, delete', 'Upgraded'), '/admin/customization/kanban': ('Create, full edit, delete', 'Upgraded'), '/admin/customization/validation-rules': ('Create, full edit, delete', 'Upgraded'), '/admin/customization/buttons': ('Create, full edit, delete', 'Upgraded'), '/admin/customization/related-lists': ('Create, full edit, delete', 'Upgraded'), '/admin/customization/picklists': ('Create, full edit, delete', 'Upgraded'), '/admin/customization/fields': ('Create, edit, explicit delete retires definition', 'Upgraded'), '/admin/customization/formulas': ('Create, edit, explicit delete retires definition', 'Upgraded')})
admin={r['route']:r for i in range(3) for r in json.loads((OUT/f'census-admin-updated-{i}.json').read_text(encoding='utf-8'))}
reader={r['route']:r for i in range(3) for r in json.loads((OUT/f'census-reader-updated-{i}.json').read_text(encoding='utf-8'))}
assert len(pages)==len(lookup)==121 and set(lookup)=={p['route'] for p in pages}
UI_LOGS={
'/pms/projects':'project-ui.log','/pms/my-work':'my-work-final.log','/pms/portfolio':'my-work-final.log','/pms/my-assignments':'native-ui.log','/pms/notes':'notes-final.log','/pms/files':'operational-retry.log','/pms/time-tracking':'operational-ui.log','/pms/clients':'regressions-ui.log',
'/hrms/timesheets':'hr-last.log','/hrms/expenses':'hr-last.log','/hrms/assets':'lifecycle-ui.log','/hrms/attendance':'lifecycle-ui.log','/hrms/documents':'documents-final.log','/hrms/employees':'regressions-ui.log','/hrms/performance':'regressions-ui.log','/hrms/payroll':'domain-ui.log',
'/crm/deals':'lifecycle-ui.log','/crm/pipeline':'native-last.log','/crm/quotations':'ui-quotation-final.json','/crm/follow-ups':'domain-ui.log','/crm/messages':'messages-ui.log','/pms/messages':'messages-ui.log','/crm/communication-hub':'domain-last.log',
'/srm/invoices':'domain-ui.log','/srm/collections':'domain-ui.log','/srm/invoice-drafts':'domain-last.log','/fam/banking':'banking-final.log','/fam/journal':'lifecycle-ui.log','/fam/vouchers':'voucher-final.log','/fam/opening-balances':'native-ui.log',
'/power-apps/automations':'applications-ui.log','/power-apps/approvals':'approvals-final.log','/analytics/reports':'regressions-ui.log','/analytics/dashboards':'applications-ui.log','/analytics/scheduled-reports':'applications-ui.log','/admin/customization/fields':'domain-ui.log','/admin/customization/formulas':'domain-ui.log'}
for slug in ['calendar','notes','tasks','workflow-automation']:UI_LOGS['/power-apps/'+slug]='native-ui.log'
for slug in ['','/quotes','/invoices','/projects','/profile']:UI_LOGS['/portal/customer'+slug]='customer-final.log'
for slug in ['','/leads','/commissions','/profile']:UI_LOGS['/portal/partner'+slug]='portals-ui.log'
UI_LOGS.update({route:'verified-ui.log; verified-retry-ui.log' for route in ['/pms/tasks', '/pms/risks', '/crm/leads', '/crm/contacts', '/crm/companies', '/crm/tickets', '/crm/quotations', '/crm/campaigns', '/crm/products-services', '/hrms/employees', '/hrms/recruitment', '/hrms/performance', '/hrms/assets', '/hrms/timesheets', '/srm/customer-360', '/fam/parties', '/fam/banking', '/srm/inventory/items', '/analytics/report-builder', '/analytics/scheduled-reports', '/portal/partner/commissions', '/srm/sales-orders', '/srm/contracts', '/srm/engagements', '/srm/billing-plans', '/srm/inventory/stock-groups', '/srm/inventory/units', '/srm/inventory/warehouses', '/power-apps/forms', '/power-apps/tables', '/power-apps/app-builder', '/power-apps/notifications', '/admin/customization/entities', '/admin/customization/layouts', '/admin/customization/views', '/admin/customization/kanban', '/admin/customization/validation-rules', '/admin/customization/buttons', '/admin/customization/related-lists', '/admin/customization/picklists', '/admin/customization/fields', '/admin/customization/formulas']})
route_evidence={p['route']:[] for p in pages}
for pattern in ['ui-workflows-*.json','ui-deep-*.json','census-admin-updated-?.json','census-reader-updated-?.json']:
 for f in sorted(OUT.glob(pattern)):
  for row in json.loads(f.read_text(encoding='utf-8')):
   if row['route'] in route_evidence:route_evidence[row['route']].append(f.name)
UI_LOGS['/pms/risks']='risk-verified-ui.log'
UI_LOGS['/crm/pipeline']='aliases-ui.log'
for slug in ['calendar','notes','tasks','workflow-automation']:UI_LOGS['/power-apps/'+slug]='aliases-ui.log'
rows=[]
for page in pages:
 route=page['route'];workflow,status=lookup[route];a=admin[route];r=reader[route]
 assert a['status']==r['status']=='rendered',route
 rows.append({'module':page['module'],'page':route,'workflow_verified':workflow,'change_or_limit':status,'admin_ui':'rendered','read_only_ui':'rendered','native_reads':len(a['reads']),'evidence':'; '.join(route_evidence[route]+([UI_LOGS[route]] if route in UI_LOGS else [])+['ui-final-summary.json','page-permissions.json','native-write-permissions.json'])})
(OUT/'page-results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
with (OUT/'page-results.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
md='All 121 pages opened as admin and scoped reader. UI and API coverage are stated separately. Read-only, reference and provider-blocked pages are not full CRUD passes. C/R/U/D means create/read/update/delete; retirement, posting and reversal follow native lifecycle rules.\n\n| Page | Own workflow verified | Result |\n|---|---|---|\n'
md+='\n'.join('| '+r['page']+' | '+r['workflow_verified']+' | '+r['change_or_limit']+' |' for r in rows)
(OUT/'page-results.md').write_text(md,encoding='utf-8')
head="""<meta charset="utf-8"><title>121 page CRUD and permissions evidence</title><style>body{font:14px system-ui;margin:32px}table{border-collapse:collapse;width:100%}td,th{padding:9px;text-align:left;border:1px solid #ddd}th{background:#eff3fa;position:sticky;top:0}tr:nth-child(even){background:#fafafa}input{padding:10px;width:450px}</style><h1>121 page verification on port 1582</h1><p>UI and API checks are explicitly distinguished. Read-only, reference and provider-blocked pages are not full CRUD passes. All rows have admin and scoped-reader page evidence.</p><input placeholder="Filter page or workflow" oninput="for(const r of document.querySelectorAll('tbody tr'))r.hidden=!r.innerText.toLowerCase().includes(this.value.toLowerCase())"><table><thead><tr><th>Module</th><th>Page</th><th>Own workflow verified</th><th>Result</th></tr></thead><tbody>"""
for r in rows:head+='<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ['module','page','workflow_verified','change_or_limit'])+'</tr>'
(OUT/'page-results.html').write_text(head+'</tbody></table>',encoding='utf-8')
print(json.dumps({'pages':len(rows),'admin':len(admin),'reader':len(reader)}))
