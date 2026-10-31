# People Directory implementation and validation

Implemented on `codex/people-directory`, based on `920654d`. Production is unchanged: the supplied request explicitly says not to deploy without an explicit request. All synthetic records used in validation were confined to disposable local databases.

## Frontend

- Replaced `PeopleManagementDirectory.tsx` with the reference-inspired purple/white desktop grid, real photo cards, five scoped counts, searchable filters, saved personal views, card/list switching and pagination. URL filters and per-view scroll positions survive profile navigation. Existing main sidebar and top bar remain.
- New reusable components under `components/people/`: `DirectoryPersonCard`, `DirectoryGroupsPanel`, `DirectoryDialogs`, `DirectoryImport`, and typed `peopleWorkspace` API helpers.
- New `PeopleDirectoryProfile.tsx` at `/pms/people/:personId`: overview, teams, batch memberships, projects, tasks and scoped audit activity. Login and employment status remain separate; no private HR documents are exposed.
- `PeopleWorkspace.css` provides desktop center/right panels and tablet/mobile group tabs. Modal dialogs use Radix focus management. The photo component falls back to initials after an image error.
- `TaskStudioPage.tsx` accepts preselected people, teams and batches directly in its full-page route. Searchable people/reviewer/owner selectors load pages, not the entire directory. Shared task and independently tracked intern assignment modes are explicit. Distribution progress, chunk retry/continue and parent-task tracking are visible. Large managed tasks support metadata editing while protecting their source assignments.
- Small integrations in `TasksReferencePage`, PMS routes and `AppLayout`, plus query links into the existing `UserAccountsPage` and `InternManagementPage` creation workflows. Existing permission and administrator verification requirements still apply.

## Backend and migration

`people_workspace.py` adds the `/project-management/people-workspace` APIs for scoped directory/reference counts, paged teams/batches/members, profile sections, CSV export, personal saved views, membership previews/changes, assignment context and resumable individual assignment jobs.

Canonical `User`/`CommonPerson`/`Employee` identities are joined by IDs. Team management reuses `PMSWorkspaceTeam`; batches and individual task execution reuse InternHub batches, memberships, distribution jobs and PMS execution/review records. Membership changes and distribution retain existing audit services. No duplicate batch or task distribution service was introduced.

Migration `pg_20261031_045_people_workspace` adds team descriptions, lead and visibility fields; a normalized `PMSWorkspaceTeamMember` junction with a composite key; role/active and PostgreSQL trigram search indexes. It backfills deduplicated eligible legacy JSON memberships, excludes guests, and retains the old JSON compatibility cache. Both team write paths and workspace removal keep the cache and junction synchronized. Introspection handles the repository's historical current-model bootstrap as well as deployed legacy schemas.

Every new read/write validates tenant and available scope. Private teams are filtered from directory and existing team/task-option APIs. Exports are permission-checked and formula-escaped. Personal views cannot be read/deleted by another user. Adding a nonmember to a team previews and requires confirmation of Member workspace access; it never grants administrator access.

## Verification

- Frontend `npm run build`: passed, with existing bundle-size/vendor annotation warnings.
- Broader SQLite regression selection: **39 passed** (directory/migration, task studio/composer/reference tasks, workspaces, teams, InternHub management and task programs).
- Final focused SQLite directory/migration tests: **8 passed**; final directory/task-studio integration selection: **10 passed**.
- Actual local PostgreSQL: clean full migration upgrade to head, downgrade to revision 044, and reapply passed in a uniquely named disposable database. PostgreSQL directory/task-studio integration selection: **10 passed**.
- The 20,000-person local fixture verifies filtered pagination and a bounded 24-card response. A 601-recipient intern job verifies 500-row chunks, resume, repeated continue without duplicates, protected assignments, and parent metadata editing. Query-count regression checks page-size growth. These are local fixture results, not a production latency claim.
- Chromium browser checks pass: real backend cards/photos/counts; combined filters; saved views; card/list mode; profiles and returning filters; creating a team with selected members; direct person and batch preselection; individual batch assignment with reviewer/progress; desktop/tablet/mobile layouts; empty results; simulated 503 failure/retry; slow response skeleton; scoped CSV download; CSV duplicate/empty-row preview and local invitation creation; existing account and InternHub batch creation dialogs. No uncaught browser errors.
- Reproducible fixture/browser scripts: `qa/people_directory_server.py` and `qa/people_directory_browser.cjs`. The server forces a temporary SQLite database, binds only to loopback and disables external workers. It must never be used as a deployed service.

## Local reproduction

From the repository root:

```powershell
backend/venv/Scripts/python.exe qa/people_directory_server.py
```

In another terminal, start Vite on `127.0.0.1:5187` with `VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:1552`, then run:

```powershell
node qa/people_directory_browser.cjs
```

Backend tests, from `backend`:

```powershell
venv/Scripts/python.exe -m pytest -q -p tests.rich_text_test_utils tests/test_people_workspace.py tests/test_people_workspace_migration.py tests/test_pms_task_studio.py
```

Set `TEST_DATABASE_URL` only to an isolated local PostgreSQL database ending in `_test` for PostgreSQL integration coverage. Never point tests at production.

## Boundaries and limitations

- Shared task assignment retains the existing 100-assignee limit. Individual intern distributions support large batches and independent progress/submissions/review; each interactive Continue action commits up to 500 recipients. Pending chunks may also be picked up by the existing configured distribution worker.
- Directory bulk member actions cap selections at 100 per operation. Team editing supports paged selection and preserves existing selected IDs. CSV import is deliberately the existing invitation workflow (Email column, up to 100 rows), not silent account provisioning or HR-data import. Email delivery itself was not exercised against an external provider.
- Batch administration remains in existing InternHub permission scope and management screens. Public profile skills/photos obey existing directory visibility settings. Creating login accounts retains existing Super Admin verification.
- The visual match preserves the real navigation and actual permitted data; the reference image's invented record counts and headshots are not copied into production.
- The new migration has not been applied to the application database and this branch has not been pushed to main or deployed.
