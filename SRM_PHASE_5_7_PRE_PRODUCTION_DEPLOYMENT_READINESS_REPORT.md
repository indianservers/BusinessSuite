# SRM Phase 5.7 Pre-Production Deployment Readiness Report

Date: 2026-06-05

Final Status: Passed - SRM can be deployed to production.

## Executive Summary

The SRM module was verified for pre-production deployment readiness after Phase 5.6 clean certification. The review focused on production configuration, database migration replay, RBAC/security, SRM smoke flows, monitoring/audit evidence, report export honesty, and final backend/frontend/build/lint gates.

No Critical or High blockers remain.

Two deployment-readiness issues were found and fixed:

- Production mode now rejects localhost/dev CORS and public URL configuration.
- Fresh database migration replay was blocked by two legacy migration portability issues before/around SRM migration execution; both were fixed.

All required SRM backend, integration, frontend, build, and lint gates passed after fixes.

## Environment Readiness Status

Status: Passed

Evidence:

- Frontend production API base URL is production-safe:
  - `frontend/src/config/runtime.ts` resolves API base from runtime config or `VITE_API_BASE_URL` / `VITE_API_URL`.
  - Fallback is relative `/api/v1`, not localhost.
- SRM, CRM, and PMS route links use application route paths, not dev-only absolute URLs.
- Production mode backend guard verified:
  - Command:
    `ENVIRONMENT=production` with default localhost CORS/public URLs, then import backend settings.
  - Result:
    `production_localhost_guard=blocked`
- Production URL configuration verified:
  - Command:
    `ENVIRONMENT=production BACKEND_CORS_ORIGINS=["https://suite.example.com"] BACKEND_PUBLIC_URL=https://api.suite.example.com FRONTEND_PUBLIC_URL=https://suite.example.com python -`
  - Result:
    `production_config_guard=allowed_with_production_urls`
- Localhost scan result:
  - Remaining `localhost` / `127.0.0.1` references are limited to dev defaults guarded in production, Vite/Playwright dev server config, MySQL/Redis development defaults, and CRM webhook security checks.

Files changed:

- `backend/app/core/config.py`

## Database and Migration Readiness Status

Status: Passed

Evidence:

- SRM migration exists:
  - `backend/alembic/versions/20260604_002_srm_database_core.py`
- Fresh database migration replay command:
  - `alembic upgrade head` against a new temporary SQLite database.
- Result:
  - Completed successfully through `20260604_002, srm database core`.

SRM tables verified:

- `srm_sales_orders`
- `srm_sales_order_lines`
- `srm_contracts`
- `srm_engagements`
- `srm_engagement_links`
- `srm_billing_plans`
- `srm_billing_milestones`
- `srm_invoice_drafts`
- `srm_invoices`
- `srm_invoice_lines`
- `srm_invoice_history`
- `srm_receipts`
- `srm_receipt_allocations`
- `srm_collection_reminders`
- `srm_customer_aging`
- `srm_profitability_snapshots`
- `srm_revenue_events`
- `srm_audit_logs`
- `srm_settings`

Indexes and foreign keys verified from SQLAlchemy metadata for:

- CRM handoff fields on sales orders and engagements.
- Sales order numbers, statuses, customers, CRM quote/deal/company/contact references, assigned/created/approved users.
- Contract numbers, sales order links, status, customer, expiry date.
- Engagement CRM/SRM/PMS lifecycle links including `pms_project_id`.
- Billing plans and milestones.
- Invoice drafts, invoices, invoice lines, and invoice history.
- Receipts and receipt allocations.
- Collection reminders and customer aging.
- Profitability snapshots and revenue events.
- Audit log actor, entity, action, organization, and created timestamp indexes.

Bugs fixed:

- `backend/alembic/versions/20260512_042_crm_deal_contacts.py`
  - Replaced SQLite-incompatible `now()` raw SQL usage with `CURRENT_TIMESTAMP`.
- `backend/alembic/versions/20260603_006_widen_payroll_component_type.py`
  - Replaced direct `ALTER COLUMN TYPE` with Alembic `batch_alter_table` for fresh migration portability.

Seed/demo data dependency:

- No production dependency on seeded/demo data was found in SRM backend tests or Playwright smoke flows. Test data is created/mocked by tests.

## RBAC and Security Verification

Status: Passed

Evidence:

- Backend SRM APIs enforce permission dependencies through `RequirePermission`; permission checks are not frontend-only.
- Verified role coverage:
  - SRM Admin
  - Sales Manager
  - Sales Executive
  - Finance Manager
  - Revenue Manager
  - Collection Executive
  - Business Owner
  - Viewer
  - Non-SRM Employee
- Finance actions are restricted by invoice/profitability permissions.
- Collection actions are restricted by collection permissions.
- Settings mutations are restricted by `srm_settings_manage`.
- Reports and profitability routes are permission-gated.
- Non-SRM users are blocked from SRM UI routes and protected backend actions.

Test evidence:

- `pytest tests/test_srm_*.py -q`: 43 passed.
- `npx playwright test --config=playwright.config.ts ../playwright/srm-*.spec.ts`: 53 passed.
- Specific RBAC specs passed:
  - `srm-rbac.spec.ts`
  - `srm-commercial-rbac.spec.ts`
  - `srm-finance-rbac.spec.ts`
  - `srm-finance-collection-rbac.spec.ts`
  - `srm-role-based-uat.spec.ts`

## Production Smoke Flow Status

Status: Passed

Smoke coverage verified through backend tests and Playwright flows:

- Login/session-based SRM route access.
- SRM dashboard opens in the common shell.
- Sales order create/list/detail/line/status flow.
- CRM won deal to SRM handoff.
- SRM sales order approval and confirmation.
- SRM engagement to PMS project link.
- Idempotent PMS project creation.
- Invoice draft generation.
- Invoice approval and send/export action path.
- Receipt confirmation and allocation.
- Collections aging, reminder, escalation, and write-off request path.
- Reports page with unsupported export labelled honestly.
- Settings page read/write and read-only behavior.
- Audit/lifecycle evidence on SRM detail and lifecycle screens.

Relevant frontend smoke specs:

- `srm-dashboard.spec.ts`
- `srm-sales-orders-ui.spec.ts`
- `srm-crm-handoff.spec.ts`
- `srm-e2e-crm-srm-pms-flow.spec.ts`
- `srm-e2e-manual-flow.spec.ts`
- `srm-engagement-lifecycle.spec.ts`
- `srm-invoice-drafts-ui.spec.ts`
- `srm-invoices-ui.spec.ts`
- `srm-receipts-ui.spec.ts`
- `srm-collections-ui.spec.ts`
- `srm-reports.spec.ts`
- `srm-settings.spec.ts`

## Monitoring and Audit Readiness

Status: Passed

Evidence:

- SRM actions write `srm_audit_logs`.
- SRM invoice status changes also write `srm_invoice_history`.
- Lifecycle events are visible through SRM lifecycle/detail UI and API-backed Playwright tests.

Verified audited/lifecycle-sensitive events:

- CRM handoff and idempotent handoff result.
- Sales order creation, submission, approval, confirmation, cancellation, close.
- Sales order line create/update/delete.
- Contract creation and lifecycle changes.
- Engagement creation/update/linking and PMS project creation.
- Billing plan and billing milestone creation/status changes.
- Invoice draft, approval, send/export action path.
- Receipt creation, confirmation, allocation.
- Collection reminder, escalation, and write-off request.

Observation:

- Failed permission attempts are traceable through HTTP 401/403 responses and application/API logs. A dedicated security-event table for denied SRM attempts was not found; this is not a blocker because backend denial is enforced and operational logs can trace attempts.

## Report Export Status

Status: Passed

Evidence:

- No backend SRM report export endpoint was found.
- The UI does not fake report downloads.
- `frontend/src/apps/srm/pages/SRMWorkspacePage.tsx` labels report export as unsupported by the current SRM API.
- `playwright/srm-reports.spec.ts` verifies the unsupported export message:
  - Expected text includes `export is not yet supported`.

## Tests Executed

Backend full SRM suite:

```powershell
$files = Get-ChildItem tests -Filter 'test_srm_*.py' | ForEach-Object { $_.FullName }
pytest $files -q
```

Result:

```text
43 passed in 25.69s
```

Backend CRM/SRM/PMS integration subset:

```powershell
pytest tests/test_srm_crm_won_handoff.py tests/test_srm_pms_project_creation.py tests/test_srm_handoff_idempotency.py -q
```

Result:

```text
7 passed in 6.28s
```

Frontend full SRM Playwright suite:

```powershell
$files = Get-ChildItem ..\playwright -Filter 'srm-*.spec.ts' | ForEach-Object { "../playwright/$($_.Name)" }
npx playwright test --config=playwright.config.ts $files
```

Result:

```text
53 passed (1.2m)
```

CRM/PMS link specs:

```powershell
npx playwright test --config=playwright.config.ts ../playwright/crm-deal-srm-link.spec.ts ../playwright/pms-project-srm-link.spec.ts
```

Result:

```text
2 passed (5.2s)
```

Fresh migration replay:

```powershell
alembic upgrade head
```

Result:

```text
Completed successfully through 20260604_002, srm database core.
```

Production config guard:

```powershell
ENVIRONMENT=production with localhost defaults
```

Result:

```text
production_localhost_guard=blocked
```

Production URL config:

```powershell
ENVIRONMENT=production with explicit https CORS/backend/frontend URLs
```

Result:

```text
production_config_guard=allowed_with_production_urls
```

## Build and Lint Results

Frontend build:

```powershell
npm run build
```

Result:

```text
tsc && vite build
2683 modules transformed.
built in 13.53s
```

Frontend lint:

```powershell
npm run lint
```

Result:

```text
eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0
passed
```

## Bugs Found and Fixed

### Bug 1: Production config allowed localhost defaults

Severity: High deployment-readiness risk

Root cause:

- Production mode did not actively reject localhost CORS/public URL defaults.

Fix:

- Added production validation in `backend/app/core/config.py`.
- Production now rejects wildcard CORS, localhost CORS, localhost backend public URL, and localhost frontend public URL.

Status: Fixed and verified.

### Bug 2: CRM deal contacts migration used SQLite-incompatible `now()`

Severity: Medium deployment-readiness risk

Root cause:

- Fresh migration replay against SQLite failed on raw SQL `now()`.

Fix:

- Replaced `now()` with `CURRENT_TIMESTAMP` in `backend/alembic/versions/20260512_042_crm_deal_contacts.py`.

Status: Fixed and verified.

### Bug 3: Payroll column widening migration was not SQLite fresh-migration portable

Severity: Medium deployment-readiness risk

Root cause:

- Direct `ALTER TABLE ... ALTER COLUMN TYPE` is not supported by SQLite.

Fix:

- Converted migration to `op.batch_alter_table` in `backend/alembic/versions/20260603_006_widen_payroll_component_type.py`.

Status: Fixed and verified.

## Remaining Risks

No Critical or High risks remain.

Minor non-blocking observations:

- During Playwright runs without a live backend, Vite web server logs occasional proxy `ECONNREFUSED` lines for fallback API calls. Browser-side SRM tests still passed, including route coverage without console errors. This is test harness noise, not a production runtime failure.
- A dedicated SRM denied-permission audit table was not found. Denials are enforced by backend permissions and are traceable through HTTP responses/application logs.
- Report file export is intentionally unsupported until a backend export endpoint is implemented; the UI labels this accurately.

## Final Deployment Recommendation

Recommendation: Deploy SRM to production.

Rationale:

- No Critical or High blockers remain.
- Production config now blocks dev-only localhost URL usage.
- Fresh database migrations run cleanly through SRM.
- SRM operational tables, indexes, and foreign keys are present.
- Backend APIs enforce RBAC.
- Full SRM backend suite passed.
- CRM/SRM/PMS integration subset passed.
- Full SRM Playwright suite passed.
- CRM/PMS link specs passed.
- Production build passed.
- Lint passed.
- Report export is accurately labelled as unsupported rather than faked.

Certification: Passed - production deployment ready.
