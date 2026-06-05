# SRM Phase 1 Module Foundation Report

## Final Phase Status

**Passed**

SRM is implemented as a separate Business Suite module, registered independently from CRM/PMS/HRMS, exposed through `/api/v1/srm`, linked from the suite index, protected by SRM-specific roles/permissions, and verified through backend, frontend route, RBAC, index card, smoke, and build checks.

## Implemented Files

### Backend

- `backend/app/apps/srm/__init__.py`
- `backend/app/apps/srm/models.py`
- `backend/app/apps/srm/schemas.py`
- `backend/app/apps/srm/schema.py`
- `backend/app/apps/srm/access.py`
- `backend/app/apps/srm/api/__init__.py`
- `backend/app/apps/srm/api/router.py`
- `backend/app/apps/srm/services/__init__.py`
- `backend/app/module_registry.py`
- `backend/app/main.py`
- `backend/app/db/init_common_db.py`
- `backend/app/db/init_db.py`
- `backend/app/api/v1/auth.py`
- `backend/tests/test_srm_module_registration.py`
- `backend/tests/test_srm_rbac.py`

### Frontend

- `frontend/src/apps/srm/types.ts`
- `frontend/src/apps/srm/api.ts`
- `frontend/src/apps/srm/routes.tsx`
- `frontend/src/apps/srm/pages/SRMWorkspacePage.tsx`
- `frontend/src/App.tsx`
- `frontend/src/appRegistry.ts`
- `frontend/src/lib/products.ts`
- `frontend/src/lib/roles.ts`
- `frontend/src/components/app/GlobalSearch.tsx`
- `frontend/src/components/app/Breadcrumbs.tsx`
- `frontend/src/pages/auth/LoginPage.tsx`
- `frontend/src/pages/ModuleIndexPage.tsx`
- `playwright/srm-test-utils.ts`
- `playwright/srm-module-smoke.spec.ts`
- `playwright/srm-routes.spec.ts`
- `playwright/srm-index-card.spec.ts`
- `playwright/srm-rbac.spec.ts`

## Routes Verified

All required SRM frontend routes were verified through Playwright smoke coverage using an authenticated SRM Admin session:

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

Status: **Passed**

Evidence:

- `playwright/srm-routes.spec.ts`
- `playwright/srm-module-smoke.spec.ts`
- Command: `npx playwright test --config=playwright.config.ts srm-module-smoke.spec.ts srm-routes.spec.ts srm-index-card.spec.ts srm-rbac.spec.ts`
- Result: `6 passed`

## APIs Verified

Backend API prefix verified:

- `/api/v1/srm`

Representative registered API routes verified by backend module registration tests:

- `/api/v1/srm/module-info`
- `/api/v1/srm/sales-orders`
- `/api/v1/srm/invoices/draft-from-sales-order/{sales_order_id}`

Additional SRM router coverage exists for:

- Sales orders
- CRM handoff
- Contracts
- Engagements
- PMS project creation
- Billing plans
- Invoice drafts
- Invoices
- Receipts
- Collections
- Profitability
- Customer 360
- Reports
- Settings

Status: **Passed**

Evidence:

- `backend/app/apps/srm/api/router.py`
- `backend/tests/test_srm_module_registration.py`
- Command: `pytest tests/test_srm_module_registration.py tests/test_srm_rbac.py -q`
- Result: `3 passed`

## Index Page Card Status

Business Suite index page now shows the required modules:

- HRMS
- CRM
- PMS
- SRM

SRM card verified with exact required content:

- Title: `Sales & Revenue Management`
- Short title: `SRM`
- Description: `Manage sales orders, contracts, billing, invoices, collections, and revenue profitability.`
- Button: `Open SRM`

Status: **Passed**

Evidence:

- `frontend/src/pages/ModuleIndexPage.tsx`
- `playwright/srm-index-card.spec.ts`

## Sidebar Status

SRM sidebar/navigation is wired through the shared product navigation model and renders inside the same protected Business Suite shell used by other modules.

Verified SRM navigation entries include:

- Dashboard
- Sales Orders
- Contracts
- Engagements
- Billing Plans
- Invoice Drafts
- Invoices
- Collections
- Revenue Recognition
- Profitability
- Customer 360
- Reports
- Settings

Status: **Passed**

Evidence:

- `frontend/src/lib/roles.ts`
- `frontend/src/apps/srm/routes.tsx`
- `playwright/srm-routes.spec.ts`

## RBAC Status

Required permissions are implemented:

- `srm_view`
- `srm_manage`
- `srm_admin`
- `srm_invoice_view`
- `srm_invoice_create`
- `srm_invoice_approve`
- `srm_collection_view`
- `srm_collection_create`
- `srm_profitability_view`
- `srm_settings_manage`

Required roles are implemented:

- SRM Admin
- Sales Manager
- Sales Executive
- Finance Manager
- Revenue Manager
- Collection Executive
- Business Owner
- Viewer

Verified access behavior:

- SRM Admin can access SRM module routes.
- Sales Executive can access sales orders and engagements.
- Sales Executive is blocked from invoices, profitability, and settings.
- Collection Executive can access collections.
- Collection Executive is blocked from invoices and settings.
- Non-SRM employee is blocked from `/srm`.
- Backend SRM RBAC test confirms unauthorized access is denied.

Status: **Passed**

Evidence:

- `backend/app/apps/srm/access.py`
- `backend/app/db/init_common_db.py`
- `backend/tests/test_srm_rbac.py`
- `frontend/src/lib/roles.ts`
- `playwright/srm-rbac.spec.ts`

## Common CSS And Layout Usage

SRM uses the existing shared shell, protected route wrapper, app layout, cards, buttons, and Business Suite page styling instead of introducing an isolated UI system.

Status: **Passed**

Evidence:

- `frontend/src/App.tsx`
- `frontend/src/apps/srm/routes.tsx`
- `frontend/src/apps/srm/pages/SRMWorkspacePage.tsx`
- `frontend/src/pages/ModuleIndexPage.tsx`

## Build Status

Frontend production build completed successfully.

Status: **Passed**

Evidence:

- Command: `npm run build`
- Result: build completed successfully with Vite.

## Test Status

### Backend

Command:

```bash
pytest tests/test_srm_module_registration.py tests/test_srm_rbac.py -q
```

Result:

```text
3 passed
```

Status: **Passed**

### Frontend

Command:

```bash
npx playwright test --config=playwright.config.ts srm-module-smoke.spec.ts srm-routes.spec.ts srm-index-card.spec.ts srm-rbac.spec.ts
```

Result:

```text
6 passed
```

Status: **Passed**

### Build

Command:

```bash
npm run build
```

Result:

```text
Build passed
```

Status: **Passed**

## Bugs Found

1. SRM index card copy did not exactly match the required title, description, and button text.
   - Severity: Medium
   - Status: Fixed

2. SRM smoke test initially used a broad text selector for `SRM Dashboard`, which matched both the sidebar navigation item and page heading.
   - Severity: Low
   - Status: Fixed

3. An initial Playwright command was run from the repository root and hit a local Playwright launcher/version issue.
   - Severity: Low
   - Status: Resolved by running the frontend Playwright command from `frontend` with the existing project config.

## Bugs Fixed

1. Updated `frontend/src/pages/ModuleIndexPage.tsx` so the SRM card uses the exact requested content.

2. Updated `playwright/srm-module-smoke.spec.ts` to verify the dashboard heading with a role-based locator instead of ambiguous text matching.

3. Added the required SRM foundation test files:
   - `backend/tests/test_srm_module_registration.py`
   - `playwright/srm-module-smoke.spec.ts`
   - `playwright/srm-routes.spec.ts`
   - `playwright/srm-index-card.spec.ts`
   - `playwright/srm-rbac.spec.ts`

## Pending Issues

No Phase 1 foundation blocker remains.

Non-blocking follow-up items beyond this module foundation scope:

- Add richer end-to-end create/edit workflow coverage using a seeded real database instead of route-level Playwright API stubs.
- Add production migration review if this deployment uses Alembic or an equivalent migration pipeline.
- Reduce existing warning noise from deprecated dependencies and test environment messages.

## Final Certification

SRM Phase 1 Module Foundation is certified as:

**Passed**

The SRM module is separate from CRM and PMS, registered in the Business Suite module system, visible on the index page, routeable in the frontend, served under `/api/v1/srm`, protected by SRM-specific roles and permissions, and verified by passing backend tests, frontend Playwright smoke/RBAC tests, and frontend production build.
