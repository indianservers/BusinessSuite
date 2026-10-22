# PostgreSQL end-to-end verification

Completed: 22 October 2026. Local PostgreSQL 18.6.

All automated checks in this verification are green after fixes. Results below combine the full runs with targeted reruns of corrected failures; the initial failures are retained in the evidence summary.

| Check | Final result | Evidence |
| --- | --- | --- |
| Main backend | 510 unique tests passed | Full run: 488 passed, 21 failed. All 21 failures plus the new concurrency regression subsequently passed. |
| Affected backend modules | 27 passed | Additional PMS access, workspace, HRMS/BGV, subscription and concurrency regression. |
| Standalone Inventory/POS | 25 passed | Full suite on its separate PostgreSQL database. |
| Browser | 246 unique tests passed | Final full run: 244 passed; two ambiguous toast selectors were corrected and both tests passed on rerun. |
| TypeScript and production frontend build | Passed | `npm run build` completed successfully. |
| Main schema | Passed | 616 application tables plus Alembic, 4,218 constraints; no expected tables or columns missing. |
| Standalone Inventory schema | Passed | 135 application tables plus Alembic; no expected tables or columns missing. |
| Running application | Passed | Restarted API on port 1534; health, login, module catalog, workspaces and invoice-list requests returned HTTP 200. |

## What was exercised

Real PostgreSQL backend coverage includes HRMS and payroll, attendance and leave, recruitment and talent, benefits and statutory exports, CRM, PMS, SRM, FAM, inventory/POS, portals, communication, Business OS, automation, subscriptions, administration, security, permissions, and cross-module handoffs. Tests validate persistence, workflow transitions, negative validation, role restrictions and supported exports where defined by the existing suite.

Eight browser specifications use the real API and disposable PostgreSQL database: six module checks visit 59 pages, and two workspace tests cover creation, invitation acceptance after login, joining, project/task creation, dates and Gantt, changing roles, removal and denied access, dragging task status and assignee, comments, reload persistence, and mobile layout. The other 238 browser tests primarily mock API responses and validate UI behavior and permissions; they are not evidence of database integration by themselves.

## Application fixes

- Standalone POS register IDs are parsed as integers before PostgreSQL lookup, with validation for invalid or inactive registers.
- WhatsApp template creation no longer passes `provider_status` twice to its model constructor.
- Subscription bootstrap uses a PostgreSQL transaction advisory lock so concurrent first requests cannot create duplicate default plans or subscriptions. A two-connection concurrency regression passes.
- Empty SRM invoice screens no longer fetch nonexistent invoice ID 1 or expose actions that require an existing invoice.
- FAM inventory workbenches retain their financial routes, record IDs, links and permissions instead of redirecting financial users into restricted SRM routes. They reuse the existing workbench component and API.
- PMS time-in-status reports normalize timestamp awareness when computing elapsed hours on PostgreSQL.
- Background-verification checks have a stable ID order, including after updating a check.
- The inventory source route list contains unique paths.

The test harness now supports isolated PostgreSQL databases. Fixtures create actual referenced records and use returned IDs instead of assuming sequence values start at 1. Browser assertions follow current role restrictions, required inputs, screen labels and accessible toast behavior. Playwright is recorded as a development dependency for reproducible installation.

## Data and limits

Tests used `business_suite_integration_test`, `business_suite_focused_test`, `business_suite_browser_test` and `business_suite_inventory_test`. Application business records were not used for test mutations. The schema verification confirmed the main employees, CRM leads, PMS projects/tasks, SRM sales orders and FAM vouchers remain empty, as requested for the schema-only migration.

This verifies the repository's automated coverage on local PostgreSQL. It does not certify every possible input, untested workflow or remote PostgreSQL deployment. External email delivery, payment settlement, government filing, external AI and background-verification providers require configured services and separate live verification; local adapter/configuration behavior is covered where tests exist. Existing deprecation and browser-data warnings did not fail the checks.

## Evidence and rerunning

- [Machine-readable results](docs/migrations/postgresql-e2e-results.json) record the latest result for every backend and browser test, with initial/full-run counts.
- [Schema verification](docs/migrations/postgresql-verification.json) records table/column coverage.
- [Reproduction instructions](qa/POSTGRESQL_TESTING.md) explain isolated databases and the browser server.

Raw logs, JUnit results and retained browser reports are under `.local/`, including `full-postgres-results.xml`, `postgres-failed-rerun.xml`, `postgres-affected-regression.xml`, `inventory-postgres-tests-2.log`, `postgres-playwright-final-full.json`, `postgres-browser-toast-rerun.log` and `postgres-frontend-build.log`.
