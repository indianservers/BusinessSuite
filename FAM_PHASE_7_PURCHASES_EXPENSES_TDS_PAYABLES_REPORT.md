# FAM Phase 7 - Purchases, Expenses, TDS and Payables Report

## Executive Summary

Final Status: Passed

FAM Phase 7 has been implemented and verified for India-first purchase and expense operations. The module now supports vendor purchase bills, purchase bill posting through the existing voucher engine, expense claims, configurable TDS sections/rates, TDS calculation and transaction tracking, vendor payment runs, purchase/expense registers, and a payables dashboard tied back to AP bill references.

TDS return filing/export remains intentionally unsupported and is labelled as not configured/unsupported where applicable.

## Implemented Backend

- Models/tables: `fam_purchase_bills`, `fam_purchase_bill_lines`, `fam_expense_claims`, `fam_expense_lines`, `fam_tds_sections`, `fam_tds_rates`, `fam_tds_transactions`, `fam_vendor_payment_runs`, `fam_vendor_payment_items`, `fam_purchase_audit_logs`.
- Migration: `backend/alembic/versions/20260606_017_fam_phase_7_purchases_tds_payables.py`.
- Schemas: purchase bills/lines, expense claims/lines, TDS sections/rates/calculation, vendor payment payloads.
- APIs:
  - `GET/POST /api/v1/fam/purchase-bills`
  - `GET/PUT /api/v1/fam/purchase-bills/{id}`
  - `POST /api/v1/fam/purchase-bills/{id}/post`
  - `POST /api/v1/fam/purchase-bills/{id}/cancel`
  - `GET/POST /api/v1/fam/expenses`
  - `POST /api/v1/fam/expenses/{id}/post`
  - `GET/POST /api/v1/fam/tds/sections`
  - `GET/POST /api/v1/fam/tds/rates`
  - `POST /api/v1/fam/tds/calculate`
  - `GET /api/v1/fam/tds/transactions`
  - `GET /api/v1/fam/tds/payable`
  - `GET /api/v1/fam/purchase-register`
  - `GET /api/v1/fam/expense-register`
  - `GET /api/v1/fam/payables/dashboard`
  - `POST /api/v1/fam/vendor-payments/prepare`
  - `POST /api/v1/fam/vendor-payments/post`

## Posting and Accounting Verification

- Purchase bills post through the existing FAM voucher engine.
- Purchase/expense ledgers are debited from purchase/expense lines.
- Input GST is posted separately from TDS payable using tax ledger selection by GST/TDS keyword where configured.
- Vendor ledger is credited for payable amount.
- TDS payable ledger is credited when TDS exists.
- TDS transactions are created with section, vendor, taxable amount, rate, deduction date, and deducted status.
- Vendor payments debit vendor ledger and credit bank/cash ledger.
- Purchase bill AP references are created and flow into AP aging/outstanding.

## Frontend

Created/verified pages:

- `/fam/purchases`
- `/fam/purchase-bills`
- `/fam/purchase-bills/new`
- `/fam/purchase-bills/:id`
- `/fam/expenses`
- `/fam/expenses/new`
- `/fam/tds`
- `/fam/tds/sections`
- `/fam/tds/transactions`
- `/fam/tds/payable`
- `/fam/purchase-register`
- `/fam/expense-register`
- `/fam/vendor-payments`
- `/fam/payables/dashboard`

Sidebar/navigation and route guards were updated for the new purchase, TDS, vendor payment, register, and payables dashboard pages.

## RBAC

Implemented/verified permissions:

- `fam_purchase_view`
- `fam_purchase_manage`
- `fam_expense_view`
- `fam_expense_manage`
- `fam_tds_view`
- `fam_tds_manage`
- `fam_vendor_payment_manage`

Backend APIs enforce permissions using `RequirePermission`; frontend routes are also guarded for FAM roles. Non-FAM employees are blocked from Phase 7 FAM routes.

## Tests Executed

Backend targeted:

```powershell
pytest tests/test_fam_purchase_bills.py tests/test_fam_purchase_posting.py tests/test_fam_expenses.py tests/test_fam_tds_sections.py tests/test_fam_tds_calculation.py tests/test_fam_tds_posting.py tests/test_fam_vendor_payments.py tests/test_fam_purchase_register.py tests/test_fam_purchase_rbac.py -q
```

Result: 9 passed.

Backend full FAM:

```powershell
$files = Get-ChildItem tests\test_fam_*.py | ForEach-Object { $_.FullName }; pytest $files -q
```

Result: 79 passed.

Migration:

```powershell
alembic upgrade head; alembic current
```

Result: upgraded `20260606_016 -> 20260606_017`; current head `20260606_017`.

Frontend targeted:

```powershell
npx playwright test --config=playwright.config.ts ../playwright/fam-purchase-bills.spec.ts ../playwright/fam-expenses.spec.ts ../playwright/fam-tds.spec.ts ../playwright/fam-vendor-payments.spec.ts ../playwright/fam-purchase-register.spec.ts ../playwright/fam-purchase-rbac.spec.ts
```

Result: 7 passed.

Frontend full FAM:

```powershell
$specs = Get-ChildItem ..\playwright\fam-*.spec.ts | ForEach-Object { '../playwright/' + $_.Name }; npx playwright test --config=playwright.config.ts $specs
```

Result: 54 passed.

Build:

```powershell
npm run build
```

Result: passed.

Lint:

```powershell
npm run lint
```

Result: passed.

## Bugs Found and Fixed

- Issue: The expense claim UI initially sent line `amount`, while the backend contract expects `taxable_value` and `gst_amount`.
  - Severity: High, because real API expense creation would fail from the UI.
  - Fix: Updated the expense form to submit `claimant_name`, `taxable_value`, and `gst_amount`.
  - Verification: Re-ran build and focused Playwright specs; then re-ran full FAM Playwright suite.

- Issue: Purchase posting originally selected the same first tax ledger for Input GST and TDS payable.
  - Severity: High, because GST input and TDS payable must be tracked separately.
  - Fix: Added tax ledger selection by keyword (`input`, `tds`) with fallback for minimal charts.
  - Verification: Python compile, targeted backend tests, full backend FAM suite.

- Issue: Full FAM route Playwright sweep timed out after Phase 7 route expansion.
  - Severity: Low, test harness only.
  - Fix: Increased the route sweep timeout and renamed it from Phase 1 to full FAM frontend routes.
  - Verification: Full FAM Playwright suite passed.

## Pending Issues

- No TDS return filing or portal export endpoint is implemented. This is intentional for this phase and is not faked.
- Ledger keyword fallback still supports minimal demo charts; production charts should configure explicit Input GST and TDS payable tax ledgers.

## Acceptance Criteria

- Purchase bills work: Passed
- Purchase posting works: Passed
- Expense vouchers work: Passed
- TDS sections/rates are configurable: Passed
- TDS calculation and posting work: Passed
- Vendor payments work: Passed
- Purchase register works: Passed
- AP aging remains accurate: Passed
- RBAC works: Passed
- Build/lint/tests pass: Passed

## Final Certification

FAM Phase 7 is certified as Passed for implementation and automated verification. No Critical or High blockers remain.
