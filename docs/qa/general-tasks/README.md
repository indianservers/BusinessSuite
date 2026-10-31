# Workspace membership and general tasks

- Each People card now exposes **Add to workspace** directly. The existing bulk workspace action remains available.
- Adding a person to a team automatically creates ordinary workspace Member access in the same transaction. The team dialog has no workspace-confirmation checkbox. Existing Guest roles are not silently upgraded; inactive or out-of-scope people cannot be enrolled.
- The People directory exposes one **Super Admin** filter. It matches superuser accounts and the `super_admin`/`Super Admin` role spellings. Role permissions and account privileges are unchanged. Saved alias filters normalize to the canonical filter.
- Task creation offers **Project task** and **General / workspace task**. General tasks require a workspace, without requiring a user project. The existing work-item types, assignment, execution and review features still apply.
- Tasks can choose a parent task in the same location. **Create subtasks** opens the full-page form with that parent selected. The backend rejects cross-location parents and cycles.

## Storage and migration

Migration `20261031_046_general_tasks` adds `pms_projects.is_task_collection` and a unique partial index allowing one general-task collection per workspace. Apply migration 045 first if it is not already deployed.

The existing task engine requires a project foreign key across assignments, comments, evidence, files and auditing. General tasks therefore use a marked internal workspace collection to reuse those relationships and permission checks. This is not exposed as a user project in project lists. The collection is protected from ordinary project editing/deletion. Existing project tasks and subtask relationships remain unchanged.

General tasks inherit the workspace boundary. Creating the collection requires workspace Member, Admin or Owner access; Guests cannot create it. Changing a collection's membership does not grant broader organization privileges.

## Verification

- Backend API and migration tests: `tests/test_pms_general_tasks.py`, plus People workspace, Task Studio and My Work regressions.
- Browser: `node qa/general_tasks_browser.cjs`, against the disposable backend on 1558 and frontend on 5190. Covers visible workspace membership, deduplicated role choices, team preview without checkbox, general-task creation, subtask creation and exclusion from project lists.
- Frontend TypeScript, scoped ESLint and Vite production build.

Local verification uses isolated SQLite and QA users. Production PostgreSQL migration execution and deployment remain pending. No live account, membership or task records were changed.
