# Full Regression Test Report

Verification date: 2026-06-04

## Final Status

Overall: **Partially Passed**

Go-live status: **Not approved** because transformation features are incomplete and UI runtime produced a notification API error in dev smoke.

## Commands Run

| Command | Result |
|---|---|
| `pytest -q` from `backend` | **225 passed**, 18356 warnings, 6m38s |
| `pytest -q tests/test_approval_os.py tests/test_workflow_engine_depth.py tests/test_workflow_inbox.py tests/test_crm_rest_api.py tests/test_pms_project_access.py tests/test_pms_readiness_features.py tests/test_timesheets.py` | **60 passed**, 3747 warnings |
| `npm run build` from `frontend` | **Passed**, Vite production build completed |
| `alembic heads` from `backend` | **Passed**, single head `20260604_001` |
| Direct Playwright browser smoke for `/hrms/approval-os` | **Partially Passed**, desktop/mobile UI checks passed; notification unread-count returned 500 in dev-server-only runtime |

## Regression Status

| Area | Status | Evidence |
|---|---|---|
| HRMS still works | **Passed for tested suite** | Full backend suite includes HRMS auth, employees, attendance, leave, payroll, documents, compliance, org, reports tests. |
| Existing CRM works | **Passed for tested suite** | `test_crm_rest_api.py` included in focused suite; CRM tests passed. |
| Existing PMS works | **Passed for tested suite** | `test_pms_project_access.py` and `test_pms_readiness_features.py` passed. |
| Login/logout works | **Passed for backend tests** | Auth tests passed in full suite; UI login/logout was not manually browser-tested. |
| Role-based routing works | **Partially Passed** | Route access code reviewed; existing route/RBAC tests are present. Approval OS `scope=all` API RBAC has a verified bug. |
| Existing tests pass | **Passed** | Full backend suite: 225 passed. |
| Build passes | **Passed** | Frontend `npm run build` passed. |
| No console/runtime errors | **Failed** | Direct UI smoke saw `GET http://127.0.0.1:5173/api/v1/notifications/unread-count` return `500`. |

## Warnings / Risk

- Backend tests run against SQLite in-memory. `backend/tests/conftest.py` explicitly warns MySQL-specific behavior is not covered.
- Full suite has many deprecation warnings, mostly Pydantic V2, datetime UTC, SQLAlchemy legacy APIs, and pytest asyncio warnings.
- Direct browser UI smoke used mocked Approval OS API responses for frontend verification. Backend API behavior was separately tested with TestClient.
- Playwright test runner module is not installed as `@playwright/test` or `playwright/test`, so repo-level Playwright specs could not be run through the configured test runner in this pass.

## Bugs Found

- Approval OS delegated fields are not accepted by create schema.
- Approval OS `scope=all` does not return `403` for employee role.
- Approval OS reject audit event is misspelled `rejectd`.
- UI runtime error on notifications unread count in dev smoke.
- CRM -> PMS -> Invoice transformation flow is not implemented end-to-end.
- Customer 360 and Global Search are not cross-module backend-backed implementations.

## Bugs Fixed

None during this verification pass.

## Pending Blockers

- Fix Approval OS bugs.
- Add missing transformation implementation and end-to-end tests.
- Run Playwright/browser suite with a working test runner and backend proxy.
- Run migrations and tests against a MySQL environment.

