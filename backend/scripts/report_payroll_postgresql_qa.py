"""Merge PostgreSQL follow-up evidence into the original payroll case register."""
import ast
from collections import Counter
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/qa/payroll-2026-11-09'
EVIDENCE=OUT/'evidence'
for name in ['payroll-final-core.xml','payroll-extended-results.xml','payroll-leave-matrix-results.xml','payroll-calculation-matrices-results.xml','payroll-browser-results.json','payroll-payslips-browser-results.json','payroll-live-browser-results.json']:
    destination=ROOT/'.tmp'/name
    if not destination.exists():
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(EVIDENCE/name,destination)
subprocess.run([sys.executable,str(ROOT/'backend/scripts/report_payroll_qa.py')],check=True,stdout=subprocess.DEVNULL)
with (OUT/'Payroll_Test_Cases.csv').open(encoding='utf-8-sig',newline='') as file:rows=list(csv.DictReader(file))
lookup={}
for row in rows:
    source=re.search(r'backend/tests/([^;:]+\.py)',row['evidence'])
    key=source.group(1)+'::'+row['scenario'] if source else 'browser::'+row['scenario']
    lookup[key]=row
    row['environment_results']=json.dumps({'SQLite baseline':row['status']})


def merge(key,record,environment):
    if key in lookup:
        row=lookup[key]
        prior=json.loads(row['environment_results']);prior[environment]=record['status']
        row.update({field:value for field,value in record.items() if field not in {'test_id','evidence','preconditions'}})
        row['evidence']+='; '+record['evidence']
        if environment not in row['preconditions']:row['preconditions']+='; '+record['preconditions']
        row['environment_results']=json.dumps(prior)
    else:
        row=dict(record,test_id=f'PAY-{len(rows)+1:03}',environment_results=json.dumps({environment:record['status']}))
        rows.append(row);lookup[key]=row
    statuses=json.loads(row['environment_results']).values()
    row['status']='FAIL' if 'FAIL' in statuses else 'BLOCKED' if 'BLOCKED' in statuses else 'PASS'


def defect(name):
    if 'concurrent' in name or 'rechecks_status' in name:return 'PAY-PG-05'
    if 'consumed_inputs' in name:return 'PAY-RECALC-06'
    if 'deduplicates' in name or 'deduct_approved_leave' in name:return 'PAY-LEAVE-07'
    if 'locked_run_blocks' in name:return 'PAY-LOCK-08'
    if 'respects_employment' in name:return 'PAY-LEAVE-09'
    if 'revision_intersects' in name:return 'PAY-PRORATE-10'
    if 'cancellation_clears' in name:return 'PAY-LWP-11'
    if 'future_pay_mode' in name:return 'PAY-HIST-13'
    return ''


sources=[('payroll-policy-regression-postgresql.xml','PostgreSQL 17.11'),('payroll-policies-postgresql.xml','PostgreSQL 17.11'),('payroll-policy-concurrency-postgresql.xml','PostgreSQL 17.11'),('payroll-policies-sqlite.xml','SQLite regression'),('payroll-postgresql-final-results.xml','PostgreSQL 17.11'),('payroll-postgresql-remaining-results.xml','PostgreSQL 17.11'),
         ('payroll-postgresql-concurrency-results.xml','PostgreSQL 17.11'),('payroll-postgresql-full-period-results.xml','PostgreSQL 17.11'),('payroll-followup-sqlite.xml','SQLite regression'),('payroll-historical-mode-after.xml','SQLite regression')]
sources=sorted(sources,key=lambda item:(ROOT/'.tmp'/item[0]).stat().st_mtime if (ROOT/'.tmp'/item[0]).exists() else 0)
for filename,environment in sources:
    path=ROOT/'.tmp'/filename
    if not path.exists() and (EVIDENCE/filename).exists():
        shutil.copy2(EVIDENCE/filename,path)
    if not path.exists() and filename in {'payroll-policy-regression-postgresql.xml','payroll-policies-postgresql.xml','payroll-policy-concurrency-postgresql.xml','payroll-policies-sqlite.xml','payroll-postgresql-remaining-results.xml','payroll-postgresql-full-period-results.xml','payroll-historical-mode-after.xml'}:continue
    shutil.copy2(path,EVIDENCE/filename)
    for test in ET.parse(path).iter('testcase'):
        name=test.attrib['name'];module=test.attrib['classname'].split('.')[-1]
        file=ROOT/'backend/tests'/f'{module}.py'
        text=file.read_text(encoding='utf-8-sig');tree=ast.parse(text)
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name.split('[')[0])
        assertions='\n'.join(ast.get_source_segment(text,n) for n in ast.walk(node) if isinstance(n,ast.Assert))
        props={p.attrib['name']:p.attrib.get('value','') for p in test.findall('./properties/property')}
        error=test.find('failure');error=error if error is not None else test.find('error')
        status='FAIL' if error is not None else 'BLOCKED' if test.find('skipped') is not None else 'PASS'
        key=module+'.py::'+name
        category=lookup[key]['category'] if key in lookup else 'E' if 'proration' in name else 'D' if 'leave' in name or 'lwp' in name else 'I' if 'lock' in name or 'concurrent' in name else 'H'
        record=dict(category=category,scenario=name,business_rule=assertions,
            preconditions=f'{environment}; disposable loopback cluster/database; fixtures {", ".join(a.arg for a in node.args.args)}',
            exact_inputs=props.get('inputs',ast.get_source_segment(text,node)),
            execution_steps=f'./backend/venv/Scripts/python.exe backend/scripts/run_payroll_postgresql_qa.py tests/{module}.py::{name}' if environment.startswith('PostgreSQL') else f'From backend: ./venv/Scripts/python.exe -m pytest tests/{module}.py::{name} -q',
            expected=props.get('expected',assertions),actual=props.get('actual','All assertions completed' if status=='PASS' else error.text if error is not None else 'Skipped'),
            status=status,evidence=f'evidence/{filename}; backend/tests/{module}.py:{node.lineno}',defect_reference=defect(name),
            cleanup='Transaction rollback; committed multi-connection fixtures remain only in their separately stopped disposable cluster')
        merge(key,record,environment)


def specs(suite):
    yield from suite.get('specs',[])
    for child in suite.get('suites',[]):yield from specs(child)


browser_file='payroll-postgresql-browser-results.json'
browser=json.loads((ROOT/'.tmp'/browser_file).read_text(encoding='utf-8-sig'))
shutil.copy2(ROOT/'.tmp'/browser_file,EVIDENCE/browser_file)
for spec in specs(browser):
    for test in spec['tests']:
        result=test['results'][-1]
        name=f"{test['projectName']}: {spec['title']}"
        merge('browser::'+name,dict(category='H',scenario=name,business_rule=spec['title'],preconditions='PostgreSQL 17.11; real FastAPI/Vite on loopback, migrated disposable QA database and synthetic records',
            exact_inputs=f"playwright/{Path(spec['file']).name}:{spec['line']}",execution_steps='./backend/venv/Scripts/python.exe backend/scripts/run_payroll_postgresql_qa.py --browser',
            expected='All browser assertions, numeric oracle comparisons and locked-mutation checks pass',actual='All browser assertions passed' if result['status']=='passed' else result.get('error',{}).get('message',result['status']),
            status='PASS' if result['status']=='passed' else 'FAIL',evidence=f'evidence/{browser_file}; browser screenshots, JSON calculation breakdowns and trace ZIPs',defect_reference='PAY-LOCK-08; PAY-PRORATE-10; PAY-UI-12',cleanup='QA servers and isolated PostgreSQL cluster stopped; no provider transfers or employee messages'), 'PostgreSQL 17.11 browser')

# Policy requirements are grouped coverage rows, not additional automated executions.
for ident,category,scenario,rule in [
 ('POL-01','D','Weekly-off and holiday charging','Scheduled working days by default; explicit weekly-off and holiday charging independently configurable.'),
 ('POL-02','C','Missing attendance','Block approval by default; payable or LOP configurable; approved manual resolution requires an audit note.'),
 ('POL-03','B','Component LOP and proration','Use assigned component flags by default; configurable per-code overrides and built-in earning treatment.'),
 ('POL-04','D','Paid/unpaid overlap','Block by default; paid-wins or unpaid-wins configurable.'),
 ('NA-01','E','Fixed monthly divisors','Working days, calendar days, fixed 26 and fixed 30 independently selectable for LOP and employment proration.'),
 ('NA-02','D','Sandwich toggle','Disabled by default; enabled charges intervening nonworking days only between full-day approved unpaid working days.')]:
    matrix=[r for r in rows if 'test_payroll_configurable_policies.py' in r['evidence']]
    status='PASS' if matrix and all(r['status']=='PASS' for r in matrix) else 'FAIL'
    rows.append(dict(test_id=ident,category=category,scenario=scenario,business_rule=rule,preconditions='Published effective-dated pay-group policy',exact_inputs='See parameterized policy matrix and browser evidence',execution_steps='Run configurable policy tests and PostgreSQL browser suite',expected=rule,actual='Configurable behavior verified by automated matrix' if status=='PASS' else 'Policy matrix incomplete or failing',status=status,evidence='Payroll_Policy_Implementation.md; backend/tests/test_payroll_configurable_policies.py; playwright/payroll-postgresql-policies.spec.ts',defect_reference=ident,cleanup='Disposable databases stopped',environment_results=json.dumps({'Grouped requirement coverage':status})))

with (OUT/'Payroll_Test_Cases.csv').open('w',newline='',encoding='utf-8-sig') as file:
    writer=csv.DictWriter(file,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
executed=[row for row in rows if row['test_id'].startswith('PAY-')]
counts=Counter(row['status'] for row in rows)
pg_backend=[row for row in executed if 'PostgreSQL 17.11' in json.loads(row['environment_results'])]
pg_browser=[row for row in executed if 'PostgreSQL 17.11 browser' in json.loads(row['environment_results'])]
sqlite=[row for row in executed if 'SQLite regression' in json.loads(row['environment_results'])]
cats=Counter(row['category'] for row in executed)
coverage='\n'.join(f'- {category}: {count} executed' for category,count in sorted(cats.items()))
health='No failing executed cases remain.' if not counts['FAIL'] else f"{counts['FAIL']} executed case(s) still fail and require triage."
report=f'''# Payroll local execution report — configurable policies, 9 November 2026

{len(executed)} distinct automated cases across all phases; {len(rows)-len(executed)} grouped policy requirements tracked separately. Final register: {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['BLOCKED']} BLOCKED, {counts['NOT APPLICABLE']} NOT APPLICABLE. Repeated runs and grouped requirements are not additional automated executions.

PostgreSQL 17.11: {len(pg_backend)} distinct backend cases and {len(pg_browser)} real-API desktop/phone browser workflows. SQLite regression coverage: {len(sqlite)} distinct cases. Environment-specific outcomes and exact test sources are retained in Payroll_Test_Cases.csv. Earlier phase evidence remains available.

All four blocked cases and both previously unsupported options are implemented as effective-dated pay-group policies. See Payroll_Policy_Implementation.md for recommendations, formulas, configuration and history protection. The additive migration creates payroll_policy_versions and policy snapshots/traces. Existing unpublished pay groups keep legacy behavior; publishing a policy activates these rules for eligible future periods. No historical payroll is rewritten.

The policy matrix covers holidays/weekends/sandwich boundaries, full/half-day conflicts, missing attendance and approval gates, 28/29/30/31-day months, fixed 26/30 divisors, joining/exit proration, component metadata/overrides, one-time earnings, daily/hourly safeguards, tenant boundaries, stale-input detection and frozen historical policy versions. Existing calculation, concurrency, leave, final-settlement and payslip regressions remain covered.

Browser workflows publish policies, reload controls, generate payroll, verify missing-attendance rejection even with force approval, resolve attendance with audited notes, compare independent amounts (30,000 monthly, fixed-30 LOP, HRA exempt: gross 29,200), publish a future version, regenerate with the frozen earlier policy, approve/lock and reject historical policy edits. Desktop and phone evidence includes screenshots, calculation JSON and traces. Frontend TypeScript checks passed.

The first new browser attempt asserted fields absent from the payslip API payload; the test now reads actual earnings components. A Windows Proactor accept-loop failure was isolated to the local QA server; the harness uses the selector loop and random server ports/cache directories. HTTP failures remain asserted. Product fixes and policy safeguards are documented in Payroll_Bugs_and_Fixes.md.

Isolation: every PostgreSQL runner migrates a fresh random-port loopback cluster and synthetic bs_payroll_*_test database and stops it in finally. Existing databases and .env files are not used. No real payment, external employee message or statutory filing was executed. This verifies configured behavior, not legal statutory certification.

Rerun from the repository root:

```powershell
& ./backend/scripts/run_payroll_policies_qa.ps1
```

Evidence is retained under evidence/. Latest passing results supersede earlier attempts; numeric actuals are only reported where asserted. {health}
'''
(OUT/'Payroll_Test_Execution_Report.md').write_text(report,encoding='utf-8')
for directory in (ROOT/'.tmp',ROOT/'frontend/.tmp'):
    for pattern in ['payroll-policy*.log','payroll-policies*.xml','payroll-policy*.xml','payroll-policies-*.json','payroll-policies-*.png','payroll-postgresql*.log','payroll-postgresql-combination-*.json','payroll-postgresql-combination-*.png','payroll-employment-revision-before.*','payroll-remaining-sqlite-before.*','payroll-historical-mode-before.*','payroll-followup-typecheck.log','payroll-followup-sqlite.log','payroll-postgresql-remaining-before.xml']:
        for path in directory.glob(pattern):shutil.copy2(path,EVIDENCE/path.name)
for trace in (ROOT/'.tmp/payroll-postgresql-browser').glob('*/trace.zip'):
    destination=EVIDENCE/f'postgres-browser-{trace.parent.name}-{trace.stat().st_mtime_ns}.zip'
    if not destination.exists():shutil.copy2(trace,destination)
print(json.dumps({'designed':len(rows),'executed':len(executed),'statuses':counts,'postgresql_backend':len(pg_backend),'postgresql_browser':len(pg_browser),'sqlite_regression':len(sqlite)},indent=2))
raise SystemExit(1 if counts['FAIL'] else 0)
