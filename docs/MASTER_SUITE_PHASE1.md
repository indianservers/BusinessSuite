# Master Suite — Phase 1 control foundation

## Implementation map

This extends the existing React/TypeScript/Vite/Zustand frontend and FastAPI/SQLAlchemy backend. PostgreSQL remains the deployment database; SQLite remains available for isolated unit tests. Existing JWT sessions, password reset/invitations, MFA/SSO infrastructure, User/Role/Permission records, CommonPerson identity links, and HRMS Employee records remain authoritative.

The five product modules are HRMS, CRM, Project Management, SRM (Sales & Inventory), and FAM (Finance & Accounting). Shared registered access groups are Forms, Scheduling, Approvals, Audit, Automation, Customization, Communication, Analytics, AI, Security, SaaS and Business OS; Intern Management is separately discovered. There are 18 access groups altogether. Sales, inventory and tasks remain features of their existing products. This phase adds no automation, integration or AI-management product features.

Existing central access implementation: `backend/app/access/{api,models,service,catalog,scope}.py`, `frontend/src/features/access/UsersAccessPage.tsx`. New control APIs live in `backend/app/access/control.py`; entitlement checks in `entitlements.py`. Navigation still uses existing `getRoleNav`/`canAccessRoute`, the shared Sidebar and product shell. Existing UI components, dialogs, buttons, theme tokens and Lucide icons are reused. No new dependencies are required.

## Pages

- `/admin/control/dashboard`: eight real summary queries, five distributions, recent central administrative events and working quick actions.
- `/admin/control/organizations`: existing companies, branch/department hierarchy, legal/tax/currency/timezone/status settings, branch managers and department heads, user/admin/module counts, and reporting teams derived from HRMS relationships. Administrators and memberships are assigned through existing Users & Access controls. Organization edits use row locks and expected timestamps.
- `/admin/access`: existing user listing/matrix, enhanced with sorting, branch labels, access-profile links and dashboard deep links. Existing bulk review/apply, version conflicts, independent module roles, custom roles, templates, account status, secure invitation setup and authorized reports remain available.
- `/admin/access?tab=Roles`: existing custom and native role management, duplication, retirement, affected users, role versions and actual permissions. The module catalog now exposes action choices discovered from actual registered HTTP operations.
- `/admin/control/modules`: dynamic registry, installed state, company entitlement, user count, authorized-company enablement count, route/permission details and links to assignment/roles. Company entitlement is separate from user grants.
- `/admin/control/users/:id`: Overview, Module Access, Security, Access History and Linked Records. Identity editing updates User/CommonPerson, leaves Employee distinct, and revokes sessions. Security details exclude token hashes, MFA secrets and HRMS personal/payroll records. Delegated administrators cannot inspect shared/global privileged users' global session histories.
- `/admin/control/security`: real active sessions, failures, privileged/MFA risk review, session revocation and deployment-global password/lockout/MFA policy configuration. Suspension/reactivation links to the reviewed central account-status workflow. Mandatory MFA cannot be enabled before active Super Admins are enrolled. Lock state uses the existing login lockout evaluator.
- `/admin/control/audit`: central before/after events, login-security records and rejected administrative requests with filters and CSV export. Legacy account-level events are included only when the account's organization can be unambiguously determined. Events expose existing request/session/IP metadata where available; central writes add correlation IDs. Audit records remain append-only.

## API additions

All routes below use `/api/v1/access/control`; reads require a global Super Admin or an explicit active administrator membership for the selected company. Mutations require existing session-bound password step-up. Sensitive changes use a per-actor database-backed 30-changes/minute budget with locking; existing authentication and failed step-up limits remain in force.

- `GET /dashboard`, `GET /organizations`, `POST /organizations`, `PUT /organizations/{id}`.
- `POST /units/{branches|departments}`, `PUT /units/{branches|departments}/{id}`.
- `GET /modules`, `PUT /modules/{module_key}`.
- `GET /users/{id}/360`, `PUT /users/{id}/identity`.
- `GET /security`, `POST /sessions/revoke`, `PUT /password-policy`.
- `GET /audit`, including filtered authorized CSV export.
- Existing `GET /access/users` adds validated sort/direction parameters; `/access/me` adds company-disabled module metadata for navigation.

Strict schemas reject undeclared fields. Tenant ownership is checked on companies, units, employee-head/manager links and identity/session targets. Shared identities and global password policy cannot be altered by ordinary company administrators. Superuser accounts remain protected by the existing central access service.

## Entitlement and authorization integration

The existing `bos_enabled_modules` table is reused for all registered module keys; no competing entitlement table is introduced. Its existing JSON metadata stores an access version. A company row lock serializes initial inserts and versioned changes. Existing companies without explicit rows retain their previous installed-module behavior; no user receives new native permissions.

Effective access requires installation, company entitlement, user module grant, action, native permissions and existing business membership/scope checks. Explicit company disables override both legacy and managed user grants, direct HTTP requests, `/access/me` navigation and background AI/operator checks. Company inactivity also denies business-module requests. Corporate access administration stays available to authorized administrators for recovery. Disabling a company module does not erase individual grant records, so reenabling restores the prior reviewed grants.

The existing ORM scope hooks still fail closed for unsupported raw SQL or global configuration. Registry discovery is not a claim of complete scope integration: Module Details explicitly reports partial legacy integration. Existing independent product authorization checks are retained.

## Migration and rollout

Only one new database field is needed: nullable `branches.manager_employee_id`, linked to the existing Employee table. Explicit relationship foreign keys preserve the existing Employee→Branch association.

- PostgreSQL migration: `pg_20261026_024_control_center.py`, revision `pg_20261026_024_control`, after the existing access migration.
- SQLite migration tree: `20261026_024_control_center.py`, revision `20261026_024_control`.
- Existing company/branch/department, BOS entitlement, audit, membership, identity, session and password-policy tables are reused.

The PostgreSQL migration chain was applied and exercised in disposable `business_suite_*_test` databases. No development or production database was migrated. Before deploying this code, back up the intended database, inventory current native roles/grants and BOS entitlements, then run `venv/Scripts/python.exe -m alembic upgrade head` from `backend` with verified environment settings. Apply schema changes before starting the updated application, because branch queries now include the new column.

Validate with a non-production Super Admin and company administrator, including entitlement revocation and cross-company denial, before moving the same release to production. The nullable field does not rewrite users or grants. Application rollback can retain the extra nullable column; restore/review changed entitlement rows separately using recorded before/after history. Do not delete audit records to roll back permissions. Only downgrade the manager-link migration after exporting manager assignments and stopping code that reads that field.

## Verification

Evidence and screenshots are in `docs/qa/suite-access/`:

- Broad PostgreSQL integration/regression run: **141 passed** (`phase1-final-postgres.log`), covering existing access, CRM lead workflows/assignment, sessions/files, AI permission checks and operator/background execution.
- Follow-up control/access PostgreSQL run: **38 passed** (`phase1-final-controls.log`), including five additional input-validation, IDOR, legacy-entitlement/background, shared-session privacy and mutation-rate tests. The real two-administrator concurrency test runs on PostgreSQL.
- Existing mocked Playwright regressions: **8 passed** (`phase1-browser-regressions.log`). These test interaction details independently of the real API workflow.
- Real Chromium workflow against the FastAPI test application and isolated SQLite database: **passed** (`phase1-live-browser.log`). It performs UI login, visits five new pages, creates a user through the UI, assigns PMS/CRM through the real matrix, reloads saved access, verifies CRM access, removes CRM, verifies direct API and frontend-route denial, checks cross-company denial and audit events, and checks desktop/mobile layout. The HTTP bridge forwards real backend responses unchanged; it supplies no mocked operational data.
- Final run of the 13 control tests plus the real browser workflow: **14 passed** (`phase1-final-live.log`).
- Production TypeScript/Vite build: `phase1-release-build.log`.

Reproduce the live browser check by starting Vite on `127.0.0.1:5201`, then running `RUN_CONTROL_BROWSER=1` with `pytest tests/test_control_browser.py` from `backend`. The test creates its own bridge and uses the ordinary test fixtures; never point it at a production account/database. Existing deprecation/build annotation warnings remain visible in verification logs.

## Known limitations and Phase 2 readiness

Phase 1 now supplies reusable control-center pages and organization/identity/entitlement APIs, with tested critical authorization paths. It is ready for a controlled staging rollout after applying the migration; production sign-off and an independent review of remaining legacy adapters are still required.

- Invitation email delivery is not configured: secure links are explicitly delivered manually.
- Scope support is conservative and partial for legacy tables/raw queries. Some Intern Hub administration still needs the separately controlled HRMS employee grant; an independent intern-employee partition adapter remains outstanding.
- SSO-only administrators need identity-provider step-up integration; this console currently uses existing password verification.
- Password/MFA policies remain deployment-global and require a global administrator; they are not falsely presented as per-company settings.
- Audit listing/export caps central records at 10,001 and legacy sources at 1,000 each; narrow date/action filters for investigations. Legacy login/request records lack reliable tenant context for shared users and are excluded from company-level consolidation in that case. Global account security history remains accessible only through authorized account views.
- Account/session lists have explicit response limits. Existing directory snapshot assembly is not a substitute for a dedicated large-deployment SQL reporting/indexing project.
- Reporting teams reuse HRMS manager relationships; this phase does not introduce a separate central team-membership system or rewrite existing CRM/PMS teams.
- External customer-portal identities retain their existing separate authentication flow. Previously issued legacy file links retain their original expiry semantics.

No Phase 2/3 approvals, automations, integration management, notifications, AI administration or system-operations features were added.
