# Power Apps - Phase 1 implementation report

## Scope and architecture

Power Apps is a standalone platform workspace at `/power-apps`. It uses the existing React/TypeScript/Vite frontend, FastAPI router discovery, SQLAlchemy models, PostgreSQL/Alembic migration chain, Axios client, login/session store, organization switching, access policies, role permissions, entitlement checks, and tenant boundary hooks.

Repository inspection covered the top-level frontend/backend/shared/integrations/deployment structure; frontend app registry, launcher, route guards and layout; backend module registration, organization identity, authorization and record scopes; existing forms, automation, approval, notification, AI, and shared-service models. No Power Apps subscriptions, widgets, actions, or data queries were inserted into PMS, CRM, HRMS, or InternHub.

The existing automation engine remains separate. Its shared `WorkflowVersion` is tied to `automation_workflows` and publication/execution identities. Power Apps drafts use a resource envelope and snapshots in separate tables so legacy execution cannot consume them. This is a draft-platform boundary, not a duplicate login, tenant, form builder, credential vault, or worker.

## Implemented behavior

- Master Suite launcher entry and optional Business OS module registration.
- Responsive white/purple shell, 12 distinct Lucide icons, catalog, searchable application navigation, workspace selector, create menu, recent work, template catalog boundary, activity indicator, user menu, and existing sign-out.
- Backend-backed counts for custom apps and execution/error history, plus genuine recent resources and audit records. Active automations, pending approvals, and form submissions are explicitly marked unsupported and return zero in Phase 1; they are not presented as fabricated usage history or counts from other modules.
- Automation draft create/list/read/update/delete, JSON schema validation, immutable-by-API version snapshots, optimistic save conflicts, version-aware deletion, audit history, loading/error/empty states, and paginated lists.
- Development/Testing/Production environment keys on the existing organization. Existing organizations receive Development through the migration. New organizations with no environment see a setup state; an authorized environment administrator can enable one. Testing and Production require explicit enablement.
- Resource queries enforce organization, environment, and ownership. Organization-wide access requires the existing organization scope grant. Other scopes conservatively narrow to ownership until assignment/team semantics are implemented.
- Planned applications render honest roadmap pages. Activity is functional for changes made through Power Apps. Existing forms remain in the shared form implementation; the Power Apps forms workspace does not copy it or silently expose module-specific forms.

## Routes

- `/power-apps`
- `/power-apps/automations`
- `/power-apps/automations/new`
- `/power-apps/automations/:resourceId`
- `/power-apps/approvals`
- `/power-apps/forms`
- `/power-apps/tables`
- `/power-apps/app-builder`
- `/power-apps/notifications`
- `/power-apps/search`
- `/power-apps/dashboards`
- `/power-apps/connectors`
- `/power-apps/documents`
- `/power-apps/ai-agents`
- `/power-apps/activity`

Backend endpoints use `/api/v1/power-apps`: catalog, environments, environment administration, overview, activity, automation CRUD, version history, and explicitly blocked publish/execute endpoints.

## Contracts and registries

The backend application registry contains IDs, names, icons, routes, descriptions, availability, required permissions, feature flags, and environment support. Authorized catalog results drive application cards and navigation. The frontend has typed routes and an icon map.

Workflow schema v1 describes manual/event/scheduled/webhook triggers, condition/branch/action/delay/approval/webhook nodes, edges, credential references, retries/backoff, idempotency, and owner execution identity. Duplicate node IDs, broken graph references, unrecognized fields, invalid bounds, tenant/owner overrides, and inline credential fields are rejected. Incomplete but valid drafts can be saved without activating anything.

Reusable contracts include `EventEnvelope`, `ExecutionContext`, `ExecutionResult`, and `ConnectorAdapter`. Deployment-controlled component and template registration APIs exist; their catalogs start empty. No adapters, integration listeners, webhook receivers, schedules, or executable handlers are registered.

Reusable services provide organization resolution, ownership/environment scoping, serialization, version snapshots, and transactional activity logging. Shared UI components are `Empty`, `ActivityList`, `PlannedApplication`, and the independent automation `DraftEditor`.

## Database migration

`backend/alembic_postgresql/versions/pg_20261027_032_power_apps.py` follows `pg_20261027_031_communication` and creates:

- `power_apps_environments`: organization-owned unique environment keys and enablement.
- `power_apps_resources`: environment-scoped ownership, draft definitions, version and timestamps; database CHECK restricts status to draft.
- `power_apps_versions`: resource version snapshots with original owner and change actor.
- `power_apps_activity`: organization/environment activity retained after resource deletion.
- `power_apps_executions`: future execution history foundation, workflow version, actor, attempt and a unique tenant/environment/workflow/idempotency key. There is no Phase 1 writer.

The migration seeds nine permissions and Development environments for existing companies, without copying users or granting ordinary roles new powers. Its forward/down/forward behavior preserves existing company records and does not duplicate permissions. The PostgreSQL predecessor contained an invalid parent revision string; only that reference was corrected to the existing `pg_20261027_030_security` revision.

No migration was applied to the configured application/production database during this task. The complete migration chain was exercised against a disposable PostgreSQL test database. Deployment must run the normal `alembic upgrade head` process before serving the new APIs.

## Permissions and security

- `power_apps_view`
- `power_apps_create`
- `power_apps_edit`
- `power_apps_delete`
- `power_apps_publish`
- `power_apps_execute`
- `power_apps_manage_credentials`
- `power_apps_manage_environment`
- `power_apps_activity_view`

Every API requires view access plus its own operation permission. Backend checks remain authoritative even if a caller bypasses route guards. Existing tenant membership, managed policy, module disablement, ownership and organization context enforcement are reused. Ordinary editing presets exclude environment administration, credential administration, publishing and execution permissions. Existing roles are not silently elevated.

Credentials are references only; there is no credential-writing API or plaintext credential store. The existing encrypted shared integration infrastructure remains the future credential authority. Publishing and execution return HTTP 409 even for authorized users, and no worker consumes Power Apps resources. Enabling Production only enables its draft workspace.

## Files added

- `backend/app/apps/power_apps/__init__.py`
- `backend/app/apps/power_apps/registry.py`
- `backend/app/apps/power_apps/contracts.py`
- `backend/app/apps/power_apps/models.py`
- `backend/app/apps/power_apps/service.py`
- `backend/app/apps/power_apps/router.py`
- `backend/alembic_postgresql/versions/pg_20261027_032_power_apps.py`
- `backend/tests/test_power_apps.py`
- `backend/tests/test_power_apps_migration.py`
- `frontend/src/apps/power-apps/PowerAppsPage.tsx`
- `frontend/src/apps/power-apps/api.ts`
- `frontend/src/apps/power-apps/registry.ts`
- `frontend/src/apps/power-apps/power-apps.css`
- `frontend/src/apps/power-apps/applications/automations/DraftEditor.tsx`
- `frontend/src/apps/power-apps/shared/EmptyState.tsx`
- `frontend/src/apps/power-apps/shared/ActivityList.tsx`
- `frontend/src/apps/power-apps/shared/PlannedApplication.tsx`
- `frontend/playwright.power-apps.config.ts`
- `playwright/power-apps.spec.ts`
- `docs/qa/power-apps-desktop.png`
- `docs/qa/power-apps-mobile.png`
- This report.

## Files changed for this implementation

- `backend/app/module_registry.py`: register standalone platform router/models alongside existing platform services.
- `backend/app/access/catalog.py`: module route/name, permission prefix, safe editing presets.
- `backend/app/access/scope.py`: permit organization metadata reads for environment configuration while retaining tenant guards.
- `backend/app/access/api.py`: attach an invited user's existing identity relationship before flush; fixes duplicate identity creation exposed by regression checks.
- `backend/app/apps/business_os/services/module_service.py`: optional module registration with no integrations.
- `backend/app/db/init_db.py`: seed permissions through the existing permission database.
- `backend/alembic_postgresql/versions/pg_20261027_031_communication.py`: predecessor revision typo only.
- `backend/tests/automation_test_utils.py`, `backend/tests/test_crm_phase_1_core_foundation.py`, `backend/tests/test_business_os_modular_foundation.py`: give legacy test fixtures the verified company context now required by existing security checks.
- `frontend/src/App.tsx`: lazy page and application/draft routes.
- `frontend/src/appRegistry.ts`: recognize the new platform key.
- `frontend/src/pages/ModuleIndexPage.tsx`: launcher entry and count.
- `frontend/src/components/layout/AppLayout.tsx`: standalone shell boundary.
- `frontend/src/lib/roles.ts`: existing-policy route guard for Power Apps.

The working tree contained extensive unrelated uncommitted work before this task, and other changes continued during implementation. This list identifies this task's edits, not every working-tree modification. Existing edits were preserved.

## Validation

- PostgreSQL: 19 Power Apps API and migration tests passed. They cover auth, catalog, real zero and nonzero aggregates, environment enablement/revocation, tenant isolation, ownership, managed-policy access, draft persistence, snapshots, stale version conflicts, delete auditing, invalid/unsafe input, disabled company modules, independent view permission, safe editing presets, and disabled execution/publication.
- Regression group: 107 passed across Power Apps/migration, existing automation workflows and RBAC, shared forms, CRM core foundation, HRMS core extensions, InternHub, PMS project access, and company security boundaries.
- Access/module-management group: 43 passed, 1 skipped across Business OS dynamic/module foundation, central access, and Power Apps. These groups overlap; their totals are not additive.
- Browser: five Playwright tests cover Master Suite entry, all 12 application routes, create/edit/reload/delete, environment switching, revoked route access, mobile overflow, and API-error recovery. Browser API fixtures are isolated test data; backend behavior is verified separately against actual PostgreSQL.
- Frontend TypeScript, targeted ESLint, and production build passed. Build warnings concern existing large chunks and third-party annotation placement.
- Desktop (1536px) and mobile (390px) screenshots were rendered and inspected. Browser tests use their own Vite server on port 5193 to avoid interference from other local test runs.

Reproduce backend checks from `backend`:

```powershell
$env:FAST_TEST_PASSWORD_HASHES='1'
venv/Scripts/python.exe scripts/run_postgres_tests.py tests/test_power_apps.py tests/test_power_apps_migration.py -q --disable-warnings
```

The runner recreates a dedicated `business_suite_*_test` database and does not target the configured app database. Reproduce browser checks from `frontend`:

```powershell
npx playwright test --config=playwright.power-apps.config.ts --workers=1
```

## Deployment and access

Run the normal PostgreSQL migrations, restart the backend with the new source, and publish the new frontend build through the existing release process. Use the existing Access Center to grant Power Apps view/create/edit permissions to intended users. Grant environment administration and activity-log access separately as appropriate. New organizations need an explicitly enabled environment. This task did not deploy or publish a release.

## Phase 2 readiness and unfinished capabilities

The dashboard, draft persistence, scoped resources, versioning, audit center and declarative contracts are ready as the foundation for Phase 2. A visual workflow editor, full condition/action configuration, cycle/executability validation, connector implementations, credential resolution, event subscriptions, schedule/webhook ingress, worker authorization rechecks, retries/recovery, delayed continuations, runtime idempotency handling and execution tests remain to be implemented before publication or execution can be enabled.

Approvals, Forms, Tables, App Builder, Notifications, Universal Search, Dashboards, Connectors, Documents and AI Agents are route/component/catalog boundaries with roadmap states. Their business tools, reporting facts and templates are not implemented. Existing shared engines can be explicitly adapted later; there is no automatic cross-module data access now.
