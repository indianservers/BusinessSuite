# My Work redesign

The `/pms/my-work` route now uses `MyWorkPage` within the existing Business Suite shell. Task creation and full task details reuse `/pms/tasks/new` and `/pms/tasks/:id`.

## Changes

- Compact task statistics, personal/all/team/batch/unassigned/review/completed scopes, list, board, calendar and recent activity.
- Avatar assignments, portalled status/priority menus, checklist-derived progress, column resizing/visibility, sorting, server pagination and mobile cards.
- Debounced search, workspace/date filters, multiple projects/people/statuses/priorities, advanced team/batch/reporter/type filters, URL state and browser-local saved views/preferences per account and organization.
- Assignment panel with paginated people and group member search, role filtering, group responsibility, removable selections, notes and individual in-app notifications.
- Bulk assignment, status/priority/date/project changes, CSV export and confirmed deletion. Each task receives its own permission and concurrency checks; partial failures are reported.

## Assignment meaning and compatibility

Migration `20261031_045_task_groups` adds `pms_task_group_targets`. It does not rewrite existing tasks or individual work records. Deploy this migration before releasing the new frontend/backend.

New shared-task creation explicitly uses `group_responsibility=true`. Selecting a team or batch creates a responsibility record and captures its name and eligible-member count. It does **not** create an individual assignment for every member. Individually selected people use canonical PMS user IDs. Group membership changes do not enroll or remove individual assignees, and do not rewrite assignment history. Choose individual members explicitly in the panel when individual responsibility is required.

Historical Task Studio callers retain the original member-snapshot behavior unless they opt in. Existing source-managed InternHub execution/review records remain protected and must be removed using their batch workflow. The independent-execution task composer mode continues to use its existing batch task workflow.

Task details return saved group selections; editing a task preserves them. Moving a task with group responsibility requires clearing that responsibility first, so it cannot retain a team/batch from an incompatible destination project. Group changes and notes are audited. Notification selection sends in-app notifications to individually selected people; group responsibility does not notify or enroll the entire group.

## Verification

- `cd backend; .\venv\Scripts\python.exe -m pytest -p tests.rich_text_test_utils tests/test_pms_my_work.py tests/test_pms_task_studio.py tests/test_statistics_metrics.py -q`
- `cd frontend; npx tsc --noEmit`
- `cd frontend; npx eslint src/apps/project-management/pages/MyWorkPage.tsx src/apps/project-management/components/TaskAssignmentPanel.tsx src/apps/project-management/pages/TaskStudioPage.tsx`
- `cd frontend; npx vite build`
- `qa/my_work_browser.cjs` uses only the disposable loopback QA backend on port 1558 and frontend on 5190. It checks saved assignments after reload, task scopes, layouts, search, bulk selection, full-page task creation and mobile/tablet sizing. Screenshots are in this directory. Seeded sample tasks exist only in that disposable QA database.

The pytest plugin above supplies the repository's existing organization bootstrap; without it the older task fixtures fail during tenant setup.

## Practical limits

- Board and calendar display the current server-paginated result page, labelled in the interface. Switch pages or narrow the date range for additional tasks.
- Saved views and table preferences are local to the current browser/account/organization.
- Bulk assignment options come from the first selected task's project; other tasks are independently validated and incompatible selections produce per-task failures. Bulk operations do not promise an all-or-nothing cross-project transaction.
- People search and expanded group membership are paginated. Group option preparation still uses the existing server-side eligibility resolver; no thousand-member batch payload is downloaded for selection.
- Verification uses an isolated SQLite database and an isolated additive-migration test. Production PostgreSQL migration execution, production credentials and deployment are not part of these local checks. Existing production records were not changed.
