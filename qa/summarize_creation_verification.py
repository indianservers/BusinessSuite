"""Consolidate sanitized creation QA evidence without credentials or response payloads."""
import json,re,xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
b=ROOT/'.local/creation-live';out=ROOT/'outputs/creation-inventory'
def read(p):return json.loads(p.read_text(encoding='utf8'))
latest={}
for line in (b/'cases.jsonl').read_text(encoding='utf8').splitlines():
 v=json.loads(line);latest[v['title']]=v
# Renamed checks retain their old failure history in the raw private run log.
renamed={"CRM legacy task composer shared window saves and reads back":"CRM legacy New task opens the shared composer and saves a real task"}
superseded=[]
for old,new in renamed.items():
 if old in latest and new in latest:
  superseded.append({'previousTitle':old,'replacementTitle':new,'replacementStatus':latest[new]['status']});latest.pop(old)
browser=[]
for name,v in sorted(latest.items()):
 annotations=[a for a in v.get('annotations',[]) if a.get('type') in ['native-page','native-write','persisted-create','native-actor']]
 browser.append({'title':name,'status':v['status'],'at':v['at'],'durationMs':v['duration'],'evidence':annotations})
def titles(value):
 for spec in value.get('specs',[]):yield spec['title']
 for suite in value.get('suites',[]):yield from titles(suite)
selected=set()
for name in ['matching-verified-results.json','native-extra-final-results.json']:
 selected.update(titles(read(b/name)))
dedicated={line.split(' › ',1)[1].strip() for line in (b/'dedicated-live-list.log').read_text(encoding='utf8').splitlines() if ' › ' in line}
matching_summary={label:{'total':len(names),'passed':sum(latest.get(name,{}).get('status')=='passed' for name in names),'unverifiedOrFailed':[name for name in sorted(names) if latest.get(name,{}).get('status')!='passed']} for label,names in [('nativeCreationWorkflows',selected),('dedicatedLiveCreationChecks',dedicated)]}
backend={}
for name in ['backend-creation-results.xml','backend-prompt-retry.xml','postgres-boundary-results.xml','backend-save-proof.xml','backend-operational-verified-v2.xml']:
 p=b/name
 if not p.exists():continue
 for t in ET.parse(p).iter('testcase'):
  key=(t.get('classname'),t.get('name'));backend[key]={'test':'::'.join(key),'status':'failed' if t.find('failure') is not None or t.find('error') is not None else 'skipped' if t.find('skipped') is not None else 'passed'}
permissions=read(b/'permissions.json')
shared=read(ROOT/'.local/smart-creation/results.json')
ledger={'date':'2026-11-08','servers':{'business':'http://127.0.0.1:1596','owner':'http://127.0.0.1:1597','database':'isolated SQLite and local PostgreSQL QA databases'},'matchingBrowserCoverage':matching_summary,'endpointCoverage':read(out/'creation-save-endpoint-ledger.json')['summary'],'backendSummary':dict(Counter(v['status'] for v in backend.values())),'browserSummary':dict(Counter(v['status'] for v in browser)),'sharedWindowAssertions':sum(len(v.get('passed',[])) for v in shared),'permissionReplays':{'attempts':len(permissions),'passed':sum(bool(v.get('passed')) for v in permissions)},'supersededChecks':superseded,'backend':list(backend.values()),'browser':browser,'sharedWindow':shared}
(out/'creation-live-verification-ledger.json').write_text(json.dumps(ledger,indent=2),encoding='utf8')
print(json.dumps({k:ledger[k] for k in ['endpointCoverage','backendSummary','browserSummary','matchingBrowserCoverage','sharedWindowAssertions','permissionReplays']},indent=2))
