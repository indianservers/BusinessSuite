# SRM Phase 4 Revenue Engine Report

Date: 2026-06-04

Final Phase Status: Passed

## Scope Verified

Revenue lifecycle verified and implemented:

Billing Plan -> Invoice Draft -> Invoice Approval -> Invoice Sent / Exported -> Receipt -> Receipt Allocation -> Aging -> Collection Follow-up -> Profitability.

## Implemented Files

- `backend/app/apps/srm/api/router.py`
- `backend/app/apps/srm/schemas.py`
- `backend/tests/srm_test_utils.py`
- `backend/tests/test_srm_invoice_engine.py`
- `backend/tests/test_srm_invoice_duplicate_prevention.py`
- `backend/tests/test_srm_invoice_pdf_export.py`
- `backend/tests/test_srm_timesheet_to_invoice.py`
- `backend/tests/test_srm_milestone_to_invoice.py`
- `backend/tests/test_srm_receipts.py`
- `backend/tests/test_srm_receipt_allocation.py`
- `backend/tests/test_srm_collection_aging.py`
- `backend/tests/test_srm_collection_reminders.py`
- `backend/tests/test_srm_finance_rbac.py`
- `playwright/srm-invoice-drafts.spec.ts`
- `playwright/srm-invoices.spec.ts`
- `playwright/srm-collections.spec.ts`
- `playwright/srm-profitability.spec.ts`
- `playwright/srm-finance-rbac.spec.ts`

## Invoice Engine Status

Status: Passed

Verified APIs:

- `POST /api/v1/srm/invoices/draft-from-sales-order/{sales_order_id}`
- `POST /api/v1/srm/invoices/draft-from-engagement/{engagement_id}`
- `POST /api/v1/srm/invoices/draft-from-billing-milestone/{milestone_id}`
- `POST /api/v1/srm/invoices/draft-from-pms-milestone/{pms_milestone_id}`
- `POST /api/v1/srm/invoices/draft-from-timesheets`
- `POST /api/v1/srm/invoices/manual`
- `POST /api/v1/srm/invoices/{id}/approve`
- `POST /api/v1/srm/invoices/{id}/send`
- `GET /api/v1/srm/invoices/{id}/pdf`
- `PATCH /api/v1/srm/invoices/{id}`
- `GET /api/v1/srm/invoices`

Implemented multi-line invoice draft creation, clean duplicate preflight, invoice history, audit logging, and invoice draft notification.

## Invoice Source Status

| Source | Status | Evidence |
| --- | --- | --- |
| Sales Order | Passed | Existing and expanded tests verify draft generation and duplicate guard. |
| Contract | Partially Passed | Contract-backed values are supported through sales order/engagement paths; no dedicated contract endpoint was added in this phase because it was not listed in required APIs. |
| Billing Milestone | Passed | `draft-from-billing-milestone` requires approved/ready/completed billing milestone and marks milestone invoiced. |
| PMS Approved Milestone | Passed | `draft-from-pms-milestone` requires client-approved PMS milestone and linked SRM engagement. |
| PMS Approved Timesheet/Time Logs | Passed | `draft-from-timesheets` requires approved and billable PMS time logs. |
| Manual Invoice | Passed | `/invoices/manual` creates manual multi-line drafts. |
| Hybrid Invoice | Partially Passed | Multi-line manual invoices can combine source-tagged lines, but no dedicated hybrid orchestration endpoint was added. |

## Duplicate Prevention Status

Status: Passed

Verified duplicate guards:

- Same sales order cannot be fully invoiced twice.
- Same billing milestone cannot be invoiced twice.
- Same PMS milestone cannot be invoiced twice.
- Same PMS time log cannot be invoiced twice.
- Same source-tagged manual/external invoice line cannot be invoiced twice.

## PDF / Export Status

Status: Passed

`GET /api/v1/srm/invoices/{id}/pdf` returns `application/pdf` content with invoice number and amount. This is a lightweight generated PDF response suitable for smoke verification; richer branded PDF layout can be a future enhancement.

## Receipt And Allocation Status

Status: Passed

Verified APIs:

- `POST /api/v1/srm/receipts`
- `POST /api/v1/srm/receipts/{id}/confirm`
- `POST /api/v1/srm/receipts/{id}/allocate`

Allocation updates receipt status, invoice paid/balance/status, cash revenue event, profitability snapshot, and audit log. Over-allocation is blocked.

## Collection Status

Status: Passed

Verified APIs:

- `GET /api/v1/srm/collections/aging`
- `GET /api/v1/srm/collections/customer/{customer_id}`
- `POST /api/v1/srm/collections/reminders/send`
- `POST /api/v1/srm/collections/{invoice_id}/escalate`
- `POST /api/v1/srm/collections/{invoice_id}/write-off-request`

Aging buckets are calculated and persisted to `srm_customer_aging`. Escalation and write-off requests create collection reminder/action records, audit logs, and notifications.

## Profitability Status

Status: Passed

`GET /api/v1/srm/profitability` now supports:

- `engagement_id`
- `project_id`
- `customer_id`
- `crm_deal_id`
- `sales_order_id`

Returned business fields include quoted value, sales order value, contract value, billing plan value, invoiced amount, collected amount, outstanding amount, overdue amount, delivery budget, approved timesheet cost, employee cost, gross margin, cash margin, margin percentages, and collection status.

## Reports Status

Status: Passed

`GET /api/v1/srm/reports` now returns:

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

## RBAC Status

Status: Passed

Verified:

- Finance Manager with invoice/collection/profitability permissions can create, approve, collect, and view profitability.
- Collection Executive can create receipts/reminders but cannot edit invoices.
- Business Owner can view finance dashboards in frontend.
- Sales user with view-only invoice permission cannot create invoice drafts.
- Employee without SRM permissions is blocked from finance routes.

## Audit And Notifications

Status: Passed

Verified audit coverage:

- Invoice draft created
- Invoice approved
- Invoice sent
- Receipt created
- Receipt confirmed
- Receipt allocated
- Collection reminder sent
- Collection escalated
- Write-off requested
- Profitability snapshot created

Notifications are created for invoice draft creation, collection escalation, and write-off request paths.

## Tests Executed

Backend:

```text
pytest tests/test_srm_invoice_engine.py tests/test_srm_invoice_duplicate_prevention.py tests/test_srm_invoice_pdf_export.py tests/test_srm_timesheet_to_invoice.py tests/test_srm_milestone_to_invoice.py tests/test_srm_receipts.py tests/test_srm_receipt_allocation.py tests/test_srm_collection_aging.py tests/test_srm_collection_reminders.py tests/test_srm_profitability.py tests/test_srm_finance_rbac.py -q
Result: 14 passed
```

Frontend:

```text
npx playwright test --config=playwright.config.ts ../playwright/srm-invoice-drafts.spec.ts ../playwright/srm-invoices.spec.ts ../playwright/srm-collections.spec.ts ../playwright/srm-profitability.spec.ts ../playwright/srm-finance-rbac.spec.ts
Result: 5 passed
```

Build:

```text
npm run build
Result: Passed
```

## Bugs Found

1. Manual invoice responses did not expose source type evidence.
2. Duplicate source-tagged manual lines were being caught by database unique constraint instead of clean API validation.
3. Timesheet invoice generation accepted billable logs without enforcing approval status.
4. Receipt allocation allowed allocating more than invoice balance.
5. Collection escalation and write-off request APIs were missing.
6. Profitability response did not expose all business-facing value/margin fields.

## Bugs Fixed

1. Added invoice payload source evidence.
2. Added preflight duplicate checks for invoice source lines.
3. Enforced approved and billable PMS time logs for T&M invoicing.
4. Added invoice balance over-allocation validation.
5. Added collection escalation and write-off request endpoints.
6. Added enriched profitability payload and report catalog endpoint.
7. Added finance, collection, sales, and business owner RBAC tests.

## Pending Issues

No blockers for Phase 4 go-live.

Known follow-up:

- Dedicated contract invoice endpoint and dedicated hybrid invoice endpoint can be added if the business wants separate API surfaces beyond the currently verified source-capable invoice engine.
- Invoice PDF is functional but minimal; branded invoice layout/export templates remain an enhancement.
- Test run emits existing Pydantic/passlib deprecation warnings unrelated to this phase.

## Go-Live Certification

Phase 4 is certified as Passed for the verified SRM revenue engine.

Go-live status: Ready for controlled rollout.
