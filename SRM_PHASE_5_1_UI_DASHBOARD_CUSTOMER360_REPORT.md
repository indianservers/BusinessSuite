# SRM Phase 5.1 UI, Dashboard, Navigation, and Customer 360 Report

## Final Status

Certification: **Passed**

Phase 5.1 is implemented and verified for SRM frontend route completion, dashboard API/UI, Customer 360 API/UI, sidebar navigation, role-aware visibility, and build stability.

## Routes Verified

Verified through Playwright route sweep:

- `/srm`
- `/srm/dashboard`
- `/srm/sales-orders`
- `/srm/contracts`
- `/srm/engagements`
- `/srm/billing-plans`
- `/srm/invoice-drafts`
- `/srm/invoices`
- `/srm/collections`
- `/srm/revenue-recognition`
- `/srm/profitability`
- `/srm/customer-360`
- `/srm/reports`
- `/srm/settings`

Evidence:

- `playwright/srm-ui-routes.spec.ts` verifies all routes render, breadcrumbs/shell text are present, non-SRM employee is blocked, and no console errors are emitted.
- `frontend/src/apps/srm/pages/SRMWorkspacePage.tsx` now provides route-specific headings, descriptions, loading state, empty state, error state, and shared card/table UI.

## Sidebar and Index Status

Status: **Passed**

- Sidebar entries verified for Dashboard, Sales Orders, Contracts, Engagements, Billing Plans, Invoice Drafts, Invoices, Collections, Revenue Recognition, Profitability, Customer 360, Reports, Settings.
- Dashboard nav item now targets `/srm/dashboard` and highlights correctly.
- SRM profile link now resolves to `/srm/profile` from SRM routes.
- Role-aware sidebar filtering verified for Collection Executive.

Evidence:

- `frontend/src/lib/roles.ts`
- `frontend/src/components/layout/Sidebar.tsx`
- `playwright/srm-navigation.spec.ts`

## Dashboard API Status

Status: **Passed**

Implemented:

- `GET /api/v1/srm/dashboard`
- Legacy `GET /api/v1/srm/reports/dashboard` now returns the same rich payload.

Metrics returned:

- Total sales orders
- Pending approvals
- Confirmed sales orders
- Active contracts
- Active engagements
- Active billing plans
- Invoice drafts pending
- Approved invoices
- Sent invoices
- Total invoiced value
- Total collected value
- Outstanding value
- Overdue value
- Collection risk
- Gross margin
- Cash margin
- Recent sales orders
- Recent invoices
- Collection alerts
- Revenue trend
- Profitability summary
- CRM/PMS linked activity summary

Evidence:

- `backend/app/apps/srm/api/router.py`
- `backend/tests/test_srm_dashboard.py`

## Dashboard UI Status

Status: **Passed**

Implemented dashboard sections:

- KPI cards
- Recent Sales Orders
- Recent Invoices
- Collection Alerts
- Revenue Trend
- Profitability Summary
- CRM/PMS Linked Activity
- Error and retry state

Evidence:

- `frontend/src/apps/srm/pages/SRMWorkspacePage.tsx`
- `playwright/srm-dashboard.spec.ts`

## Customer 360 Status

Status: **Passed**

Implemented:

- `GET /api/v1/srm/customer-360`
- Existing `GET /api/v1/srm/customer-360/{customer_id}` retained and upgraded to the same payload builder.
- Search supports `customer_id`, `crm_deal_id`, `sales_order_id`, `engagement_id`, and `q`.
- UI search sends free text/numeric terms through `q`, allowing backend resolution across customer ID, CRM deal ID, sales order ID, engagement ID, and record numbers.

Customer 360 displays:

- CRM references
- Sales orders
- Contracts
- Engagements
- Billing plans
- Invoices
- Receipts
- Outstanding amount
- Aging
- Collection reminders
- Profitability
- PMS projects
- Timeline / audit trail

Evidence:

- `backend/app/apps/srm/api/router.py`
- `backend/tests/test_srm_customer_360.py`
- `frontend/src/apps/srm/pages/SRMWorkspacePage.tsx`
- `playwright/srm-customer-360.spec.ts`

## RBAC Status

Status: **Passed**

Verified:

- Dashboard API blocks authenticated SRM users without SRM permissions.
- Dashboard API allows SRM viewer with `srm_view`.
- Customer 360 API blocks authenticated SRM users without SRM permissions.
- Customer 360 API allows SRM viewer with `srm_view`.
- Non-SRM employee is blocked from SRM frontend routes.
- Collection Executive sidebar hides finance/settings routes and shows Collections.

Evidence:

- `backend/tests/test_srm_dashboard.py`
- `backend/tests/test_srm_customer_360.py`
- `backend/tests/test_srm_rbac.py`
- `playwright/srm-ui-routes.spec.ts`
- `playwright/srm-navigation.spec.ts`

## Backend Tests Executed

Command:

```bash
pytest tests/test_srm_dashboard.py tests/test_srm_customer_360.py tests/test_srm_rbac.py -q
```

Result:

- **5 passed**
- Warnings only: existing Pydantic and pytest asyncio deprecation warnings.

## Frontend Tests Executed

Command:

```bash
npx playwright test --config=playwright.config.ts ../playwright/srm-ui-routes.spec.ts ../playwright/srm-navigation.spec.ts ../playwright/srm-dashboard.spec.ts ../playwright/srm-customer-360.spec.ts
```

Result:

- **8 passed**
- Web server emitted existing `NO_COLOR` / `FORCE_COLOR` warning only.

## Build Status

Command:

```bash
npm run build
```

Result:

- **Passed**
- `tsc && vite build` completed successfully.

## Bugs Found

1. Dashboard API only exposed a lightweight legacy `/reports/dashboard` payload.
   - Severity: High
   - Fix: Added rich `/srm/dashboard` payload and delegated legacy dashboard endpoint to it.

2. Customer 360 only supported `/customer-360/{customer_id}` and omitted billing plans, aging, reminders, PMS projects, and audit timeline.
   - Severity: High
   - Fix: Added queryable `/customer-360` endpoint with broader linked lifecycle payload.

3. SRM workspace used a generic list page for dashboard and Customer 360.
   - Severity: High
   - Fix: Added dedicated Dashboard and Customer 360 views using shared cards, buttons, inputs, badges, and route states.

4. Sidebar dashboard label/target did not match Phase 5.1 expectation.
   - Severity: Medium
   - Fix: Updated SRM nav to `Dashboard` targeting `/srm/dashboard`.

5. SRM profile route from sidebar fell back to `/`.
   - Severity: Medium
   - Fix: Updated shared Sidebar profile path handling for `/srm`.

6. Playwright selectors were ambiguous because content labels overlapped with sidebar/user text.
   - Severity: Low
   - Fix: Tightened selectors to exact links/headings.

7. Backend RBAC test data initially used `.test` email domains rejected by validation.
   - Severity: Low
   - Fix: Switched test users to valid `example.com` emails.

8. Build found TypeScript unknown-key/action-cast issues in the rebuilt SRM workspace.
   - Severity: Medium
   - Fix: Added KPI tuple typing and explicit SRM action map.

## Bugs Fixed

All High and Medium Phase 5.1 bugs found during verification were fixed.

Files changed or added:

- `backend/app/apps/srm/api/router.py`
- `backend/tests/test_srm_dashboard.py`
- `backend/tests/test_srm_customer_360.py`
- `frontend/src/apps/srm/api.ts`
- `frontend/src/apps/srm/pages/SRMWorkspacePage.tsx`
- `frontend/src/lib/roles.ts`
- `frontend/src/components/layout/Sidebar.tsx`
- `playwright/srm-ui-routes.spec.ts`
- `playwright/srm-navigation.spec.ts`
- `playwright/srm-dashboard.spec.ts`
- `playwright/srm-customer-360.spec.ts`
- `playwright/srm-test-utils.ts`

## Pending Issues

- No blocking issues remain for Phase 5.1.
- Existing repository-wide warnings remain outside this phase: Pydantic V2 deprecation warnings and Playwright web server color environment warning.

## Certification

**Passed**

SRM Phase 5.1 UI completion, navigation, dashboard, Customer 360, RBAC checks, tests, and production build are verified from actual backend tests, Playwright UI tests, and build execution.
