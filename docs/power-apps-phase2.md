# Power Apps - Phase 2 completion report

Date: 2026-10-27

## Delivered

Automation Studio is a standalone visual workflow editor inside Power Apps. It does not insert functionality into PMS, CRM, HRMS, or InternHub. It reuses Phase 1 identity, tenant/environment scoping, permissions, draft resources, optimistic versions, snapshots and activity logging.

The editor uses React Flow (`@xyflow/react` 12.12.0 in the lockfile) with the existing React 18/Vite/TypeScript stack. Its light canvas, purple rail, compact controls, colored nodes and spacious branching layout follow the supplied Make reference while using Business Suite's design language.

- Full-screen canvas with pan, wheel/pinch zoom, snap-to-grid, optional dots, smart paths, branch/edge labels, rendered mini-map, fit-to-screen and auto-layout.
- Node dragging, multiple selection, keyboard deletion with confirmation, internal copy/paste, duplication, grouping/ungrouping and an 80-step undo/redo history.
- Searchable toolbox across the twelve requested categories, native drag-and-drop, and a searchable plus-button picker. Custom catalog categories are supported.
- Schema-driven configuration with names/descriptions, all fourteen requested field kinds, searchable upstream variable insertion, output schemas, reference-only credentials, retry/timeouts, error handling, validation and help.
- Resizable/collapsible panels, responsive tablet controls and mobile overview/node inspection. Keyboard shortcuts and visible focus states are included.
- Debounced autosave, visible save state, optimistic conflicts, save-as-copy recovery and user/organization/environment/workflow-scoped recovery in the current browser tab.
- Stored-record list filters for All, My, Shared, Drafts, Published and Disabled; versioned Templates view. Shared means other-owned records already visible through the existing organization-wide grant. Disabled contains archived drafts; it does not claim a running workflow was disabled.
- Authorized create, rename, duplicate, edit, archive/unarchive and delete. Archived drafts are read-only. Published workflows cannot be created or destructively changed through these APIs.
- Version history, snapshot comparison and restore as a separate new draft. Restoring never overwrites the source workflow or its snapshots.
- Test input, structural validation, local preview timeline, node input/output inspection and error details. Preview results are never written as workflow execution history.

## Routes

- `/power-apps/automations`
- `/power-apps/automations/new`
- `/power-apps/automations/:resourceId/edit`
- `/power-apps/automations/:resourceId/versions`
- `/power-apps/automations/:resourceId/settings`
- The earlier `/power-apps/automations/:resourceId` link also opens Studio.

An `environment=development|testing|production` query parameter preserves the selected workspace between list/editor/history/settings routes. All backend reads and writes independently validate environment authorization.

## Editor-ready versus executable

There are **48 editor-ready node definitions**, **21 side-effect-free local previews**, and **zero runtime executors**. Every node visibly states **Not Executable Yet**. Configured means configuration is structurally complete; it does not mean a live connection or executor has been authorized.

The 21 local-preview types are:

Manual Trigger, If / Else, Switch, AND / OR Condition, Filter, Compare Values, Check Empty Value, Evaluate Expression, Route by Priority, Parallel Branch, Merge, Stop Workflow, Set Variable, Transform Data, Map Fields, Format Date, Format Number, Parse JSON, Build JSON, Aggregate Values, Log Event

All other nodes can be configured and connected, but their preview result is explicitly `not_executable`, with no fabricated output. This includes scheduled/event/webhook ingress, emails, notifications, tasks, approvals, delays/waits/loops, connector actions, HTTP requests, AI calls, sub-workflows and internal service actions.

Expressions are bounded property-path references such as `{{trigger.record.id}}` and `{{steps.create_task.output.task_id}}`. They are not JavaScript, Python, or general-purpose arithmetic code. Comparisons and boolean logic have declared fields. There is no `eval`, `new Function`, arbitrary source-code node, credential decryption or outbound request in preview.

## Schema and validation

Visual definitions use schema version 2 and catalog version 1. They store plain nodes, typed ports, directed edges, positions, viewport, visual groups and workflow settings in the existing resource JSON. Schema v1 remains accepted by the existing API. Studio imports older definitions for explicit review, preserves bounded delay/retry settings and normalizes numeric legacy node IDs; original snapshots remain available.

Server validation rejects unsupported types, extra fields, malformed/unsafe expressions, inline secret fields, incompatible ports, duplicate edges, over-connected ports, non-finite or out-of-range positions and arbitrary graph cycles. Drafts may remain incomplete; Validate separately reports missing triggers, unreachable nodes, missing parameters/credential references, branch gaps, invalid dates/timezones and invalid upstream/output references.

Loops are explicit nodes with a maximum of 1,000 iterations; there is no arbitrary cyclic graph or loop executor. The persisted editor limit is 500 nodes and 1,500 edges. Local preview is limited to 250 nodes and 32 KB of test input. Large or deeply nested parsed JSON is bounded.

## Reusable component API

`AutomationBuilder` accepts workflow/environment IDs, edit/read-only mode, an initial plain document, effective permission flags, a configurable node catalog, persistence/validation/preview callbacks, version/restore callbacks, theme tokens, reference providers and an optional modular configuration panel.

Example integration boundary:

```tsx
<AutomationBuilder
  workflowId={record.id}
  environmentId={environment}
  mode="edit"
  initialDocument={document}
  version={record.version}
  savedAt={record.updated_at}
  recoveryKey={scopedRecoveryKey}
  nodeCatalog={catalog}
  permissions={effectivePermissions}
  onSave={saveWithExpectedVersion}
  onValidate={validateOnServer}
  onPreview={previewPureNodes}
  onBack={openAutomations}
/>
```

The editor does not know business-module APIs. The Power Apps page supplies the existing server API callbacks. Server-side `register_node` installs trusted extensions; a browser-supplied custom catalog cannot bypass the server's registry or publish guard.

Reference selectors are real reusable comboboxes. The supplied page can select the signed-in user and authorized Power Apps sub-workflows. Record/template/credential lookups without an installed adapter show an explicit unavailable-lookup message and allow a known reference or upstream mapping; they do not fabricate directories, templates, credentials or external records. Connection secrets are never loaded into the browser.

## Templates

Eight versioned, deployment-owned workflow definitions are stored in `automation_templates.json` and validated at startup:

1. New record to assigned task.
2. Form submission to approval.
3. Status changed to notification.
4. Scheduled reminder.
5. Critical bug escalation.
6. Employee onboarding checklist.
7. Lead created to representative task.
8. Approval completed to record update.

Each has its own template version, schema-v2 definition, required-adapter list, requires-configuration flag and `executable=false`. Use template creates a new authorized environment-scoped draft. It does not register a trigger, enable a business-module integration, or activate anything.

## Database and APIs

`pg_20261027_033_power_studio` adds nullable `archived_at` and an organization/environment/lifecycle index to the existing resource table. It preserves existing definitions and can be reversed. Schema version 2 requires no duplicate workflow/user/tenant tables. Snapshots now include archival state; sensitive credential-reference changes get a separate activity entry.

API additions under `/api/v1/power-apps/automations`:

- GET `node-catalog`, `templates`.
- POST `templates/:templateId/use`.
- POST `validate`, `preview`.
- POST `:id/duplicate`, `:id/restore`.
- POST `:id/archive`, `:id/unarchive`.
- Existing list/read/update/delete/version endpoints are reused and extended.

Rename preserves the stored definition and uses the existing PUT/version check. Lifecycle actions require edit permission; copy/restore/template use require create permission and source visibility. Every endpoint also requires view access. Existing tenant boundaries and central record scopes remain in force.

The existing publish and execute endpoints still return HTTP 409 even for fully authorized administrators. The database still restricts resource status to draft. No Phase 2 graph is consumed by a worker.

## Files

Backend files added:

- `backend/app/apps/power_apps/node_catalog.json`
- `backend/app/apps/power_apps/node_registry.py`
- `backend/app/apps/power_apps/graph.py`
- `backend/app/apps/power_apps/studio.py`
- `backend/app/apps/power_apps/studio_api.py`
- `backend/app/apps/power_apps/automation_templates.json`
- `backend/app/apps/power_apps/templates.py`
- `backend/alembic_postgresql/versions/pg_20261027_033_power_studio.py`
- `backend/tests/test_power_studio.py`
- `backend/tests/test_power_studio_migration.py`
- `backend/scripts/power_studio_qa_server.py`

Frontend files added:

- `frontend/src/apps/power-apps/applications/automations/AutomationEditorPage.tsx`
- `frontend/src/apps/power-apps/applications/automations/AutomationList.tsx`
- `frontend/src/apps/power-apps/applications/automations/automations.css`
- `frontend/src/apps/power-apps/applications/automations/builder/AutomationBuilder.tsx`
- `frontend/src/apps/power-apps/applications/automations/builder/ConfigurationPanel.tsx`
- `frontend/src/apps/power-apps/applications/automations/builder/NodeIcon.tsx`
- `frontend/src/apps/power-apps/applications/automations/builder/NodeLibrary.tsx`
- `frontend/src/apps/power-apps/applications/automations/builder/ReferenceSelector.tsx`
- `frontend/src/apps/power-apps/applications/automations/builder/StudioEdge.tsx`
- `frontend/src/apps/power-apps/applications/automations/builder/StudioNode.tsx`
- `frontend/src/apps/power-apps/applications/automations/builder/StudioPanels.tsx`
- `frontend/src/apps/power-apps/applications/automations/builder/graph.ts`
- `frontend/src/apps/power-apps/applications/automations/builder/studio.css`
- `frontend/src/apps/power-apps/applications/automations/builder/types.ts`
- `frontend/src/apps/power-apps/applications/automations/builder/useDocument.ts`
- `frontend/src/apps/power-apps/applications/automations/builder/useDraftPersistence.ts`
- `frontend/src/apps/power-apps/applications/automations/studioApi.ts`

Test/config files added:

- `playwright/power-apps-fixtures.ts`
- `playwright/power-studio.spec.ts`
- `playwright/power-studio-live.spec.ts`
- `frontend/playwright.power-studio-live.config.ts`

Existing files extended:

- Backend Power Apps `contracts.py`, `models.py`, `router.py`, `service.py`.
- `backend/app/module_registry.py` and `backend/app/access/catalog.py`.
- `frontend/package.json` and `frontend/package-lock.json`.
- `frontend/src/App.tsx` and Power Apps `PowerAppsPage.tsx` / `registry.ts`.
- Existing Power Apps browser spec and focused Playwright configuration.

The working tree also contains unrelated uncommitted work from before/during this task. The legacy JSON `DraftEditor.tsx` was retained; it was not copied into another engine.

## Migration compatibility repair

A concurrent PMS migration, `pg_20261027_034_custom_columns`, was added after Studio's revision. Full PostgreSQL validation revealed it tried to add columns already created by an older migration's current ORM model. Its compatibility repair now checks existing columns/indexes/constraints/tables and preserves already-assigned company scopes during backfill. An explicit regression test verifies it can run twice without erasing existing scopes. This is a migration-chain repair, not a Power Apps integration into PMS; PMS runtime code was not changed by this task.

## Validation and evidence

- **47 PostgreSQL tests passed**, including Phase 1 compatibility, schema-v2 persistence, real aggregation, tenant/environment/ownership enforcement, stale-save conflicts, archive/restore/copy, all 48 node contracts, template definitions, unsafe graphs/expressions/secret rejection, sensitive-reference auditing, pure preview branching and migration preservation.
- **20 focused browser tests passed**, covering all twelve catalog routes, desktop/mobile layout, creation, dragging, connecting true/false branches, configuration, variable insertion, save/reopen, undo/redo, copy/paste/reference remapping, grouping, keyboard deletion, management filters/actions, version comparison/restore, settings, templates, conflict recovery, read-only access, mini-map, wheel zoom, synthesized touch pinch, legacy migration and reference selection.
- **Two real-API browser tests passed** against an isolated temporary SQLite QA server with normal authentication/authorization: real save/reload and preview output, snapshots, zero execution history, blocked publishing, tenant denial and read-only reviewer denial. PostgreSQL schema/API coverage is separate and uses the guarded disposable test-database runner.
- TypeScript, targeted ESLint and the production build passed. The build retains the existing large-chunk/third-party annotation warnings.
- A broader suite run recorded **164 passed, 1 skipped, 2 failed**. The failures are `test_custom_fields_validate_types_and_project_scope` and `test_type_specific_fields_and_plural_names` in `test_pms_project_access.py`: they expect 404 while concurrently modified PMS custom-field code returns 422 (`Custom field is not applicable to this record`). Power Apps does not call that code, and its runtime behavior was left unchanged. This report does not certify the entire repository as regression-free.

Screenshots and machine-readable timing evidence are under `docs/qa/power-studio/`. Screenshots use clearly isolated test fixtures, not claimed production activity.

Browser benchmarks measured 10/50/100/250-node documents, first load, name-edit responsiveness, serialization and structural validation. They include virtualized rendering, fit-to-screen and persistence. Exact readings are preserved in `performance-10.json`, `performance-50.json`, `performance-100.json`, and `performance-250.json`; these are development-machine observations, not universal frame-rate guarantees. Snapshot timing is after actual browser work, and no fabricated execution timings are displayed in the product.

## Reproduce

From `frontend`:

```powershell
npx playwright test --config=playwright.power-apps.config.ts --workers=1
npx playwright test --config=playwright.power-studio-live.config.ts
npm run build
npx eslint src/apps/power-apps src/App.tsx --ext ts,tsx --max-warnings 0
```

The live config owns a separate frontend/API process and a temporary QA database. No application data is used. From `backend`:

```powershell
$env:FAST_TEST_PASSWORD_HASHES='1'
$env:POSTGRES_TEST_DATABASE='business_suite_power_studio_test'
venv/Scripts/python.exe scripts/run_postgres_tests.py tests/test_power_apps.py tests/test_power_studio.py tests/test_power_apps_migration.py tests/test_power_studio_migration.py -q --disable-warnings
```

The runner only recreates the named `business_suite_*_test` database. No migration or deployment was performed against the configured application/production database. Apply the normal release migrations and frontend/backend release process before serving Studio in a deployed environment.

## Phase 3 readiness

Phase 2 is complete as a visual design, persistence, validation, versioning and pure-preview layer. Phase 3 must implement and test the permission-aware worker, execution leases, immutable published definitions, credential resolution, trigger ingress, schedules, real connectors/actions, node-attempt records, bounded-loop runtime, idempotency, retries/backoff, delay/approval continuations, error routes and crash recovery before enabling Publish or Execute.

Publishing/activation, external integrations and live business mutations remain deliberately unavailable. There is no automatic cross-module data access.
