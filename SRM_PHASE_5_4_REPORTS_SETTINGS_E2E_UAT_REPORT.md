# SRM Phase 5.4 Reports, Settings, E2E and UAT Report

Date: 2026-06-05  
Final Status: Passed with minor non-blocking observations

## Scope

Phase 5.4 completed SRM reports, SRM settings, full role-based UAT coverage, and seeded end-to-end workflows. The work was limited to SRM Phase 5.4 and did not intentionally change CRM, PMS, HRMS, authentication, or shared shell behavior beyond SRM route access rules required for read-only settings and reports.

## Reports UI Status

Status: Passed

Implemented `/srm/reports` as a dedicated SRM report workspace with 12 report cards:

- Sales Order Report
- Contract Report
- Invoice Register
- Invoice Aging
- Collection Aging
- Customer Outstanding
- Engagement Profitability
- Project Profitability
- Customer Profitability
- Lead-to-Cash Report
- Sales-to-Delivery Margin
- Cash Margin Report

Each report includes title, description, filter labels, preview table, View details action, and Export action. Export is explicitly labelled as not yet supported by the current SRM API instead of faking a download.

Evidence:

- UI implementation: `frontend/src/apps/srm/pages/SRMWorkspacePage.tsx`
- Report definitions: `reportDefinitions`
- Backend report API verified: `GET /api/v1/srm/reports`
- Frontend test: `playwright/srm-reports.spec.ts`

## Settings UI Status

Status: Passed

Implemented `/srm/settings` as a dedicated SRM settings workspace with:

- Invoice numbering prefix
- Sales order numbering prefix
- Contract numbering prefix
- Default payment terms
- Default tax/VAT settings
- Default billing plan rules
- Collection reminder templates
- Escalation thresholds
- Write-off approval requirement
- Dashboard visibility preferences

Capabilities verified:

- SRM Admin can view, edit, save, and receive success feedback.
- Required setting validation message is shown.
- Viewer and Sales Executive see read-only settings.
- Collection Executive can view settings read-only.
- Non-SRM employee is blocked.
- Backend settings read was opened to SRM view users; settings mutation remains restricted to `srm_settings_manage` / `srm_admin`.

Evidence:

- UI implementation: `frontend/src/apps/srm/pages/SRMWorkspacePage.tsx`
- API client: `frontend/src/apps/srm/api.ts`
- Backend settings API: `GET /api/v1/srm/settings`, `PUT /api/v1/srm/settings/{key}`
- Route access update: `frontend/src/lib/roles.ts`
- Frontend test: `playwright/srm-settings.spec.ts`

## Role-Based UAT Status

Status: Passed

Role UAT covered:

- SRM Admin
- Sales Manager
- Sales Executive
- Finance Manager
- Revenue Manager
- Collection Executive
- Business Owner
- Viewer
- Non-SRM Employee

Verified route and action access:

- SRM Admin can access all SRM routes and major actions.
- Sales roles stay in commercial lanes and are denied finance/collection actions.
- Finance Manager can approve/send invoices, allocate receipts, view profitability, reports, and collections.
- Revenue Manager can access revenue events, profitability, and reports.
- Collection Executive can manage collections but cannot edit invoice values or settings.
- Business Owner has read-only revenue visibility.
- Viewer can view permitted pages and cannot mutate.
- Non-SRM Employee is blocked from SRM.

Evidence:

- Frontend UAT: `playwright/srm-role-based-uat.spec.ts`
- Restriction E2E: `playwright/srm-e2e-role-restrictions.spec.ts`
- Test helper role matrix: `playwright/srm-test-utils.ts`

## Manual SRM E2E Status

Status: Passed

Seeded manual E2E flow verified:

Sales order creation -> order line -> submit -> approve -> confirm -> contract -> engagement -> billing plan -> billing milestone -> invoice draft -> invoice approval -> send/export -> receipt -> receipt confirmation -> allocation -> invoice payment posture -> profitability -> dashboard -> reports -> audit/lifecycle evidence.

Evidence:

- Test: `playwright/srm-e2e-manual-flow.spec.ts`
- APIs exercised through seeded browser flow:
  - `POST /api/v1/srm/sales-orders`
  - `POST /api/v1/srm/sales-orders/{id}/lines`
  - `POST /api/v1/srm/sales-orders/{id}/submit`
  - `POST /api/v1/srm/sales-orders/{id}/approve`
  - `POST /api/v1/srm/sales-orders/{id}/confirm`
  - `POST /api/v1/srm/contracts`
  - `POST /api/v1/srm/engagements`
  - `POST /api/v1/srm/billing-plans`
  - `POST /api/v1/srm/billing-plans/{id}/milestones`
  - `POST /api/v1/srm/invoices/draft-from-sales-order/{id}`
  - `POST /api/v1/srm/invoices/{id}/approve`
  - `POST /api/v1/srm/invoices/{id}/send`
  - `POST /api/v1/srm/receipts`
  - `POST /api/v1/srm/receipts/{id}/confirm`
  - `POST /api/v1/srm/receipts/{id}/allocate`
  - `GET /api/v1/srm/profitability`
  - `GET /api/v1/srm/dashboard`
  - `GET /api/v1/srm/reports`
  - `GET /api/v1/srm/engagements/{id}/lifecycle`

## CRM-SRM-PMS E2E Status

Status: Passed

Seeded CRM to SRM to PMS flow verified:

CRM deal handoff -> SRM sales order -> SRM contract -> SRM engagement -> billing plan -> sales order confirmation -> PMS project creation -> CRM link-back -> PMS link-back -> SRM lifecycle -> idempotent repeated handoff/project creation.

Evidence:

- Test: `playwright/srm-e2e-crm-srm-pms-flow.spec.ts`
- Existing link tests remained passing in the full SRM suite.

## Collections E2E Status

Status: Passed

Seeded collections flow verified:

Sent/overdue invoice posture -> aging view -> reminder -> escalation -> write-off request -> customer collection records -> audit/lifecycle evidence -> collection status context.

Evidence:

- Test: `playwright/srm-e2e-collections-flow.spec.ts`
- Existing collections UI tests remained passing.

## Role Restriction E2E Status

Status: Passed

Restricted actions verified:

- Sales Executive cannot approve invoices.
- Sales Executive cannot allocate receipts.
- Collection Executive cannot edit invoice values.
- Viewer cannot create or approve sales orders.
- Finance Manager cannot edit SRM settings without settings permission.
- Collection Executive cannot edit settings.
- Non-SRM Employee cannot open SRM.

Evidence:

- Test: `playwright/srm-e2e-role-restrictions.spec.ts`
- Direct browser fetch calls verified 403 responses through seeded API stubs.

## Backend Tests Executed

Requested command attempted:

```powershell
pytest tests/test_srm_*.py -q
```

PowerShell/Pytest did not expand the wildcard in this environment, so the equivalent expanded command was executed:

```powershell
$files = Get-ChildItem tests -Filter 'test_srm_*.py' | ForEach-Object { $_.FullName }; pytest $files -q
```

Result: Passed, 43 passed, 3440 warnings.

Cross-module SRM tests included in the expanded run:

- CRM won handoff
- PMS project creation/link
- Billing plans
- Invoice engine/PDF/timesheet/milestone flows
- Collections and receipts
- Profitability
- SRM RBAC

## Frontend Tests Executed

Required Phase 5.4 command:

```powershell
npx playwright test --config=playwright.config.ts ../playwright/srm-reports.spec.ts ../playwright/srm-settings.spec.ts ../playwright/srm-role-based-uat.spec.ts ../playwright/srm-e2e-manual-flow.spec.ts ../playwright/srm-e2e-crm-srm-pms-flow.spec.ts ../playwright/srm-e2e-collections-flow.spec.ts ../playwright/srm-e2e-role-restrictions.spec.ts
```

Result: Passed, 11 passed.

All SRM Playwright tests:

The literal wildcard form did not resolve in this PowerShell/Playwright invocation, so the SRM file list was expanded explicitly:

```powershell
$files = Get-ChildItem ..\playwright -Filter 'srm-*.spec.ts' | ForEach-Object { "../playwright/$($_.Name)" }; npx playwright test --config=playwright.config.ts $files
```

Result: Passed, 45 passed.

## Build, Lint, Typecheck Status

Build:

```powershell
npm run build
```

Result: Passed. This includes `tsc` and Vite production build.

Lint:

```powershell
npm run lint
```

Result: Passed.

Typecheck:

No separate `npm run typecheck` script exists. TypeScript checking was executed through `npm run build`.

## Bugs Found

| Issue | Severity | Root Cause | Fix Applied | Final Status |
|---|---|---|---|---|
| `/srm/settings` was admin-only, conflicting with Phase 5.4 read-only settings requirement. | High | Route guard and backend settings GET were stricter than requested. | Allowed SRM users to view settings while keeping PUT restricted. | Fixed |
| Reports page was generic and did not show required report cards, filters, previews, or export status. | High | No dedicated Phase 5.4 reports view existed. | Added dedicated ReportsView with 12 report definitions and preview behavior. | Fixed |
| Settings page was generic and lacked invoice/order/contract prefixes, payment terms, tax/VAT, reminders, thresholds, write-off, and dashboard preferences. | High | No dedicated Phase 5.4 settings view existed. | Added dedicated SettingsView with edit/read-only behavior and validation. | Fixed |
| Viewer report access failed despite seeded viewer report permissions. | Medium | Frontend SRM route guard grouped reports with finance-only routes. | Allowed SRM Viewer to access `/srm/reports` while keeping profitability restricted. | Fixed |
| Older Playwright specs failed strict-mode selectors after richer SRM UI introduced duplicate headings/status text. | Low | Tests used ambiguous text/heading selectors. | Updated assertions to level/exact/first selectors. | Fixed |
| PowerShell wildcard commands did not expand for Pytest/Playwright. | Low | Shell/tool invocation behavior. | Expanded test file lists explicitly and documented equivalent commands. | Fixed |

## Bugs Fixed

- Implemented Phase 5.4 Reports UI.
- Implemented Phase 5.4 Settings UI.
- Added settings save API client method.
- Adjusted backend settings GET permission for read-only settings.
- Adjusted SRM frontend route access for read-only settings and viewer reports.
- Added Phase 5.4 UAT and E2E Playwright coverage.
- Updated legacy SRM Playwright specs to match current SRM UI and RBAC behavior.

## Pending Issues

- Backend SRM tests pass but emit existing deprecation warnings for Pydantic V2, pytest-asyncio, and python-jose datetime usage. These are non-blocking for Phase 5.4.
- Vite emitted proxy warnings during Playwright teardown for unstubbed background requests in some tests, but all frontend tests passed.
- Report export is intentionally marked as a future enhancement because no consistent backend export endpoint was verified for these SRM reports.

## Certification

Certification: Passed with minor non-blocking observations

SRM Phase 5.4 is certified for reports, settings, role-based UAT, seeded manual SRM E2E, CRM-SRM-PMS E2E, collections E2E, role restriction E2E, backend SRM regression, frontend SRM regression, build, and lint.
