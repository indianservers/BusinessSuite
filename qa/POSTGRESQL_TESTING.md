# PostgreSQL regression tests

Run these from the repository root with local PostgreSQL started and `backend/.env` configured. Test runners recreate only their dedicated `business_suite_*_test` databases; they do not copy or modify application business records.

## Backend and standalone Inventory/POS

```powershell
Push-Location backend
venv/Scripts/python.exe scripts/run_postgres_tests.py -v --tb=short
venv/Scripts/python.exe scripts/verify_postgresql_schema.py
Pop-Location
backend/venv/Scripts/python.exe qa/run_inventory_postgres_tests.py
```

The backend runner defaults to `business_suite_integration_test`. Optional `POSTGRES_TEST_DATABASE` must start with `business_suite_` and end with `_test`. Inventory uses `business_suite_inventory_test`.

## Browser tests

Install frontend dependencies with `npm ci` and Chromium with `node frontend/node_modules/playwright/cli.js install chromium` if needed. In one terminal:

```powershell
backend/venv/Scripts/python.exe qa/pms_workspace_server.py
```

This recreates `business_suite_browser_test`, applies the PostgreSQL migration baseline, seeds QA users and sample workspace records, and serves the real API on port 8766. Keep it running. In another terminal:

```powershell
Push-Location frontend
node node_modules/playwright/cli.js test --config=playwright.postgres.config.ts
npm run build
Pop-Location
```

The configuration starts Vite on port 5182, proxies to the disposable API, and writes reports/traces under `.local/`. Existing application services on ports 1534 and 5173 are independent.

`postgresql-live.spec.ts` uses real API requests without interception and visits 59 pages. `pms-workspaces.spec.ts` also uses the real API for invitations, joining, member roles/removal, scheduled tasks, Gantt, dragging, comments, and persistence. Other browser specifications primarily mock API responses to isolate UI and permission behavior. Backend and standalone Inventory suites use real PostgreSQL.

External credentials and services (email delivery, payment settlement, statutory filing, external AI and background-verification providers) are not certified by these local tests. Their local validation, configuration states, and supported adapter behavior are covered where tests exist.
