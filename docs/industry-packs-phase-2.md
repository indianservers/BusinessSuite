# Industry packs and onboarding — Phase 2

Implemented 7 November 2026. The packs configure real CRM operations on the existing platform. They are not a certification of specialist salon, workshop, dealer, filing or logistics engines.

## Where to start

Open **CRM → Pipeline templates** (`/crm/pipeline-templates`) and choose **Set up this industry pack**. The workspace setup guide links to this page. Document/mail-merge templates at `/crm/templates` keep their existing purpose.

The installer requires organization administration, the native CRM, automation and analytics configuration permissions, and the existing administrator password/social verification. Choose an existing active, centrally managed CRM execution identity with viewing and task-creation permission. Superusers are not execution identities. The runtime continues checking that identity's current access and record visibility on every execution.

## Reused components

The canonical catalog contains the 56 existing pipeline templates plus Bike Repair Shop, Bike Sales, Accounting Firm and MSME Trading variants. Both the frontend library and backend installer read the same checked-in catalog.

Each of the 60 packs installs:

- A native CRM pipeline, its industry stages and namespaced business fields.
- Three published, immutable-versioned workflows in the existing shared workflow engine: a task after a new record, an in-app reminder if the record is still open after 24 hours, and a handoff task when entering the second stage.
- Three saved reports in Analytics: pipeline records with business fields, SQL stage totals, and the linked CRM follow-up task queue. Report totals and pages come from scoped source queries, not sample arrays. Industry pipeline filters cannot be overridden at run time.
- A private, versioned form in the existing Forms module for collecting intake responses. It does not automatically create a commercial record or publish a public website form.
- Two central Access Management templates (viewer and operator), with own-record scope and native CRM/report permissions. Installation does not assign users or change their access policies.

Recommended existing modules can be enabled during onboarding subject to existing entitlements. Other enabled modules are preserved. Pack installation does not bypass module access, create a second workflow engine or duplicate the accounting/stock/project modules.

The main native deal capture and detail forms select business fields for the record's pipeline. Native deal writes reject fields belonging to another pack pipeline. Pack extra fields remain optional at CRM storage level so installing a pack does not impose new required fields on unrelated pipelines.

## Actual workflow execution

Native deal creation and stage changes emit shared service events. The existing scheduled-job processor dispatches matching published workflows and executes the native CRM task API or in-app notification adapter. The deployment must continue running its scheduled-job processor; installation is not a substitute for operating that worker.

The 24-hour reminder rechecks the current record status before notifying. Re-saving an unchanged stage does not produce another stage-handoff task. Disabled/revoked execution identities cannot continue to act. No email, SMS or WhatsApp provider action is installed or sent.

Earlier template previews listed specialist suggestions such as stylist utilization, statutory filing automation or transport dispatch. The catalog now advertises the concrete follow-up workflows and reports that are implemented. Specialist operating capabilities remain in the later phases.

## Lifecycle and preservation

The existing company-scoped DomainPackRegistry stores namespaced installation manifests, asset IDs, catalog version/digest, configuration fingerprints and version history. No new database tables or migration are required.

- Installation is transactional and serializes on the company row. A failed publication or configuration step rolls back the installation.
- Repeated installation of the same unchanged version reuses the existing assets and does not create duplicate workflows, reports, forms or pipelines.
- Upgrades require the expected installed version. Existing IDs and business records are retained; new fields/assets can be added.
- Edits or removal of managed assets cause a conflict rather than silently overwriting customer configuration. Catalog changes require a version bump.
- Changes that remove installed assets/options or change field types require an explicit migration and are rejected by the automatic installer.
- Disable stops pack workflows, cancels pending jobs for the exact company/published workflow versions, closes intake, deactivates the pipeline and gates pack reports. It preserves customers, deals, tasks, responses, published versions and execution history.
- Background job cancellation uses a company-and-version-constrained queue update after company administration and verification checks, because background rows can be absent from a user's branch-scoped view.
- Re-enable reuses native assets and publishes new execution versions. In-flight operations with uncertain outcomes are not silently retried or erased.
- The older workforce-domain-pack endpoint cannot partially disable these installations.

No destructive uninstall is exposed. Staff access is managed separately through existing central Access Management; disabling a pack does not silently revoke legitimate access to retained business records.

## Sample data

Installation starts without customers or deals. **Add optional sample records** is a separate verified action. It creates labelled `[Sample]` deal rows, is repeatable without duplicates and suppresses workflow generation during initial demo creation. Samples use the effective CRM currency. They are visible business records and will appear in reports if explicitly added; they are not accounting postings or customer messages.

## APIs

All routes are authenticated and registered under the existing CRM access boundary:

- `GET /industry-packs/catalog`
- `GET /industry-packs/installed`
- `GET /industry-packs/execution-identities`
- `POST /industry-packs/{key}/preflight`
- `POST /industry-packs/{key}/install`
- `POST /industry-packs/{key}/disable`
- `POST /industry-packs/{key}/sample-data`

Install payload: `run_as_user_id`, optional `modules`, and `expected_version` for an existing version. Mutations use the existing `X-Access-Step-Up` verification header. Saved reports run/export through the normal Analytics endpoints.

## Verification

Results: 104 backend regression tests passed, 25 pack acceptance tests passed on isolated PostgreSQL, and five final report-scope/export/lifecycle checks passed after tightening multi-company-owner isolation. Desktop/mobile onboarding checks and the final TypeScript/Vite production build passed. These suites overlap; the counts are not distinct totals. JUnit reports contain zero failures, errors or skipped cases.

Backend acceptance exercises actual HTTP deal writes, event capture, shared job execution, native task creation, delayed notification, real report queries/totals/custom fields/CSV export, tenant isolation, privilege/revocation checks, idempotency, rollback, conflict preservation, upgrades, disable/re-enable, optional demo data and destructive-update rejection. Every catalog template's three graphs are validated.

The PostgreSQL runner creates and stops a separate loopback-only test cluster and applies the real migration setup. It never changes the app database. The browser suite mounts production onboarding components with mocked APIs and checks managed-identity selection, verification, preflight conflicts, clean setup, report preview, explicit sample opt-in, disable and desktop/mobile layout.

Commands from `backend`:

```powershell
$env:FAST_TEST_PASSWORD_HASHES='1'
./venv/Scripts/python.exe -m pytest tests/test_industry_packs.py -q
./venv/Scripts/python.exe scripts/verify_customization_postgresql.py tests/test_industry_packs.py
```

Commands from `frontend`:

```powershell
node scripts/test-industry-packs.cjs
npm.cmd run build
```

Acceptance artifacts are under `outputs/industry-packs-phase-2/` (JUnit reports and desktop/mobile screenshots). Live deployment/provider operations are not part of these local tests.

Next phase: shared resource booking and salon operations, reusing CRM, HR, services, POS, inventory and finance.
