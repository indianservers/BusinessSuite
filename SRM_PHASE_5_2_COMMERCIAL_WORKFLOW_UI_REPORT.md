# SRM Phase 5.2 - Commercial Workflow UI Report

## Final Status

**Passed with minor non-blocking observations**

The SRM commercial workflow UI for Sales Orders, Contracts, Engagements, Billing Plans, and CRM-SRM-PMS readiness has been completed and verified through the exact requested Phase 5.2 frontend command, targeted backend regression, and production build.

## Sales Order UI Status

**Status: Passed**

Verified:

- `/srm/sales-orders` list route renders in the SRM shell.
- `/srm/sales-orders/1` detail route renders.
- List page shows commercial order data, status, customer, amount, updated date, and available row actions.
- Detail page shows customer, CRM deal reference, sales order number, status, commercial amount fields, linked engagement/contract/billing/PMS references where available.
- API actions verified for line add, submit, approve, confirm, and invoice draft from sales order.
- Validation and duplicate-prevention behavior is covered by backend sales order and invoice duplicate tests.

Evidence:

- `playwright/srm-sales-orders-ui.spec.ts`
- `backend/tests/test_srm_sales_order.py`
- `backend/tests/test_srm_invoice_duplicate_prevention.py` through broader suite from prior certification

## Contract UI Status

**Status: Passed**

Verified:

- `/srm/contracts` list route renders in the SRM shell.
- `/srm/contracts/1` detail route renders.
- List page shows contract title, active status, customer, value, and date columns.
- Detail page shows customer, linked sales order, linked engagement, contract value, billing terms, status, and audit-capable record fields.
- API lifecycle actions verified for create, activate, expire, terminate, and renew.
- Invalid lifecycle transition coverage is handled by backend contract tests.

Evidence:

- `playwright/srm-contracts-ui.spec.ts`
- `backend/tests/test_srm_contracts.py`

## Engagement UI Status

**Status: Passed**

Verified:

- `/srm/engagements` list route renders.
- `/srm/engagements/2` detail route renders.
- Engagement list shows delivery engagement data and project creation action.
- Detail page shows CRM deal/quote, customer, sales order, contract, billing plan, PMS project, delivery/billing status, budget, and audit-capable fields.
- Lifecycle API shows CRM, SRM, and PMS relationships.
- PMS project creation is verified after confirmed sales order.
- Duplicate PMS project creation returns an idempotent result.
- Blocked-before-confirmation reason is represented in test evidence as "Sales order must be confirmed before PMS project creation"; backend integration verifies the actual rule.

Evidence:

- `playwright/srm-engagements-ui.spec.ts`
- `backend/tests/test_srm_engagements.py`
- `backend/tests/test_srm_pms_project_creation.py`
- `backend/tests/test_srm_handoff_idempotency.py`

## Billing Plan UI Status

**Status: Passed**

Verified:

- `/srm/billing-plans` list route renders.
- `/srm/billing-plans/4` detail route renders.
- UI copy exposes supported plan types: fixed fee, milestone, T&M, recurring, and hybrid.
- Detail page shows linked sales order, engagement, contract, total amount, invoiced/balance-oriented fields, milestones, and audit-capable record fields.
- API actions verified for create, create from sales order, add milestone, activate, pause, complete, cancel, and invoice draft from billing milestone.
- Duplicate milestone invoice prevention is covered by backend invoice tests and Phase 5.4/5.5 regression.

Evidence:

- `playwright/srm-billing-plans-ui.spec.ts`
- `backend/tests/test_srm_billing_plans.py`
- `backend/tests/test_srm_billing_plan_from_sales_order.py` through broader suite from prior certification

## CRM-SRM-PMS Link Status

**Status: Passed**

Verified:

- CRM Deal Won handoff creates or links SRM sales order, contract, engagement, and billing plan through API.
- Second CRM handoff is idempotent.
- Confirmed sales order supports PMS project creation from SRM engagement.
- Second PMS project creation is idempotent.
- CRM deal detail shows Commercial Handoff card and SRM/PMS links.
- PMS project detail shows SRM Engagement Link card.
- SRM engagement lifecycle API returns CRM/SRM/PMS relationship evidence.

Evidence:

- `playwright/srm-crm-pms-commercial-flow.spec.ts`
- Existing link specs:
  - `playwright/crm-deal-srm-link.spec.ts`
  - `playwright/pms-project-srm-link.spec.ts`
- Backend tests:
  - `test_srm_crm_won_handoff.py`
  - `test_srm_pms_project_creation.py`
  - `test_srm_handoff_idempotency.py`

## Commercial RBAC Status

**Status: Passed**

Verified:

- SRM Admin can access commercial workflow routes and actions.
- Sales Manager can access commercial workflow routes.
- Sales Executive can access sales-order and engagement lanes, while finance/collection routes are blocked.
- Business Owner has read-oriented access and no invoice approval action.
- Viewer can view permitted commercial pages and cannot perform create/edit/submit actions.
- Non-SRM Employee is blocked from commercial SRM routes.

Evidence:

- `playwright/srm-commercial-rbac.spec.ts`
- `backend/tests/test_srm_rbac.py`

## Backend Tests Executed

Command executed from `backend`:

```powershell
pytest tests/test_srm_sales_order.py tests/test_srm_contracts.py tests/test_srm_engagements.py tests/test_srm_billing_plans.py tests/test_srm_crm_won_handoff.py tests/test_srm_pms_project_creation.py tests/test_srm_handoff_idempotency.py tests/test_srm_rbac.py -q
```

Result:

- **15 passed, 1084 warnings in 16.13s**
- No failures.

Warnings:

- Existing Pydantic V2 deprecation warnings.
- Existing pytest-asyncio deprecation warnings.
- Existing `python-jose` `datetime.utcnow` deprecation warnings.

These warnings are non-blocking for Phase 5.2.

## Frontend Tests Executed

Command executed from `frontend`:

```powershell
npx playwright test --config=playwright.config.ts ../playwright/srm-sales-orders-ui.spec.ts ../playwright/srm-contracts-ui.spec.ts ../playwright/srm-engagements-ui.spec.ts ../playwright/srm-billing-plans-ui.spec.ts ../playwright/srm-commercial-rbac.spec.ts ../playwright/srm-crm-pms-commercial-flow.spec.ts
```

Final result:

- **8 passed in 38.7s**
- No failures after fixes.

Non-blocking warning:

- Vite proxy `ECONNREFUSED` messages appeared during test teardown after assertions had already passed. This is consistent with prior SRM Playwright teardown noise and did not affect test outcomes.

## Build Status

Command executed from `frontend`:

```powershell
npm run build
```

Result:

- **Passed**
- Runs `tsc && vite build`.
- Production build completed successfully.
- Build duration: **10m 43s**.

## Bugs Found

### Bug 1 - Missing Required Phase 5.2 Playwright Spec Artifacts

- Severity: Medium
- Root cause: Commercial workflow functionality had adjacent coverage, but the exact requested Phase 5.2 filenames were absent.
- Files changed:
  - `playwright/srm-sales-orders-ui.spec.ts`
  - `playwright/srm-contracts-ui.spec.ts`
  - `playwright/srm-engagements-ui.spec.ts`
  - `playwright/srm-billing-plans-ui.spec.ts`
  - `playwright/srm-commercial-rbac.spec.ts`
  - `playwright/srm-crm-pms-commercial-flow.spec.ts`
- Fix applied: Added exact Phase 5.2 specs with list/detail/action/status/RBAC/link assertions.
- Final status: Fixed.

### Bug 2 - Commercial Detail Stubs Returned List-Shaped Data

- Severity: Medium
- Root cause: Shared Playwright SRM stubs returned broad list records for detail routes in some cases, reducing detail-page test evidence.
- Files changed:
  - `playwright/srm-test-utils.ts`
- Fix applied: Added exact detail-shaped stubs for `/srm/sales-orders/1`, `/srm/contracts/1`, `/srm/engagements/1`, `/srm/engagements/2`, `/srm/billing-plans/1`, and `/srm/billing-plans/4`.
- Final status: Fixed.

### Bug 3 - Initial New Spec Assertions Expected IDs on List Primary Columns

- Severity: Low
- Root cause: The SRM list UI displays human titles/names as primary values, while record IDs appear in details/API/link cards.
- Files changed:
  - `playwright/srm-sales-orders-ui.spec.ts`
  - `playwright/srm-contracts-ui.spec.ts`
  - `playwright/srm-engagements-ui.spec.ts`
  - `playwright/srm-crm-pms-commercial-flow.spec.ts`
- Fix applied: Updated list assertions to match visible UI and kept ID verification on detail/API/link surfaces.
- Final status: Fixed.

## Bugs Fixed

Fixed during Phase 5.2:

- Added all missing required Playwright spec files.
- Added commercial detail route stubs for meaningful detail-page verification.
- Corrected new test assertions to align with the actual UI rendering.
- Corrected CRM/PMS commercial flow route assertions to use the existing `/crm/deals/501` and `/pms/projects/301` link-card behavior.

No product Critical or High workflow blockers were found.

## Pending Issues

Non-blocking:

- Backend deprecation warnings should be cleaned up in a platform maintenance pass.
- Vite proxy teardown warning noise should be reduced in Playwright infrastructure.
- Some UI commercial lifecycle actions are verified through API-backed test actions and list/detail surfaces rather than full create/edit modal workflows, because the current SRM architecture centralizes many operations in action buttons and API workflows.

## Certification

**Passed with minor non-blocking observations**

SRM Phase 5.2 commercial workflow UI is certified for controlled rollout continuity. Sales Orders, Contracts, Engagements, Billing Plans, CRM-SRM-PMS links, commercial RBAC, targeted backend regression, exact requested frontend regression, and production build are all passing.
