# PMS implementation phases

Date: 2026-10-23. Scope: the non-LLM gaps identified in the ClickUp comparison.
Existing uncommitted work is preserved. Completion means persistent behavior,
backend permissions, usable UI and relevant verification, not a route or mockup.

## Phase 1 — trustworthy configuration and core work

- Navigation: replace misleading destinations with the actual supported feature;
  retain workspace, project, view and return context.
- Settings: remove unsaved controls; expose only settings with implemented behavior.
- Custom fields: typed project definitions and task values, then field lifecycle,
  required validation, create-task integration, table columns/filtering and scope.
- Workflows: configurable ordered statuses and categories used consistently by
  boards, task forms, automation and reports, with transition validation.
- Recurrence: editable schedules, occurrence generation, timezone/end conditions,
  duplicate prevention and recovery tests.
- Task experience: shared field components and consistent drawer/detail actions;
  improve inline editing, column controls and saved view behavior.
- Practice workflow: client/service/period/preparer/reviewer/billing information.

### Implemented in the first slice

- Added persisted project custom-field definitions and task values for text,
  number, date, checkbox and dropdown.
- Added server permission checks, project isolation and value validation.
- Added the same field editor to full task details and the workspace drawer.
- Replaced generic unsaved settings checkboxes with links to existing management
  screens and explicit descriptions.
- Added SQLite and PostgreSQL migration revisions for the new tables.

### Remaining in Phase 1

Required fields, field edit/archive and audit events, field-aware task creation,
list filtering/columns, configurable workflows, recurrence execution, navigation
cleanup and the remaining task-view consolidation are not complete.

## Phase 2 — team execution and operational visibility

- Teams with aliases, icons, membership, assignment and sharing semantics.
- Automation: expanded triggers/actions, conditions, editable rules and execution
  failure/retry history.
- Dashboard builder: saved widgets/layouts/filters, drilldown, sharing and export.
- Structured templates: subtasks/checklists/fields/relative dates and target project.
- Intake designer: typed/conditional questions, files, routing and submissions.
- Planner: day/week/agenda, duration, time blocking and rescheduling.
- Time/resource planning: timer verification, dated capacity, schedules, holidays,
  effort allocation, approval and billing export.
- Unified personal work, watcher/reminder and notification workflows.

## Phase 3 — collaboration, integrations and administration

- Private DMs, channels, threads, unread state, reactions, attachments and pins.
- Collaborative documents and whiteboards; media recording/calls evaluated as a
  separate infrastructure capability.
- Calendar/mail connectors, connection lifecycle and delivery health, generic
  outgoing webhooks, imports with mapping/dry run and workspace exports.
- Shared-platform security audit and implementation of SSO/2FA/session policies,
  custom permissions, access requests and private sharing enforcement.
- Trash coverage, deleted-by metadata, bulk restore and retention/purge semantics.
- Accessibility, mobile, role/tenant isolation, concurrent updates, network failure,
  data-volume and recovery verification across all completed capabilities.

## Verification and rollout

The first slice has targeted backend field-validation/access tests and a browser
test using mocked API persistence. These do not replace deployed database and
live browser acceptance checks. Apply the migration for the database deployment
before enabling the new custom-field API in that environment. No production
migration or deployment has been performed by this slice.


### Phase 2 first slice

Implemented workspace Teams with unique aliases, collaborator membership, create,
edit, search and backend role/workspace isolation. Teams do not grant access or
expand task assignments yet; icons, team assignment and sharing remain pending.
Automation rules can now be edited and duplicated; duplicates start paused and
editing preserves the rule's existing enabled/paused state. Execution actions
remain priority and assignee updates. Dashboard builder and other Phase 2 work
are still pending. Team migrations are included for both database tracks but no
production migration or deployment has been performed.


### Phase 3 first slice

Implemented one-to-one direct conversations scoped to a workspace. Conversation
and message records persist; only current participants can read messages, and
admins have no participant bypass. Sending requires both people to remain active
non-guest collaborators. Client request IDs make retries idempotent. The UI
supports collaborator selection, conversation search, per-conversation drafts,
recent-message polling and loading earlier history. It is accessible from shared
chat and Settings and preserves the originating workspace.

Channels, threads, reactions, attachments, unread counts/notifications, document
collaboration, external integrations, security policy administration and broader
recovery/scale work remain pending. No production migration or deployment has
been performed. Database migration revisions are included for both tracks.


### Task type manager increment

Added organization task type definitions with categories, descriptions, icon/color,
default priority, accessible active-task usage, archive/restore and recommended
presets, including practice-specific work. Task creation loads active definitions
and applies the chosen type's priority in the form; the backend rejects unknown
or archived types on creation and explicit type changes. Existing task types are
preserved when archived. Names remain immutable identifiers. This does not yet
provide type-specific custom fields, required-field rules, transitions or
conversion of a classified task into another module's business record. Migration
revisions are included; no deployed database migration has been performed.


### Persisted time tracker increment

Time Tracking now includes a server-backed timer with project/task selection,
notes, billable flag, refresh, stop/save and confirmed discard. A user has one
active timer; session keys protect stale requests and repeated stop requests
return the saved log instead of duplicating it. Stop creates a standard time log
and activity in the same transaction. Duration rounds up to whole minutes and
is attributed to the start date in the stored browser time zone. Manual entry
also accepts durations such as 3h 20m. Timer migrations are included for both
tracks; deployment has not been performed. Global toolbar timer controls,
time-entry tags and additional weekly timesheet UX remain separate work.


### Project Docs increment

Added saved project documents, Markdown editing and safe preview (headings, lists,
checklists, quotes, links, code and tables), task linking, Markdown export,
Ctrl+S, word count, unsaved-change warnings, version history and revision loading.
Saves use an atomic version condition to reject stale writers without overwriting
the newer content. Revision content is immutable and restoring creates a new
version on save. Project permissions are checked on document/history operations.
Both migration tracks are included; no deployed migration has been applied.

This is not full Google Docs or Sheets parity. WYSIWYG editing, simultaneous
coediting, comments/suggestions, granular sharing, nested wiki pages, print/PDF
and Office import/export, spreadsheet formulas, calculation, charts, pivots,
data validation and automation remain pending.


### Subtask management increment

Existing subtasks already support nested children, independent task detail,
completion/reopening, priority, due date, story points, deletion and progress.
Added multiple collaborator assignments during creation and inline editing,
explicit parent-assignee inheritance, descriptions, search and completion
filters, persisted up/down ordering and promotion to a standalone project task.
Reordering checks project permissions and requires every current child exactly
once. Promotion preserves nested children. Clearing a due date now sends null.

Not full ClickUp parity: inline expandable multi-level trees, bulk operations,
recursive duplication, date shifting, descendant effort rollups, automatic parent
completion rules and drag/drop reparenting remain pending.


### Task detail controls increment

Added a searchable priority picker with colored flags, scoped Alt+1 through
Alt+4 shortcuts while the picker is open, and Escape dismissal. Normal maps to
existing Medium values for compatibility. Task details now include the existing
server-backed timer, fixed to the current task, with elapsed time, notes, billable
status, stop/save, discard and another-task warning. Time logs refresh on save.
Custom field definitions can be renamed directly from task details; dropdown
options can be edited subject to existing server checks protecting used values.
Unsaved field values are preserved while editing a definition. Empty fields can
be collapsed. Project field permissions remain enforced by the existing API.
Per-person priority rankings, clearing a priority, AI prioritization/autofill and
field deletion/type conversion are not part of this increment.


### Task fields and view navigation increment

Added searchable field visibility controls grouped into Shown and Available
properties, required Title, Show all, Reset, browser persistence and a link to
the custom-field manager. Existing server saved views still store column choices
with filters. Added shared view navigation on the task list and project Kanban,
including a searchable view catalogue and project-aware links for list/table/
gallery, board, Gantt and dashboard. Workspace pages are labeled explicitly.
Gallery uses the same paginated task query, filters, status grouping and selected
properties as the list; Table starts with grouping off. Project IDs in list URLs
initialize and update the project filter.

This does not add custom-field value columns, arbitrary new view instances,
view pinning, whiteboards, mind maps, map views, external embeds or Google/Figma
synchronization. Those remain pending rather than appearing as working entries.


### Inline subtask creation increment

Task list/table rows and mobile/gallery cards now provide Add subtask. The inline
composer supports title, priority, due date, optional inheritance of parent
assignees, Enter submission and Escape/Cancel. Children start in To Do regardless
of the parent's completion state. Failed requests preserve the draft and duplicate
submission is guarded. Successful creation updates the parent's displayed count
and shows the new child beneath the parent with a task-detail link. These inline
child previews are session-local; full existing-child expansion remains pending.
Desktop/mobile browser coverage includes failure/retry and assignee inheritance.


## 2026-10-24 — Unified collaboration messaging

The `/pms/messages` inbox now includes workspace general chat, public/private
channels, one-to-one conversations, group messages, root messages and threaded
replies, soft-delete tombstones, edit metadata, paginated history, search, read
markers, mute state and in-app notifications. The workspace rail and PMS sidebar
include aggregate unread badges. Existing project files may be selected from an
authorized workspace file picker without copying or broadening project access.

### Data and compatibility

Four additive tables (`pms_chat_conversations`, `pms_chat_members`,
`pms_chat_messages`, `pms_chat_attachments`) share one DTO/access model. This
avoids a destructive rewrite of the established two-person DM schema. Legacy
conversations/messages and workspace chat entries retain their original IDs and
API URLs. A repeat-safe lazy adapter copies their history with source-ID foreign
keys; it generates no backfill notifications. New DM and general-root sends also
write the legacy source record. The old DM send API delegates to the new send
path. New shared-inbox IDs are separate canonical IDs, with legacy IDs returned
for compatibility; this is not an in-place ID replacement.

### Policy

- Public means discoverable only inside the current workspace, never anonymous.
- Workspace Owners/Admins create channels. Their creator and joined workspace
  Owners/Admins manage channels. Groups are managed by their creator; leaving a
  group as owner transfers ownership to an eligible remaining collaborator.
- Current workspace membership is required at every boundary. Guests retain
  read-only workspace chat access and cannot send/create/upload/manage.
- Private channels and DMs require active conversation membership. Newly invited
  private/group participants see messages after an ID join boundary; they cannot
  reply to earlier roots. Later continuations of pre-join threads are also hidden
  from history, search, unread totals and notifications. Public self-join permits
  public history. One-to-one
  participants cannot be expanded; create a fresh group instead.
- Every visible, nondeleted message by another author, including thread replies,
  counts as unread. Mark-read/mark-all-read is explicit and monotonic. Own sends,
  edits and tombstones do not inflate unread counts. Mute suppresses in-app
  notifications, not unread tracking. No email/external delivery was added.
- All query terms must match text or permitted attachment filenames (maximum 12
  words, 200 characters). PostgreSQL uses a simple-dictionary full-text GIN index;
  SQLite uses escaped case-insensitive substring matching. Search returns ID
  cursors and visible root-message context; dates are UTC.
- Authenticated realtime sends content-free invalidation hints only to current
  room/workspace members. Removed participants receive one invalidation to clear
  their view, and no subsequent room hints. Durable APIs always recheck access.
  Ten-second inbox/history polling is the recovery/serverless fallback.

### Files and deployment

Uploads use the established private local/S3/Vercel Blob storage abstraction,
`MAX_UPLOAD_SIZE_MB`, extension/magic checks, safe generated keys, rate limits,
owner-bound staging and atomic association. Downloads are authenticated proxy
responses, not public links. HTML/SVG/executable uploads are rejected. Only
native PNG/JPEG/WebP chat uploads have authenticated object-URL image previews.
Linked project images use download-only metadata because their original MIME
claims are not revalidated by chat. A shared project file
retains its source permission and is never deleted by chat cleanup.

Apply `20261024_005` (SQLite path) or `pg_20261024_005` (PostgreSQL path) before
rolling out the application/worker. Downgrades retain history. Both migration
functions were exercised twice on SQLite; a real PostgreSQL execution was not
available in this session. Existing Celery worker plus beat performs hourly
cleanup: staged uploads expire after 24 hours, deleted-message files after 30
days (configurable via `PMS_CHAT_DELETED_FILE_RETENTION_DAYS`). No deployment,
production migration, worker activation, or external delivery was performed.

### Local verification and reproduction

The full PMS and PostgreSQL-configuration test selection passed (93 tests).
Focused browser checks used real React components and authenticated APIs backed
by a disposable SQLite database, not mocked message responses. They exercised
private channel, DM/group creation, threads, reload persistence, upload/download,
image preview, project-file selection, search/deep links, unread/read state,
live delivery/removal, delayed sends/drafts, keyboard send, deletion, and a 320px
layout. Six concurrent HTTP starts deduplicated to one DM; six identical sends
deduplicated to one message. PostgreSQL locks/FTS and cloud-provider storage were
not integration-tested against live services.

Reproduce locally with `backend/venv/Scripts/python.exe
backend/scripts/run_pms_messaging_qa.py`, start Vite on 5176, then run
`node frontend/scripts/prepare-pms-messaging-qa.cjs`. Open the three emitted
loopback URLs for synthetic owner/member/third-user sessions. These entry pages
and the QA session endpoint must never be deployed. The QA server uses a separate
temporary database, upload directory and signing key. Add `poll-only=1` to disable
realtime in the harness or `delay=1` to delay a send by 1.5 seconds. Remove entry
pages with `node frontend/scripts/prepare-pms-messaging-qa.cjs --clean`.

Optional presence/typing and structured mentions/thread-follow preferences are
not claimed. The Chat capability remains Partial pending production/PostgreSQL
acceptance. Native operating-system file drag/drop was not separately exercised;
file selection and the shared upload path were verified.
