# Unified suite implementation — 12 November 2026

## Stage 1: inspected architecture and dependency map

This is the existing React/Vite + FastAPI/SQLAlchemy suite. Preserve both Alembic
chains (`backend/alembic` and `backend/alembic_postgresql`) and module installation
through `backend/app/module_registry.py` and `frontend/src/appRegistry.ts`.

Read-only inspection of the configured PostgreSQL database found 840 tables.
Selected baseline counts: `crm_companies` 411, `crm_contacts` 1252, `crm_leads` 429,
`employees` 235, `crm_teams` 0, `pms_tasks` 1308, `pms_calendar_events` 0,
`srm_products` 190, `srm_invoices` 122, `srm_sales_orders` 126,
`suite_business_relationships` 267. Counts are observations, not migration targets.
No connection strings or personal records are included here.

Canonical dependencies:

- Customers/vendors: `CRMCompany`, `CRMContact` and
  `suite_business_relationships`; shared master-data APIs, `CompaniesPage` and
  `CompanySelect`. SRM commercial customer resolution uses these CRM IDs.
- People/employees: `common_people` links users; `employees` remains HRMS-owned.
  Do not merge the employee and contact tables by phone/email.
- Leads: `crm_leads`; `LeadManagementPage` and CRM lead API. Existing conversion,
  record visibility and source/history must remain authoritative.
- Tasks: `pms_tasks`, assigned users, projects and workspace membership;
  `PMSTaskRecordLink` already exists. `/crm/tasks` renders `TaskExperiencePage`.
  Legacy CRM task records remain available at `/crm/tasks/legacy`.
- Notes: persistent PMS `NotesPage`; shared editor is presentation, not a new
  store. `pms_notes` is not the table name; do not invent a replacement table.
- Catalog: `srm_products` is the unified product/service master; shared catalog
  API extends it with `shared_catalog_details`/`shared_catalog_links`. CRM product
  and service identities have compatibility migrations and must not be recopied.
- Sales, POS, inventory: one installed `srm` module, existing POS/session/held-bill/
  return workflows, warehouse movements and commercial invoices. Embedded legacy
  inventory remains an integration boundary; do not assume its IDs are SRM IDs.
- Accounting: existing `shared/accounting_sync` and FAM posting/reversal controls.
  Reuse these, including idempotency, rather than creating a second journal.
- Calendar: `PMSCalendarEvent` and PMS Planner; CRM scheduling also projects native
  records through `/scheduling`. These are not yet one appointment system.
- Teams: CRM sales teams and PMS workspace team configuration have distinct
  semantics. `/common/teams` currently exposes the existing PMS team page; this
  does not merge teams or convert collaborator users into HR employees.

Authorization flows through authentication, company/branch context, module
entitlements, permission dependencies and record visibility. Shared route module
context is navigation metadata only and cannot replace these checks.

## Stage 2: common route foundation

`frontend/src/lib/common-routes.ts` owns the eleven proposed common routes,
native page destinations, supported module context and safe exact aliases.
`CommonEntityPage` mounts the registered native route element instead of creating
duplicate page implementations. Context persists as `?module=crm|pms|hrms|srm|fam`
through refresh/deep links. Workspace/project query parameters are retained by
navigation. Source-aware catalog/company/follow-up adapters remain in use.

Role-filtered module navigation and command catalogs use these shared links.
The shell resolves module branding and navigation from common context. Common
routes require both originating module access and access to the selected native
destination; backend APIs retain their original authorization. Unknown entities
and invalid module values fail closed. Native URLs and APIs remain available.

There is no schema migration in this stage and no data was updated. Existing
CRM-specific calendar and legacy finance party screens are deliberately not
aliased to a different data source. List aliases are exact: detail/new/import
routes continue through their established native workflows.

## Stage 3 increment: shared task filtering

The existing `GET /api/v1/project-management/tasks` accepts optional
`sourceModule=all|crm|pms` (default `all`, preserving existing API consumers).
CRM filtering reuses `pms_task_record_links` and CRM record-visibility queries;
the original accessible-project scope stays in effect. Multiple links cannot
duplicate list rows. Tenant-mismatched links and deleted/inaccessible targets
do not qualify. No relationship or task is created by filtering.

Both classic and WhatsApp task themes expose the module filter. Opening CRM
Tasks defaults to CRM-linked tasks; All Modules lists all tasks permitted by
the existing PMS API. Saved views retain common-route module context. There
is no claim that HR or Sales task associations have already been implemented.

### Changed files and verification

- Route registry/page/shell: `frontend/src/lib/common-routes.ts`,
  `frontend/src/common/CommonEntityPage.tsx`, `frontend/src/App.tsx`,
  `frontend/src/lib/roles.ts`, `frontend/src/hooks/use-module-action.ts`.
- Navigation: `frontend/src/components/layout/ModuleNavigation.tsx`,
  `frontend/src/components/layout/PMSMoreMenu.tsx`,
  `frontend/src/components/layout/PMSPersonalNavigation.tsx`,
  `frontend/src/components/app/Breadcrumbs.tsx`,
  `frontend/src/lib/navigation-menu.ts`, `navigation-workspaces.ts`,
  `products.ts`, `moduleCatalog.ts`.
- Existing source-aware views: `frontend/src/shared/catalog/CatalogPage.tsx`,
  `frontend/src/shared/follow-ups/FollowUpsPage.tsx`.
- Tasks: `backend/app/apps/project_management/api/router.py`,
  `frontend/src/apps/project-management/types.ts`,
  `frontend/src/apps/project-management/pages/TasksReferencePage.tsx`,
  `frontend/src/apps/project-management/pages/WhatsAppTasksPage.tsx`.
- Tests: `frontend/scripts/test-common-routes.cjs` (129 route/adapter/alias/
  context/refresh/permission scenarios), `backend/tests/test_common_task_scope.py`
  (10 scenarios); npm command `test:common-routes` added.
- `frontend/scripts/test-search-navigation.cjs` now expects canonical shared
  destinations; global-search and PMS personal-navigation regressions passed.
- Existing backend suites: shared POS catalog, contact directory, CRM shared
  relationships: **32 passed**. New task scope plus existing task-record links:
  **19 passed**. Frontend `tsc --noEmit` passed; desktop navigation, branding and
  route guard browser regressions passed.

These are scoped regression results, not the requested 100 end-to-end business
workflow acceptance scenarios. Migration status: **not required**, no schema or
business record changes. Production backup/deployment status: **not performed**.

The guarded PostgreSQL runner was also attempted against a separate disposable
`business_suite_common_routes_20261112_test` database. The configured database
role lacks `CREATE DATABASE`, so that run stopped before fixtures/migrations or
tests could execute. PostgreSQL runtime integration remains unverified; the
passing backend results above used isolated SQLite fixtures. The configured
application database was only inspected read-only.

## Dependent stages and acceptance gaps

1. **Shared records:** extend Sales-only access to leads using an explicit
   authorized adapter; add reliable module associations/default filters to tasks
   and notes; reconcile team semantics without silently merging. Common route
   availability does not mean every role can access every entity.
2. **Sales consolidation:** display Sales & POS while preserving `srm` module key,
   existing URLs and inventory ownership. Complete capabilities/settings registry
   before replacing industry presets.
3. **Catalog/tax:** add validated item subtypes to the existing catalog; extend the
   existing tax engine with effective-date rules, preserved invoice-line snapshots,
   inclusive prices, discounts and jurisdiction components. Do not accept
   client-calculated financial totals as authoritative.
4. **Appointments:** extend existing Calendar with an appointment association to
   canonical customer, employees and catalog services. Transactional employee and
   exclusive-resource conflict checks must include concurrent requests, working
   hours, leave, holidays, buffers and timezone changes. Creation must not charge.
5. **Packages/subscriptions/AMC:** build on SRM contracts, billing plans,
   recurrence, follow-ups, PMS tasks and calendar; enforce redemption uniqueness
   and reversals. Preserve existing contract IDs.
6. **Finance:** connect completed appointment/contract service billing through
   existing commercial invoices and idempotent FAM posting/reversal workflows.
7. **Hardening:** pagination, invalidation, backend record-level permissions,
   responsive interaction, concurrency and full browser workflow coverage.
8. **Release:** run the existing tests plus at least 100 meaningful integration
   scenarios. A test count alone is not acceptance. Reconcile counts/relationships
   and balances against a consistent snapshot, then rehearse rollback on a
   disposable restored PostgreSQL database. Take and verify a production backup
   before applying any future production migrations.

These stages remain requirements, not claims of completed implementation.
No deployment, production migration, backup or financial reconciliation has
been performed by the common-route change.
