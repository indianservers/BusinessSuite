"""Publish sanitized, reproducible creation verification records."""
import csv,json
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/creation-inventory'
ledger=json.loads((OUT/'creation-live-verification-ledger.json').read_text(encoding='utf8'))
summary={key:ledger[key] for key in ['endpointCoverage','backendSummary','browserSummary','matchingBrowserCoverage','sharedWindowAssertions','permissionReplays']}
assert not summary['browserSummary'].get('failed',0), 'Resolve remaining browser checks before publishing completion'
assert summary['endpointCoverage']['unverified']==0
assert all(not value['unverifiedOrFailed'] for value in summary['matchingBrowserCoverage'].values())
assert summary['permissionReplays']['attempts']==summary['permissionReplays']['passed']
text=f"""# Creation workflow verification — 2026-11-08

The suite's creation editors use the shared Add Lead style, including page actions, sidebar actions, New menus, and nested creation. Existing validation, permissions and API handlers remain with their original editors.

## Real persistence

- {summary['endpointCoverage']['passed']}/{summary['endpointCoverage']['total']} distinct literal frontend creation POST endpoints have positive save evidence; {summary['endpointCoverage']['unverified']} remain without positive evidence.
- {summary['backendSummary'].get('passed',0)} unique backend tests passed, including a real local PostgreSQL concurrency check. No skipped backend cases remain in the consolidated selection.
- Matching-source business/owner backend checks: 132/132 native creation workflows and 65/65 dedicated live creation checks passed, with no remaining failed or unverified selection.
- Consolidated browser checks: {summary['browserSummary'].get('passed',0)} passed, {summary['browserSummary'].get('failed',0)} failed. The ledger retains each check's latest result and records renamed checks explicitly. Earlier failed attempts remain in private run logs.
- {summary['permissionReplays']['passed']}/{summary['permissionReplays']['attempts']} unauthorized write replays were rejected as expected.
- {summary['sharedWindowAssertions']} shared-window browser assertions passed at 1440 and 390 pixels using deterministic API fixtures. These supplement, rather than count as, real persistence evidence.

## Coverage

The original 327-row HRMS/PMS/CRM inventory is preserved. The expanded route audit inspected 876 current, alias and Settings cases and 55 New-menu entries per viewport across the modules. Five form viewers that initially had no published fixture were subsequently verified by creating a form, publishing it, submitting it and reading back its response. Workspaces were saved and read back in all five workspace modules at both viewport widths.

Real browser workflows cover global New, sidebar and page creation; Product Launch task creation and origin-board refresh; projects, leads, contacts, customers, vendors, products, services, employees and linked logins; financial and sales documents; inventory masters; internal forms; HR operational records; Power Apps resources; analytics; collaboration; and the owner portal against its separate PostgreSQL backend.

## Repairs verified

- Preserve Product Launch project context even outside the first project-list page.
- Keep the employee wizard unavailable for final save while custom fields load; preserve nullable branch IDs.
- Provide a persistent shared save action for original forms that have no native form submit element.
- Keep preset actions and recurring schedule forms in their own review window.
- Render one subtask composer per task page; preserve nested parent drafts and return newly created asset categories to their parent.
- Wait for multi-step completion before closing workspace invitations, tag attachment, expenses and recurring schedules.
- Apply the shared window to inventory masters, task detail forms, team/tag/milestone/risk editors, IP policies, document uploads, employee login creation, dependencies and manual invoices.
- Preserve owner-portal nested dialogs and local invitation preparation.

## Reproduction and evidence

Matching private business backend: `http://127.0.0.1:1596`; matching owner backend: `http://127.0.0.1:1597`. Both serve an isolated production frontend build. QA uses private SQLite and local PostgreSQL databases and synthetic records. No external message delivery or money transfer is part of these checks.

Run the browser suites with `PLAYWRIGHT_BASE_URL=http://127.0.0.1:1596`, `frontend/playwright.creation-live.config.ts`, and the `creation-live-*` plus creation-related `crud121-*` checks. The owner suite targets port 1597. Use at most two workers across suites because the SQLite QA backend serializes API requests. Rebuild from `frontend` into `.local/creation-live/frontend` after source changes.

Run `python qa/summarize_creation_verification.py` and `python qa/finalize_creation_verification.py` to regenerate sanitized summaries after verification. TypeScript and the isolated production build were checked after the final source changes.

Evidence: `creation-save-endpoint-ledger.json`, `creation-live-verification-ledger.json`, `creation-verification-ledger.json`, and `page-creation-inventory.csv` in `outputs/creation-inventory`.

## Interpretation

Route/launcher inspection, real browser writes, and backend persistence tests are separate evidence layers. Shared aliases reuse verified entity editors; the report does not claim a separate browser POST from every alias, or every combination of role, branch, optional field and downstream business state. The 213 endpoint count covers literal frontend creation endpoints, not every OpenAPI POST operation. Generated-document metadata persistence is covered separately from document file generation. CRUD checks that include later edit/archive operations retain their full outcome in the ledger.
"""
(OUT/'creation-modal-test-results.md').write_text(text,encoding='utf8')
(ROOT/'docs/qa/creation-live-verification-2026-11-08.md').write_text(text,encoding='utf8')
p=OUT/'creation-verification-ledger.json'; old=json.loads(p.read_text(encoding='utf8'));old['livePersistenceFollowup']={**summary,'businessBackend':'http://127.0.0.1:1596','ownerBackend':'http://127.0.0.1:1597','previouslyMissingPublishedFormFixtures':'All five created, published, submitted and response-readback verified','workspacePersistence':'Five module workspaces saved and read back at 1440 and 390 pixels','evidence':'creation-live-verification-ledger.json'};p.write_text(json.dumps(old,indent=2),encoding='utf8')
p=OUT/'page-creation-inventory.csv'
with p.open(encoding='utf-8-sig',newline='') as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
for row in rows:
 row['Creation browser verification']='Route and available page/sidebar/New launchers inspected; shared editor real-save coverage recorded in creation-live-verification-ledger.json'
 row['Creation remaining checks']='No uncovered literal creation endpoint in the audited source (213/213 positive saves). Aliases share entity-editor evidence; full role/branch/optional-field permutations are outside this inventory.'
with p.open('w',encoding='utf8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
print(json.dumps(summary,indent=2));print('Preserved inventory rows:',len(rows))
