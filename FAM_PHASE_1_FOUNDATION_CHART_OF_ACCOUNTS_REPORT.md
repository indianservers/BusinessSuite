# FAM Phase 1 Foundation & Chart of Accounts Report

Date: 2026-06-06  
Module: FAM - Finance & Accounting Management  
Final Phase Status: Passed

## Executive Summary

FAM Phase 1 has been implemented as a separate Business Suite module. It is not merged into CRM, PMS, or SRM. The foundation includes India-first company financial settings, financial years, chart of accounts, ledger groups, ledgers, opening balances, cost centers, branches, audit logs, dashboard shell, frontend routes, backend APIs, seeded roles/permissions, migrations, and smoke/regression tests.

SRM remains the operational sales/revenue engine. FAM is clearly labelled as the statutory books engine and does not duplicate SRM invoice screens.

## Implemented Files

Backend:
- `backend/app/apps/fam/__init__.py`
- `backend/app/apps/fam/models.py`
- `backend/app/apps/fam/schemas.py`
- `backend/app/apps/fam/schema.py`
- `backend/app/apps/fam/access.py`
- `backend/app/apps/fam/api/__init__.py`
- `backend/app/apps/fam/api/router.py`
- `backend/alembic/versions/20260605_011_fam_phase_1_foundation.py`
- Updated `backend/app/module_registry.py`
- Updated `backend/app/core/config.py`
- Updated `backend/app/main.py`
- Updated `backend/app/db/init_db.py`
- Updated `backend/app/db/init_common_db.py`
- Updated `backend/tests/conftest.py`

Frontend:
- `frontend/src/apps/fam/api.ts`
- `frontend/src/apps/fam/routes.tsx`
- `frontend/src/apps/fam/types.ts`
- `frontend/src/apps/fam/FAMWorkspacePage.tsx`
- Updated `frontend/src/App.tsx`
- Updated `frontend/src/appRegistry.ts`
- Updated `frontend/src/lib/products.ts`
- Updated `frontend/src/lib/roles.ts`
- Updated `frontend/src/pages/ModuleIndexPage.tsx`
- Updated `frontend/src/pages/auth/LoginPage.tsx`
- Updated `frontend/src/components/app/Breadcrumbs.tsx`
- Updated `frontend/src/components/app/GlobalSearch.tsx`

Tests:
- `backend/tests/fam_test_utils.py`
- `backend/tests/test_fam_settings.py`
- `backend/tests/test_fam_financial_years.py`
- `backend/tests/test_fam_ledger_groups.py`
- `backend/tests/test_fam_ledgers.py`
- `backend/tests/test_fam_opening_balances.py`
- `backend/tests/test_fam_cost_centers.py`
- `backend/tests/test_fam_branches.py`
- `backend/tests/test_fam_rbac.py`
- `backend/tests/test_fam_audit_logs.py`
- `playwright/fam-test-utils.ts`
- `playwright/fam-dashboard.spec.ts`
- `playwright/fam-settings.spec.ts`
- `playwright/fam-chart-of-accounts.spec.ts`
- `playwright/fam-ledger-groups.spec.ts`
- `playwright/fam-ledgers.spec.ts`
- `playwright/fam-opening-balances.spec.ts`
- `playwright/fam-rbac.spec.ts`
- `playwright/fam-routes.spec.ts`
- `playwright/fam-index-card.spec.ts`

## Database Readiness

Tables created/verified:
- `fam_company_financial_settings`
- `fam_financial_years`
- `fam_accounting_periods`
- `fam_ledger_groups`
- `fam_ledgers`
- `fam_opening_balances`
- `fam_cost_centers`
- `fam_branches`
- `fam_audit_logs`

Migration:
- `20260605_011_fam_phase_1_foundation.py`
- Fresh migration chain verified with SQLite proxy using Alembic upgrade to head.
- Production MySQL staging migration should still be run during deployment release gates.

Indexes/constraints included:
- Company scoped unique settings.
- Financial year company/name uniqueness.
- Ledger group company/code uniqueness.
- Ledger company/code and company/name uniqueness.
- Opening balance company/year/ledger uniqueness.
- Cost center company/code uniqueness.
- Branch company/branch code uniqueness.
- Foreign keys for financial year, ledger group hierarchy, ledgers, opening balances, cost center hierarchy.

## Backend APIs Verified

API prefix: `/api/v1/fam`

Verified API areas:
- `GET /fam/module-info`
- `GET /fam/dashboard`
- `GET /fam/settings`
- `PUT /fam/settings`
- `GET /fam/financial-years`
- `POST /fam/financial-years`
- `PUT /fam/financial-years/{year_id}`
- `POST /fam/financial-years/{year_id}/close`
- `POST /fam/financial-years/{year_id}/lock`
- `GET /fam/ledger-groups`
- `POST /fam/ledger-groups`
- `PUT /fam/ledger-groups/{group_id}`
- `DELETE /fam/ledger-groups/{group_id}`
- `GET /fam/ledgers`
- `POST /fam/ledgers`
- `PUT /fam/ledgers/{ledger_id}`
- `DELETE /fam/ledgers/{ledger_id}`
- `GET /fam/opening-balances`
- `POST /fam/opening-balances`
- `POST /fam/opening-balances/post`
- `GET /fam/cost-centers`
- `POST /fam/cost-centers`
- `GET /fam/branches`
- `POST /fam/branches`
- `GET /fam/audit-logs`
- `GET /fam/chart-of-accounts`

Validation verified:
- Financial year end date must be after start date.
- Financial year overlaps are rejected.
- Invalid ledger group nature is rejected.
- Invalid ledger type is rejected.
- Unknown ledger group is rejected.
- Duplicate ledger code/name is rejected.
- System ledger groups cannot be deleted.
- Opening balance cannot have both debit and credit.
- Opening balances must balance before posting.
- Closed/locked financial years block opening balance postings.
- GST/PAN/TAN placeholder validation exists.

## Frontend Routes Verified

Routes implemented and tested:
- `/fam`
- `/fam/dashboard`
- `/fam/profile`
- `/fam/settings`
- `/fam/financial-years`
- `/fam/chart-of-accounts`
- `/fam/ledger-groups`
- `/fam/ledgers`
- `/fam/opening-balances`
- `/fam/cost-centers`
- `/fam/branches`
- `/fam/audit`

Suite integration:
- Business Suite index card added.
- FAM login context added.
- Sidebar navigation added.
- Breadcrumbs added.
- Global search static FAM results added.
- Installed-app registry includes FAM by default.
- Shared shell, cards, buttons, labels, badges, toast, and layout are reused.

## RBAC Status

Permissions seeded:
- `fam_view`
- `fam_manage`
- `fam_admin`
- `fam_settings_manage`
- `fam_chart_view`
- `fam_chart_manage`
- `fam_opening_balance_view`
- `fam_opening_balance_manage`
- `fam_cost_center_manage`
- `fam_branch_manage`
- `fam_audit_view`

Roles seeded:
- `fam_admin`
- `accountant`
- `finance_manager`
- `auditor`
- `business_owner`
- `fam_viewer`
- `non_fam_employee`

Backend RBAC verified:
- Non-FAM role without permissions is blocked.
- FAM viewer can view but cannot mutate chart records.
- FAM admin can reach foundation APIs.
- Mutating APIs require backend permissions, not only frontend route guards.

Frontend RBAC verified:
- FAM Admin can open settings.
- Non-FAM employee is blocked from FAM routes.
- Auditor can open audit and is blocked from settings.

## Audit Status

Audit logs are written for:
- Settings update.
- Financial year create/update/close/lock.
- Ledger group create/update/delete.
- Ledger create/update/delete.
- Opening balance create/post.
- Cost center create.
- Branch create.

Audit log API verified:
- `GET /api/v1/fam/audit-logs`

## Bugs Found And Fixed

1. Missing production FAM seed permissions and roles  
Severity: High  
Root cause: FAM API enforcement existed, but `init_db.py` / `init_common_db.py` did not seed FAM permissions.  
Fix applied: Added FAM permissions and roles to seed lists.

2. FAM form labels were not associated with inputs  
Severity: Medium  
Root cause: Shared FAM `Field` wrapper rendered labels visually but without `htmlFor`/input `id`.  
Fix applied: `Field` now assigns stable ids and aria labels to controls.

3. FAM dashboard KPI tuple TypeScript inference failed production build  
Severity: Medium  
Root cause: KPI array mixed strings and object-typed values without explicit tuple typing.  
Fix applied: Typed KPI rows as `Array<[string, React.ReactNode]>` and normalized current FY display.

4. Playwright selector strictness issues  
Severity: Low  
Root cause: Duplicate visible text in table/toast regions.  
Fix applied: Tests now use exact cell selectors or first exact toast match.

5. FAM index card smoke test selected the last suite sign-in button after Inventory was added  
Severity: Low  
Root cause: The test used the last visible `Sign in` link, which became the Inventory card after the cloned Inventory module was added to the Business Suite index.  
Fix applied: Scoped the assertion to the FAM card heading ancestor and verified the FAM card links to `/fam/login`.

## Tests Executed

Backend FAM suite:
```powershell
pytest (Get-ChildItem tests/test_fam_*.py | ForEach-Object { $_.FullName }) -q
```
Result: `15 passed in 9.06s`

Latest rerun: `15 passed in 8.96s`

Fresh migration chain check:
```powershell
$env:DATABASE_URL='sqlite:///./fam_migration_check.db'; $env:MYSQL_PASSWORD=''; alembic upgrade head
```
Result: Passed through `20260605_011`, temporary database removed after verification.

Frontend FAM Playwright suite:
```powershell
npx playwright test --config=playwright.config.ts ../playwright/fam-dashboard.spec.ts ../playwright/fam-settings.spec.ts ../playwright/fam-chart-of-accounts.spec.ts ../playwright/fam-ledger-groups.spec.ts ../playwright/fam-ledgers.spec.ts ../playwright/fam-opening-balances.spec.ts ../playwright/fam-rbac.spec.ts ../playwright/fam-routes.spec.ts ../playwright/fam-index-card.spec.ts
```
Result: `10 passed`

Latest rerun after index-card selector fix: `10 passed`

Frontend build:
```powershell
npm run build
```
Result: Passed

Frontend lint:
```powershell
npm run lint
```
Result: Passed

## Pending Issues

- MySQL production/staging migration execution was not run in this local environment. Alembic fresh-install ordering was verified with SQLite.
- Accounting vouchers, journal entries, GST returns, bank reconciliation, purchase/payables, and SRM-to-FAM posting are outside Phase 1 and not implemented here.
- FAM dashboard receivables/payables are correctly labelled placeholders and are not fake integrations.

## Certification

Certification: Passed

FAM Phase 1 is ready as a separate Business Suite accounting foundation module with tested UI routes, backend APIs, database models/migration, RBAC, seed roles/permissions, audit logging, chart of accounts, opening balance workflow, build, lint, and focused regression coverage.
