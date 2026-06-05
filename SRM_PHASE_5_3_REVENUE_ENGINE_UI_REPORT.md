# SRM Phase 5.3 Revenue Engine UI Report

Date: 2026-06-05  
Final Phase Status: Passed

## Scope Verified

Phase 5.3 was limited to the SRM revenue engine UI for invoice drafts, invoices, receipts, collections, profitability, revenue operations, and finance/collection RBAC. Prior SRM foundation, CRM handoff, and dashboard/customer-360 scope were not refactored.

## Implemented Files

- `frontend/src/apps/srm/api.ts`
  - Added UI client methods for manual invoices, invoice draft sources, invoice lines, receipt creation/confirmation/allocation, collection reminders/escalations/write-off requests, customer collections, and profitability filters.
- `frontend/src/apps/srm/pages/SRMWorkspacePage.tsx`
  - Added `InvoiceDraftsView`, `InvoicesView`, `CollectionsView`, `ProfitabilityView`, and `RevenueEventsView`.
  - Added revenue action handling with visible UI status messages.
  - Added finance/collection action visibility checks.
  - Increased summary evidence display so profitability values include revenue, cost, margin, and collection status.
- `playwright/srm-test-utils.ts`
  - Added SRM finance/revenue/viewer test roles and mocked revenue-engine API responses.
- `playwright/srm-invoice-drafts-ui.spec.ts`
- `playwright/srm-invoices-ui.spec.ts`
- `playwright/srm-receipts-ui.spec.ts`
- `playwright/srm-collections-ui.spec.ts`
- `playwright/srm-profitability-ui.spec.ts`
- `playwright/srm-revenue-events-ui.spec.ts`
- `playwright/srm-finance-collection-rbac.spec.ts`

## Routes Verified

- `/srm/invoice-drafts` - Passed
- `/srm/invoices` - Passed
- `/srm/collections` - Passed
- `/srm/profitability` - Passed
- `/srm/revenue-recognition` - Passed as Revenue Events / Revenue Operations, not full IFRS 15 automation
- `/srm/settings` RBAC denial for collection executive - Passed

## APIs Verified Through UI Tests

- `POST /api/v1/srm/invoices/draft-from-sales-order/{id}`
- `POST /api/v1/srm/invoices/draft-from-engagement/{id}`
- `POST /api/v1/srm/invoices/draft-from-billing-milestone/{id}`
- `POST /api/v1/srm/invoices/draft-from-pms-milestone/{id}`
- `POST /api/v1/srm/invoices/draft-from-timesheets`
- `POST /api/v1/srm/invoices/manual`
- `GET /api/v1/srm/invoice-drafts`
- `GET /api/v1/srm/invoices`
- `GET /api/v1/srm/invoices/{id}`
- `POST /api/v1/srm/invoices/{id}/approve`
- `POST /api/v1/srm/invoices/{id}/send`
- `POST /api/v1/srm/invoices/{id}/lines`
- `GET /api/v1/srm/invoices/{id}/pdf`
- `POST /api/v1/srm/receipts`
- `POST /api/v1/srm/receipts/{id}/confirm`
- `POST /api/v1/srm/receipts/{id}/allocate`
- `GET /api/v1/srm/collections/aging`
- `GET /api/v1/srm/collections/customer/{customer_id}`
- `POST /api/v1/srm/collections/reminders/send`
- `POST /api/v1/srm/collections/{invoice_id}/escalate`
- `POST /api/v1/srm/collections/{invoice_id}/write-off-request`
- `GET /api/v1/srm/profitability`
- `GET /api/v1/srm/dashboard`
- `GET /api/v1/srm/reports/lead-to-cash`

## Feature Results

| Feature | Status | Evidence |
|---|---|---|
| Invoice draft UI | Passed | Draft actions for sales order, engagement, billing milestone, PMS milestone, timesheets, and manual invoice verified. Duplicate/error message verified. |
| Invoice UI | Passed | Invoice detail, approval, send/export, PDF link, invoice lines, allocation section, audit/history, and API validation error verified. |
| Receipts UI | Passed | Receipt create, confirm, partial allocation, full allocation, and allocation validation error verified. |
| Collections UI | Passed | Aging buckets, invoice aging, customer outstanding, reminders, escalation, write-off request, and history sections verified. |
| Profitability UI | Passed | Filters and ordered profitability evidence for quoted value, sales order value, contract value, billing plan value, costs, gross margin, cash margin, and collection status verified. |
| Revenue Recognition route | Passed | UI labels route as Revenue Events / Revenue Operations and explicitly states it is not a full IFRS 15 automation engine. |
| Finance/Collection RBAC | Passed | Finance manager actions visible; collection executive collection actions visible but settings denied; sales executive and non-SRM employee denied; business owner read-only behavior verified. |

## Bugs Found And Fixed

- Playwright selectors were ambiguous because toast notifications and in-page action messages both expose `role=status`.
  - Fix: Scoped status assertions to `main`.
- Repeated headings caused strict-mode failures in Playwright.
  - Fix: Used level/exact heading assertions.
- Profitability mock response did not include the full revenue/cost/margin evidence expected by the UI verification.
  - Fix: Expanded SRM profitability test payload.
- Profitability summary card did not expose late-order cash margin and collection status fields.
  - Fix: Added ordered profitability evidence object and increased summary display cap.

## Tests Executed

Backend command:

```powershell
pytest tests/test_srm_invoice_engine.py tests/test_srm_invoice_duplicate_prevention.py tests/test_srm_invoice_pdf_export.py tests/test_srm_timesheet_to_invoice.py tests/test_srm_milestone_to_invoice.py tests/test_srm_receipts.py tests/test_srm_receipt_allocation.py tests/test_srm_collection_aging.py tests/test_srm_collection_reminders.py tests/test_srm_profitability.py tests/test_srm_finance_rbac.py -q
```

Backend result: Passed, 14 passed, 1073 warnings.

Frontend command:

```powershell
npx playwright test --config=playwright.config.ts ../playwright/srm-invoice-drafts-ui.spec.ts ../playwright/srm-invoices-ui.spec.ts ../playwright/srm-receipts-ui.spec.ts ../playwright/srm-collections-ui.spec.ts ../playwright/srm-profitability-ui.spec.ts ../playwright/srm-revenue-events-ui.spec.ts ../playwright/srm-finance-collection-rbac.spec.ts
```

Frontend result: Passed, 13 passed.

Build command:

```powershell
npm run build
```

Build result: Passed. TypeScript and Vite production build completed successfully.

## Pending Issues

- Backend regression emits existing deprecation warnings for Pydantic V2 style migration, pytest-asyncio, and `python-jose` datetime usage. These warnings did not fail Phase 5.3 tests.
- Revenue recognition remains correctly labelled as operational revenue events; no full IFRS 15 automation was certified in this phase.

## Certification

SRM Phase 5.3 Revenue Engine UI is certified as Passed for the requested scope. Invoice drafts, invoices, receipts, collections, profitability, revenue events, finance/collection RBAC, backend regression, frontend Playwright verification, and frontend build were all verified from actual code and tests.
