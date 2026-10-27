# PMS custom columns

The Custom Field Manager at `/pms/custom-fields` now manages reusable company fields and fields limited to a project. Each definition targets Tasks, Projects, or both. Existing project definitions remain task fields and retain their values. Company-wide definitions stay within the active verified company; PMS administrators manage them, while project managers manage project definitions. Record editing uses existing task/project permissions.

The library includes Financial Year, Client reference and Service line starters, twelve field types, scope and type filters, field previews, rename, and archive/restore. Archiving hides a definition without deleting its stored values. Used dropdown options cannot be removed. Type, location and entity target remain fixed after creation.

Fields appear in task and project creation forms, project edit/detail views, task details and drawers, the task column picker, the project card/table views, and workspace task lists. Task/project tables support inline value editing. Task column visibility works with browser preferences and saved views; project field visibility uses browser preferences. Project cloning remaps project definitions and copies values, task duplication copies applicable active values, and recurring tasks inherit their predecessor's custom values. Values on tasks and projects are independent, including for a field targeting both.

## Deployment

Apply the appropriate migration chain before starting the updated backend:

- PostgreSQL: `pg_20261027_034_custom_columns`, after `pg_20261027_033_power_studio`.
- Legacy chain: `20261027_034_custom_columns`, after `20261027_031_communication`.

The migration makes the existing field project reference optional, adds company/scope/target/archive metadata, backfills existing project fields, and creates `pms_project_custom_field_values`. It preserves existing task field definitions and values. Downgrade intentionally refuses to discard company/project data. No production database has been changed by this work.

## Validation

- `backend/tests/test_pms_custom_columns.py`: typed values including zero/false, native create/update, company boundaries, permission checks, invalid creation without orphan records, rename/archive/restore, cloning, recurrence and legacy definitions.
- `backend/tests/test_custom_columns_migration.py`: both migration variants preserve populated existing definitions and values on a disposable database.
- `backend/tests/test_pms_migration_chain.py` and `test_pms_workspace_tools.py`: migration linkage and existing project/task creation integrations.
- `playwright/custom-columns-live.spec.ts`: real HTTP against a disposable local backend; template creation, project/task forms, inline edits, reload persistence, column visibility persistence, rename/archive/restore, and mobile overflow checks.
- Frontend production build and TypeScript checks.

Screenshots are in `docs/qa/custom-fields-desktop.png`, `custom-fields-mobile.png`, and `custom-task-columns.png`.

A separately attempted existing `test_pms_task_composer.py` fixture failed before project/task creation because its account helper does not create a verified Company record. The custom-column tests create verified companies and exercise recurrence through the real API.

## Boundaries

This adds optional data columns, not custom SQL, formulas, relational fields, custom sorting/filter operators, or a cross-module field service for CRM/HRMS. Those modules retain their existing independent field systems. Lists load values through a bounded authorized batch endpoint; archived values reappear on restore. PostgreSQL DDL is prepared but was not run against a production or external PostgreSQL database.
